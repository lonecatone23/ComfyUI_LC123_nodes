"""
Video awareness for per-frame nodes, with no switch: a batch is checked frame to frame. Neighbours that look alike are
one clip (they share a segment); a very different frame is a separate image or a scene cut and starts a new segment.
Measurements (white balance, levels, depth range, noise) are then smoothed over nearby frames of the same segment, so a
clip stops pumping, while separate images and single images come out exactly as before.
The same file lives in LC123 and LC MaskMaker (each pack stands alone).
"""

import math

import torch
import torch.nn.functional as F

THUMB_MAX = 0.08  # mean abs difference of 32x32 thumbnails (0..1); consecutive video frames sit well under it
HIST_MAX = 0.15   # colour histogram distance (0..1); separate generations and hard cuts land above it
SIGMA = 3.0       # frames: how far a measurement is shared


def _frames(images):
    """IMAGE (B,H,W,C) or a list of HxWxC arrays -> float tensor (B,3,H,W) on the CPU."""
    if isinstance(images, torch.Tensor):
        x = images[..., :3].detach().float().cpu()
    else:
        x = torch.stack([torch.as_tensor(a[..., :3]).float() for a in images])
    return x.movedim(-1, 1).clamp(0.0, 1.0)


def segments(images):
    """One segment id per frame. Consecutive frames that look alike share an id."""
    b = len(images)
    if b < 2:
        return [0] * b
    thumbs, small = [], []
    for s in range(0, b, 16):  # a few frames at a time: a long, big video never gets a full float copy
        x = _frames(images[s:s + 16])
        thumbs.append(F.adaptive_avg_pool2d(x, (32, 32)))
        small.append(F.adaptive_avg_pool2d(x, (128, 128)))
    thumbs, small = torch.cat(thumbs), torch.cat(small)
    idx = (small * 15.999).long().flatten(2)
    hist = torch.zeros(b, 3, 16)
    hist.scatter_add_(2, idx, torch.ones_like(idx, dtype=torch.float32))
    hist = hist / hist.sum(-1, keepdim=True)
    seg = [0]
    for i in range(1, b):
        td = float((thumbs[i] - thumbs[i - 1]).abs().mean())
        hd = float(0.5 * (hist[i] - hist[i - 1]).abs().sum(-1).mean())
        same = td < THUMB_MAX and hd < HIST_MAX
        seg.append(seg[-1] if same else seg[-1] + 1)
    return seg


def is_clip(seg):
    """True when at least two frames share a segment (there is something to steady)."""
    return len(seg) != len(set(seg))


def smooth(values, seg, sigma=SIGMA):
    """Per-frame measurements (B, ...) -> the same, Gaussian-averaged over neighbours in the same segment.
    Takes a tensor, a numpy array or a list of numbers and returns the same kind."""
    if not is_clip(seg):
        return values
    kind = type(values)
    v = torch.as_tensor(values if not isinstance(values, list) else [float(a) for a in values]).detach().double()
    out = torch.empty_like(v)
    reach = int(math.ceil(sigma * 3))
    for i in range(len(seg)):
        lo, hi = max(0, i - reach), min(len(seg), i + reach + 1)
        js = [j for j in range(lo, hi) if seg[j] == seg[i]]
        w = torch.tensor([math.exp(-((j - i) ** 2) / (2 * sigma * sigma)) for j in js], dtype=torch.float64, device=v.device)
        w = w.view(-1, *([1] * (v.dim() - 1)))
        out[i] = (v[js] * w).sum(0) / w.sum()
    if kind is list:
        return [float(a) for a in out]
    if kind is torch.Tensor:
        return out.to(dtype=values.dtype, device=values.device)
    return out.numpy().astype(values.dtype)


def smooth_masks(masks, images, seg, reach=2, tol=0.06):
    """Masks (B,H,W) -> steadied over nearby frames of the same segment. A pixel only borrows from a neighbour where
    the picture there barely changed, so moving edges stay sharp and only the threshold flicker goes."""
    if not is_clip(seg):
        return masks
    m = masks.float()
    luma = _frames(images)
    luma = (0.299 * luma[:, 0] + 0.587 * luma[:, 1] + 0.114 * luma[:, 2]).unsqueeze(1)
    if luma.shape[-2:] != m.shape[-2:]:
        luma = F.interpolate(luma, size=m.shape[-2:], mode="bilinear", align_corners=False)
    luma = F.avg_pool2d(luma, 5, stride=1, padding=2, count_include_pad=False)[:, 0].to(m.device)
    out = torch.empty_like(m)
    for i in range(m.shape[0]):
        acc = m[i].clone()
        wsum = torch.ones_like(acc)
        for j in range(max(0, i - reach), min(m.shape[0], i + reach + 1)):
            if j == i or seg[j] != seg[i]:
                continue
            wt = math.exp(-((j - i) ** 2) / 2.0) * torch.exp(-((luma[i] - luma[j]) / tol) ** 2)
            acc = acc + wt * m[j]
            wsum = wsum + wt
        out[i] = acc / wsum
    return out.to(masks.dtype)
