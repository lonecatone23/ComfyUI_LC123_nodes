"""
LC Dynamic Overlay
------------------
Image A = base (sets resolution).
Image B = overlay, fit-scaled (no stretch/crop), centered.
Opacity composites B over A.

Frontend caches A+B after one run; circular knob updates the preview live.

Class ID: LCDynamicOverlay
Display:  LC Dynamic Overlay
"""

from __future__ import annotations

import os
import random

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image

import folder_paths


def _to_nchw(img: torch.Tensor) -> torch.Tensor:
    if img.ndim == 3:
        img = img.unsqueeze(0)
    return img.permute(0, 3, 1, 2).contiguous()


def _to_bhwc(img: torch.Tensor) -> torch.Tensor:
    return img.permute(0, 2, 3, 1).contiguous()


def _fit_resize(img_nchw: torch.Tensor, out_h: int, out_w: int) -> torch.Tensor:
    b, c, h, w = img_nchw.shape
    if h == out_h and w == out_w:
        return img_nchw
    scale = min(out_w / max(w, 1), out_h / max(h, 1))
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))
    resized = F.interpolate(
        img_nchw, size=(new_h, new_w), mode="bilinear", align_corners=False
    )
    canvas = torch.zeros(
        b, c, out_h, out_w, device=img_nchw.device, dtype=img_nchw.dtype
    )
    y0 = (out_h - new_h) // 2
    x0 = (out_w - new_w) // 2
    canvas[:, :, y0 : y0 + new_h, x0 : x0 + new_w] = resized
    return canvas


def _match_batch(a: torch.Tensor, b: torch.Tensor):
    if a.shape[0] == b.shape[0]:
        return a, b
    if a.shape[0] == 1:
        a = a.expand(b.shape[0], -1, -1, -1)
    elif b.shape[0] == 1:
        b = b.expand(a.shape[0], -1, -1, -1)
    else:
        n = min(a.shape[0], b.shape[0])
        a, b = a[:n], b[:n]
    return a, b


def _save_preview(tensor_bhwc: torch.Tensor, prefix: str) -> dict:
    img = tensor_bhwc[0].detach().cpu().numpy()
    img = (np.clip(img, 0.0, 1.0) * 255).astype(np.uint8)
    if img.shape[-1] == 1:
        img = np.repeat(img, 3, axis=-1)
    elif img.shape[-1] > 3:
        img = img[:, :, :3]
    pil = Image.fromarray(img)
    out_dir = folder_paths.get_temp_directory()
    os.makedirs(out_dir, exist_ok=True)
    filename = f"{prefix}_{random.randint(0, 2**31 - 1):08x}.png"
    pil.save(os.path.join(out_dir, filename), compress_level=1)
    return {"filename": filename, "subfolder": "", "type": "temp"}


class LCDynamicOverlay:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image_a": ("IMAGE",),
                "image_b": ("IMAGE",),
                "opacity": (
                    "FLOAT",
                    {
                        "default": 0.5,
                        "min": 0.0,
                        "max": 1.0,
                        "step": 0.01,
                    },
                ),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "overlay"
    CATEGORY = "LC123/image"
    OUTPUT_NODE = True
    DESCRIPTION = (
        "Overlay image B on A. A sets resolution; B is fit-scaled. After one run, adjust opacity on the node without regenerating."
    )

    def overlay(self, image_a, image_b, opacity: float):
        opacity = float(max(0.0, min(1.0, opacity)))

        a = _to_nchw(image_a)
        b = _to_nchw(image_b)
        a, b = _match_batch(a, b)

        _, _, ah, aw = a.shape
        b_fit = _fit_resize(b, ah, aw)

        # Coverage: 1 where fitted B was drawn, 0 on letterbox pad.
        # Prevents black pad pixels from darkening image A.
        b_sum = b_fit.abs().sum(dim=1, keepdim=True)
        # Rebuild coverage from fit geometry (zeros outside placed B)
        _, _, bh0, bw0 = b.shape
        scale = min(aw / max(bw0, 1), ah / max(bh0, 1))
        new_w = max(1, int(round(bw0 * scale)))
        new_h = max(1, int(round(bh0 * scale)))
        y0 = (ah - new_h) // 2
        x0 = (aw - new_w) // 2
        cover = torch.zeros(
            a.shape[0], 1, ah, aw, device=a.device, dtype=a.dtype
        )
        cover[:, :, y0 : y0 + new_h, x0 : x0 + new_w] = 1.0
        alpha = opacity * cover
        out = (a * (1.0 - alpha) + b_fit * alpha).clamp(0.0, 1.0)
        out_bhwc = _to_bhwc(out)
        a_bhwc = _to_bhwc(a)
        b_bhwc = _to_bhwc(b_fit)

        meta_a = _save_preview(a_bhwc, "lc_ov_a")
        meta_b = _save_preview(b_bhwc, "lc_ov_b")
        meta_out = _save_preview(out_bhwc, "lc_ov_out")

        return {
            "ui": {
                "images": [meta_a, meta_b, meta_out],
            },
            "result": (out_bhwc,),
        }


NODE_CLASS_MAPPINGS = {
    "LCDynamicOverlay": LCDynamicOverlay,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LCDynamicOverlay": "LC Dynamic Overlay",
}
