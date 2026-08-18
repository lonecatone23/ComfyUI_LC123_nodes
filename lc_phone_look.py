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
    from .lc_image_helpers import tensor_to_np, np_to_tensor, blend
except ImportError:
    from lc_image_helpers import tensor_to_np, np_to_tensor, blend

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
    },
    "Quiet": {
        "wb_temperature": -0.10,
        "wb_tint": -0.04,
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
    },
    "Amateur": {
        "wb_temperature": 0.22,
        "wb_tint": 0.08,
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
    },
    "Cool day": {
        "wb_temperature": -0.35,
        "wb_tint": -0.12,
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
    },
    "Warm evening": {
        "wb_temperature": 0.40,
        "wb_tint": 0.08,
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
    },
    "Bright open": {
        "wb_temperature": -0.02,
        "wb_tint": 0.19,
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
    },
    "iPhone": {
        "wb_temperature": 0.10,
        "wb_tint": 0.02,
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
    },
    "Canon R5": {
        "wb_temperature": 0.14,
        "wb_tint": 0.04,
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
    },
}

PRESETS["Custom"] = None
PRESET_NAMES = list(PRESETS.keys())


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
    ker = np.ones(2 * r + 1, dtype=np.float64) / float(2 * r + 1)
    h = np.apply_along_axis(lambda m: np.convolve(m, ker, mode="same"), axis=1, arr=ch.astype(np.float64))
    v = np.apply_along_axis(lambda m: np.convolve(m, ker, mode="same"), axis=0, arr=h)
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
):
    h, w = img.shape[:2]
    rgb = np.clip(img.astype(np.float32), 0, 1)
    lin = _srgb_to_lin(rgb)

    # --- WB (0 = no change) ---
    temp = float(np.clip(wb_temperature, -1, 1))
    tint = float(np.clip(wb_tint, -1, 1))
    if abs(temp) > 1e-5 or abs(tint) > 1e-5:
        gains = np.array(
            [
                1.0 + 0.22 * temp - 0.06 * tint,
                1.0 + 0.05 * tint,
                1.0 - 0.26 * temp - 0.04 * tint,
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
        y = np.clip(_luma(lin), 0, None)
        t = np.clip((y - 0.55) / 0.45, 0, 1)
        compress = (t * t) * hi * 0.40
        lin = lin * (1.0 - compress[..., None])

    # --- Local HDR (0 = off) ---
    hl = float(np.clip(hdr_local, 0, 1))
    if hl > 1e-5:
        y = np.clip(_luma(lin), 0, None)
        r = max(2, min(28, int(min(h, w) * 0.028)))
        yb = _box_blur(y, r)
        detail = y - yb
        y_new = yb + detail * (1.0 - 0.45 * hl)
        # open shadows a touch via local mean
        y_new = y_new + hl * 0.12 * (1.0 - np.clip(yb / 0.4, 0, 1))
        ratio = np.clip((y_new + 1e-5) / (y + 1e-5), 0.65, 1.5)
        lin = lin * ratio[..., None]

    lin = np.clip(lin, 0, 1.25)
    rgb = np.clip(_lin_to_srgb(np.clip(lin, 0, 1)), 0, 1)

    # --- Vibrance (0 = no change; negative desaturates muted colors) ---
    vib = float(np.clip(vibrance, -1, 1))
    if abs(vib) > 1e-5:
        rch, gch, bch = rgb[..., 0], rgb[..., 1], rgb[..., 2]
        mx = np.maximum(np.maximum(rch, gch), bch)
        mn = np.minimum(np.minimum(rch, gch), bch)
        chroma = mx - mn
        weight = (1.0 - np.clip(chroma * 2.0, 0, 1)) * abs(vib) * 0.7
        skin = _skin_w(rgb) * float(np.clip(skin_protect, 0, 1))
        weight = weight * (1.0 - 0.9 * skin)
        mean = rgb.mean(axis=-1, keepdims=True)
        if vib >= 0:
            rgb = mean + (rgb - mean) * (1.0 + weight[..., None])
        else:
            rgb = mean + (rgb - mean) * (1.0 - weight[..., None])
        rgb = np.clip(rgb, 0, 1)

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

    # --- Texture / clarity (0 = no change; can go negative to soften) ---
    tex = float(np.clip(texture, -1, 1)) * 0.7
    cla = float(np.clip(clarity, -1, 1)) * 0.7
    if abs(tex) > 1e-5 or abs(cla) > 1e-5:
        y = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
        yf = _box_blur(y, 1)
        fine = np.clip(y - yf, -0.2, 0.2)
        mid_r = max(2, min(18, int(min(h, w) * 0.015)))
        ym = _box_blur(y, mid_r)
        mid = np.clip(y - ym, -0.25, 0.25)
        y2 = y + tex * fine + cla * mid
        ratio = np.clip((y2 + 1e-5) / (y + 1e-5), 0.75, 1.3)
        rgb = np.clip(rgb * ratio[..., None], 0, 1)

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

    # --- Grain (0 = off), mono ---
    gr = float(np.clip(grain, 0, 1))
    if gr > 1e-5:
        rng = np.random.default_rng((int(seed) + h * 17 + w * 31) & 0xFFFFFFFF)
        mono = rng.normal(0.0, 1.0, (h, w)).astype(np.float32)
        y = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
        wgt = np.clip((y - 0.03) / 0.2, 0.2, 1.0) * (0.45 + 0.55 * (1.0 - np.clip(y, 0, 1)))
        rgb = np.clip(rgb + mono[..., None] * gr * 0.07 * wgt[..., None], 0, 1)

    # Neutralize deep blacks
    y = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
    blk = np.clip(1.0 - y / 0.1, 0, 1) ** 1.6
    if float(blk.max()) > 1e-4:
        gray = np.clip(y, 0, 1)[..., None]
        rgb = rgb * (1.0 - blk[..., None]) + gray * blk[..., None]

    rgb = np.nan_to_num(rgb, nan=0.0, posinf=1.0, neginf=0.0)
    return np.clip(rgb, 0, 1).astype(np.float32)


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
                        "tooltip": "Starting preset. Customize below by moving the sliders. 0 on a control = no change from that stage.",
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
                        "tooltip": "0 = off. Neutral mono grain (stronger in shadows).",
                    },
                ),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "run"
    CATEGORY = "LC123/image"
    OUTPUT_NODE = True
    DESCRIPTION = (
        "Standalone phone-style look. Style fills the sliders; most controls use 0 = no change. "
        "Strength blends with the original. Not a lens geometry tool."
    )

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
    ):
        if strength <= 0:
            return _preview(self, image, image)

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
