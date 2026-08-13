"""
LC Watermark — composite watermark with live drag/size/opacity (no wipe).
Bypass when watermark is missing.
"""

from __future__ import annotations

import numpy as np
from PIL import Image
from nodes import PreviewImage

from .lc_image_helpers import tensor_to_np, np_to_tensor


def _preview(self, result_tensor, base_tensor=None, wm_tensor=None):
    out = {"ui": {}, "result": (result_tensor,)}
    try:
        after = self.save_images(result_tensor, filename_prefix="lc_after")
        out["ui"]["lc_preview"] = after["ui"]["images"]
        if base_tensor is not None:
            before = self.save_images(base_tensor, filename_prefix="lc_before")
            out["ui"]["lc_before"] = before["ui"]["images"]
        if wm_tensor is not None:
            wm = self.save_images(wm_tensor, filename_prefix="lc_wm")
            out["ui"]["lc_watermark"] = wm["ui"]["images"]
    except Exception:
        pass
    return out


def _to_rgba_pil(arr: np.ndarray) -> Image.Image:
    a = np.asarray(arr, dtype=np.float32)
    a = np.clip(a, 0.0, 1.0)
    if a.ndim == 2:
        a = np.stack([a, a, a], axis=-1)
    if a.shape[-1] == 1:
        a = np.repeat(a, 3, axis=-1)
    h, w, c = a.shape
    if c == 3:
        rgba = np.dstack([a, np.ones((h, w), dtype=np.float32)])
    else:
        rgba = a[..., :4]
    return Image.fromarray((rgba * 255.0).round().astype(np.uint8), mode="RGBA")


def _paste_watermark(
    base_rgb: np.ndarray,
    wm_rgba: Image.Image,
    size_percent: float,
    opacity: float,
    x_percent: float,
    y_percent: float,
    margin_percent: float,
) -> np.ndarray:
    bh, bw = base_rgb.shape[:2]
    base = _to_rgba_pil(base_rgb)

    size_percent = float(np.clip(size_percent, 1.0, 100.0))
    opacity = float(np.clip(opacity, 0.0, 1.0))
    margin_percent = float(np.clip(margin_percent, 0.0, 45.0))

    target_w = max(1, int(round(bw * (size_percent / 100.0))))
    aspect = wm_rgba.height / max(1, wm_rgba.width)
    target_h = max(1, int(round(target_w * aspect)))
    wm = wm_rgba.resize((target_w, target_h), Image.Resampling.LANCZOS)

    if opacity < 1.0:
        r, g, b, a = wm.split()
        a = a.point(lambda p, o=opacity: int(p * o))
        wm = Image.merge("RGBA", (r, g, b, a))

    mx = bw * (margin_percent / 100.0)
    my = bh * (margin_percent / 100.0)
    usable_w = max(1.0, bw - 2 * mx)
    usable_h = max(1.0, bh - 2 * my)

    # x/y = center of watermark in usable area (0–100)
    cx = mx + (float(np.clip(x_percent, 0.0, 100.0)) / 100.0) * usable_w
    cy = my + (float(np.clip(y_percent, 0.0, 100.0)) / 100.0) * usable_h
    x = int(round(cx - target_w / 2.0))
    y = int(round(cy - target_h / 2.0))
    x = int(np.clip(x, 0, max(0, bw - target_w)))
    y = int(np.clip(y, 0, max(0, bh - target_h)))

    base.paste(wm, (x, y), wm)
    return np.asarray(base.convert("RGB"), dtype=np.float32) / 255.0


class LCWatermark(PreviewImage):
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "size_percent": (
                    "FLOAT",
                    {
                        "default": 20.0,
                        "min": 1.0,
                        "max": 100.0,
                        "step": 0.5,
                        "tooltip": "Watermark width as % of base width. Live on node after first run.",
                    },
                ),
                "opacity": (
                    "FLOAT",
                    {
                        "default": 0.85,
                        "min": 0.0,
                        "max": 1.0,
                        "step": 0.05,
                        "tooltip": "Opacity 0–1. Live on node after first run.",
                    },
                ),
                "x_percent": (
                    "FLOAT",
                    {
                        "default": 90.0,
                        "min": 0.0,
                        "max": 100.0,
                        "step": 0.5,
                        "tooltip": "Horizontal center %. Drag on preview to set.",
                    },
                ),
                "y_percent": (
                    "FLOAT",
                    {
                        "default": 90.0,
                        "min": 0.0,
                        "max": 100.0,
                        "step": 0.5,
                        "tooltip": "Vertical center %. Drag on preview to set.",
                    },
                ),
                "margin_percent": (
                    "FLOAT",
                    {
                        "default": 0.5,
                        "min": 0.0,
                        "max": 10.0,
                        "step": 0.1,
                        "tooltip": "Edge padding as % of image (small, similar to Text Overlay ~6px).",
                    },
                ),
            },
            "optional": {
                "watermark": (
                    "IMAGE",
                    {
                        "tooltip": "Watermark (RGB/RGBA). Missing = bypass (pass-through).",
                    },
                ),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "run"
    CATEGORY = "LC123/image"
    OUTPUT_NODE = True
    DESCRIPTION = (
        "Composite a watermark image. Drag to place; size and opacity update live after the first run. No watermark input = bypass."
    )

    def run(
        self,
        image,
        size_percent=20.0,
        opacity=0.85,
        x_percent=90.0,
        y_percent=90.0,
        margin_percent=3.0,
        watermark=None,
    ):
        if watermark is None:
            return _preview(self, image, image, None)

        base_frames = tensor_to_np(image)
        wm_frames = tensor_to_np(watermark)
        wm_pil = _to_rgba_pil(wm_frames[0])

        out_frames = [
            _paste_watermark(
                frame,
                wm_pil,
                size_percent,
                opacity,
                x_percent,
                y_percent,
                margin_percent,
            )
            for frame in base_frames
        ]
        result = np_to_tensor(out_frames)
        # Pass first watermark frame as IMAGE tensor for UI (batch of 1)
        wm_tensor = np_to_tensor([wm_frames[0] if wm_frames[0].shape[-1] >= 3 else wm_frames[0]])
        # ensure 3ch for save_images
        w0 = wm_frames[0]
        if w0.shape[-1] == 4:
            w0 = w0[..., :3]
        elif w0.ndim == 2:
            w0 = np.stack([w0, w0, w0], axis=-1)
        wm_tensor = np_to_tensor([w0.astype(np.float32)])
        return _preview(self, result, image, wm_tensor)


NODE_CLASS_MAPPINGS = {
    "LCWatermark": LCWatermark,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LCWatermark": "LC Watermark 💧",
}
