"""
LC Apply LUT
------------
Apply a .cube LUT from models/luts (same layout as Pro Post).
Self-contained cube parser — no Pro Post dependency.
"""

import os
import numpy as np
import torch
import folder_paths
from nodes import PreviewImage

from .lc_image_helpers import tensor_to_np, np_to_tensor, blend

# Register models/luts like Pro Post
_dir_luts = os.path.join(folder_paths.models_dir, "luts")
os.makedirs(_dir_luts, exist_ok=True)
if "luts" not in folder_paths.folder_names_and_paths:
    folder_paths.folder_names_and_paths["luts"] = ([_dir_luts], {".cube"})


def _parse_cube(path: str):
    """Minimal .cube LUT parser → size, table (N,N,N,3), domain."""
    size = None
    domain_min = np.array([0.0, 0.0, 0.0], dtype=np.float64)
    domain_max = np.array([1.0, 1.0, 1.0], dtype=np.float64)
    data = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            up = line.upper()
            if up.startswith("TITLE"):
                continue
            if up.startswith("LUT_3D_SIZE"):
                size = int(line.split()[-1])
                continue
            if up.startswith("DOMAIN_MIN"):
                parts = line.split()
                domain_min = np.array([float(parts[1]), float(parts[2]), float(parts[3])], dtype=np.float64)
                continue
            if up.startswith("DOMAIN_MAX"):
                parts = line.split()
                domain_max = np.array([float(parts[1]), float(parts[2]), float(parts[3])], dtype=np.float64)
                continue
            if up.startswith("LUT_1D") or up.startswith("LUT_3D_INPUT"):
                continue
            parts = line.split()
            if len(parts) >= 3:
                try:
                    data.append([float(parts[0]), float(parts[1]), float(parts[2])])
                except ValueError:
                    continue
    if size is None:
        n = len(data)
        size = int(round(n ** (1 / 3)))
    table = np.array(data, dtype=np.float32)
    expected = size * size * size
    if table.shape[0] < expected:
        raise ValueError(f"LUT {path}: expected {expected} entries, got {table.shape[0]}")
    table = table[:expected].reshape(size, size, size, 3)
    return size, table, domain_min.astype(np.float32), domain_max.astype(np.float32)


def _trilinear_lut(img, table, domain_min, domain_max):
    """img HxWx3 float 0-1 in domain space → apply 3D LUT."""
    size = table.shape[0]
    dom = domain_max - domain_min
    dom = np.where(dom < 1e-8, 1.0, dom)
    # map to 0..size-1 indices
    coords = (img - domain_min) / dom
    coords = np.clip(coords, 0.0, 1.0) * (size - 1)

    x = coords[..., 0]
    y = coords[..., 1]
    z = coords[..., 2]

    x0 = np.floor(x).astype(np.int32)
    y0 = np.floor(y).astype(np.int32)
    z0 = np.floor(z).astype(np.int32)
    x1 = np.clip(x0 + 1, 0, size - 1)
    y1 = np.clip(y0 + 1, 0, size - 1)
    z1 = np.clip(z0 + 1, 0, size - 1)
    x0 = np.clip(x0, 0, size - 1)
    y0 = np.clip(y0, 0, size - 1)
    z0 = np.clip(z0, 0, size - 1)

    xd = (x - x0).astype(np.float32)[..., None]
    yd = (y - y0).astype(np.float32)[..., None]
    zd = (z - z0).astype(np.float32)[..., None]

    c000 = table[x0, y0, z0]
    c100 = table[x1, y0, z0]
    c010 = table[x0, y1, z0]
    c110 = table[x1, y1, z0]
    c001 = table[x0, y0, z1]
    c101 = table[x1, y0, z1]
    c011 = table[x0, y1, z1]
    c111 = table[x1, y1, z1]

    c00 = c000 * (1 - xd) + c100 * xd
    c01 = c001 * (1 - xd) + c101 * xd
    c10 = c010 * (1 - xd) + c110 * xd
    c11 = c011 * (1 - xd) + c111 * xd
    c0 = c00 * (1 - yd) + c10 * yd
    c1 = c01 * (1 - yd) + c11 * yd
    out = c0 * (1 - zd) + c1 * zd
    return out.astype(np.float32)


def _preview(self, result_tensor, source_tensor=None):
    """Attach after (and optional before) preview images for on-node compare wipe."""
    out = {"ui": {}, "result": (result_tensor,)}
    try:
        after = self.save_images(result_tensor, filename_prefix="lc_after")
        out["ui"]["lc_preview"] = after["ui"]["images"]
        if source_tensor is not None:
            before = self.save_images(source_tensor, filename_prefix="lc_before")
            out["ui"]["lc_before"] = before["ui"]["images"]
    except Exception:
        pass
    return out


class LCApplyLUT(PreviewImage):
    @classmethod
    def INPUT_TYPES(cls):
        try:
            names = folder_paths.get_filename_list("luts")
        except Exception:
            names = []
        if not names:
            names = ["(no .cube files in models/luts)"]
        return {
            "required": {
                "image": ("IMAGE",),
                "lut_name": (names, {
                    "tooltip": "Place .cube files in ComfyUI/models/luts/",
                }),
                "strength": ("FLOAT", {
                    "default": 0.3, "min": 0.0, "max": 1.0, "step": 0.01,
                    "tooltip": "Blend between original (0) and LUT (1)",
                }),
                "log": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "Apply inverse gamma before LUT and restore after (log workflow)",
                }),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "run"
    CATEGORY = "LC123/image"
    OUTPUT_NODE = True
    DESCRIPTION = (
        "Apply a .cube 3D LUT from models/luts. "
        "Strength blends with the original. Optional log (gamma) path."
    )

    def run(self, image, lut_name, strength, log):
        if strength <= 0 or not lut_name or lut_name.startswith("(no"):
            return _preview(self, image, image)

        # resolve path
        try:
            lut_path = folder_paths.get_full_path("luts", lut_name)
        except Exception:
            lut_path = os.path.join(_dir_luts, lut_name)
        if not lut_path or not os.path.isfile(lut_path):
            # try direct under models/luts
            alt = os.path.join(_dir_luts, lut_name)
            if os.path.isfile(alt):
                lut_path = alt
            else:
                print(f"[LC Apply LUT] file not found: {lut_name}")
                return _preview(self, image, image)

        try:
            size, table, dmin, dmax = _parse_cube(lut_path)
        except Exception as e:
            print(f"[LC Apply LUT] parse error: {e}")
            return _preview(self, image, image)

        arrays = tensor_to_np(image)
        out = []
        for img in arrays:
            original = img.copy()
            im = img.astype(np.float32)
            non_default = not (np.allclose(dmin, 0.0) and np.allclose(dmax, 1.0))
            if non_default:
                im = im * (dmax - dmin) + dmin
            if log:
                im = np.power(np.clip(im, 0, None), 1.0 / 2.2)
            mapped = _trilinear_lut(im, table, dmin if non_default else np.zeros(3, np.float32),
                                    dmax if non_default else np.ones(3, np.float32))
            if log:
                mapped = np.power(np.clip(mapped, 0, None), 2.2)
            if non_default:
                mapped = (mapped - dmin) / np.maximum(dmax - dmin, 1e-8)
            mapped = np.clip(mapped, 0, 1).astype(np.float32)
            out.append(blend(original, mapped, strength))

        result = np_to_tensor(out)
        return _preview(self, result, image)


NODE_CLASS_MAPPINGS = {
    "LCApplyLUT": LCApplyLUT,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LCApplyLUT": "LC Apply LUT",
}
