"""
Aspect Ratio Simplifier — single node consolidating:
  image resolution detect + optional CR-style presets + resize + empty latent.
"""

from __future__ import annotations

import math
from typing import Optional, Tuple

import torch
import comfy.utils

MAX_RESOLUTION = 16384

# CR Aspect Ratio Social Media presets (Suzie1 / Comfyroll)
ASPECT_PRESETS = {
    "custom": None,
    "Instagram Portrait - 1080x1350": (1080, 1350),
    "Instagram Square - 1080x1080": (1080, 1080),
    "Instagram Landscape - 1080x608": (1080, 608),
    "Instagram Stories/Reels - 1080x1920": (1080, 1920),
    "Facebook Landscape - 1080x1350": (1080, 1350),
    "Facebook Marketplace - 1200x1200": (1200, 1200),
    "Facebook Stories - 1080x1920": (1080, 1920),
    "TikTok - 1080x1920": (1080, 1920),
    "YouTube Banner - 2560x1440": (2560, 1440),
    "LinkedIn Profile Banner - 1584x396": (1584, 396),
    "LinkedIn Page Cover - 1128x191": (1128, 191),
    "LinkedIn Post - 1200x627": (1200, 627),
    "Pinterest Pin Image - 1000x1500": (1000, 1500),
    "CivitAI Cover - 1600x400": (1600, 400),
    "OpenArt App - 1500x1000": (1500, 1000),
    "SDXL Square - 1024x1024": (1024, 1024),
    "SDXL Portrait - 832x1216": (832, 1216),
    "SDXL Landscape - 1216x832": (1216, 832),
    "1:1 - 1024x1024": (1024, 1024),
    "3:4 - 896x1152": (896, 1152),
    "4:3 - 1152x896": (1152, 896),
    "9:16 - 768x1344": (768, 1344),
    "16:9 - 1344x768": (1344, 768),
}

UPSCALE_METHODS = [
    "nearest-exact",
    "bicubic",
    "bilinear",
    "lanczos",
    "area",
    "nvidia_rtx_vsr",
]

PROPORTIONS = [
    "crop",
    "stretch",
    "resize",
    "pad",
    "total_pixels",
]

CROP_LOCATIONS = ["center", "top", "bottom", "left", "right"]


def _image_size(image: torch.Tensor) -> Tuple[int, int]:
    # IMAGE: [B, H, W, C]
    return int(image.shape[2]), int(image.shape[1])


def _clamp_to_max(w: int, h: int, max_res: int) -> Tuple[int, int]:
    if max_res <= 0:
        return w, h
    longer = max(w, h)
    if longer <= max_res:
        return w, h
    scale = max_res / float(longer)
    return max(1, int(round(w * scale))), max(1, int(round(h * scale)))


def _make_divisible(v: int, d: int) -> int:
    if d is None or d <= 1:
        return max(1, v)
    return max(d, (v // d) * d)


def _parse_pad_color(pad_color: str):
    try:
        parts = [float(x.strip()) for x in pad_color.split(",")]
        if len(parts) == 1:
            parts = parts * 3
        while len(parts) < 3:
            parts.append(0.0)
        if any(p > 1.0 for p in parts[:3]):
            parts = [p / 255.0 for p in parts]
        return parts[0], parts[1], parts[2]
    except Exception:
        return 0.0, 0.0, 0.0


def _common_upscale(samples, width, height, method, crop="disabled"):
    """Wrap comfy.utils.common_upscale; samples are BCHW."""
    if method == "nvidia_rtx_vsr":
        try:
            return comfy.utils.common_upscale(samples, width, height, method, crop)
        except Exception:
            method = "lanczos"
    return comfy.utils.common_upscale(samples, width, height, method, crop)


def _resize_image(
    image: torch.Tensor,
    width: int,
    height: int,
    upscale_method: str,
    proportion: str,
    crop_position: str,
    pad_color: str = "0, 0, 0",
    divisible_by: int = 2,
) -> Tuple[torch.Tensor, int, int]:
    """
    Resize BHWC image. Returns (image, out_w, out_h).
    Modes mirror KJ ImageResizeKJv2 subset:
      stretch, resize, pad, crop, total_pixels
    """
    B, H, W, C = image.shape
    width = int(width)
    height = int(height)

    if proportion == "total_pixels":
        total_pixels = max(1, width * height)
        aspect = W / max(H, 1)
        new_h = int(math.sqrt(total_pixels / aspect))
        new_w = int(math.sqrt(total_pixels * aspect))
        width, height = new_w, new_h

    if divisible_by and divisible_by > 1:
        width = _make_divisible(width, divisible_by)
        height = _make_divisible(height, divisible_by)

    width = max(1, min(width, MAX_RESOLUTION))
    height = max(1, min(height, MAX_RESOLUTION))

    samples = image.movedim(-1, 1)  # BCHW

    if proportion == "stretch":
        out = _common_upscale(samples, width, height, upscale_method, "disabled")
        out = out.movedim(1, -1)
        return out, width, height

    if proportion == "resize" or proportion == "total_pixels":
        ratio = min(width / W, height / H)
        new_w = max(1, int(round(W * ratio)))
        new_h = max(1, int(round(H * ratio)))
        if divisible_by and divisible_by > 1:
            new_w = _make_divisible(new_w, divisible_by)
            new_h = _make_divisible(new_h, divisible_by)
        out = _common_upscale(samples, new_w, new_h, upscale_method, "disabled")
        out = out.movedim(1, -1)
        return out, new_w, new_h

    if proportion == "pad":
        ratio = min(width / W, height / H)
        new_w = max(1, int(round(W * ratio)))
        new_h = max(1, int(round(H * ratio)))
        scaled = _common_upscale(samples, new_w, new_h, upscale_method, "disabled")
        scaled = scaled.movedim(1, -1)  # BHWC
        pr, pg, pb = _parse_pad_color(pad_color)
        canvas = torch.zeros((B, height, width, C), dtype=image.dtype, device=image.device)
        if C >= 3:
            canvas[..., 0] = pr
            canvas[..., 1] = pg
            canvas[..., 2] = pb
        elif C == 1:
            canvas[..., 0] = pr
        if crop_position == "center":
            x0 = (width - new_w) // 2
            y0 = (height - new_h) // 2
        elif crop_position == "top":
            x0 = (width - new_w) // 2
            y0 = 0
        elif crop_position == "bottom":
            x0 = (width - new_w) // 2
            y0 = height - new_h
        elif crop_position == "left":
            x0 = 0
            y0 = (height - new_h) // 2
        elif crop_position == "right":
            x0 = width - new_w
            y0 = (height - new_h) // 2
        else:
            x0 = (width - new_w) // 2
            y0 = (height - new_h) // 2
        x0 = max(0, x0)
        y0 = max(0, y0)
        mw = min(new_w, width - x0)
        mh = min(new_h, height - y0)
        canvas[:, y0 : y0 + mh, x0 : x0 + mw, :] = scaled[:, :mh, :mw, :]
        return canvas, width, height

    # crop: scale to cover target, then crop
    ratio = max(width / W, height / H)
    new_w = max(1, int(math.ceil(W * ratio)))
    new_h = max(1, int(math.ceil(H * ratio)))
    scaled = _common_upscale(samples, new_w, new_h, upscale_method, "disabled")
    scaled = scaled.movedim(1, -1)  # BHWC
    if crop_position == "center":
        x0 = max(0, (new_w - width) // 2)
        y0 = max(0, (new_h - height) // 2)
    elif crop_position == "top":
        x0 = max(0, (new_w - width) // 2)
        y0 = 0
    elif crop_position == "bottom":
        x0 = max(0, (new_w - width) // 2)
        y0 = max(0, new_h - height)
    elif crop_position == "left":
        x0 = 0
        y0 = max(0, (new_h - height) // 2)
    elif crop_position == "right":
        x0 = max(0, new_w - width)
        y0 = max(0, (new_h - height) // 2)
    else:
        x0 = max(0, (new_w - width) // 2)
        y0 = max(0, (new_h - height) // 2)
    out = scaled[:, y0 : y0 + height, x0 : x0 + width, :]
    if out.shape[1] != height or out.shape[2] != width:
        canvas = torch.zeros((B, height, width, C), dtype=image.dtype, device=image.device)
        canvas[:, : out.shape[1], : out.shape[2], :] = out
        out = canvas
    return out, width, height


def _resize_mask(
    mask: torch.Tensor,
    src_w: int,
    src_h: int,
    target_w: int,
    target_h: int,
    upscale_method: str,
    proportion: str,
    crop_position: str,
    divisible_by: int = 2,
) -> torch.Tensor:
    """
    Resize MASK [B,H,W] with the same geometry as the image.
    Uses the image's original W/H for proportion math so mask tracks the image crop/pad.
    Forces nearest-exact for crisp mask edges (falls back only if requested method fails).
    """
    # Treat mask as single-channel BHWC image for shared geometry
    if mask.dim() == 2:
        mask = mask.unsqueeze(0)
    # Ensure batch matches geometry source size if needed — use mask's own H/W
    # but target geometry is driven by image-derived target_w/target_h and src from image.
    mask_img = mask.unsqueeze(-1)  # BHWC

    # Temporarily rewrite source dims: scale mask from its native size into the
    # same relative transform the image used (src_w/src_h → target).
    # If mask spatial size differs from image, first stretch mask to image size
    # with nearest so coordinates align, then apply the same transform.
    mh, mw = int(mask_img.shape[1]), int(mask_img.shape[2])
    if (mw, mh) != (src_w, src_h):
        m_bchw = mask_img.movedim(-1, 1)
        m_bchw = _common_upscale(m_bchw, src_w, src_h, "nearest-exact", "disabled")
        mask_img = m_bchw.movedim(1, -1)

    # Prefer nearest for masks regardless of UI method (binary edges stay clean)
    method = "nearest-exact"
    out, _, _ = _resize_image(
        mask_img,
        target_w,
        target_h,
        method,
        proportion,
        crop_position,
        pad_color="0, 0, 0",
        divisible_by=divisible_by,
    )
    return out.squeeze(-1).clamp(0.0, 1.0)


def _empty_latent(width: int, height: int, batch_size: int):
    return {"samples": torch.zeros([batch_size, 4, height // 8, width // 8])}


def _mask_size(mask: torch.Tensor) -> Tuple[int, int]:
    # MASK: [B, H, W] or [H, W]
    if mask.dim() == 2:
        return int(mask.shape[1]), int(mask.shape[0])
    return int(mask.shape[2]), int(mask.shape[1])


def _blank_image(batch: int, height: int, width: int, ref: Optional[torch.Tensor] = None) -> torch.Tensor:
    device = ref.device if ref is not None else torch.device("cpu")
    dtype = ref.dtype if ref is not None else torch.float32
    return torch.zeros((batch, height, width, 3), dtype=dtype, device=device)


class AspectRatioSimplifier:
    """
    Get resolution from image (preferred) or mask, OR use a CR-style preset /
    custom size, then resize. Emits image, mask, width, height, empty latent,
    batch size.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "max_resolution": (
                    "INT",
                    {
                        "default": 2048,
                        "min": 0,
                        "max": MAX_RESOLUTION,
                        "step": 8,
                        "tooltip": "Clamp longer side. 0 = no clamp.",
                    },
                ),
                "resolution_source": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "label_on": "custom / preset",
                        "label_off": "image/mask",
                    },
                ),
                "aspect_ratio": (list(ASPECT_PRESETS.keys()),),
                "custom_width": (
                    "INT",
                    {"default": 1024, "min": 16, "max": MAX_RESOLUTION, "step": 8},
                ),
                "custom_height": (
                    "INT",
                    {"default": 1024, "min": 16, "max": MAX_RESOLUTION, "step": 8},
                ),
                "swap_dimensions": (["Off", "On"],),
                "upscale_method": (UPSCALE_METHODS, {"default": "nearest-exact"}),
                "proportion": (PROPORTIONS, {"default": "crop"}),
                "crop_location": (CROP_LOCATIONS, {"default": "center"}),
                "pad_color": (
                    "STRING",
                    {
                        "default": "0, 0, 0",
                        "tooltip": "RGB for pad mode. 0-255 or 0-1.",
                    },
                ),
                "divisible_by": (
                    "INT",
                    {"default": 8, "min": 1, "max": 128, "step": 1},
                ),
                "batch_size": (
                    "INT",
                    {
                        "default": 1,
                        "min": 1,
                        "max": 4096,
                        "tooltip": "Empty latent batch. Image/mask batch is preserved from input.",
                    },
                ),
            },
            "optional": {
                "image": ("IMAGE",),
                "mask": ("MASK",),
            },
        }

    RETURN_TYPES = ("IMAGE", "MASK", "INT", "INT", "LATENT", "INT")
    RETURN_NAMES = ("image", "mask", "width", "height", "latent", "batch")
    FUNCTION = "run"
    CATEGORY = "LC123"
    DESCRIPTION = (
        "Resolve target size from the input image (preferred) or mask, or a CR-style "
        "aspect preset. Resize image and/or mask with the same geometry. "
        "Works with image only, mask only, or both."
    )

    def run(
        self,
        max_resolution,
        resolution_source,
        aspect_ratio,
        custom_width,
        custom_height,
        swap_dimensions,
        upscale_method,
        proportion,
        crop_location,
        pad_color,
        divisible_by,
        batch_size,
        image=None,
        mask=None,
    ):
        has_image = image is not None
        has_mask = mask is not None
        has_source = has_image or has_mask

        # Source size from image (preferred) or mask when present
        if has_image:
            src_w, src_h = _image_size(image)
            src_batch = int(image.shape[0])
            src_ref = image
        elif has_mask:
            src_w, src_h = _mask_size(mask)
            src_batch = 1 if mask.dim() == 2 else int(mask.shape[0])
            src_ref = mask
        else:
            src_w = src_h = 0
            src_batch = max(1, int(batch_size))
            src_ref = None

        def _preset_size():
            preset = ASPECT_PRESETS.get(aspect_ratio)
            if preset is None:
                tw, th = int(custom_width), int(custom_height)
            else:
                tw, th = preset
            if swap_dimensions == "On":
                tw, th = th, tw
            return tw, th

        # resolution_source False = image/mask, True = custom/preset
        # No image/mask (disconnected or upstream bypassed) → always custom/preset
        if has_source and not resolution_source:
            tw, th = src_w, src_h
        else:
            tw, th = _preset_size()

        max_res = int(max_resolution)
        tw, th = _clamp_to_max(tw, th, max_res)
        div = int(divisible_by) if divisible_by else 1
        if div > 1:
            # Round down so we never exceed max_resolution after alignment
            tw = max(div, (tw // div) * div)
            th = max(div, (th // div) * div)
            # If still over max (e.g. div > max), clamp to max then down-align
            if tw > max_res:
                tw = max(div, (max_res // div) * div) if max_res >= div else max_res
            if th > max_res:
                th = max(div, (max_res // div) * div) if max_res >= div else max_res
        tw = max(1, int(tw))
        th = max(1, int(th))
        pad_rgb = _parse_pad_color(pad_color)

        # --- image ---
        if has_image:
            out_image, out_w, out_h = _resize_image(
                image,
                tw,
                th,
                upscale_method,
                proportion,
                crop_location,
                pad_color=pad_rgb,
                divisible_by=int(divisible_by),
            )
        elif has_mask:
            # Mask-only: geometry via proxy, then blank RGB image
            proxy = mask.unsqueeze(-1) if mask.dim() == 3 else mask.unsqueeze(0).unsqueeze(-1)
            proxy = proxy.repeat(1, 1, 1, 3)
            _, out_w, out_h = _resize_image(
                proxy,
                tw,
                th,
                "nearest-exact",
                proportion,
                crop_location,
                pad_color=pad_rgb,
                divisible_by=int(divisible_by),
            )
            out_image = _blank_image(src_batch, out_h, out_w, ref=src_ref)
        else:
            # Nothing connected — blank image at custom/preset size
            out_w, out_h = tw, th
            out_image = _blank_image(src_batch, out_h, out_w, ref=None)

        # --- mask ---
        if has_mask:
            out_mask = _resize_mask(
                mask,
                src_w=src_w,
                src_h=src_h,
                target_w=out_w,
                target_h=out_h,
                upscale_method=upscale_method,
                proportion=proportion,
                crop_position=crop_location,
                divisible_by=int(divisible_by),
            )
        else:
            out_mask = torch.zeros(
                (src_batch, out_h, out_w),
                dtype=out_image.dtype,
                device=out_image.device,
            )

        latent = _empty_latent(out_w, out_h, int(batch_size))
        return (out_image, out_mask, int(out_w), int(out_h), latent, int(batch_size))


NODE_CLASS_MAPPINGS = {
    "AspectRatioSimplifier": AspectRatioSimplifier,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "AspectRatioSimplifier": "📐 Aspect Ratio Simplifier",
}
