"""
LC Normal From Depth / LC Normal From Image
-------------------------------------------
- From Depth: depth → normals (for LC Lighting Control + DA-V2)
- From Image: RGB luma gradients (fallback without a normal pack)
"""

from __future__ import annotations

import torch
import torch.nn.functional as F


def _bhwc(t: torch.Tensor) -> torch.Tensor:
    if t.ndim == 3:
        t = t.unsqueeze(0)
    return t


def _to_gray(img: torch.Tensor) -> torch.Tensor:
    t = _bhwc(img).float()
    if t.shape[-1] > 3:
        t = t[..., :3]
    if t.shape[-1] == 1:
        return t
    r, g, b = t[..., 0:1], t[..., 1:2], t[..., 2:3]
    return 0.299 * r + 0.587 * g + 0.114 * b


def _depth_bhw(depth: torch.Tensor) -> torch.Tensor:
    t = _bhwc(depth).float()
    if t.shape[-1] >= 3:
        d = _to_gray(t).squeeze(-1)
    else:
        d = t[..., 0]
    # Per-image percentile stretch so soft DA-V2 maps still have usable slope
    out = []
    for i in range(d.shape[0]):
        x = d[i].reshape(-1)
        lo = torch.quantile(x, 0.02)
        hi = torch.quantile(x, 0.98)
        if float(hi - lo) < 1e-6:
            out.append(torch.zeros_like(d[i]))
        else:
            y = ((d[i] - lo) / (hi - lo)).clamp(0.0, 1.0)
            out.append(y)
    return torch.stack(out, dim=0)


def _blur2d(x: torch.Tensor, radius: int) -> torch.Tensor:
    if radius <= 0:
        return x
    k = int(radius) * 2 + 1
    t = F.avg_pool2d(x.unsqueeze(1), kernel_size=k, stride=1, padding=k // 2)
    return t.squeeze(1)


def _sobel_normals(height: torch.Tensor, scale: float) -> torch.Tensor:
    """
    height B,H,W → normals B,H,W,3 in [-1,1]
    Sobel gradients; scale multiplies slope (higher = more relief in the map).
    """
    # B1HW
    h = height.unsqueeze(1)
    # Sobel kernels
    kx = torch.tensor(
        [[[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]]],
        dtype=h.dtype,
        device=h.device,
    ).view(1, 1, 3, 3)
    ky = torch.tensor(
        [[[-1, -2, -1], [0, 0, 0], [1, 2, 1]]],
        dtype=h.dtype,
        device=h.device,
    ).view(1, 1, 3, 3)
    # reflect pad for edge stability
    hp = F.pad(h, (1, 1, 1, 1), mode="reflect")
    dx = F.conv2d(hp, kx)  # dH/dx
    dy = F.conv2d(hp, ky)  # dH/dy
    s = float(scale)
    # Camera looks down -Z in image space; normal from height field:
    nx = -dx * s
    ny = -dy * s
    nz = torch.ones_like(nx)
    n = torch.cat([nx, ny, nz], dim=1)  # B3HW
    n = n / n.norm(dim=1, keepdim=True).clamp_min(1e-8)
    return n.permute(0, 2, 3, 1)  # BHW3


def _encode_normals(n: torch.Tensor) -> torch.Tensor:
    """[-1,1] BHW3 → [0,1] IMAGE"""
    return (n * 0.5 + 0.5).clamp(0.0, 1.0)


class LCNormalFromDepth:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "depth": ("IMAGE", {"tooltip": "Depth map (Depth Anything V2, etc.)."}),
                "scale": (
                    "FLOAT",
                    {
                        "default": 8.0,
                        "min": 0.5,
                        "max": 64.0,
                        "step": 0.5,
                        "tooltip": "Relief strength. DA-V2 maps are smooth — try 6–16.",
                    },
                ),
                "invert_depth": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "tooltip": "Toggle if relief looks inverted (holes vs bumps).",
                    },
                ),
                "pre_blur": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 16,
                        "step": 1,
                        "tooltip": "0 keeps max detail from depth. Blur only if noisy.",
                    },
                ),
                "detail_boost": (
                    "FLOAT",
                    {
                        "default": 0.5,
                        "min": 0.0,
                        "max": 2.0,
                        "step": 0.05,
                        "tooltip": "Unsharp depth before gradients (brings back soft DA-V2 form).",
                    },
                ),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("normal_map",)
    FUNCTION = "run"
    CATEGORY = "LC123/image"
    DESCRIPTION = (
        "Normal map from depth (Sobel on contrast-stretched depth). "
        "Use with DA-V2 → this → LC Lighting Control. "
        "Not a filter for an existing normal map — generates normals from depth only."
    )

    def run(
        self,
        depth,
        scale: float = 8.0,
        invert_depth: bool = False,
        pre_blur: int = 0,
        detail_boost: float = 0.5,
    ):
        d = _depth_bhw(depth)
        if invert_depth:
            d = 1.0 - d
        if int(pre_blur) > 0:
            d = _blur2d(d, int(pre_blur))
        # Unsharp: d + boost*(d - blur(d))
        boost = float(detail_boost)
        if boost > 0:
            smooth = _blur2d(d, 2)
            d = (d + boost * (d - smooth)).clamp(0.0, 1.0)
        n = _sobel_normals(d, float(scale))
        return (_encode_normals(n),)


class LCNormalFromImage:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "scale": (
                    "FLOAT",
                    {
                        "default": 4.0,
                        "min": 0.5,
                        "max": 32.0,
                        "step": 0.5,
                        "tooltip": "Gradient strength.",
                    },
                ),
                "pre_blur": (
                    "INT",
                    {
                        "default": 1,
                        "min": 0,
                        "max": 16,
                        "step": 1,
                    },
                ),
                "detail": (
                    "FLOAT",
                    {
                        "default": 0.45,
                        "min": 0.0,
                        "max": 1.0,
                        "step": 0.05,
                        "tooltip": "Mix fine vs coarse luma scales.",
                    },
                ),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("normal_map",)
    FUNCTION = "run"
    CATEGORY = "LC123/image"
    DESCRIPTION = (
        "Approximate normals from RGB (multi-scale luma + Sobel). "
        "Fallback if you have no normal pack; depth-based normals are preferred for relight."
    )

    def run(self, image, scale: float = 4.0, pre_blur: int = 1, detail: float = 0.45):
        g = _to_gray(image).squeeze(-1)
        coarse = _blur2d(g, max(int(pre_blur), 1) * 2 + 2)
        fine = _blur2d(g, int(pre_blur))
        n_c = _sobel_normals(coarse, float(scale) * 0.7)
        n_f = _sobel_normals(fine, float(scale))
        d = float(max(0.0, min(1.0, detail)))
        n = n_c * (1.0 - d) + n_f * d
        n = n / n.norm(dim=-1, keepdim=True).clamp_min(1e-8)
        return (_encode_normals(n),)


NODE_CLASS_MAPPINGS = {
    "LCNormalFromDepth": LCNormalFromDepth,
    "LCNormalFromImage": LCNormalFromImage,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LCNormalFromDepth": "LC Normal From Depth",
    "LCNormalFromImage": "LC Normal From Image",
}
