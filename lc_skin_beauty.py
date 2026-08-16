"""
LC Skin Beauty — draft
----------------------
Mask-aware skin cooling / brightening in CIELAB.
Inspired by the general approach of open MIT skin-beauty tools (mask + LAB),
implemented independently for LC123.

Presets drive defaults; strength scales the effect. Optional external MASK.
"""

from __future__ import annotations

import numpy as np
from nodes import PreviewImage

from .lc_image_helpers import tensor_to_np, np_to_tensor, blend


# ---------------------------------------------------------------------------
# Presets (amounts are "full strength" at strength=1.0)
# ---------------------------------------------------------------------------
PRESETS = {
    "Natural": {
        "coolness": 0.22,
        "brightness": 0.12,
        "rosy": 0.08,
        "evenness": 0.18,
        "shadow_lift": 0.15,
        "smooth": 0.06,
        "texture_preserve": 0.88,
        "saturation": -0.08,
        "highlight_protect": 0.75,
        "mask_sensitivity": 0.55,
        "mask_feather": 0.45,
    },
    "Light": {
        "coolness": 0.12,
        "brightness": 0.06,
        "rosy": 0.04,
        "evenness": 0.10,
        "shadow_lift": 0.08,
        "smooth": 0.04,
        "texture_preserve": 0.94,
        "saturation": -0.04,
        "highlight_protect": 0.85,
        "mask_sensitivity": 0.50,
        "mask_feather": 0.35,
    },
    "Fresh": {
        "coolness": 0.32,
        "brightness": 0.18,
        "rosy": 0.06,
        "evenness": 0.22,
        "shadow_lift": 0.18,
        "smooth": 0.08,
        "texture_preserve": 0.86,
        "saturation": -0.10,
        "highlight_protect": 0.70,
        "mask_sensitivity": 0.58,
        "mask_feather": 0.50,
    },
    "Porcelain": {
        "coolness": 0.40,
        "brightness": 0.28,
        "rosy": 0.05,
        "evenness": 0.30,
        "shadow_lift": 0.25,
        "smooth": 0.14,
        "texture_preserve": 0.82,
        "saturation": -0.12,
        "highlight_protect": 0.65,
        "mask_sensitivity": 0.60,
        "mask_feather": 0.55,
    },
    "Warm keep": {
        "coolness": 0.08,
        "brightness": 0.10,
        "rosy": 0.18,
        "evenness": 0.25,
        "shadow_lift": 0.16,
        "smooth": 0.08,
        "texture_preserve": 0.90,
        "saturation": -0.04,
        "highlight_protect": 0.80,
        "mask_sensitivity": 0.55,
        "mask_feather": 0.45,
    },
    "Custom": {
        "coolness": 0.25,
        "brightness": 0.15,
        "rosy": 0.08,
        "evenness": 0.20,
        "shadow_lift": 0.15,
        "smooth": 0.08,
        "texture_preserve": 0.88,
        "saturation": -0.06,
        "highlight_protect": 0.75,
        "mask_sensitivity": 0.55,
        "mask_feather": 0.45,
    },
}

PRESET_NAMES = list(PRESETS.keys())


# ---------------------------------------------------------------------------
# Color helpers (numpy, per-pixel HxWx3 float 0-1)
# ---------------------------------------------------------------------------
def _srgb_to_linear(rgb: np.ndarray) -> np.ndarray:
    a = 0.055
    return np.where(
        rgb <= 0.04045, rgb / 12.92, ((rgb + a) / (1.0 + a)) ** 2.4
    ).astype(np.float32)


def _linear_to_srgb(rgb: np.ndarray) -> np.ndarray:
    a = 0.055
    return np.where(
        rgb <= 0.0031308,
        rgb * 12.92,
        (1.0 + a) * np.power(np.clip(rgb, 0, None), 1.0 / 2.4) - a,
    ).astype(np.float32)


def _rgb_to_lab(rgb: np.ndarray) -> np.ndarray:
    """sRGB 0-1 → Lab (L 0-100, a/b roughly -128..127)."""
    lin = _srgb_to_linear(np.clip(rgb, 0, 1))
    # sRGB to XYZ (D65)
    m = np.array(
        [
            [0.4124564, 0.3575761, 0.1804375],
            [0.2126729, 0.7151522, 0.0721750],
            [0.0193339, 0.1191920, 0.9503041],
        ],
        dtype=np.float32,
    )
    xyz = lin @ m.T
    # D65 white
    xyz[..., 0] /= 0.95047
    xyz[..., 1] /= 1.00000
    xyz[..., 2] /= 1.08883

    def f(t):
        delta = 6.0 / 29.0
        return np.where(t > delta**3, np.cbrt(t), t / (3 * delta**2) + 4.0 / 29.0)

    fx, fy, fz = f(xyz[..., 0]), f(xyz[..., 1]), f(xyz[..., 2])
    L = 116.0 * fy - 16.0
    a = 500.0 * (fx - fy)
    b = 200.0 * (fy - fz)
    return np.stack([L, a, b], axis=-1).astype(np.float32)


def _lab_to_rgb(lab: np.ndarray) -> np.ndarray:
    L, a, b = lab[..., 0], lab[..., 1], lab[..., 2]
    fy = (L + 16.0) / 116.0
    fx = fy + a / 500.0
    fz = fy - b / 200.0

    def finv(t):
        delta = 6.0 / 29.0
        return np.where(t > delta, t**3, 3 * delta**2 * (t - 4.0 / 29.0))

    xyz = np.stack([finv(fx) * 0.95047, finv(fy), finv(fz) * 1.08883], axis=-1)
    m_inv = np.array(
        [
            [3.2404542, -1.5371385, -0.4985314],
            [-0.9692660, 1.8760108, 0.0415560],
            [0.0556434, -0.2040259, 1.0572252],
        ],
        dtype=np.float32,
    )
    lin = xyz @ m_inv.T
    return np.clip(_linear_to_srgb(np.clip(lin, 0, None)), 0, 1).astype(np.float32)


def _box_blur(ch: np.ndarray, radius: int) -> np.ndarray:
    """Simple separable box blur; radius in pixels. Exact HxW out."""
    if radius <= 0:
        return ch
    pad = int(radius)
    k = 2 * pad + 1
    h0, w0 = int(ch.shape[0]), int(ch.shape[1])
    src = ch.astype(np.float32)

    # horizontal
    x = np.pad(src, ((0, 0), (pad, pad)), mode="edge")
    c = np.zeros((h0, w0 + 2 * pad + 1), dtype=np.float32)
    c[:, 1:] = np.cumsum(x, axis=1)
    h = (c[:, k : k + w0] - c[:, 0:w0]) / float(k)

    # vertical
    y = np.pad(h, ((pad, pad), (0, 0)), mode="edge")
    c = np.zeros((h0 + 2 * pad + 1, w0), dtype=np.float32)
    c[1:, :] = np.cumsum(y, axis=0)
    v = (c[k : k + h0, :] - c[0:h0, :]) / float(k)
    return v.astype(np.float32)



def _auto_skin_mask(rgb: np.ndarray, sensitivity: float, feather: float = 0.45) -> np.ndarray:
    """
    Skin probability: solid face/body skin, reject busy fabric prints.
    Eyes/lips protected. Pattern kill is mild on smooth regions so face stays full.
    """
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    lab = _rgb_to_lab(rgb)
    L, aa, bb = lab[..., 0], lab[..., 1], lab[..., 2]
    chroma = np.sqrt(aa * aa + bb * bb).astype(np.float32)
    h, w = int(rgb.shape[0]), int(rgb.shape[1])
    base = min(h, w)

    # Base skin (balanced — not as tight as mask_v2)
    skin_rgb = (
        (r > 0.36)
        & (g > 0.16)
        & (b > 0.09)
        & (r > g)
        & (r > b)
        & ((r - g) > 0.05)
        & ((r - g) < 0.50)
        & ((r - b) < 0.58)
    ).astype(np.float32)

    skin_lab = (
        (L > 32.0)
        & (L < 92.0)
        & (aa > 3.0)
        & (aa < 38.0)
        & (bb > 2.0)
        & (bb < 40.0)
        & (chroma > 6.0)
        & (chroma < 50.0)
    ).astype(np.float32)

    m = np.clip(0.42 * skin_rgb + 0.58 * skin_lab, 0, 1)

    # Eyes / lips / teeth / micro-detail
    dark = np.clip((36.0 - L) / 18.0, 0.0, 1.0)
    rad_d = max(1, int(round(base * 0.004)))
    L_blur = _box_blur(L.astype(np.float32), max(2, rad_d * 3))
    detail = np.clip(np.abs(L - L_blur) / 14.0, 0.0, 1.0)
    lips = (
        np.clip((aa - 24.0) / 16.0, 0.0, 1.0)
        * np.clip((chroma - 30.0) / 18.0, 0.0, 1.0)
        * np.clip(1.0 - np.abs(L - 55.0) / 35.0, 0.0, 1.0)
    )
    bright_low_chroma = np.clip((L - 80.0) / 14.0, 0.0, 1.0) * np.clip(
        (16.0 - chroma) / 12.0, 0.0, 1.0
    )
    protect = np.clip(
        dark * 0.92 + detail * 0.35 + lips * 0.88 + bright_low_chroma * 0.65,
        0.0,
        1.0,
    )
    m = m * (1.0 - protect)

    # Pattern rejection — only where local variance is *high*
    # Smooth face has low variance and is mostly left alone.
    rad_v = max(2, int(round(base * 0.014)))

    def _local_var(ch: np.ndarray, rad: int) -> np.ndarray:
        mu = _box_blur(ch, rad)
        mu2 = _box_blur(ch * ch, rad)
        return np.clip(mu2 - mu * mu, 0.0, None)

    L_n = (L / 100.0).astype(np.float32)
    c_n = (chroma / 60.0).astype(np.float32)
    var_L = _local_var(L_n, rad_v)
    var_c = _local_var(c_n, rad_v)
    # Soft knee: ignore mild variance (skin pores), hit strong print variance
    pattern = np.clip((var_L - 0.004) / 0.016, 0.0, 1.0) * 0.50 + np.clip(
        (var_c - 0.006) / 0.022, 0.0, 1.0
    ) * 0.50
    pattern = np.clip(pattern, 0.0, 1.0)
    m = m * (1.0 - 0.75 * pattern)

    # Speckle cleanup (light)
    rad_o = max(1, int(round(base * 0.003)))
    m_s = _box_blur(m, rad_o)
    m = np.clip(m * np.clip((m_s - 0.08) / 0.55, 0.0, 1.0), 0.0, 1.0)

    # Feather + threshold
    f = float(np.clip(feather, 0.0, 1.0))
    rad = max(1, int(round(base * (0.003 + 0.012 * f))))
    m = _box_blur(m, rad)
    thr = 0.36 - (sensitivity - 0.5) * 0.22
    m = np.clip((m - thr) / max(1e-5, (0.95 - thr)), 0, 1)
    m = _box_blur(m, max(1, rad // 2))
    return m.astype(np.float32)


def _normalize_mask(mask: np.ndarray, h: int, w: int) -> np.ndarray:
    if mask is None:
        return None
    m = mask.astype(np.float32)
    if m.ndim == 3:
        m = m[..., 0] if m.shape[-1] in (1, 3, 4) else m.mean(axis=-1)
    if m.shape[0] != h or m.shape[1] != w:
        # nearest resize
        ys = (np.linspace(0, m.shape[0] - 1, h)).astype(np.int32)
        xs = (np.linspace(0, m.shape[1] - 1, w)).astype(np.int32)
        m = m[ys][:, xs]
    return np.clip(m, 0, 1).astype(np.float32)


def _apply_skin(
    rgb: np.ndarray,
    mask: np.ndarray,
    coolness: float,
    brightness: float,
    rosy: float,
    evenness: float,
    shadow_lift: float,
    smooth: float,
    texture_preserve: float,
    saturation: float,
    highlight_protect: float,
) -> np.ndarray:
    lab = _rgb_to_lab(rgb)
    L, a, b = lab[..., 0].copy(), lab[..., 1].copy(), lab[..., 2].copy()

    hp = np.clip(highlight_protect, 0, 1)
    # Highlight zone softens whitening/cool on bright skin
    highlight_zone = np.clip((L - 68.0) / 28.0, 0, 1)
    lift_guard = 1.0 - 0.78 * hp * highlight_zone
    m = mask * (1.0 - 0.35 * hp * highlight_zone)

    # Cool: reduce b* (yellow)
    b = b - m * coolness * 18.0
    # Rosy: push a* (red/pink) — independent of cool
    a = a + m * rosy * 9.0
    # Slight cool can still tame flush
    a = a - m * coolness * 3.0

    # Brightness (overall lift under mask, protected on highlights)
    L = L + m * brightness * 12.0 * lift_guard
    # Shadow lift: more lift in dark skin regions
    shadow_w = np.clip(1.0 - L / 100.0, 0, 1) ** 2
    L = L + m * shadow_lift * 10.0 * shadow_w

    # Saturation: scale chroma around neutral
    sat = float(saturation)
    if abs(sat) > 1e-4:
        scale = 1.0 + sat * 0.45
        a = a * (1.0 - m) + (a * scale) * m
        b = b * (1.0 - m) + (b * scale) * m

    # Evenness: pull toward local mean
    if evenness > 1e-4:
        rad = max(2, int(round(min(rgb.shape[0], rgb.shape[1]) * 0.04)))
        a_blur = _box_blur(a, rad)
        b_blur = _box_blur(b, rad)
        L_blur = _box_blur(L, rad)
        a = a * (1 - m * evenness) + a_blur * (m * evenness)
        b = b * (1 - m * evenness) + b_blur * (m * evenness)
        L = L * (1 - m * evenness * 0.35) + L_blur * (m * evenness * 0.35)

    # Smooth modulated by texture_preserve (1 = keep texture, 0 = allow full smooth)
    tp = float(np.clip(texture_preserve, 0, 1))
    smooth_eff = smooth * (1.0 - 0.86 * tp)
    if smooth_eff > 1e-4:
        rad = max(1, int(round(min(rgb.shape[0], rgb.shape[1]) * 0.012)))
        L_s = _box_blur(L, rad)
        L = L * (1 - m * smooth_eff * 0.65) + L_s * (m * smooth_eff * 0.65)

    L = np.clip(L, 0, 100)
    out = _lab_to_rgb(np.stack([L, a, b], axis=-1))
    m3 = m[..., None]
    return np.clip(rgb * (1.0 - m3) + out * m3, 0, 1).astype(np.float32)


def process_frame(
    rgb: np.ndarray,
    mask_in: np.ndarray | None,
    preset: str,
    strength: float,
    coolness: float,
    brightness: float,
    rosy: float,
    evenness: float,
    shadow_lift: float,
    smooth: float,
    texture_preserve: float,
    saturation: float,
    highlight_protect: float,
    mask_sensitivity: float,
    mask_feather: float,
) -> tuple[np.ndarray, np.ndarray]:
    # Preset loads widgets in JS; processing uses current slider values.
    s = float(np.clip(strength, 0, 2))
    coolness = float(coolness) * s
    brightness = float(brightness) * s
    rosy = float(rosy) * s
    evenness = float(np.clip(evenness * min(s, 1.0), 0, 1))
    shadow_lift = float(shadow_lift) * s
    smooth = float(np.clip(smooth * min(s, 1.0), 0, 1))
    texture_preserve = float(np.clip(texture_preserve, 0, 1))
    saturation = float(saturation) * min(s, 1.0)
    highlight_protect = float(np.clip(highlight_protect, 0, 1))
    mask_sensitivity = float(np.clip(mask_sensitivity, 0, 1))
    mask_feather = float(np.clip(mask_feather, 0, 1))

    h, w = rgb.shape[:2]
    auto = _auto_skin_mask(rgb, mask_sensitivity, mask_feather)
    if mask_in is not None:
        ext = _normalize_mask(mask_in, h, w)
        # External (e.g. SAM person) limits where auto skin can apply.
        # Multiply = skin-colored pixels only inside the segment (kills background / off-body).
        # Soft floor keeps a little auto near edges if segment is hard-cut.
        skin = np.clip(auto * np.clip(ext, 0, 1), 0, 1)
        # If external is nearly empty, fall back to auto
        if float(ext.max()) < 0.05:
            skin = auto
    else:
        skin = auto

    out = _apply_skin(
        rgb,
        skin,
        coolness,
        brightness,
        rosy,
        evenness,
        shadow_lift,
        smooth,
        texture_preserve,
        saturation,
        highlight_protect,
    )
    mix = float(np.clip(s if s <= 1 else 1.0, 0, 1))
    if mix < 0.999:
        m3 = skin[..., None] * mix
        out = rgb * (1 - m3) + out * m3
    return out.astype(np.float32), skin.astype(np.float32)


# ---------------------------------------------------------------------------
# Comfy node
# ---------------------------------------------------------------------------
class LCSkinBeauty(PreviewImage):
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE", {"tooltip": "Source image (batch ok)."}),
                "preset": (
                    PRESET_NAMES,
                    {
                        "default": "Natural",
                        "tooltip": "Starting preset. Customize below by moving the sliders.",
                    },
                ),
                "strength": (
                    "FLOAT",
                    {
                        "default": 1.0,
                        "min": 0.0,
                        "max": 2.0,
                        "step": 0.05,
                        "tooltip": "How much of the effect to apply. 0 = original image, 1 = full, above 1 = stronger.",
                    },
                ),
                "coolness": (
                    "FLOAT",
                    {
                        "default": 0.22,
                        "min": 0.0,
                        "max": 1.0,
                        "step": 0.05,
                        "tooltip": "Cool vs warm skin. 0 = no shift, 1 = much less yellow / cooler.",
                    },
                ),
                "brightness": (
                    "FLOAT",
                    {
                        "default": 0.12,
                        "min": 0.0,
                        "max": 1.0,
                        "step": 0.05,
                        "tooltip": "Skin whitening / lightness. 0 = none, 1 = strong lift (highlights still protected).",
                    },
                ),
                "rosy": (
                    "FLOAT",
                    {
                        "default": 0.08,
                        "min": -0.3,
                        "max": 0.5,
                        "step": 0.05,
                        "tooltip": "Rosy flush. Negative = less red, 0 = neutral, higher = pinker cheeks/lips-adjacent skin.",
                    },
                ),
                "evenness": (
                    "FLOAT",
                    {
                        "default": 0.18,
                        "min": 0.0,
                        "max": 1.0,
                        "step": 0.05,
                        "tooltip": "Even skin tone. 0 = keep variation, 1 = strong local color averaging.",
                    },
                ),
                "shadow_lift": (
                    "FLOAT",
                    {
                        "default": 0.15,
                        "min": 0.0,
                        "max": 1.0,
                        "step": 0.05,
                        "tooltip": "Shadow recovery. 0 = no change in dark areas, 1 = lift shadows more than midtones.",
                    },
                ),
                "smooth": (
                    "FLOAT",
                    {
                        "default": 0.06,
                        "min": 0.0,
                        "max": 1.0,
                        "step": 0.05,
                        "tooltip": "Soft smoothing. 0 = full texture, 1 = softer skin (use with texture preserve).",
                    },
                ),
                "texture_preserve": (
                    "FLOAT",
                    {
                        "default": 0.88,
                        "min": 0.0,
                        "max": 1.0,
                        "step": 0.05,
                        "tooltip": "Texture keep. 0 = allow smooth to flatten detail, 1 = protect pores/micro-contrast.",
                    },
                ),
                "saturation": (
                    "FLOAT",
                    {
                        "default": -0.08,
                        "min": -0.5,
                        "max": 0.5,
                        "step": 0.05,
                        "tooltip": "Skin saturation. Negative = quieter color, 0 = unchanged, positive = richer.",
                    },
                ),
                "highlight_protect": (
                    "FLOAT",
                    {
                        "default": 0.75,
                        "min": 0.0,
                        "max": 1.0,
                        "step": 0.05,
                        "tooltip": "Highlight protect. 0 = treat bright skin same as midtones, 1 = mostly skip highlights.",
                    },
                ),
                "mask_sensitivity": (
                    "FLOAT",
                    {
                        "default": 0.55,
                        "min": 0.0,
                        "max": 1.0,
                        "step": 0.05,
                        "tooltip": "Mask reach. 0 = only obvious skin, 1 = wider (may include more non-skin).",
                    },
                ),
                "mask_feather": (
                    "FLOAT",
                    {
                        "default": 0.45,
                        "min": 0.0,
                        "max": 1.0,
                        "step": 0.05,
                        "tooltip": "Mask edge. 0 = harder cut, 1 = softer feather into non-skin.",
                    },
                ),
            },
            "optional": {
                "mask": (
                    "MASK",
                    {
                        "tooltip": "Optional external skin mask (higher precision). Combined with auto mask.",
                    },
                ),
            },
        }

    RETURN_TYPES = ("IMAGE", "MASK")
    RETURN_NAMES = ("image", "skin_mask")
    FUNCTION = "run"
    CATEGORY = "LC123/image"
    OUTPUT_NODE = True
    DESCRIPTION = (
        "LC Skin Beauty (draft) — mask-aware cool/bright skin in LAB with presets. "
        "Protects highlights; optional external MASK. On-node before/after wipe."
    )

    def run(
        self,
        image,
        preset="Natural",
        strength=1.0,
        coolness=0.22,
        brightness=0.12,
        rosy=0.08,
        evenness=0.18,
        shadow_lift=0.15,
        smooth=0.06,
        texture_preserve=0.88,
        saturation=-0.08,
        highlight_protect=0.75,
        mask_sensitivity=0.55,
        mask_feather=0.45,
        mask=None,
    ):
        if image is None:
            raise ValueError(
                "LC Skin Beauty: image is empty. Check upstream wires / bypassers."
            )

        frames = tensor_to_np(image)
        mask_frames = None
        if mask is not None:
            # mask tensor [B,H,W]
            import torch

            if hasattr(mask, "detach"):
                mt = mask.detach().cpu().numpy().astype(np.float32)
                mask_frames = [mt[i] for i in range(mt.shape[0])]
            elif isinstance(mask, (list, tuple)):
                mask_frames = mask

        out_imgs = []
        out_masks = []
        for i, fr in enumerate(frames):
            rgb = np.clip(fr[..., :3], 0, 1).astype(np.float32)
            mi = None
            if mask_frames is not None:
                mi = mask_frames[min(i, len(mask_frames) - 1)]
            processed, skin = process_frame(
                rgb,
                mi,
                preset,
                strength,
                coolness,
                brightness,
                rosy,
                evenness,
                shadow_lift,
                smooth,
                texture_preserve,
                saturation,
                highlight_protect,
                mask_sensitivity,
                mask_feather,
            )
            if fr.shape[-1] == 4:
                processed = np.concatenate(
                    [processed, fr[..., 3:4]], axis=-1
                )
            out_imgs.append(processed)
            out_masks.append(skin)

        result = np_to_tensor(out_imgs)
        import torch

        mask_t = torch.from_numpy(np.stack(out_masks, axis=0).astype(np.float32))

        # Preview wipe (same contract as other LC image nodes)
        out = {"ui": {}, "result": (result, mask_t)}
        try:
            after = self.save_images(result, filename_prefix="lc_after")
            out["ui"]["lc_preview"] = after["ui"]["images"]
            before = self.save_images(image, filename_prefix="lc_before")
            out["ui"]["lc_before"] = before["ui"]["images"]
        except Exception:
            pass
        return out


NODE_CLASS_MAPPINGS = {
    "LCSkinBeauty": LCSkinBeauty,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LCSkinBeauty": "LC Skin Beauty ✨",
}
