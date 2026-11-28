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

from .lc_image_helpers import tensor_to_np, np_to_tensor, preview_frames, _alpha_safe

_dir_luts = os.path.join(folder_paths.models_dir, "luts")
os.makedirs(_dir_luts, exist_ok=True)
if "luts" not in folder_paths.folder_names_and_paths:
    folder_paths.folder_names_and_paths["luts"] = ([_dir_luts], {".cube"})


class _LUT1DError(ValueError):
    """A 1D .cube: reported to the user instead of being misread as a 3D lattice."""


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
            if up.startswith("LUT_1D_SIZE"):
                raise _LUT1DError(
                    f"{os.path.basename(path)} is a 1D LUT (LUT_1D_SIZE). LC Apply LUT only reads 3D .cube LUTs "
                    "(LUT_3D_SIZE)."
                )
            if up.startswith("LUT_3D_INPUT_RANGE"):
                # Resolve's form of DOMAIN_MIN / DOMAIN_MAX: one low / high value for all three channels
                parts = line.split()
                domain_min = np.full(3, float(parts[1]), dtype=np.float64)
                domain_max = np.full(3, float(parts[2]), dtype=np.float64)
                continue
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
    if size < 2:
        raise ValueError(f"LUT {path}: LUT_3D_SIZE {size} is too small (needs at least 2)")
    table =np.asarray(data, dtype=np.float32)
    expected = size * size * size
    if table.shape[0] < expected:
        raise ValueError(f"LUT {path}: expected {expected} entries, got {table.shape[0]}")
    # File order: R fastest, then G, then B → reshape (B, G, R, 3)
    table = table[:expected].reshape(size, size, size, 3)
    return size, table, domain_min.astype(np.float32), domain_max.astype(np.float32)


# Parsed LUTs keyed on (path, mtime, size): a queued run does not re-read the same .cube, an edited file is re-read.
_CUBE_CACHE = {}
_CUBE_CACHE_MAX = 8


def _load_cube(path: str):
    st = os.stat(path)
    key = (os.path.abspath(path), st.st_mtime_ns, st.st_size)
    hit = _CUBE_CACHE.get(key)
    if hit is not None:
        return hit
    parsed = _parse_cube(path)
    for old in [k for k in _CUBE_CACHE if k[0] == key[0]]:
        del _CUBE_CACHE[old]
    while len(_CUBE_CACHE) >= _CUBE_CACHE_MAX:
        del _CUBE_CACHE[next(iter(_CUBE_CACHE))]
    _CUBE_CACHE[key] = parsed
    return parsed


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


def _tetrahedral_lut(img, table, chunk=1 << 22):
    """
    img HxWx3 in 0..1, table (S,S,S,3) indexed [b, g, r]. Tetrahedral interpolation on the GPU when there is one.
    Inside its lattice cube, a colour walks from the low corner to the high corner one axis at a time, largest
    fraction first; the four corners on that path are the tetrahedron it sits in, weighted by the differences of the
    sorted fractions. A grey (equal fractions) only ever mixes grey-axis entries, so neutrals stay cleaner than with
    trilinear, which mixes all eight corners.
    """
    import torch
    try:
        import comfy.model_management as mm
        dev = mm.get_torch_device()
    except Exception:
        dev = torch.device("cpu")
    size = table.shape[0]
    lut = torch.from_numpy(np.ascontiguousarray(table, dtype=np.float32)).to(dev).reshape(-1, 3)  # [b, g, r] order
    stride = torch.tensor([1, size, size * size], device=dev)  # r, g, b steps in the flat [b, g, r] table
    pix = torch.from_numpy(np.ascontiguousarray(img, dtype=np.float32)).to(dev).reshape(-1, 3)
    out = torch.empty_like(pix)
    for start in range(0, pix.shape[0], chunk):
        pos = pix[start:start + chunk].clamp(0.0, 1.0) * (size - 1)
        cell = pos.floor().clamp(0, size - 2)
        frac = (pos - cell).clamp(0.0, 1.0)
        order = torch.argsort(frac, dim=1, descending=True, stable=True)
        f = torch.gather(frac, 1, order)  # f0 >= f1 >= f2
        idx = (cell.long() * stride).sum(1)
        steps = stride[order]  # the axis to step along, largest fraction first
        c0 = idx
        c1 = c0 + steps[:, 0]
        c2 = c1 + steps[:, 1]
        c3 = c2 + steps[:, 2]
        out[start:start + chunk] = (lut[c0] * (1.0 - f[:, 0:1]) + lut[c1] * (f[:, 0:1] - f[:, 1:2])
                                    + lut[c2] * (f[:, 1:2] - f[:, 2:3]) + lut[c3] * f[:, 2:3])
    return out.reshape(img.shape).cpu().numpy().astype(np.float32)


def _preview(self, result_tensor, source_tensor=None):
    out = {"ui": {}, "result": (result_tensor,)}
    try:
        after = self.save_images(preview_frames(result_tensor), filename_prefix="lc_after")
        out["ui"]["lc_preview"] = after["ui"]["images"]
        if source_tensor is not None:
            before = self.save_images(preview_frames(source_tensor), filename_prefix="lc_before")
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
                    {
                        # shipped sample, a gentle start; falls back to the first file if it was removed
                        "default": "LC_Crushed_Blacks.cube" if "LC_Crushed_Blacks.cube" in names else names[0],
                        "tooltip": "Folder: ComfyUI/models/luts/  — put .cube files there",
                    },
                ),
                "strength": (
                    "FLOAT",
                    {
                        "default": 0.3,
                        "min": 0.0,
                        "max": 2.0,
                        "step": 0.01,
                        "tooltip": "0 = original, 1 = full LUT, >1 overdrives the LUT change (up to 2×). 0.2–0.4 is usually plenty. Full strength is a sledgehammer.",
                    },
                ),
                "log": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "tooltip": "OFF for normal photo/sRGB LUTs (recommended). ON only if the LUT is authored for log/linear (inverse-gamma in, gamma out).",
                    },
                ),
                "interpolation": (
                    ["tetrahedral", "trilinear"],
                    {
                        "default": "tetrahedral",
                        "tooltip": "tetrahedral = cleaner greys and smoother gradients, runs on the GPU (what grading apps use). trilinear = the old method.",
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

    @_alpha_safe
    def run(self, image, lut_name, strength, log, interpolation="tetrahedral"):
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
            size, table, dmin, dmax = _load_cube(lut_path)
        except _LUT1DError:
            raise
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

            # Pixel value -> 0..1 lattice coords inside the LUT's domain (identity when domain is 0..1)
            im_01 = (im - dmin) / dom
            im_01 = np.clip(im_01, 0.0, 1.0)

            mapped = _tetrahedral_lut(im_01, table) if interpolation == "tetrahedral" else _trilinear_lut(im_01, table)

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
