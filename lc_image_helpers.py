"""
Shared image helpers for LC darkroom-style nodes.
"""

import numpy as np
import torch


def tensor_to_np(image):
    """[B,H,W,C] float tensor 0-1 → list of HxWxC float32 arrays."""
    t = image.detach().cpu().numpy().astype(np.float32)
    return [t[i] for i in range(t.shape[0])]


def np_to_tensor(arrays):
    return torch.from_numpy(np.stack(arrays, axis=0).astype(np.float32))


def srgb_to_linear(img):
    a = 0.055
    return np.where(img <= 0.04045, img / 12.92, ((img + a) / (1 + a)) ** 2.4).astype(np.float32)


def linear_to_srgb(img):
    a = 0.055
    return np.where(img <= 0.0031308, img * 12.92, (1 + a) * np.power(np.clip(img, 0, None), 1 / 2.4) - a).astype(np.float32)


def blend(a, b, t):
    t = float(np.clip(t, 0.0, 1.0))
    if t <= 0:
        return a
    if t >= 1:
        return b
    return (a * (1.0 - t) + b * t).astype(np.float32)


def luminance(img):
    return (img[..., 0] * 0.2126 + img[..., 1] * 0.7152 + img[..., 2] * 0.0722).astype(np.float32)
