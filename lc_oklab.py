"""
Oklab colour tools for LC image nodes (Oklab by Björn Ottosson), built on lc_color_science.py.

- match(): colour transfer in Oklab. "oklab" fits the full 3x3 colour covariance (linear Monge-Kantorovich, Pitie
  & Kokaram 2007), so it matches the whole colour cloud, not each channel on its own. "oklab + distribution" adds
  sliced optimal-transport passes (IDT) that also match the cloud's shape (several colour populations, tints that
  differ between shadows and highlights). Fitted on a downsampled sample, applied to every pixel, on the GPU.
- Protections in Oklab: skin hue / chroma hold and a neutral guard (a grey may take a cast, never become a colour).
- to_srgb(): back to sRGB with hue-preserving gamut mapping and a soft lightness shoulder instead of hard clipping,
  so over-range colours do not flatten into solid patches.
"""

from __future__ import annotations

import torch

from .lc_color_science import (DistributionTransfer, gamut_map_to_linear, guard_neutrals, linear_to_oklab, linear_to_srgb,
                               mean_cov, mkl, protect_skin, skin_membership, srgb_to_oklab)
from .lc_temporal import segments, smooth

MAX_POINTS = 65536


def _device():
    try:
        import comfy.model_management as mm

        return mm.get_torch_device()
    except Exception:
        return torch.device("cpu")


def _sample(lab_hw3: torch.Tensor, n: int = MAX_POINTS) -> torch.Tensor:
    """Evenly strided sample of an (H,W,3) image as (N,3). Deterministic, so the same input fits the same way."""
    flat = lab_hw3.reshape(-1, 3)
    step = max(1, flat.shape[0] // n)
    return flat[::step][:n]


def to_srgb(lab: torch.Tensor) -> torch.Tensor:
    """Oklab (...,3) -> sRGB 0..1, gamut-mapped (hue and lightness kept, chroma reduced only where it must be)."""
    return linear_to_srgb(gamut_map_to_linear(lab)).clamp(0.0, 1.0)


def match(image_bhwc: torch.Tensor, reference_bhwc: torch.Tensor, distribution: bool = False,
          skin_protect: float = 0.5, neutral_guard: bool = True, strength: float = 1.0) -> torch.Tensor:
    """Colour-match every image to the reference(s). Reference batch the same size as the image batch: frame i is
    matched to reference i. Otherwise every reference frame is pooled into one target look.
    One frame at a time on the GPU (a long video never sits there whole); the result is built where the input lives.
    strength blends original (0) to matched (1). Shows a progress bar (fit pass, then apply pass)."""
    import comfy.utils

    dev = _device()
    n, n_ref = image_bhwc.shape[0], reference_bhwc.shape[0]
    pair = n_ref == n and n > 1

    def lab_of(t, i):
        return srgb_to_oklab(t[i, ..., :3].to(dev, torch.float32).clamp(0, 1))

    if not pair:
        per = max(1, MAX_POINTS // n_ref)
        pooled = torch.cat([_sample(lab_of(reference_bhwc, i), per) for i in range(n_ref)], 0)
    pbar = comfy.utils.ProgressBar(2 * n)
    fits = []
    for i in range(n):
        src = _sample(lab_of(image_bhwc, i))
        dst = _sample(lab_of(reference_bhwc, i)) if pair else pooled
        mu_s, cov_s = mean_cov(src)
        mu_d, cov_d = mean_cov(dst)
        a, b = mkl(mu_s, cov_s, mu_d, cov_d)
        fits.append(torch.cat([a.to(torch.float32), b.to(torch.float32).view(3, 1)], 1))
        pbar.update(1)
    # a video clip shares its colour transform over nearby frames, so the match does not pump; separate images keep
    # their own
    fits = smooth(torch.stack(fits), segments(image_bhwc))
    out = torch.empty((n, *image_bhwc.shape[1:3], 3), dtype=torch.float32, device=image_bhwc.device)
    for i in range(n):
        lab = lab_of(image_bhwc, i)
        a, b = fits[i][:, :3], fits[i][:, 3]
        flat = lab.reshape(-1, 3)
        mapped = flat @ a.T + b
        if distribution:
            dst = _sample(lab_of(reference_bhwc, i)) if pair else pooled
            chain = DistributionTransfer.fit(_sample(lab) @ a.T + b, dst, iterations=10)
            mapped = chain(mapped)
        mapped = mapped.reshape(lab.shape)
        if neutral_guard:
            mapped = guard_neutrals(lab, mapped)
        if skin_protect > 0:
            mapped = protect_skin(lab, mapped, float(skin_protect))
        res = to_srgb(mapped)
        if strength < 1.0:
            orig = image_bhwc[i, ..., :3].to(dev, torch.float32).clamp(0, 1)
            res = torch.lerp(orig, res, float(strength))
        out[i] = res.clamp(0, 1).to(out.device)
        pbar.update(1)
    return out


# ---------------------------------------------------------------- numpy helpers for the numpy-based LC nodes
def linear_to_srgb_safe(lin):
    """Linear RGB numpy (H,W,3), possibly out of range, -> sRGB 0..1 numpy with hue-preserving gamut mapping
    instead of clipping each channel (which shifts hue and flattens bright colours into solid patches)."""
    import numpy as np


    t = torch.from_numpy(np.ascontiguousarray(lin, dtype=np.float32))
    return to_srgb(linear_to_oklab(t)).numpy().astype(np.float32)


def vibrance(img, vibrance_pct, saturation_pct, protect_skin):
    """sRGB numpy (H,W,3) -> sRGB numpy. Scales Oklab chroma, so hue never shifts. Vibrance lifts low-chroma colours
    most and leaves strong ones nearly alone; saturation scales everything; skin gets 70 % less vibrance."""
    import numpy as np


    lab = srgb_to_oklab(torch.from_numpy(np.ascontiguousarray(img[..., :3], dtype=np.float32)))
    c = (lab[..., 1:2] ** 2 + lab[..., 2:3] ** 2).sqrt()
    scale = torch.ones_like(c)
    if abs(vibrance_pct) > 0.5:
        t = (c / 0.20).clamp(0, 1)
        weight = 1.0 - t * t * (3 - 2 * t)  # full on greys and pastels, none on colours already at chroma 0.2+
        if protect_skin:
            weight = weight * (1.0 - 0.7 * skin_membership(lab))
        scale = scale * (1.0 + (vibrance_pct / 100.0) * weight)
    if abs(saturation_pct) > 0.5:
        scale = scale * (1.0 + saturation_pct / 100.0)
    lab = torch.cat([lab[..., 0:1], lab[..., 1:3] * scale.clamp(min=0.0)], -1)
    return to_srgb(lab).numpy().astype(np.float32)


def vibrance_signed(rgb, vib, skin_protect):
    """LC Photo Style's vibrance in Oklab: vib -1..1 (negative mutes), skin_protect 0..1. Hue never shifts."""
    import numpy as np


    lab = srgb_to_oklab(torch.from_numpy(np.ascontiguousarray(rgb[..., :3], dtype=np.float32)))
    c = (lab[..., 1:2] ** 2 + lab[..., 2:3] ** 2).sqrt()
    t = (c / 0.20).clamp(0, 1)
    weight = (1.0 - t * t * (3 - 2 * t)) * abs(float(vib)) * 0.7
    weight = weight * (1.0 - 0.9 * skin_membership(lab) * float(skin_protect))
    scale = 1.0 + weight if vib >= 0 else (1.0 - weight).clamp(min=0.0)
    return to_srgb(torch.cat([lab[..., 0:1], lab[..., 1:3] * scale], -1)).numpy().astype(np.float32)
