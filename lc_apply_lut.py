"""
LC Apply LUT
------------
Apply a .cube LUT from models/luts (same layout as Pro Post).
Self-contained cube parser — no Pro Post dependency.

Fixes vs earlier LC version:
- log defaults OFF (most photo LUTs are display/sRGB-referred; log path washed the image)
- .cube lattice indexed as [B,G,R] per Adobe/IRIDAS (R varies fastest in the file)
- Domain handled once, cleanly
"""

from __future__ import annotations

import os

import numpy as np
import folder_paths
from nodes import PreviewImage

from .lc_image_helpers import tensor_to_np, np_to_tensor

_dir_luts = os.path.join(folder_paths.models_dir, "luts")
os.makedirs(_dir_luts, exist_ok=True)
if "luts" not in folder_paths.folder_names_and_paths:
    folder_paths.folder_names_and_paths["luts"] = ([_dir_luts], {".cube"})


def _parse_cube(path: str):
    """Parse .cube → size, table shaped (S,S,S,3) indexable as [b,g,r], domain min/max."""
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
            if up.startswith("TITLE") or up.startswith("LUT_1D") or up.startswith("LUT_3D_INPUT"):
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
            parts = line.split()
            if len(parts) >= 3:
                try:
                    data.append([float(parts[0]), float(parts[1]), float(parts[2])])
                except ValueError:
                    continue
    if size is None:
        n = len(data)
        size = int(round(n ** (1.0 / 3.0)))
    table = np.asarray(data, dtype=np.float32)
    expected = size * size * size
    if table.shape[0] < expected:
        raise ValueError(f"LUT {path}: expected {expected} entries, got {table.shape[0]}")
    # File order: R fastest, then G, then B → reshape (B, G, R, 3)
    table = table[:expected].reshape(size, size, size, 3)
    return size, table, domain_min.astype(np.float32), domain_max.astype(np.float32)


def _trilinear_lut(img, table):
    """
    img HxWx3 in 0..1 (already normalized into the LUT's working range).
    table (S,S,S,3) indexed [b, g, r].
    """
    size = table.shape[0]
    # coords in lattice units
    c = np.clip(img, 0.0, 1.0) * (size - 1)
    r = c[..., 0]
    g = c[..., 1]
    b = c[..., 2]

    r0 = np.floor(r).astype(np.int32)
    g0 = np.floor(g).astype(np.int32)
    b0 = np.floor(b).astype(np.int32)
    r1 = np.clip(r0 + 1, 0, size - 1)
    g1 = np.clip(g0 + 1, 0, size - 1)
    b1 = np.clip(b0 + 1, 0, size - 1)
    r0 = np.clip(r0, 0, size - 1)
    g0 = np.clip(g0, 0, size - 1)
    b0 = np.clip(b0, 0, size - 1)

    rd = (r - r0).astype(np.float32)[..., None]
    gd = (g - g0).astype(np.float32)[..., None]
    bd = (b - b0).astype(np.float32)[..., None]

    # table[b, g, r]
    c000 = table[b0, g0, r0]
    c100 = table[b0, g0, r1]
    c010 = table[b0, g1, r0]
    c110 = table[b0, g1, r1]
    c001 = table[b1, g0, r0]
    c101 = table[b1, g0, r1]
    c011 = table[b1, g1, r0]
    c111 = table[b1, g1, r1]

    c00 = c000 * (1.0 - rd) + c100 * rd
    c01 = c001 * (1.0 - rd) + c101 * rd
    c10 = c010 * (1.0 - rd) + c110 * rd
    c11 = c011 * (1.0 - rd) + c111 * rd
    c0 = c00 * (1.0 - gd) + c10 * gd
    c1 = c01 * (1.0 - gd) + c11 * gd
    out = c0 * (1.0 - bd) + c1 * bd
    return out.astype(np.float32)


def _preview(self, result_tensor, source_tensor=None):
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
                "lut_name": (
                    names,
                    {"tooltip": "Place .cube files in ComfyUI/models/luts/"},
                ),
                "strength": (
                    "FLOAT",
                    {
                        "default": 1.0,
                        "min": 0.0,
                        "max": 2.0,
                        "step": 0.01,
                        "tooltip": "0 = original, 1 = full LUT, >1 overdrives the LUT change (up to 2×). Try 0.7–1.2 for most grades.",
                    },
                ),
                "log": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "tooltip": "OFF for normal photo/sRGB LUTs (recommended). ON only if the LUT is authored for log/linear (inverse-gamma in, gamma out).",
                    },
                ),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "run"
    CATEGORY = "LC123/image"
    OUTPUT_NODE = True
    DESCRIPTION = (
        "Apply a .cube 3D LUT from models/luts. "
        "Strength 0–2 (1 = full LUT, >1 overdrives). Leave log OFF for typical creative LUTs."
    )

    def run(self, image, lut_name, strength, log):
        if strength <= 0 or not lut_name or lut_name.startswith("(no"):
            return _preview(self, image, image)

        try:
            lut_path = folder_paths.get_full_path("luts", lut_name)
        except Exception:
            lut_path = os.path.join(_dir_luts, lut_name)
        if not lut_path or not os.path.isfile(lut_path):
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

        dom = dmax - dmin
        dom = np.where(dom < 1e-8, 1.0, dom).astype(np.float32)

        arrays = tensor_to_np(image)
        out = []
        for img in arrays:
            original = img.copy()
            im = np.clip(img.astype(np.float32), 0.0, 1.0)

            # Optional log path: linearize → sample → re-encode (only for log-authored LUTs)
            if log:
                im = np.power(np.clip(im, 0.0, None), 1.0 / 2.2)

            # Map 0..1 into domain, then back to 0..1 lattice coords for sampling
            # (identity when domain is 0..1)
            im_dom = im * dom + dmin
            im_01 = (im_dom - dmin) / dom
            im_01 = np.clip(im_01, 0.0, 1.0)

            mapped = _trilinear_lut(im_01, table)

            # If domain was non-default, table values are often still 0..1 RGB;
            # clip only — do not re-expand unless the LUT itself stores domain-scaled RGB.
            mapped = np.clip(mapped, 0.0, 1.0)

            if log:
                mapped = np.power(np.clip(mapped, 0.0, None), 2.2)
                mapped = np.clip(mapped, 0.0, 1.0)

            # strength 1 = full LUT; >1 extrapolates the delta (overdrive)
            s = float(strength)
            mapped = original + s * (mapped - original)
            mapped = np.clip(mapped, 0.0, 1.0).astype(np.float32)
            out.append(mapped)

        return _preview(self, np_to_tensor(out), image)


NODE_CLASS_MAPPINGS = {
    "LCApplyLUT": LCApplyLUT,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LCApplyLUT": "LC Apply LUT",
}
