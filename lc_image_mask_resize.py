"""
LC ImageMask Resize 📐
----------------------
Slim Aspect Ratio Simplifier: image + mask resize only.
Same widget names and order as 📐 Aspect Ratio Simplifier, minus
max_resolution, resolution_source, swap, pad, batch, and latent.
"""

from __future__ import annotations

import math

import torch

from .aspect_ratio import (
    ASPECT_PRESETS,
    MAX_RESOLUTION,
    UPSCALE_METHODS,
    _blank_image,
    _image_size,
    _make_divisible,
    _mask_size,
    _resize_image,
    _resize_mask,
)

# ARS proportion minus pad (pad needs pad_color, which this node does not have)
PROPORTIONS = [
    "crop",
    "stretch",
    "resize",
    "total_pixels",
]

CROP_LOCATIONS = ["center", "top", "bottom", "left", "right"]

UPSCALE_BY = ["none", "multiplier", "megapixels"]


def _match_input_aspect(tw: int, th: int, src_w: int, src_h: int) -> tuple[int, int]:
    """Keep input ratio. Longer output side = max(settings W, settings H)."""
    if src_w < 1 or src_h < 1:
        return tw, th
    max_side = max(int(tw), int(th), 1)
    if src_w >= src_h:
        out_w = max_side
        out_h = max(1, int(round(max_side * src_h / float(src_w))))
    else:
        out_h = max_side
        out_w = max(1, int(round(max_side * src_w / float(src_h))))
    return out_w, out_h


def _apply_upscale_by(tw: int, th: int, mode: str, value: float) -> tuple[int, int]:
    mode = (mode or "none").strip().lower()
    if mode == "none":
        return tw, th
    tw = max(1, int(tw))
    th = max(1, int(th))
    if mode == "multiplier":
        m = min(4.0, max(0.25, float(value)))
        return max(1, int(round(tw * m))), max(1, int(round(th * m)))
    if mode == "megapixels":
        mp = min(8.0, max(0.01, float(value)))
        aspect = tw / float(th) if th else 1.0
        area = mp * 1_000_000.0
        nw = max(1, int(round(math.sqrt(area * aspect))))
        nh = max(1, int(round(area / float(nw))))
        return nw, nh
    return tw, th


class LCImageMaskResize:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "match_aspect_ratio": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "label_on": "match input",
                        "label_off": "use settings",
                        "tooltip": "On: keep the incoming image/mask ratio. The larger of the current width/height settings is the long side. Off: use preset or custom W×H as-is.",
                    },
                ),
                "aspect_ratio": (
                    list(ASPECT_PRESETS.keys()),
                    {
                        "tooltip": "Preset size, or custom to use custom_width × custom_height.",
                    },
                ),
                "custom_width": (
                    "INT",
                    {
                        "default": 1024,
                        "min": 16,
                        "max": MAX_RESOLUTION,
                        "step": 8,
                        "tooltip": "Target width for custom size. Also the size source (with height) when match_aspect_ratio is on.",
                    },
                ),
                "custom_height": (
                    "INT",
                    {
                        "default": 1024,
                        "min": 16,
                        "max": MAX_RESOLUTION,
                        "step": 8,
                        "tooltip": "Target height for custom size. Also the size source (with width) when match_aspect_ratio is on.",
                    },
                ),
                "upscale_by": (
                    UPSCALE_BY,
                    {
                        "default": "none",
                        "tooltip": "none = use the size above. multiplier = scale that size. megapixels = set total pixels at the current ratio.",
                    },
                ),
                "multiplier": (
                    "FLOAT",
                    {
                        "default": 1.00,
                        "min": 0.25,
                        "max": 4.00,
                        "step": 0.25,
                        "round": 0.25,
                        "precision": 2,
                        "tooltip": "Scale factor when upscale_by is multiplier. Steps of 0.25, max 4.00.",
                    },
                ),
                "megapixels": (
                    "FLOAT",
                    {
                        "default": 1.00,
                        "min": 0.01,
                        "max": 8.00,
                        "step": 0.01,
                        "round": 0.01,
                        "precision": 2,
                        "tooltip": "Target megapixels when upscale_by is megapixels. Steps of 0.01, max 8.00.",
                    },
                ),
                "upscale_method": (
                    UPSCALE_METHODS,
                    {
                        "default": "lanczos",
                        "tooltip": "Resampling filter. Lanczos is a good default for photos. Masks use nearest.",
                    },
                ),
                "proportion": (
                    PROPORTIONS,
                    {
                        "default": "crop",
                        "tooltip": "stretch=force size; resize=fit inside; crop=fill+crop; total_pixels=match pixel budget (custom W×H).",
                    },
                ),
                "crop_location": (
                    CROP_LOCATIONS,
                    {
                        "default": "center",
                        "tooltip": "Crop anchor when proportion is crop.",
                    },
                ),
                "divisible_by": (
                    "INT",
                    {
                        "default": 8,
                        "min": 1,
                        "max": 128,
                        "step": 1,
                        "tooltip": "Final width/height are floored to a multiple of this, then the image/mask is resampled to that size. 16 for Z-Image / Flux; 8 for SDXL. 1 = off.",
                    },
                ),
            },
            "optional": {
                "image": ("IMAGE",),
                "mask": ("MASK",),
            },
        }

    RETURN_TYPES = ("IMAGE", "MASK", "INT", "INT")
    RETURN_NAMES = ("image", "mask", "width", "height")
    FUNCTION = "resize"
    CATEGORY = "LC123"
    DESCRIPTION = (
        "Resize an image and/or mask to a preset or custom W×H. "
        "match_aspect_ratio uses the larger settings side and keeps the input ratio. "
        "upscale_by can then multiply that size or set megapixels. "
        "Final size is a multiple of divisible_by."
    )

    @classmethod
    def VALIDATE_INPUTS(cls, aspect_ratio=None, upscale_by=None, **kwargs):
        return True

    def resize(
        self,
        match_aspect_ratio,
        aspect_ratio,
        custom_width,
        custom_height,
        upscale_by,
        multiplier,
        megapixels,
        upscale_method,
        proportion,
        crop_location,
        divisible_by,
        image=None,
        mask=None,
        **_kwargs,
    ):
        has_image = image is not None
        has_mask = mask is not None

        if has_image:
            src_w, src_h = _image_size(image)
            src_batch = int(image.shape[0])
            src_ref = image
        elif has_mask:
            src_w, src_h = _mask_size(mask)
            src_batch = 1 if mask.dim() == 2 else int(mask.shape[0])
            src_ref = None
        else:
            src_w = src_h = 0
            src_batch = 1
            src_ref = None

        preset = ASPECT_PRESETS.get(aspect_ratio, None)
        if preset is None:
            tw, th = int(custom_width), int(custom_height)
        else:
            tw, th = int(preset[0]), int(preset[1])

        if match_aspect_ratio and src_w > 0 and src_h > 0:
            tw, th = _match_input_aspect(tw, th, src_w, src_h)

        tw, th = _apply_upscale_by(
            tw,
            th,
            upscale_by,
            multiplier if (upscale_by or "").strip().lower() == "multiplier" else megapixels,
        )

        div = int(divisible_by) if divisible_by else 1
        if div > 1:
            tw = _make_divisible(tw, div)
            th = _make_divisible(th, div)
        tw = max(1, min(int(tw), MAX_RESOLUTION))
        th = max(1, min(int(th), MAX_RESOLUTION))

        if has_image:
            out_image, out_w, out_h = _resize_image(
                image,
                tw,
                th,
                upscale_method,
                proportion,
                crop_location,
                pad_color="0, 0, 0",
                divisible_by=div,
            )
        elif has_mask:
            proxy = mask.unsqueeze(-1) if mask.dim() == 3 else mask.unsqueeze(0).unsqueeze(-1)
            if proxy.shape[-1] == 1:
                proxy = proxy.repeat(1, 1, 1, 3)
            _, out_w, out_h = _resize_image(
                proxy,
                tw,
                th,
                "nearest-exact",
                proportion,
                crop_location,
                pad_color="0, 0, 0",
                divisible_by=div,
            )
            out_image = _blank_image(src_batch, out_h, out_w, ref=src_ref)
        else:
            out_w, out_h = tw, th
            out_image = _blank_image(src_batch, out_h, out_w, ref=None)

        if has_mask:
            out_mask = _resize_mask(
                mask,
                src_w=src_w or out_w,
                src_h=src_h or out_h,
                target_w=out_w,
                target_h=out_h,
                upscale_method=upscale_method,
                proportion=proportion,
                crop_position=crop_location,
                divisible_by=div,
            )
        else:
            out_mask = torch.zeros(
                (src_batch, out_h, out_w),
                dtype=out_image.dtype,
                device=out_image.device,
            )

        return (out_image, out_mask, int(out_w), int(out_h))


NODE_CLASS_MAPPINGS = {
    "LCImageMaskResize": LCImageMaskResize,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LCImageMaskResize": "LC Image-Mask Resize 📐",
}
