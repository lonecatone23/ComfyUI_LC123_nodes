"""
LC Image Split — live sticky A|B wipe preview; baked split IMAGE out.

Wipe position is controlled only by the split_position slider (not by dragging
the preview). The preview updates live when the slider moves. Output is the
baked composite for Save Image.
"""

from __future__ import annotations

import numpy as np
import torch
from nodes import PreviewImage

from .lc_image_helpers import tensor_to_np, np_to_tensor


def _match_size(a: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    ha, wa = a.shape[:2]
    hb, wb = b.shape[:2]
    if (ha, wa) == (hb, wb):
        return a, b
    t = torch.from_numpy(b[None, ...].transpose(0, 3, 1, 2))
    t = torch.nn.functional.interpolate(t, size=(ha, wa), mode="nearest")
    b2 = t[0].numpy().transpose(1, 2, 0)
    return a, b2.astype(np.float32)


def _split_frame(a: np.ndarray, b: np.ndarray, pos: float, divider: bool) -> np.ndarray:
    a, b = _match_size(a, b)
    h, w = a.shape[:2]
    pos = float(np.clip(pos, 0.0, 1.0))
    cut = int(round(pos * w))
    cut = max(0, min(w, cut))
    out = b.copy()
    if cut > 0:
        out[:, :cut] = a[:, :cut]
    if divider and 0 < cut < w:
        x0 = max(0, cut - 1)
        x1 = min(w, cut + 1)
        out[:, x0:x1] = np.clip(out[:, x0:x1] * 0.25 + 0.85, 0, 1)
    return out.astype(np.float32)


class LCImageSplit(PreviewImage):
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image_a": ("IMAGE", {"tooltip": "Left side of the wipe."}),
                "image_b": ("IMAGE", {"tooltip": "Right side of the wipe."}),
                "split_position": (
                    "FLOAT",
                    {
                        "default": 0.5,
                        "min": 0.0,
                        "max": 1.0,
                        "step": 0.01,
                        "tooltip": "Wipe position 0–1. Adjust with this slider only — dragging the image does not change it. Preview updates live.",
                    },
                ),
                "show_divider": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "tooltip": "Thin light seam on the cut in the saved/output image.",
                    },
                ),
            },
            "hidden": {
                "prompt": "PROMPT",
                "extra_pnginfo": "EXTRA_PNGINFO",
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("split 🖼️",)
    FUNCTION = "run"
    CATEGORY = "LC123/image"
    OUTPUT_NODE = True
    DESCRIPTION = (
        "A|B wipe on the node (slider-only; no drag on image). Output is the baked split for saving."
    )

    def run(
        self,
        image_a,
        image_b,
        split_position=0.5,
        show_divider=True,
        prompt=None,
        extra_pnginfo=None,
    ):
        arrays_a = tensor_to_np(image_a)
        arrays_b = tensor_to_np(image_b)
        n = max(len(arrays_a), len(arrays_b))
        out = []
        for i in range(n):
            a = arrays_a[min(i, len(arrays_a) - 1)]
            b = arrays_b[min(i, len(arrays_b) - 1)]
            out.append(_split_frame(a, b, split_position, bool(show_divider)))
        tensor = np_to_tensor(out)

        # UI keeps full A and B so the frontend can draw a live wipe
        ui = {"a_images": [], "b_images": [], "images": []}
        saved_a = self.save_images(
            image_a, filename_prefix="lc.split.a_", prompt=prompt, extra_pnginfo=extra_pnginfo
        )
        saved_b = self.save_images(
            image_b, filename_prefix="lc.split.b_", prompt=prompt, extra_pnginfo=extra_pnginfo
        )
        saved_out = self.save_images(
            tensor, filename_prefix="lc.split.out_", prompt=prompt, extra_pnginfo=extra_pnginfo
        )
        ui["a_images"] = saved_a["ui"]["images"]
        ui["b_images"] = saved_b["ui"]["images"]
        # Do not put baked composite in images[] — JS draws live wipe from A/B
        # (PreviewImage default would otherwise freeze the static split)
        return {"ui": ui, "result": (tensor,)}


NODE_CLASS_MAPPINGS = {
    "LCImageSplit": LCImageSplit,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LCImageSplit": "LC Image Split 🖼️",
}
