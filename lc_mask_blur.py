"""
LC Mask Blur — Gaussian / box blur on MASK (drop-in for essentials MaskBlur+).
"""

from __future__ import annotations

import torch
import torch.nn.functional as F


def _mask_bhw(mask: torch.Tensor) -> torch.Tensor:
    t = mask
    if not isinstance(t, torch.Tensor):
        t = torch.as_tensor(t)
    t = t.float()
    if t.ndim == 2:
        t = t.unsqueeze(0)
    if t.ndim == 4:
        # BHWC or BCHW
        if t.shape[-1] in (1, 3, 4):
            t = t.mean(dim=-1)
        else:
            t = t[:, 0]
    return t.clamp(0.0, 1.0)


def _gaussian_kernel1d(radius: int, sigma: float, device, dtype) -> torch.Tensor:
    if radius <= 0:
        k = torch.ones(1, device=device, dtype=dtype)
        return k / k.sum()
    x = torch.arange(-radius, radius + 1, device=device, dtype=dtype)
    k = torch.exp(-(x * x) / (2.0 * sigma * sigma))
    return k / k.sum()


def _gaussian_blur_bhw(x: torch.Tensor, amount: float) -> torch.Tensor:
    """Separable Gaussian. amount ~ essentials 'amount' (pixels)."""
    if amount <= 0:
        return x
    radius = max(1, int(round(float(amount))))
    sigma = max(0.5, float(amount) * 0.5)
    b, h, w = x.shape
    device, dtype = x.device, x.dtype
    k1 = _gaussian_kernel1d(radius, sigma, device, dtype)
    # horizontal
    kh = k1.view(1, 1, 1, -1)
    pad_w = radius
    y = F.pad(x.unsqueeze(1), (pad_w, pad_w, 0, 0), mode="reflect")
    y = F.conv2d(y, kh)
    # vertical
    kv = k1.view(1, 1, -1, 1)
    pad_h = radius
    y = F.pad(y, (0, 0, pad_h, pad_h), mode="reflect")
    y = F.conv2d(y, kv)
    return y.squeeze(1).clamp(0.0, 1.0)


class LCMaskBlur:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "mask": ("MASK",),
                "amount": (
                    "FLOAT",
                    {
                        "default": 3.0,
                        "min": 0.0,
                        "max": 64.0,
                        "step": 0.5,
                        "tooltip": "Blur radius (pixels). 0 = no blur.",
                    },
                ),
                "device": (
                    ["auto", "cpu", "gpu"],
                    {
                        "default": "auto",
                        "tooltip": "Where to run the blur.",
                    },
                ),
            }
        }

    RETURN_TYPES = ("MASK",)
    RETURN_NAMES = ("MASK",)
    FUNCTION = "run"
    CATEGORY = "LC123/mask"
    DESCRIPTION = "Blur a mask (Gaussian). Replacement for essentials MaskBlur+."

    def run(self, mask, amount: float = 3.0, device: str = "auto"):
        m = _mask_bhw(mask)
        if device == "gpu" and torch.cuda.is_available():
            dev = torch.device("cuda")
        elif device == "cpu":
            dev = torch.device("cpu")
        else:
            dev = m.device if m.is_cuda else (
                torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")
            )
        m = m.to(dev)
        out = _gaussian_blur_bhw(m, float(amount))
        # Comfy MASK is typically B,H,W on CPU for many nodes — stay on same device as input preferred
        if not mask.is_cuda and out.is_cuda:
            out = out.cpu()
        return (out,)


NODE_CLASS_MAPPINGS = {
    "LCMaskBlur": LCMaskBlur,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LCMaskBlur": "LC Mask Blur",
}
