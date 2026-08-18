"""
LC Image Grid 🖼️
----------------
Build a grid from a batch of images (CR Image Grid Panel–style, self-contained).

- Pads cells to a common size (max width × max height in the batch)
- Optional cell gap, cell outline, outer border
- max_columns controls layout (rows = ceil(n / cols))
"""

from __future__ import annotations

import math
from typing import List, Optional, Tuple

import numpy as np
import torch
from PIL import Image, ImageOps

from .lc_image_helpers import tensor_to_np, np_to_tensor


def _hex_to_rgb(hex_str: str, fallback=(0, 0, 0)) -> Tuple[int, int, int]:
    s = (hex_str or "").strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) != 6:
        return fallback
    try:
        return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)
    except ValueError:
        return fallback


def _tensor_batch_to_pils(image: torch.Tensor) -> List[Image.Image]:
    """IMAGE tensor [B,H,W,C] float 0–1 → list of RGB PIL."""
    arrays = tensor_to_np(image)
    out = []
    for arr in arrays:
        a = np.clip(arr, 0, 1)
        if a.ndim == 2:
            a = np.stack([a, a, a], axis=-1)
        if a.shape[-1] > 3:
            a = a[..., :3]
        out.append(Image.fromarray((a * 255.0).astype(np.uint8), mode="RGB"))
    return out


def _pad_to_size(im: Image.Image, tw: int, th: int, fill: Tuple[int, int, int]) -> Image.Image:
    """Center-pad (or crop if larger) to exact tw×th."""
    w, h = im.size
    if w == tw and h == th:
        return im
    canvas = Image.new("RGB", (tw, th), fill)
    # scale down if larger than cell, keep aspect
    scale = min(tw / max(w, 1), th / max(h, 1), 1.0)
    if scale < 1.0:
        nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
        im = im.resize((nw, nh), Image.Resampling.LANCZOS)
        w, h = im.size
    x = (tw - w) // 2
    y = (th - h) // 2
    canvas.paste(im, (x, y))
    return canvas


def _apply_outline(im: Image.Image, thickness: int, color: Tuple[int, int, int]) -> Image.Image:
    if thickness <= 0:
        return im
    return ImageOps.expand(im, border=int(thickness), fill=color)


class LCImageGrid:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "max_columns": (
                    "INT",
                    {
                        "default": 3,
                        "min": 1,
                        "max": 64,
                        "step": 1,
                        "tooltip": "Max images per row. Rows are filled left→right, top→bottom.",
                    },
                ),
                "gap": (
                    "INT",
                    {
                        "default": 8,
                        "min": 0,
                        "max": 256,
                        "step": 1,
                        "tooltip": "Space between cells (pixels).",
                    },
                ),
                "cell_pad": (
                    "INT",
                    {
                        "default": 4,
                        "min": 0,
                        "max": 256,
                        "step": 1,
                        "tooltip": "Padding inside each cell around the image (before outline).",
                    },
                ),
                "outline_thickness": (
                    "INT",
                    {
                        "default": 2,
                        "min": 0,
                        "max": 64,
                        "step": 1,
                        "tooltip": "Outline drawn around each cell image.",
                    },
                ),
                "border_thickness": (
                    "INT",
                    {
                        "default": 2,
                        "min": 0,
                        "max": 256,
                        "step": 1,
                        "tooltip": "Outer border around the whole grid.",
                    },
                ),
                "bg_color": (
                    "STRING",
                    {
                        "default": "#000000",
                        "tooltip": "Background / gap fill color (#RRGGBB).",
                    },
                ),
                "outline_color": (
                    "STRING",
                    {
                        "default": "#FFFFFF",
                        "tooltip": "Cell outline color (#RRGGBB).",
                    },
                ),
                "border_color": (
                    "STRING",
                    {
                        "default": "#000000",
                        "tooltip": "Outer border color (#RRGGBB).",
                    },
                ),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "make_grid"
    CATEGORY = "LC123/image"
    DESCRIPTION = (
        "Arrange a batch of images into a grid (CR Image Grid–style). "
        "Cells are padded to a shared size; optional gap, outline, and outer border."
    )

    def make_grid(
        self,
        images,
        max_columns=3,
        gap=8,
        cell_pad=4,
        outline_thickness=2,
        border_thickness=2,
        bg_color="#000000",
        outline_color="#FFFFFF",
        border_color="#000000",
    ):
        pils = _tensor_batch_to_pils(images)
        if not pils:
            # empty → 64×64 black
            empty = Image.new("RGB", (64, 64), (0, 0, 0))
            return (np_to_tensor([np.array(empty).astype(np.float32) / 255.0]),)

        bg = _hex_to_rgb(bg_color, (0, 0, 0))
        oc = _hex_to_rgb(outline_color, (255, 255, 255))
        bc = _hex_to_rgb(border_color, (0, 0, 0))

        cols = max(1, int(max_columns))
        n = len(pils)
        rows = max(1, int(math.ceil(n / cols)))

        cell_w = max(im.width for im in pils)
        cell_h = max(im.height for im in pils)
        pad = max(0, int(cell_pad))
        if pad:
            cell_w += 2 * pad
            cell_h += 2 * pad

        cells: List[Image.Image] = []
        for im in pils:
            if pad:
                canvas = Image.new("RGB", (im.width + 2 * pad, im.height + 2 * pad), bg)
                canvas.paste(im, (pad, pad))
                im = canvas
            im = _pad_to_size(im, cell_w, cell_h, bg)
            im = _apply_outline(im, int(outline_thickness), oc)
            cells.append(im)

        # After outline, cell size may have grown — re-read
        cw = cells[0].width
        ch = cells[0].height
        g = max(0, int(gap))

        grid_w = cols * cw + (cols - 1) * g
        grid_h = rows * ch + (rows - 1) * g
        grid = Image.new("RGB", (max(1, grid_w), max(1, grid_h)), bg)

        for i, cell in enumerate(cells):
            r, c = divmod(i, cols)
            x = c * (cw + g)
            y = r * (ch + g)
            grid.paste(cell, (x, y))

        bt = max(0, int(border_thickness))
        if bt > 0:
            grid = ImageOps.expand(grid, border=bt, fill=bc)

        arr = np.array(grid).astype(np.float32) / 255.0
        return (np_to_tensor([arr]),)


NODE_CLASS_MAPPINGS = {
    "LCImageGrid": LCImageGrid,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LCImageGrid": "LC Image Grid 🖼️",
}
