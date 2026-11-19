"""
LC Photo Style 📷 — camera / phone finish looks (presets drive the sliders).
Preset dropdown drives sliders (Skin Beauty pattern).
Slider 0 = no change on that control (where applicable).
"""
from __future__ import annotations

from typing import Dict

import numpy as np

from nodes import PreviewImage

try:
    from .lc_image_helpers import tensor_to_np, np_to_tensor, blend, _alpha_safe
except ImportError:
    from lc_image_helpers import tensor_to_np, np_to_tensor, blend, _alpha_safe

try:
    from .lc_image_tools import _preview
except ImportError:
    try:
        from lc_image_tools import _preview
    except ImportError:
        def _preview(self, result, original):
            return (result,)


# ---------------------------------------------------------------------------
# Presets — values match widget ranges (0 = neutral on bipolar controls)
# ---------------------------------------------------------------------------
PRESETS: Dict[str, dict] = {
    "Standard": {
        "wb_temperature": 0.08,
        "wb_tint": 0.00,
        "exposure": 0.04,
        "contrast": 0.12,
        "shadows": 0.25,
        "highlights": 0.30,
        "hdr_local": 0.20,
        "vibrance": 0.22,
        "skin_protect": 0.65,
        "shadow_cool": 0.10,
        "highlight_warm": 0.12,
        "texture": 0.18,
        "clarity": 0.12,
        "vignette": 0.14,
        "grain": 0.10,
        "black_lift": 0.00,
        "natural": 0.00,
        "auto_wb": 0.00,
        "phone_sharpen": 0.00,
        "noise_smear": 0.00,
        "compression": 0.00,
        "lens": 0.00,
        "resolution": 0.00,
        "clip": 0.00,
    },
    "Natural": {
        "wb_temperature": 0.03,
        "wb_tint": 0.00,
        "exposure": 0.02,
        "contrast": 0.06,
        "shadows": 0.18,
        "highlights": 0.22,
        "hdr_local": 0.10,
        "vibrance": 0.10,
        "skin_protect": 0.75,
        "shadow_cool": 0.04,
        "highlight_warm": 0.06,
        "texture": 0.08,
        "clarity": 0.05,
        "vignette": 0.06,
        "grain": 0.05,
        "black_lift": 0.00,
        "natural": 0.00,
        "auto_wb": 0.00,
        "phone_sharpen": 0.00,
        "noise_smear": 0.00,
        "compression": 0.00,
        "lens": 0.00,
        "resolution": 0.00,
        "clip": 0.00,
    },
    "Dramatic": {
        "wb_temperature": 0.02,
        "wb_tint": 0.00,
        "exposure": -0.06,
        "contrast": 0.28,
        "shadows": 0.08,
        "highlights": 0.45,
        "hdr_local": 0.25,
        "vibrance": 0.15,
        "skin_protect": 0.60,
        "shadow_cool": 0.18,
        "highlight_warm": 0.10,
        "texture": 0.22,
        "clarity": 0.22,
        "vignette": 0.28,
        "grain": 0.12,
        "black_lift": 0.00,
        "natural": 0.00,
        "auto_wb": 0.00,
        "phone_sharpen": 0.00,
        "noise_smear": 0.00,
        "compression": 0.00,
        "lens": 0.00,
        "resolution": 0.00,
        "clip": 0.00,
    },
    "Quiet": {
        "wb_temperature": -0.10,
        "wb_tint": 0.04,
        "exposure": -0.04,
        "contrast": 0.04,
        "shadows": 0.20,
        "highlights": 0.20,
        "hdr_local": 0.08,
        "vibrance": 0.02,
        "skin_protect": 0.80,
        "shadow_cool": 0.16,
        "highlight_warm": 0.02,
        "texture": 0.06,
        "clarity": 0.04,
        "vignette": 0.12,
        "grain": 0.08,
        "black_lift": 0.00,
        "natural": 0.00,
        "auto_wb": 0.00,
        "phone_sharpen": 0.00,
        "noise_smear": 0.00,
        "compression": 0.00,
        "lens": 0.00,
        "resolution": 0.00,
        "clip": 0.00,
    },
    "Muted": {
        "wb_temperature": 0.00,
        "wb_tint": 0.00,
        "exposure": 0.00,
        "contrast": 0.08,
        "shadows": 0.15,
        "highlights": 0.25,
        "hdr_local": 0.08,
        "vibrance": -0.20,
        "skin_protect": 0.70,
        "shadow_cool": 0.08,
        "highlight_warm": 0.04,
        "texture": 0.08,
        "clarity": 0.06,
        "vignette": 0.08,
        "grain": 0.06,
        "black_lift": 0.00,
        "natural": 0.00,
        "auto_wb": 0.00,
        "phone_sharpen": 0.00,
        "noise_smear": 0.00,
        "compression": 0.00,
        "lens": 0.00,
        "resolution": 0.00,
        "clip": 0.00,
    },
    "Amateur": {
        "wb_temperature": 0.22,
        "wb_tint": -0.08,
        "exposure": 0.08,
        "contrast": 0.24,
        "shadows": 0.10,
        "highlights": 0.18,
        "hdr_local": 0.05,
        "vibrance": 0.30,
        "skin_protect": 0.25,
        "shadow_cool": 0.02,
        "highlight_warm": 0.22,
        "texture": 0.28,
        "clarity": 0.18,
        "vignette": 0.32,
        "grain": 0.22,
        "black_lift": 0.00,
        "natural": 0.00,
        "auto_wb": 0.00,
        "phone_sharpen": 0.00,
        "noise_smear": 0.00,
        "compression": 0.00,
        "lens": 0.00,
        "resolution": 0.00,
        "clip": 0.00,
    },
    "Cool day": {
        "wb_temperature": -0.35,
        "wb_tint": 0.12,
        "exposure": 0.02,
        "contrast": 0.14,
        "shadows": 0.22,
        "highlights": 0.35,
        "hdr_local": 0.18,
        "vibrance": 0.12,
        "skin_protect": 0.55,
        "shadow_cool": 0.22,
        "highlight_warm": 0.04,
        "texture": 0.16,
        "clarity": 0.14,
        "vignette": 0.16,
        "grain": 0.10,
        "black_lift": 0.00,
        "natural": 0.00,
        "auto_wb": 0.00,
        "phone_sharpen": 0.00,
        "noise_smear": 0.00,
        "compression": 0.00,
        "lens": 0.00,
        "resolution": 0.00,
        "clip": 0.00,
    },
    "Warm evening": {
        "wb_temperature": 0.40,
        "wb_tint": -0.08,
        "exposure": 0.06,
        "contrast": 0.16,
        "shadows": 0.28,
        "highlights": 0.28,
        "hdr_local": 0.15,
        "vibrance": 0.18,
        "skin_protect": 0.60,
        "shadow_cool": 0.02,
        "highlight_warm": 0.28,
        "texture": 0.14,
        "clarity": 0.12,
        "vignette": 0.20,
        "grain": 0.12,
        "black_lift": 0.00,
        "natural": 0.00,
        "auto_wb": 0.00,
        "phone_sharpen": 0.00,
        "noise_smear": 0.00,
        "compression": 0.00,
        "lens": 0.00,
        "resolution": 0.00,
        "clip": 0.00,
    },
    "Bright open": {
        "wb_temperature": -0.02,
        "wb_tint": -0.19,
        "exposure": 0.37,
        "contrast": 0.14,
        "shadows": 0.79,
        "highlights": 0.82,
        "hdr_local": 0.51,
        "vibrance": 0.12,
        "skin_protect": 0.61,
        "shadow_cool": 0.22,
        "highlight_warm": 0.04,
        "texture": 0.32,
        "clarity": 0.33,
        "vignette": 0.24,
        "grain": 0.16,
        "black_lift": 0.00,
        "natural": 0.00,
        "auto_wb": 0.00,
        "phone_sharpen": 0.00,
        "noise_smear": 0.00,
        "compression": 0.00,
        "lens": 0.00,
        "resolution": 0.00,
        "clip": 0.00,
    },
    "iPhone": {
        "wb_temperature": 0.10,
        "wb_tint": -0.02,
        "exposure": 0.08,
        "contrast": 0.12,
        "shadows": 0.42,
        "highlights": 0.48,
        "hdr_local": 0.32,
        "vibrance": 0.28,
        "skin_protect": 0.72,
        "shadow_cool": 0.14,
        "highlight_warm": 0.16,
        "texture": 0.22,
        "clarity": 0.16,
        "vignette": 0.08,
        "grain": 0.06,
        "black_lift": 0.13,
        "natural": 0.35,
        "auto_wb": 0.40,
        "phone_sharpen": 0.20,
        "noise_smear": 0.15,
        "compression": 0.00,
        "lens": 0.12,
        "resolution": 0.00,
        "clip": 0.00,
    },
    "iPhone Luminous": {
        "wb_temperature": 0.14,
        "wb_tint": -0.02,
        "exposure": 0.22,
        "contrast": 0.06,
        "shadows": 0.54,
        "highlights": 0.48,
        "hdr_local": 0.32,
        "vibrance": 0.32,
        "skin_protect": 0.72,
        "shadow_cool": 0.14,
        "highlight_warm": 0.16,
        "texture": 0.22,
        "clarity": 0.16,
        "vignette": 0.08,
        "grain": 0.06,
        "black_lift": 0.13,
        "natural": 0.35,
        "auto_wb": 0.40,
        "phone_sharpen": 0.20,
        "noise_smear": 0.15,
        "compression": 0.00,
        "lens": 0.12,
        "resolution": 0.00,
        "clip": 0.00,
    },
    "iPhone Vibrant": {
        "wb_temperature": 0.10,
        "wb_tint": -0.02,
        "exposure": 0.08,
        "contrast": 0.20,
        "shadows": 0.42,
        "highlights": 0.48,
        "hdr_local": 0.32,
        "vibrance": 0.50,
        "skin_protect": 0.72,
        "shadow_cool": 0.14,
        "highlight_warm": 0.16,
        "texture": 0.22,
        "clarity": 0.22,
        "vignette": 0.08,
        "grain": 0.06,
        "black_lift": 0.13,
        "natural": 0.35,
        "auto_wb": 0.40,
        "phone_sharpen": 0.20,
        "noise_smear": 0.15,
        "compression": 0.00,
        "lens": 0.12,
        "resolution": 0.00,
        "clip": 0.00,
    },
    "iPhone Cozy": {
        "wb_temperature": 0.26,
        "wb_tint": -0.02,
        "exposure": 0.08,
        "contrast": 0.07,
        "shadows": 0.42,
        "highlights": 0.48,
        "hdr_local": 0.32,
        "vibrance": 0.31,
        "skin_protect": 0.72,
        "shadow_cool": 0.14,
        "highlight_warm": 0.26,
        "texture": 0.22,
        "clarity": 0.16,
        "vignette": 0.08,
        "grain": 0.06,
        "black_lift": 0.13,
        "natural": 0.35,
        "auto_wb": 0.40,
        "phone_sharpen": 0.20,
        "noise_smear": 0.15,
        "compression": 0.00,
        "lens": 0.12,
        "resolution": 0.00,
        "clip": 0.00,
    },
    "iPhone Ethereal": {
        "wb_temperature": -0.02,
        "wb_tint": 0.03,
        "exposure": 0.20,
        "contrast": 0.04,
        "shadows": 0.50,
        "highlights": 0.55,
        "hdr_local": 0.32,
        "vibrance": 0.14,
        "skin_protect": 0.72,
        "shadow_cool": 0.18,
        "highlight_warm": 0.08,
        "texture": 0.22,
        "clarity": 0.08,
        "vignette": 0.08,
        "grain": 0.06,
        "black_lift": 0.13,
        "natural": 0.35,
        "auto_wb": 0.40,
        "phone_sharpen": 0.20,
        "noise_smear": 0.15,
        "compression": 0.00,
        "lens": 0.12,
        "resolution": 0.00,
        "clip": 0.00,
    },
    "iPhone Amber": {
        "wb_temperature": 0.40,
        "wb_tint": -0.12,
        "exposure": 0.08,
        "contrast": 0.12,
        "shadows": 0.42,
        "highlights": 0.48,
        "hdr_local": 0.32,
        "vibrance": 0.28,
        "skin_protect": 0.72,
        "shadow_cool": 0.14,
        "highlight_warm": 0.26,
        "texture": 0.22,
        "clarity": 0.16,
        "vignette": 0.08,
        "grain": 0.06,
        "black_lift": 0.13,
        "natural": 0.35,
        "auto_wb": 0.40,
        "phone_sharpen": 0.20,
        "noise_smear": 0.15,
        "compression": 0.00,
        "lens": 0.12,
        "resolution": 0.00,
        "clip": 0.00,
    },
    "iPhone Gold": {
        "wb_temperature": 0.30,
        "wb_tint": -0.02,
        "exposure": 0.08,
        "contrast": 0.12,
        "shadows": 0.42,
        "highlights": 0.48,
        "hdr_local": 0.32,
        "vibrance": 0.32,
        "skin_protect": 0.72,
        "shadow_cool": 0.14,
        "highlight_warm": 0.34,
        "texture": 0.22,
        "clarity": 0.16,
        "vignette": 0.08,
        "grain": 0.06,
        "black_lift": 0.13,
        "natural": 0.35,
        "auto_wb": 0.40,
        "phone_sharpen": 0.20,
        "noise_smear": 0.15,
        "compression": 0.00,
        "lens": 0.12,
        "resolution": 0.00,
        "clip": 0.00,
    },
    "iPhone Rose Gold": {
        "wb_temperature": 0.20,
        "wb_tint": 0.43,
        "exposure": 0.08,
        "contrast": 0.12,
        "shadows": 0.42,
        "highlights": 0.48,
        "hdr_local": 0.32,
        "vibrance": 0.28,
        "skin_protect": 0.72,
        "shadow_cool": 0.14,
        "highlight_warm": 0.16,
        "texture": 0.22,
        "clarity": 0.16,
        "vignette": 0.08,
        "grain": 0.06,
        "black_lift": 0.13,
        "natural": 0.35,
        "auto_wb": 0.40,
        "phone_sharpen": 0.20,
        "noise_smear": 0.15,
        "compression": 0.00,
        "lens": 0.12,
        "resolution": 0.00,
        "clip": 0.00,
    },
    "iPhone Cool Rose": {
        "wb_temperature": -0.06,
        "wb_tint": 0.38,
        "exposure": 0.08,
        "contrast": 0.12,
        "shadows": 0.42,
        "highlights": 0.48,
        "hdr_local": 0.32,
        "vibrance": 0.28,
        "skin_protect": 0.72,
        "shadow_cool": 0.14,
        "highlight_warm": 0.16,
        "texture": 0.22,
        "clarity": 0.16,
        "vignette": 0.08,
        "grain": 0.06,
        "black_lift": 0.13,
        "natural": 0.35,
        "auto_wb": 0.40,
        "phone_sharpen": 0.20,
        "noise_smear": 0.15,
        "compression": 0.00,
        "lens": 0.12,
        "resolution": 0.00,
        "clip": 0.00,
    },
    "iPhone Neutral": {
        "wb_temperature": -0.08,
        "wb_tint": -0.02,
        "exposure": 0.08,
        "contrast": 0.12,
        "shadows": 0.42,
        "highlights": 0.48,
        "hdr_local": 0.32,
        "vibrance": 0.28,
        "skin_protect": 0.72,
        "shadow_cool": 0.02,
        "highlight_warm": 0.02,
        "texture": 0.22,
        "clarity": 0.16,
        "vignette": 0.08,
        "grain": 0.06,
        "black_lift": 0.13,
        "natural": 0.35,
        "auto_wb": 0.40,
        "phone_sharpen": 0.20,
        "noise_smear": 0.15,
        "compression": 0.00,
        "lens": 0.12,
        "resolution": 0.00,
        "clip": 0.00,
    },
    "Selfie": {
        "wb_temperature": 0.16,
        "wb_tint": -0.02,
        "exposure": 0.12,
        "contrast": 0.12,
        "shadows": 0.47,
        "highlights": 0.48,
        "hdr_local": 0.32,
        "vibrance": 0.28,
        "skin_protect": 0.82,
        "shadow_cool": 0.14,
        "highlight_warm": 0.16,
        "texture": 0.14,
        "clarity": 0.12,
        "vignette": 0.04,
        "grain": 0.10,
        "black_lift": 0.13,
        "natural": 0.35,
        "auto_wb": 0.40,
        "phone_sharpen": 0.45,
        "noise_smear": 0.45,
        "compression": 0.00,
        "lens": 0.30,
        "resolution": 0.00,
        "clip": 0.00,
    },
    "Shared": {
        "wb_temperature": 0.10,
        "wb_tint": -0.02,
        "exposure": 0.08,
        "contrast": 0.16,
        "shadows": 0.42,
        "highlights": 0.48,
        "hdr_local": 0.32,
        "vibrance": 0.34,
        "skin_protect": 0.72,
        "shadow_cool": 0.14,
        "highlight_warm": 0.16,
        "texture": 0.18,
        "clarity": 0.16,
        "vignette": 0.08,
        "grain": 0.06,
        "black_lift": 0.13,
        "natural": 0.35,
        "auto_wb": 0.40,
        "phone_sharpen": 0.35,
        "noise_smear": 0.30,
        "compression": 0.65,
        "lens": 0.15,
        "resolution": 0.00,
        "clip": 0.00,
    },
    "Samsung Galaxy": {
        "wb_temperature": -0.18,
        "wb_tint": 0.02,
        "exposure": 0.14,
        "contrast": 0.16,
        "shadows": 0.55,
        "highlights": 0.55,
        "hdr_local": 0.48,
        "vibrance": 0.48,
        "skin_protect": 0.70,
        "shadow_cool": 0.10,
        "highlight_warm": 0.02,
        "texture": 0.14,
        "clarity": 0.22,
        "vignette": 0.04,
        "grain": 0.03,
        "black_lift": 0.06,
        "natural": 0.30,
        "auto_wb": 0.55,
        "phone_sharpen": 0.45,
        "noise_smear": 0.35,
        "compression": 0.00,
        "lens": 0.10,
        "resolution": 0.00,
        "clip": 0.00,
    },
    "2000s Digicam": {
        "wb_temperature": -0.15,
        "wb_tint": -0.04,
        "exposure": 0.22,
        "contrast": 0.20,
        "shadows": 0.05,
        "highlights": 0.00,
        "hdr_local": 0.00,
        "vibrance": 0.25,
        "skin_protect": 0.40,
        "shadow_cool": 0.15,
        "highlight_warm": 0.00,
        "texture": 0.10,
        "clarity": 0.05,
        "vignette": 0.10,
        "grain": 0.15,
        "black_lift": 0.00,
        "natural": 0.30,
        "auto_wb": 0.00,
        "phone_sharpen": 0.55,
        "noise_smear": 0.20,
        "compression": 0.55,
        "lens": 0.55,
        "resolution": 0.35,
        "clip": 0.60,
    },
    "Early Phone": {
        "wb_temperature": 0.22,
        "wb_tint": -0.06,
        "exposure": 0.06,
        "contrast": 0.06,
        "shadows": 0.10,
        "highlights": 0.10,
        "hdr_local": 0.00,
        "vibrance": -0.10,
        "skin_protect": 0.50,
        "shadow_cool": 0.00,
        "highlight_warm": 0.15,
        "texture": -0.20,
        "clarity": -0.15,
        "vignette": 0.25,
        "grain": 0.35,
        "black_lift": 0.08,
        "natural": 0.30,
        "auto_wb": 0.00,
        "phone_sharpen": 0.35,
        "noise_smear": 0.70,
        "compression": 0.45,
        "lens": 0.70,
        "resolution": 0.50,
        "clip": 0.45,
    },
    "Webcam": {
        "wb_temperature": -0.05,
        "wb_tint": -0.18,
        "exposure": 0.12,
        "contrast": -0.05,
        "shadows": 0.20,
        "highlights": 0.00,
        "hdr_local": 0.00,
        "vibrance": -0.35,
        "skin_protect": 0.40,
        "shadow_cool": 0.00,
        "highlight_warm": 0.00,
        "texture": -0.10,
        "clarity": -0.10,
        "vignette": 0.20,
        "grain": 0.45,
        "black_lift": 0.12,
        "natural": 0.30,
        "auto_wb": 0.00,
        "phone_sharpen": 0.25,
        "noise_smear": 0.55,
        "compression": 0.80,
        "lens": 0.40,
        "resolution": 0.85,
        "clip": 0.35,
    },
    "2012 Filter": {
        "wb_temperature": 0.15,
        "wb_tint": 0.03,
        "exposure": 0.06,
        "contrast": -0.10,
        "shadows": 0.35,
        "highlights": 0.30,
        "hdr_local": 0.10,
        "vibrance": 0.05,
        "skin_protect": 0.65,
        "shadow_cool": 0.45,
        "highlight_warm": 0.40,
        "texture": 0.08,
        "clarity": 0.10,
        "vignette": 0.45,
        "grain": 0.12,
        "black_lift": 0.80,
        "natural": 0.30,
        "auto_wb": 0.20,
        "phone_sharpen": 0.10,
        "noise_smear": 0.10,
        "compression": 0.25,
        "lens": 0.10,
        "resolution": 0.20,
        "clip": 0.00,
    },
    "Nikon Z7 II": {
        "wb_temperature": -0.04,
        "wb_tint": 0.00,
        "exposure": 0.02,
        "contrast": 0.18,
        "shadows": 0.22,
        "highlights": 0.38,
        "hdr_local": 0.14,
        "vibrance": 0.08,
        "skin_protect": 0.70,
        "shadow_cool": 0.12,
        "highlight_warm": 0.06,
        "texture": 0.20,
        "clarity": 0.18,
        "vignette": 0.10,
        "grain": 0.05,
        "black_lift": 0.00,
        "natural": 0.00,
        "auto_wb": 0.00,
        "phone_sharpen": 0.00,
        "noise_smear": 0.00,
        "compression": 0.00,
        "lens": 0.00,
        "resolution": 0.00,
        "clip": 0.00,
    },
    "Canon R5": {
        "wb_temperature": 0.14,
        "wb_tint": -0.04,
        "exposure": 0.05,
        "contrast": 0.14,
        "shadows": 0.32,
        "highlights": 0.42,
        "hdr_local": 0.20,
        "vibrance": 0.20,
        "skin_protect": 0.68,
        "shadow_cool": 0.06,
        "highlight_warm": 0.18,
        "texture": 0.16,
        "clarity": 0.14,
        "vignette": 0.08,
        "grain": 0.05,
        "black_lift": 0.00,
        "natural": 0.00,
        "auto_wb": 0.00,
        "phone_sharpen": 0.00,
        "noise_smear": 0.00,
        "compression": 0.00,
        "lens": 0.00,
        "resolution": 0.00,
        "clip": 0.00,
    },
}

PRESET_NAMES = list(PRESETS.keys()) + ["Custom"]  # Custom = your own sliders (moving one switches to it)


def _srgb_to_lin(x):
    a = 0.055
    return np.where(x <= 0.04045, x / 12.92, ((x + a) / (1 + a)) ** 2.4).astype(np.float32)


def _lin_to_srgb(x):
    a = 0.055
    x = np.clip(x, 0, None)
    return np.where(x <= 0.0031308, x * 12.92, (1 + a) * np.power(x, 1 / 2.4) - a).astype(np.float32)


def _luma(lin):
    return (0.2126 * lin[..., 0] + 0.7152 * lin[..., 1] + 0.0722 * lin[..., 2]).astype(np.float32)


def _box_blur(ch, r):
    """Separable box blur; output shape always matches input (HxW)."""
    r = int(max(r, 0))
    if r < 1:
        return ch.astype(np.float32)
    # repeat the edge pixels instead of padding with black: zeros used to darken a band along every border
    k = 2 * r + 1
    x = np.pad(ch.astype(np.float64), ((0, 0), (r, r)), mode="edge")
    c = np.concatenate([np.zeros((x.shape[0], 1)), np.cumsum(x, axis=1)], axis=1)
    h = (c[:, k:] - c[:, :-k]) / k
    y = np.pad(h, ((r, r), (0, 0)), mode="edge")
    c = np.concatenate([np.zeros((1, y.shape[1])), np.cumsum(y, axis=0)], axis=0)
    v = (c[k:, :] - c[:-k, :]) / k
    return v.astype(np.float32)


def _skin_w(rgb):
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    d = mx - mn + 1e-6
    h = np.zeros_like(r)
    m = d > 1e-5
    mr = m & (mx == r)
    mg = m & (mx == g) & ~mr
    mb = m & ~mr & ~mg
    h[mr] = 60 * (((g[mr] - b[mr]) / d[mr]) % 6)
    h[mg] = 60 * ((b[mg] - r[mg]) / d[mg] + 2)
    h[mb] = 60 * ((r[mb] - g[mb]) / d[mb] + 4)
    s = d / (mx + 1e-6)
    center, half = 25.0, 30.0
    dh = np.abs(((h - center + 180) % 360) - 180)
    hue_w = np.clip(1.0 - dh / half, 0, 1)
    sat_w = np.clip((s - 0.05) / 0.3, 0, 1) * np.clip((0.7 - s) / 0.25, 0, 1)
    val_w = np.clip((mx - 0.1) / 0.3, 0, 1)
    return (hue_w * sat_w * val_w).astype(np.float32)


# ---------------------------------------------------------------------------
# Phone stages (2026-11): what makes a picture read as "shot on a phone". All 0 = off.
# ---------------------------------------------------------------------------
def _natural(rgb, amount, seed):
    """LC Natural Look's de-AI part (loud colours, orange skin, glossy glow, fine texture), without its highlight
    rolloff and grain: the phone stages after it do those."""
    import torch
    from .lc_natural_look import natural_look
    x = torch.from_numpy(np.ascontiguousarray(rgb, dtype=np.float32))[None]
    return natural_look(x, float(amount), 0.75, int(seed), rolloff=False, grain=False)[0].numpy().astype(np.float32)


def _lens(rgb, amount):
    """A wide phone lens: corners a little soft, a hint of colour fringing toward the edges (red and blue scaled
    apart around the center). Phones correct most of it, so even 1 stays mild."""
    import cv2
    h, w = rgb.shape[:2]
    side = min(h, w)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    r2 = (((xx - (w - 1) / 2) / ((w - 1) / 2)) ** 2 + ((yy - (h - 1) / 2) / ((h - 1) / 2)) ** 2) / 2.0  # corner = 1
    out = rgb.copy()
    s = 0.0012 * amount  # fringe: red out, blue in, by up to 0.12 % of the frame
    for c, k in ((0, 1.0 + s), (2, 1.0 - s)):
        m = np.float32([[k, 0, (1 - k) * (w - 1) / 2], [0, k, (1 - k) * (h - 1) / 2]])
        out[..., c] = cv2.warpAffine(np.ascontiguousarray(rgb[..., c]), m, (w, h), flags=cv2.INTER_LINEAR,
                                     borderMode=cv2.BORDER_REFLECT)
    sigma = max(0.5, side / 900.0) * 1.6 * amount
    soft = cv2.GaussianBlur(out, (0, 0), sigma)
    wgt = np.clip(r2 * 1.4 - 0.25, 0, 1)[..., None] ** 1.5  # sharp center, soft corners
    return (out * (1 - wgt) + soft * wgt).astype(np.float32)


def _auto_wb(lin, amount):
    """Phone auto white balance: shades-of-gray estimate of the light's colour (p = 6, Finlayson) from the well-exposed
    pixels, neutralized by luminance-kept channel gains. Capped so a deliberate colour (sunset, neon) only bends."""
    y = _luma(lin)
    m = (y > 0.02) & (y < 0.9)
    if int(m.sum()) < 64:
        return lin
    px = lin[m]
    e = np.power(np.mean(np.power(np.clip(px, 1e-6, None), 6.0), axis=0), 1.0 / 6.0)
    gains = np.clip(e.mean() / np.maximum(e, 1e-6), 0.8, 1.25)
    gains = gains / float(gains @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32))
    return (lin * (1.0 + (gains - 1.0) * float(amount))).astype(np.float32)


def _noise_smear(rgb, amount):
    """Phone noise reduction in the dark areas: edge-aware smoothing that wipes fine texture out of the shadows (the
    'watercolor' look of a phone picture taken indoors), stronger the darker it gets."""
    import torch
    from .lc_guided import guided
    h, w = rgb.shape[:2]
    y = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
    t = torch.from_numpy(np.ascontiguousarray(rgb, dtype=np.float32)).permute(2, 0, 1)[None]
    g = torch.from_numpy(np.ascontiguousarray(y, dtype=np.float32))[None, None]
    r = max(2, int(min(h, w) / 450))
    sm = guided(g, t, r, 4e-4)[0].permute(1, 2, 0).numpy()
    dark = np.clip(1.0 - (y - 0.08) / 0.32, 0, 1) ** 1.5
    wgt = np.clip(dark * float(amount) * 1.2, 0, 1)[..., None]
    return (rgb * (1 - wgt) + sm * wgt).astype(np.float32)


def _phone_sharpen(rgb, amount):
    """The phone's own sharpening: a small-radius unsharp mask on brightness with the faint bright halo phones leave,
    strongest on edges, light on smooth areas like skin."""
    import cv2
    h, w = rgb.shape[:2]
    y = (0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]).astype(np.float32)
    sigma = max(0.8, min(h, w) / 1100.0)
    d = y - cv2.GaussianBlur(y, (0, 0), sigma)
    gx = cv2.Sobel(y, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(y, cv2.CV_32F, 0, 1, ksize=3)
    edge = np.clip((np.sqrt(gx * gx + gy * gy) - 0.04) / 0.20, 0, 1)
    edge = cv2.GaussianBlur(edge, (0, 0), sigma)
    y2 = y + d * float(amount) * 1.6 * (0.25 + 0.75 * edge)
    ratio = np.clip((y2 + 1e-4) / (y + 1e-4), 0.6, 1.6)
    return np.clip(rgb * ratio[..., None], 0, 1).astype(np.float32)


def _compression(rgb, amount):
    """A JPEG save: 0.3 is a typical phone file, 1 a picture re-shared through social media (blocking, mushy colour)."""
    import cv2
    q = int(round(95 - 75 * float(amount)))
    bgr = np.ascontiguousarray((np.clip(rgb[..., ::-1], 0, 1) * 255.0 + 0.5).astype(np.uint8))
    ok, buf = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, q])
    if not ok:
        return rgb
    return np.ascontiguousarray(cv2.imdecode(buf, cv2.IMREAD_COLOR)[..., ::-1]).astype(np.float32) / 255.0


def _process_frame(
    img,
    wb_temperature,
    wb_tint,
    exposure,
    contrast,
    shadows,
    highlights,
    hdr_local,
    vibrance,
    skin_protect,
    shadow_cool,
    highlight_warm,
    texture,
    clarity,
    vignette,
    grain,
    seed,
    black_lift=0.0,
    natural=0.0,
    auto_wb=0.0,
    phone_sharpen=0.0,
    noise_smear=0.0,
    compression=0.0,
    lens=0.0,
    resolution=0.0,
    clip=0.0,
):
    h, w = img.shape[:2]
    rgb = np.clip(img.astype(np.float32), 0, 1)
    # the order of a phone: the render's AI tells out first, then the lens, then the camera's processing
    if natural > 1e-5:
        rgb = np.clip(_natural(rgb, natural, seed), 0, 1)
    if lens > 1e-5:
        rgb = np.clip(_lens(rgb, float(np.clip(lens, 0, 1))), 0, 1)
    lin = _srgb_to_lin(rgb)
    if auto_wb > 1e-5:
        lin = _auto_wb(lin, float(np.clip(auto_wb, 0, 1)))

    # --- WB (0 = no change) ---
    temp = float(np.clip(wb_temperature, -1, 1))
    tint = float(np.clip(wb_tint, -1, 1))
    if abs(temp) > 1e-5 or abs(tint) > 1e-5:
        gains = np.array(
            [
                1.0 + 0.22 * temp + 0.06 * tint,  # positive tint = magenta (less green), negative = green
                1.0 - 0.05 * tint,
                1.0 - 0.26 * temp + 0.04 * tint,
            ],
            dtype=np.float32,
        )
        gains = np.clip(gains, 0.55, 1.6)
        y0 = float(_luma(lin).mean())
        lin = lin * gains
        y1 = float(_luma(lin).mean())
        lin = lin * ((y0 + 1e-5) / (y1 + 1e-5))

    # --- Exposure (0 = no change) ---
    exp = float(np.clip(exposure, -0.5, 0.5))
    if abs(exp) > 1e-5:
        lin = lin * (2.0 ** exp)

    # --- Contrast (0 = no change; + punches, - flattens) ---
    c = float(np.clip(contrast, -1, 1))
    if abs(c) > 1e-5:
        y = _luma(lin)
        # map [-1,1] → pivot scale
        scale = 1.0 + 0.85 * c
        y2 = 0.18 + (y - 0.18) * scale
        ratio = np.clip((y2 + 1e-5) / (y + 1e-5), 0.4, 2.5)
        lin = lin * ratio[..., None]

    # --- Shadows (0 = no change). Lift DARKS only — multiplicative, no white haze ---
    sh = float(np.clip(shadows, 0, 1))
    if sh > 1e-5:
        y = np.clip(_luma(lin), 0, None)
        # Strong only in deep shadows; zero by midtones
        mask = np.clip(1.0 - y / 0.32, 0, 1) ** 2.2
        # Lift luma, keep chromatic ratios (no additive gray)
        y_new = y * (1.0 + sh * 0.85 * mask) + sh * 0.04 * mask
        ratio = np.clip((y_new + 1e-5) / (y + 1e-5), 1.0, 2.2)
        # Only apply where mask is active
        ratio = 1.0 + (ratio - 1.0) * mask
        lin = lin * ratio[..., None]

    # --- Highlights (0 = no change). Soft compress brights ---
    hi = float(np.clip(highlights, 0, 1))
    if hi > 1e-5:
        # Reinhard soft knee on luma, applied as a ratio so colour stays put. Monotonic: a brighter pixel always stays
        # brighter (the old t^2 squeeze turned 1.0 darker than 0.85 at full strength), and it rolls toward 1, never clips.
        y = np.clip(_luma(lin), 0, None)
        k = 1.0 - 0.45 * hi  # knee starts at 0.55 at full strength, as before
        t = np.maximum(y - k, 0.0) / (1.0 - k)
        y_new = np.where(y > k, k + (1.0 - k) * t / (1.0 + t), y)
        lin = lin * ((y_new + 1e-6) / (y + 1e-6))[..., None]

    # --- Clip (0 = off): an old sensor's blown highlights, pushed up and cut hard at white instead of rolled off ---
    cl = float(np.clip(clip, 0, 1))
    if cl > 1e-5:
        k = 0.78 - 0.30 * cl  # where the push starts (in linear light)
        lin = np.where(lin > k, k + (lin - k) * (1.0 + 3.0 * cl), lin)
        lin = np.clip(lin, 0, 1)

    # --- Local HDR (0 = off) ---
    hl = float(np.clip(hdr_local, 0, 1))
    if hl > 1e-5:
        # Durand-style local tone mapping (after ComfyUI-CameraForensicRealism, re-written): split log brightness into
        # a broad base and the detail on top, compress only the base around its mean (local shadows up, local
        # highlights down) and pass the detail through untouched, so texture never flattens. The base comes from
        # an edge-aware guided filter, so bright edges do not grow halos; its reach scales with the frame.
        import torch
        from .lc_guided import guided
        y = np.maximum(_luma(lin), 1e-6)
        ly = torch.from_numpy(np.log2(y).astype(np.float32))[None, None]
        r = max(4, int(min(h, w) * 0.05))
        base = guided(ly, ly, r, 0.5)[0, 0].numpy()
        detail = np.log2(y) - base
        mean = float(base.mean())
        new_log = mean + (base - mean) * (1.0 - 0.45 * hl) + detail
        y_new = np.exp2(new_log)
        y_new *= float(y.mean()) / max(1e-6, float(y_new.mean()))  # same overall brightness: the presets were tuned on it
        ratio = np.clip(y_new / y, 0.35, 2.8)
        lin = lin * ratio[..., None]

    lin = np.clip(lin, 0, 1.25)
    rgb = np.clip(_lin_to_srgb(np.clip(lin, 0, 1)), 0, 1)

    # --- Vibrance (0 = no change; negative desaturates muted colors) ---
    vib = float(np.clip(vibrance, -1, 1))
    if abs(vib) > 1e-5:
        # chroma scaled in Oklab (hue-safe, Oklab skin detection, gamut-mapped instead of clipped)
        from .lc_oklab import vibrance_signed
        rgb = vibrance_signed(rgb, vib, float(np.clip(skin_protect, 0, 1)))

    # --- Split tone (0 = off); skip pure blacks ---
    y = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
    sc = float(np.clip(shadow_cool, 0, 1))
    hw = float(np.clip(highlight_warm, 0, 1))
    if sc > 1e-5 or hw > 1e-5:
        gate = np.clip((y - 0.07) / 0.14, 0, 1)
        sh_m = ((1.0 - np.clip(y / 0.5, 0, 1)) ** 2) * gate
        hi_m = (np.clip((y - 0.55) / 0.45, 0, 1) ** 2) * gate
        cool = np.array([0.93, 0.98, 1.08], dtype=np.float32)
        warm = np.array([1.08, 1.02, 0.93], dtype=np.float32)
        rgb = rgb * (1.0 + sc * 0.85 * sh_m[..., None] * (cool - 1.0))
        rgb = rgb * (1.0 + hw * 0.85 * hi_m[..., None] * (warm - 1.0))
        rgb = np.clip(rgb, 0, 1)

    # --- Noise reduction smear in the darks (0 = off), before any sharpening, as in a phone ---
    if noise_smear > 1e-5:
        rgb = np.clip(_noise_smear(rgb, float(np.clip(noise_smear, 0, 1))), 0, 1)

    # --- Texture / clarity (0 = no change; can go negative to soften) ---
    tex = float(np.clip(texture, -1, 1)) * 0.7
    cla = float(np.clip(clarity, -1, 1)) * 0.7
    if abs(tex) > 1e-5 or abs(cla) > 1e-5:
        y = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
        yf = _box_blur(y, 1)
        fine = 0.2 * np.tanh((y - yf) / 0.2)  # soft limit (tanh) instead of a hard clip: big edges roll off, no halo step
        mid_r = max(2, min(18, int(min(h, w) * 0.015)))
        ym = _box_blur(y, mid_r)
        mid = 0.25 * np.tanh((y - ym) / 0.25)
        y2 = y + tex * fine + cla * mid
        ratio = np.clip((y2 + 1e-5) / (y + 1e-5), 0.75, 1.3)
        rgb = np.clip(rgb * ratio[..., None], 0, 1)

    # --- Phone sharpening, with its faint halo (0 = off) ---
    if phone_sharpen > 1e-5:
        rgb = _phone_sharpen(rgb, float(np.clip(phone_sharpen, 0, 1)))

    # --- Vignette (0 = off) ---
    vig = float(np.clip(vignette, 0, 1))
    if vig > 1e-5:
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        cy, cx = (h - 1) / 2.0, (w - 1) / 2.0
        ny = (yy - cy) / max(cy, 1.0)
        nx = (xx - cx) / max(cx, 1.0)
        r2 = nx * nx + ny * ny
        fall = 1.0 / (1.0 + 0.75 * r2) ** 2
        mask = np.clip(1.0 - vig * 0.9 * (1.0 - fall), 0.3, 1.0)
        rgb = rgb * mask[..., None]

    # --- Grain (0 = off): phone sensor noise, the same model as LC Film Grain's "sensor" response. Phones clean up
    # most of the colour speckle, so it is mostly brightness noise with a little colour.
    gr = float(np.clip(grain, 0, 1))
    if gr > 1e-5:
        import torch

        from .lc_grain import sensor_noise

        rng = np.random.default_rng((int(seed) + h * 17 + w * 31) & 0xFFFFFFFF)
        mono = rng.normal(0.0, 1.0, (h, w, 1)).astype(np.float32)
        chroma = rng.normal(0.0, 1.0, (h, w, 3)).astype(np.float32)
        noise = (0.8 * mono + 0.2 * chroma) / 0.8246
        rgb = sensor_noise(torch.from_numpy(np.ascontiguousarray(rgb, dtype=np.float32)), torch.from_numpy(noise),
                           gr * 0.105).numpy()

    # Neutralize deep blacks
    y = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
    blk = np.clip(1.0 - y / 0.1, 0, 1) ** 1.6
    if float(blk.max()) > 1e-4:
        gray = np.clip(y, 0, 1)[..., None]
        rgb = rgb * (1.0 - blk[..., None]) + gray * blk[..., None]

    # --- Black lift (0 = off): phones never crush black, the darkest tone sits a little above 0 (faded, matte blacks)
    bl = float(np.clip(black_lift, 0, 1))
    if bl > 1e-5:
        lift = 0.12 * bl  # 1 = the faded matte black of a 2012 filter; a phone's own lift is about 0.13
        rgb = lift + (1.0 - lift) * rgb

    rgb = np.nan_to_num(rgb, nan=0.0, posinf=1.0, neginf=0.0)
    rgb = np.clip(rgb, 0, 1).astype(np.float32)

    # --- Resolution (0 = off): the small sensor of an older camera. The picture is made at that size and scaled back
    # up softly; a JPEG save happens at the small size, so its blocks grow with it, the way an old file looks today.
    res = float(np.clip(resolution, 0, 1))
    small = None
    if res > 1e-5:
        import cv2
        mp = h * w
        target = mp ** (1.0 - res) * 300_000.0 ** res  # 1 = about 0.3 MP (a 2005 webcam)
        s = min(1.0, (target / mp) ** 0.5)
        if s < 0.999:
            small = cv2.resize(rgb, (max(16, int(w * s)), max(16, int(h * s))), interpolation=cv2.INTER_AREA)

    # --- Saved as a JPEG (0 = off), last, like the file the phone writes ---
    if small is not None:
        import cv2
        if compression > 1e-5:
            small = _compression(small, float(np.clip(compression, 0, 1)))
        rgb = np.clip(cv2.resize(small, (w, h), interpolation=cv2.INTER_CUBIC), 0, 1).astype(np.float32)
    elif compression > 1e-5:
        rgb = _compression(rgb, float(np.clip(compression, 0, 1)))
    return rgb


class LCPhoneLook(PreviewImage):
    @classmethod
    def INPUT_TYPES(cls):
        d = PRESETS["Standard"]
        return {
            "required": {
                "image": ("IMAGE",),
                "style": (
                    PRESET_NAMES,
                    {
                        "default": "Standard",
                        "tooltip": "Starting preset. Moving a slider switches to Custom. 0 on a control = no change from that stage.",
                    },
                ),
                "strength": (
                    "FLOAT",
                    {
                        "default": 0.85,
                        "min": 0.0,
                        "max": 1.0,
                        "step": 0.05,
                        "tooltip": "0 = original image, 1 = full processed look.",
                    },
                ),
                "seed": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 0xFFFFFFFFFFFFFFFF,
                        "tooltip": "Grain seed only.",
                    },
                ),
                "wb_temperature": (
                    "FLOAT",
                    {
                        "default": d["wb_temperature"],
                        "min": -1.0,
                        "max": 1.0,
                        "step": 0.01,
                        "tooltip": "0 = no WB change. Negative = cooler, positive = warmer.",
                    },
                ),
                "wb_tint": (
                    "FLOAT",
                    {
                        "default": d["wb_tint"],
                        "min": -1.0,
                        "max": 1.0,
                        "step": 0.01,
                        "tooltip": "0 = no tint. Negative = green, positive = magenta.",
                    },
                ),
                "exposure": (
                    "FLOAT",
                    {
                        "default": d["exposure"],
                        "min": -0.5,
                        "max": 0.5,
                        "step": 0.01,
                        "tooltip": "0 = no exposure change (EV).",
                    },
                ),
                "contrast": (
                    "FLOAT",
                    {
                        "default": d["contrast"],
                        "min": -1.0,
                        "max": 1.0,
                        "step": 0.01,
                        "tooltip": "0 = no contrast change. Positive punches midtones, negative flattens.",
                    },
                ),
                "shadows": (
                    "FLOAT",
                    {
                        "default": d["shadows"],
                        "min": 0.0,
                        "max": 1.0,
                        "step": 0.01,
                        "tooltip": "0 = no change. Lifts dark areas only (keeps color, no white haze).",
                    },
                ),
                "highlights": (
                    "FLOAT",
                    {
                        "default": d["highlights"],
                        "min": 0.0,
                        "max": 1.0,
                        "step": 0.01,
                        "tooltip": "0 = no change. Softly compresses bright areas.",
                    },
                ),
                "hdr_local": (
                    "FLOAT",
                    {
                        "default": d["hdr_local"],
                        "min": 0.0,
                        "max": 1.0,
                        "step": 0.01,
                        "tooltip": "0 = off. Mild local tone (open shadows / tame local contrast).",
                    },
                ),
                "vibrance": (
                    "FLOAT",
                    {
                        "default": d["vibrance"],
                        "min": -1.0,
                        "max": 1.0,
                        "step": 0.01,
                        "tooltip": "0 = no change. Positive boosts muted colors; negative pulls them down.",
                    },
                ),
                "skin_protect": (
                    "FLOAT",
                    {
                        "default": d["skin_protect"],
                        "min": 0.0,
                        "max": 1.0,
                        "step": 0.01,
                        "tooltip": "Limits vibrance on skin hues (only matters when vibrance ≠ 0).",
                    },
                ),
                "shadow_cool": (
                    "FLOAT",
                    {
                        "default": d["shadow_cool"],
                        "min": 0.0,
                        "max": 1.0,
                        "step": 0.01,
                        "tooltip": "0 = off. Cool (blue) tint in mid-shadows — skips pure black.",
                    },
                ),
                "highlight_warm": (
                    "FLOAT",
                    {
                        "default": d["highlight_warm"],
                        "min": 0.0,
                        "max": 1.0,
                        "step": 0.01,
                        "tooltip": "0 = off. Warm tint in highlights.",
                    },
                ),
                "texture": (
                    "FLOAT",
                    {
                        "default": d["texture"],
                        "min": -1.0,
                        "max": 1.0,
                        "step": 0.01,
                        "tooltip": "0 = no change. Fine detail; negative softens.",
                    },
                ),
                "clarity": (
                    "FLOAT",
                    {
                        "default": d["clarity"],
                        "min": -1.0,
                        "max": 1.0,
                        "step": 0.01,
                        "tooltip": "0 = no change. Mid-scale local contrast; negative softens.",
                    },
                ),
                "vignette": (
                    "FLOAT",
                    {
                        "default": d["vignette"],
                        "min": 0.0,
                        "max": 1.0,
                        "step": 0.01,
                        "tooltip": "0 = off. Corner falloff.",
                    },
                ),
                "grain": (
                    "FLOAT",
                    {
                        "default": d["grain"],
                        "min": 0.0,
                        "max": 1.0,
                        "step": 0.01,
                        "tooltip": "0 = off. Phone camera noise (the same as LC Film Grain's sensor response): strongest in the shadows, mostly brightness with a little colour speckle.",
                    },
                ),
            },
            "optional": {
                "black_lift": (
                    "FLOAT",
                    {
                        "default": 0.0,
                        "min": 0.0,
                        "max": 1.0,
                        "step": 0.01,
                        "tooltip": "0 = off. Lifts the black point a little: phones never crush black, so the darkest tones read as a soft matte gray. About 0.13 for a phone; up to 1 for the faded matte black of a 2012 filter.",
                    },
                ),
                "natural": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0, "step": 0.01,
                                      "tooltip": "0 = off. Takes the AI look out first (LC Natural Look's pass): loud colors pulled back, orange skin calmed, the glossy glow toned down, fine texture lifted. 0.3 to 0.5 for most renders."}),
                "auto_wb": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0, "step": 0.01,
                                      "tooltip": "0 = off. Phone auto white balance: finds the picture's color cast and neutralizes it before the style's own warmth. 1 = full correction; a sunset or neon light only bends, it is not removed."}),
                "phone_sharpen": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0, "step": 0.01,
                                            "tooltip": "0 = off. The phone's own sharpening: crisp edges with the faint bright halo phones leave, light on skin. Texture is the halo-free fine detail; this is the phone tell."}),
                "noise_smear": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0, "step": 0.01,
                                          "tooltip": "0 = off. Phone noise reduction in the dark areas: the slight watercolor smoothing that wipes fine texture out of the shadows. Stronger the darker it gets."}),
                "compression": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0, "step": 0.01,
                                          "tooltip": "0 = off. Saved as a JPEG at the end: 0.3 is a typical phone file, 1 a picture re-shared through social media (blocking, mushy color)."}),
                "lens": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0, "step": 0.01,
                                   "tooltip": "0 = off. A wide phone lens: corners a little soft and a hint of color fringing toward the edges. Phones correct most of it, so it stays mild."}),
                "resolution": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0, "step": 0.01,
                                         "tooltip": "0 = off. The small sensor of an older camera: the picture is made at that size and scaled back up soft. 0.35 is a 2000s digicam, 1 a 2005 webcam (about 0.3 MP). With compression on, the JPEG blocks grow with it."}),
                "clip": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0, "step": 0.01,
                                   "tooltip": "0 = off. Blown highlights the way old sensors did it: bright areas pushed up and cut hard at white, no soft rolloff. Use with highlights low."}),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "run"
    CATEGORY = "LC123/image"
    OUTPUT_NODE = True
    DESCRIPTION = (
        "Phone and camera looks in one node, for simple workflows: iPhone, Samsung, selfie, shared, camera bodies and "
        "retro cameras (digicam, early phone, webcam, 2012 filter). Style fills the sliders; 0 = no change on a "
        "control. Strength blends with the original."
    )

    @_alpha_safe
    def run(
        self,
        image,
        style="Standard",
        strength=0.85,
        seed=0,
        wb_temperature=0.0,
        wb_tint=0.0,
        exposure=0.0,
        contrast=0.0,
        shadows=0.0,
        highlights=0.0,
        hdr_local=0.0,
        vibrance=0.0,
        skin_protect=0.65,
        shadow_cool=0.0,
        highlight_warm=0.0,
        texture=0.0,
        clarity=0.0,
        vignette=0.0,
        grain=0.0,
        black_lift=0.0,
        natural=0.0,
        auto_wb=0.0,
        phone_sharpen=0.0,
        noise_smear=0.0,
        compression=0.0,
        lens=0.0,
        resolution=0.0,
        clip=0.0,
    ):
        if strength <= 0:
            return _preview(self, image, image)
        phone = dict(natural=natural, auto_wb=auto_wb, phone_sharpen=phone_sharpen, noise_smear=noise_smear,
                     compression=compression, lens=lens, resolution=resolution, clip=clip)

        # All zeros → identity (fast path)
        near_zero = (
            abs(wb_temperature) < 1e-5
            and abs(wb_tint) < 1e-5
            and abs(exposure) < 1e-5
            and abs(contrast) < 1e-5
            and shadows < 1e-5
            and highlights < 1e-5
            and hdr_local < 1e-5
            and abs(vibrance) < 1e-5
            and shadow_cool < 1e-5
            and highlight_warm < 1e-5
            and abs(texture) < 1e-5
            and abs(clarity) < 1e-5
            and vignette < 1e-5
            and grain < 1e-5
            and black_lift < 1e-5
            and all(v < 1e-5 for v in phone.values())
        )
        if near_zero:
            return _preview(self, image, image)

        arrays = tensor_to_np(image)
        out = []
        for i, frame in enumerate(arrays):
            graded = _process_frame(
                frame,
                wb_temperature,
                wb_tint,
                exposure,
                contrast,
                shadows,
                highlights,
                hdr_local,
                vibrance,
                skin_protect,
                shadow_cool,
                highlight_warm,
                texture,
                clarity,
                vignette,
                grain,
                int(seed) + i * 997,
                black_lift,
                **phone,
            )
            if strength < 1.0:
                graded = blend(frame, graded, float(strength))
            out.append(graded)
        return _preview(self, np_to_tensor(out), image)


NODE_CLASS_MAPPINGS = {
    "LCPhoneLook": LCPhoneLook,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LCPhoneLook": "LC Photo Style 📷",
}
