"""
Guided filter (Kaiming He, Jian Sun, Xiaoou Tang, "Guided Image Filtering", ECCV 2010): an edge-aware blur in constant
time per pixel. Splitting two images with the SAME guide gives both low-frequency layers the same edges, so swapping or
mixing them cannot leave a halo along a hard edge.

The box means come from running sums, one direction at a time, averaged over the part of the window that lies inside
the image.
"""

from __future__ import annotations

import torch


def _running_mean(x: torch.Tensor, radius: int, dim: int) -> torch.Tensor:
    """Mean of the 2r+1 values around each position along dim, from a running sum (one row or column at a time, so
    the sums stay small and float32 stays exact enough on a 4K frame)."""
    n = x.shape[dim]
    run = torch.nn.functional.pad(x.cumsum(dim).movedim(dim, -1), (1, 0)).movedim(-1, dim)  # run[i] = sum x[:i]
    pos = torch.arange(n, device=x.device)
    start, stop = (pos - radius).clamp(0, n), (pos + radius + 1).clamp(0, n)
    count = (stop - start).to(x.dtype).view([-1 if d == (dim % x.ndim) else 1 for d in range(x.ndim)])
    return (run.index_select(dim, stop) - run.index_select(dim, start)) / count


def box(x: torch.Tensor, radius: int) -> torch.Tensor:
    """Mean over a (2r+1) x (2r+1) window on the last two dims (H, W); at the borders, over the pixels that exist."""
    if radius <= 0:
        return x
    return _running_mean(_running_mean(x, radius, x.ndim - 2), radius, x.ndim - 1)


def guided(guide: torch.Tensor, src: torch.Tensor, radius: int, eps: float = 1e-3) -> torch.Tensor:
    """guide: [N,1,H,W]; src: [N,C,H,W]. Edge-aware low-pass of src that follows the guide's edges (He et al.,
    Algorithm 1)."""
    mean_g, mean_s = box(guide, radius), box(src, radius)
    var_g = (box(guide * guide, radius) - mean_g * mean_g).clamp_min(0.0)
    cov_gs = box(guide * src, radius) - mean_g * mean_s
    a = cov_gs / (var_g + eps)
    b = mean_s - a * mean_g
    return box(a, radius) * guide + box(b, radius)


def luma(x: torch.Tensor) -> torch.Tensor:
    """[N,3,H,W] RGB to [N,1,H,W] Rec.709 luminance."""
    w = x.new_tensor([0.2126, 0.7152, 0.0722]).view(1, 3, 1, 1)
    return (x[:, :3] * w).sum(1, keepdim=True)
