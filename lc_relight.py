"""
LC Lighting Control
----------
Post-process relight using a normal map + depth map, with optional subject mask
→ internal virtual-dome normals. Clean-room implementation (no third-party relight code).

Outputs:
  - image: relit result
  - debug_mask: feathered mask used for virtual normals (debug; safe to ignore / remove later)
"""

from __future__ import annotations

import numpy as np
import torch


def _to_bhwc(t: torch.Tensor) -> torch.Tensor:
    if t.ndim == 3:
        t = t.unsqueeze(0)
    return t


def _image_np(img: torch.Tensor) -> np.ndarray:
    """BHWC float32 RGB in 0..1"""
    t = _to_bhwc(img).detach().cpu().float().numpy()
    if t.shape[-1] > 3:
        t = t[..., :3]
    return np.clip(t, 0.0, 1.0)


def _mask_np(mask, h: int, w: int) -> np.ndarray | None:
    if mask is None:
        return None
    t = mask
    if isinstance(t, torch.Tensor):
        t = t.detach().cpu().float().numpy()
    t = np.asarray(t, dtype=np.float32)
    if t.ndim == 4:
        t = t[:, :, :, 0]
    elif t.ndim == 3 and t.shape[-1] in (1, 3, 4):
        t = t[..., 0]
    elif t.ndim == 3:
        pass  # BHW
    elif t.ndim == 2:
        t = t[None, ...]
    else:
        return None
    out = []
    for i in range(t.shape[0]):
        m = t[i]
        if m.shape[0] != h or m.shape[1] != w:
            # nearest resize
            ys = (np.linspace(0, m.shape[0] - 1, h)).astype(np.float32)
            xs = (np.linspace(0, m.shape[1] - 1, w)).astype(np.float32)
            yi, xi = np.meshgrid(ys, xs, indexing="ij")
            m = m[
                np.clip(yi.astype(np.int32), 0, m.shape[0] - 1),
                np.clip(xi.astype(np.int32), 0, m.shape[1] - 1),
            ]
        out.append(np.clip(m, 0.0, 1.0))
    return np.stack(out, axis=0)


def _resize_map(m: np.ndarray, h: int, w: int) -> np.ndarray:
    """m: HW or HWC → HWC float"""
    if m.ndim == 2:
        m = m[..., None]
    mh, mw = m.shape[0], m.shape[1]
    if mh == h and mw == w:
        return m.astype(np.float32)
    ys = np.linspace(0, mh - 1, h).astype(np.float32)
    xs = np.linspace(0, mw - 1, w).astype(np.float32)
    yi, xi = np.meshgrid(ys, xs, indexing="ij")
    yi = np.clip(yi.astype(np.int32), 0, mh - 1)
    xi = np.clip(xi.astype(np.int32), 0, mw - 1)
    return m[yi, xi].astype(np.float32)


def _decode_normals(normal_img: np.ndarray) -> np.ndarray:
    """HWC RGB 0..1 → HWC unit normals."""
    n = normal_img[..., :3].astype(np.float32) * 2.0 - 1.0
    # Common: OpenGL-style Y flip not applied; assume map already matches image space
    lens = np.linalg.norm(n, axis=-1, keepdims=True)
    lens = np.maximum(lens, 1e-6)
    return n / lens


def _depth_hw(depth_img: np.ndarray) -> np.ndarray:
    """Return depth HW with 0 = near, 1 = far.

    Depth Anything and many preview maps are often bright = near. After a
    0–1 stretch we detect that (subject/center brighter than border) and invert
    so cast shadows and depth falloff use a consistent near/far convention.
    """
    if depth_img.ndim == 3:
        d = depth_img.mean(axis=-1)
    else:
        d = depth_img
    d = d.astype(np.float32)
    dmin, dmax = float(d.min()), float(d.max())
    if dmax - dmin > 1e-6:
        d = (d - dmin) / (dmax - dmin)
    else:
        d = np.zeros_like(d)

    h, w = d.shape
    if h >= 16 and w >= 16:
        cy, cx = h // 2, w // 2
        rh, rw = max(h // 6, 2), max(w // 6, 2)
        center = float(d[cy - rh : cy + rh, cx - rw : cx + rw].mean())
        # Border ring
        b = max(h // 12, 1)
        border_vals = np.concatenate(
            [
                d[:b, :].ravel(),
                d[-b:, :].ravel(),
                d[:, :b].ravel(),
                d[:, -b:].ravel(),
            ]
        )
        border = float(border_vals.mean())
        # If center is "farther" in the raw encoding, map is bright-near → invert
        if center > border + 0.04:
            d = 1.0 - d
    return d


def _box_blur(m: np.ndarray, radius: int) -> np.ndarray:
    """Separable box blur; output shape always matches input HW."""
    if radius <= 0:
        return m.astype(np.float32)
    h, w = m.shape
    r = int(radius)
    k = r * 2 + 1
    mp = np.pad(m.astype(np.float32), ((r, r), (r, r)), mode="edge")
    # vertical window sum via cumsum on axis 0
    c = np.zeros((mp.shape[0] + 1, mp.shape[1]), dtype=np.float64)
    c[1:] = np.cumsum(mp, axis=0)
    vert = (c[k : k + h] - c[0:h]) / float(k)
    # horizontal
    c2 = np.zeros((vert.shape[0], vert.shape[1] + 1), dtype=np.float64)
    c2[:, 1:] = np.cumsum(vert, axis=1)
    out = (c2[:, k : k + w] - c2[:, 0:w]) / float(k)
    return out.astype(np.float32)



def _virtual_normals_from_mask(mask_hw: np.ndarray, softness: float) -> tuple[np.ndarray, np.ndarray]:
    """
    mask_hw: 0..1 HW
    Returns (normals HWC, feathered_mask HW)
    """
    h, w = mask_hw.shape
    # Softness 0..1 → blur radius relative to min side
    radius = int(max(0, min(h, w) * 0.02 * float(softness) * 10))
    feather = _box_blur(mask_hw, max(radius, 0))
    feather = np.clip(feather, 0.0, 1.0)
    # Height field: extra blur for dome
    height = _box_blur(feather, max(radius + 1, 1))
    # Gradients (central differences)
    gy = np.zeros_like(height)
    gx = np.zeros_like(height)
    gy[1:-1, :] = (height[2:, :] - height[:-2, :]) * 0.5
    gx[:, 1:-1] = (height[:, 2:] - height[:, :-2]) * 0.5
    # Scale slopes for readable dome
    scale = 2.5
    nx = -gx * scale
    ny = -gy * scale
    nz = np.ones_like(height)
    n = np.stack([nx, ny, nz], axis=-1)
    lens = np.linalg.norm(n, axis=-1, keepdims=True)
    n = n / np.maximum(lens, 1e-6)
    return n, feather


def _light_map(
    normals: np.ndarray,
    depth: np.ndarray,
    lx: float,
    ly: float,
    lz: float,
    intensity: float,
    point_size: float,
    depth_scale: float,
    gamma: float,
) -> np.ndarray:
    """
    Spotlight + directional form shading.

    Widget: +X = from the right of the frame, +Y = from above, Z floored at 0.
    N·L uses flipped X so estimated/DirectX normal maps match that widget.
    Cone aim stays in screen space (unflipped).
    """
    h, w = depth.shape
    xs = (np.arange(w, dtype=np.float32) + 0.5) / w * 2.0 - 1.0
    ys = 1.0 - (np.arange(h, dtype=np.float32) + 0.5) / h * 2.0
    xx, yy = np.meshgrid(xs, ys)

    # N·L: flip X for estimated normal maps (R often opposite OpenGL +X).
    # Screen/cone: widget +X = right of frame, +Y = up.
    ss = np.array([float(lx), float(ly), max(float(lz), 0.0)], dtype=np.float32)
    sn = float(np.linalg.norm(ss))
    if sn < 1e-6:
        ss = np.array([0.0, 0.0, 1.0], dtype=np.float32)
        sn = 1.0
    sx, sy, sz = ss[0] / sn, ss[1] / sn, ss[2] / sn
    ax, ay, az = -sx, sy, sz
    ln = float(np.hypot(np.hypot(ax, ay), az)) or 1.0
    ax, ay, az = ax / ln, ay / ln, az / ln

    soft = float(np.clip(point_size, 0.02, 1.5))
    cone_r = 0.12 + soft * 1.10 + (soft * soft) * 0.40

    # Cone follows the widget on screen (not the flipped N·L axis)
    aim_x = sx * 0.22 * min(soft, 1.0)
    aim_y = sy * 0.22 * min(soft, 1.0)
    rho = np.sqrt((xx - aim_x) ** 2 + (yy - aim_y) ** 2 + 1e-8)

    # Wider penumbra (less ring-like edge)
    inner = cone_r * 0.35
    outer = cone_r * 1.05
    tcone = np.clip((rho - inner) / max(outer - inner, 1e-4), 0.0, 1.0)
    # Quintic smoothstep — softer than cubic, fewer visible bands
    cone = 1.0 - (tcone * tcone * tcone * (tcone * (tcone * 6.0 - 15.0) + 10.0))

    ndotl = (
        normals[..., 0] * ax
        + normals[..., 1] * ay
        + normals[..., 2] * az
    )
    ndotl = np.clip(ndotl, 0.0, 1.0)
    g = max(float(gamma), 0.05)
    lambert = ndotl ** g

    ds = float(max(depth_scale, 0.0))
    d = depth.astype(np.float32)
    if ds > 1e-6:
        steep = 0.35 + (1.0 - min(soft / 1.5, 1.0)) * 1.0
        try:
            d_near = float(np.quantile(d, 0.05))
        except Exception:
            d_near = float(d.min())
        rel = np.clip(d - d_near, 0.0, 1.0)
        # Smooth exponential-style falloff (no hard power bands)
        atten = np.exp(-rel * ds * steep * 2.2)
        peak = float(np.quantile(atten, 0.95)) if atten.size else 1.0
        if peak > 1e-6:
            atten = atten / peak
        atten = np.clip(atten, 0.0, 1.0)
    else:
        atten = np.ones_like(d, dtype=np.float32)

    term = lambert * cone * atten * float(intensity)
    return term.astype(np.float32)



def _cast_shadow_ss(
    depth: np.ndarray,
    lx: float,
    ly: float,
    lz: float,
    steps: int = 32,
    max_range: float = 0.32,
    bias: float = 0.04,
    thickness: float = 0.35,
) -> np.ndarray:
    """
    Contact-style screen-space shadows from a camera depth map (0=near, 1=far).

    Tuned to avoid the "grey haze over everything" failure mode of soft DA-V2 depth:
      - adaptive bias (ignores tiny depth noise)
      - short march (contact / form blockers, not global darkening)
      - haze floor stripped so only clear occlusions remain
    """
    h, w = depth.shape
    d = depth.astype(np.float32)
    # Normalize depth span so bias is meaningful across maps
    d_lo = float(np.quantile(d, 0.02))
    d_hi = float(np.quantile(d, 0.98))
    span = max(d_hi - d_lo, 1e-4)
    d_n = np.clip((d - d_lo) / span, 0.0, 1.0)

    steps = int(max(4, min(int(steps), 48)))
    max_range = float(np.clip(max_range, 0.04, 0.6))
    # Bias as fraction of depth span — kills noise-driven haze
    bias_n = max(float(bias), 0.03)
    thickness_n = max(float(thickness), bias_n * 1.5)

    # March TOWARD the light in SCREEN space (widget axes, not N·L flip).
    # +X = right of frame, +Y = up. Shadows land on the opposite side of the key.
    axis = np.array([float(lx), float(ly), max(float(lz), 0.0)], dtype=np.float32)
    an = float(np.linalg.norm(axis)) + 1e-8
    ax, ay = axis[0] / an, axis[1] / an
    # If light is almost pure +Z (front), little lateral occlusion signal —
    # use a tiny default aim so we still get some contact from depth ridges
    lat = float(np.hypot(ax, ay))
    if lat < 0.08:
        ax, ay = 0.0, 0.35  # mild "from above" for frontal key contact
        lat = 0.35
    ax, ay = ax / lat, ay / lat

    march_px = max_range * float(np.hypot(h, w))
    yy_i, xx_i = np.meshgrid(
        np.arange(h, dtype=np.float32),
        np.arange(w, dtype=np.float32),
        indexing="ij",
    )
    # March TOWARD the light in screen space.
    # +X = right, +Y = up (row decreases). Prior sign put contact darkening
    # on the KEY side for side lights — flip lateral so occlusion falls on
    # the opposite side of the form from the light.
    step_x = ax * (march_px / steps)
    step_y = -ay * (march_px / steps)

    occ = np.zeros((h, w), dtype=np.float32)
    d0 = d_n

    # Accumulate with soft max — discrete max() + few steps caused ring ripples
    for s in range(1, steps + 1):
        sx = xx_i + step_x * float(s)
        sy = yy_i + step_y * float(s)
        valid = (sx >= 1) & (sx <= w - 2) & (sy >= 1) & (sy <= h - 2)
        # Bilinear-ish via weighted neighbors would be ideal; use rounded sample
        si = np.clip(np.rint(sy), 0, h - 1).astype(np.int32)
        sj = np.clip(np.rint(sx), 0, w - 1).astype(np.int32)
        d_s = d_n[si, sj]
        delta = d0 - d_s
        # Smooth distance weight (no sharp step boundaries)
        u = float(s) / float(steps)
        dist_fade = (1.0 - u) * (1.0 - u)
        raw = (delta - bias_n) / max(thickness_n, 1e-4)
        # Smoothstep on occlusion weight
        r = np.clip(raw, 0.0, 1.0)
        r = r * r * (3.0 - 2.0 * r)
        wgt = r * dist_fade
        wgt = np.where(valid, wgt, 0.0).astype(np.float32)
        # Soft blend instead of hard maximum reduces concentric bands
        occ = np.maximum(occ, wgt)
        occ = occ + 0.15 * wgt * (1.0 - occ)

    floor = 0.10
    occ = np.clip((occ - floor) / max(1.0 - floor, 1e-4), 0.0, 1.0)
    # Gentler curve than pure square
    occ = occ * occ * (3.0 - 2.0 * occ)
    return occ.astype(np.float32)



def _apply_light_to_image(
    rgb: np.ndarray,
    light: np.ndarray,
    ambient: float,
) -> np.ndarray:
    """Highlight / shadow only (no color tint).

      out = rgb * (ambient + light_map)

    light_map peaks near `intensity` on the lit side and falls toward 0 in shadow.
    Neutral starting point: ambient ≈ 0.5, intensity ≈ 0.55 → mild direction, similar overall brightness.
    Lower ambient / raise intensity for dramatic key-and-shadow.
    """
    amb = float(ambient)
    pure = np.clip(light, 0.0, 4.0)
    L = pure + amb
    # Direct multiply — preserves hue, reshapes luminance from the light map
    out = rgb * L[..., None]
    return np.clip(out, 0.0, 1.0).astype(np.float32)


class LCRelight:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE", {"tooltip": "Source image to relight."}),
                "normal_map": ("IMAGE", {"tooltip": "Normal map (RGB). Same subject framing as the image."}),
                "depth_map": ("IMAGE", {"tooltip": "Depth map. Light parallax + screen-space cast shadows."}),
                "ambient_light": (
                    "FLOAT",
                    {
                        "default": 0.25,
                        "min": 0.0,
                        "max": 1.5,
                        "step": 0.05,
                        "tooltip": "Shadow floor. 0 = pure key only (deep blacks). 0.25 = mild fill.",
                    },
                ),
                "depth_scale": (
                    "FLOAT",
                    {
                        "default": 0.50,
                        "min": 0.0,
                        "max": 2.0,
                        "step": 0.05,
                        "tooltip": "Depth → distance. Higher = far pixels fall off harder (with ambient 0 + small size).",
                    },
                ),
                "light1_x": (
                    "FLOAT",
                    {"default": 0.0, "min": -1.0, "max": 1.0, "step": 0.05,
                     "tooltip": "Light 1 X: -1 left, 0 center, +1 right."},
                ),
                "light1_y": (
                    "FLOAT",
                    {"default": 0.5, "min": -1.0, "max": 1.0, "step": 0.05,
                     "tooltip": "Light 1 Y: -1 below (under-light), 0 midline, +1 overhead."},
                ),
                "light1_z": (
                    "FLOAT",
                    {"default": 0.90, "min": 0.0, "max": 1.0, "step": 0.05,
                     "tooltip": "Light 1 Z: 0 = side plane, +1 = front (camera side). Floored at 0."},
                ),
                "light1_intensity": (
                    "FLOAT",
                    {"default": 1.0, "min": 0.0, "max": 2.0, "step": 0.05,
                     "tooltip": "Light 1 key. Try 2.0 + ambient 0 for hard under/side light like a studio key."},
                ),
                "light1_size": (
                    "FLOAT",
                    {"default": 1.0, "min": 0.05, "max": 2.0, "step": 0.05,
                     "tooltip": "Light 1 cone width: small = spot, large = flood."},
                ),
                "enable_light_2": (
                    "BOOLEAN",
                    {"default": False, "tooltip": "Enable second light (fill / rim)."},
                ),
                "light2_x": (
                    "FLOAT",
                    {"default": -1.0, "min": -1.0, "max": 1.0, "step": 0.05,
                     "tooltip": "Light 2 X: -1 left … +1 right."},
                ),
                "light2_y": (
                    "FLOAT",
                    {"default": 0.0, "min": -1.0, "max": 1.0, "step": 0.05,
                     "tooltip": "Light 2 Y: -1 below … +1 overhead."},
                ),
                "light2_z": (
                    "FLOAT",
                    {"default": 0.5, "min": 0.0, "max": 1.0, "step": 0.05,
                     "tooltip": "Light 2 Z: 0…+1 front. Floored at 0."},
                ),
                "light2_intensity": (
                    "FLOAT",
                    {"default": 1.0, "min": 0.0, "max": 2.0, "step": 0.05, "tooltip": "Light 2 brightness."},
                ),
                "light2_size": (
                    "FLOAT",
                    {"default": 0.5, "min": 0.05, "max": 2.0, "step": 0.05, "tooltip": "Light 2 cone width."},
                ),
                "cast_shadows": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "tooltip": "Screen-space cast shadows from depth.",
                    },
                ),
                "shadow_strength": (
                    "FLOAT",
                    {
                        "default": 0.5,
                        "min": 0.0,
                        "max": 1.0,
                        "step": 0.05,
                        "tooltip": "How hard cast shadows darken the key (0 = off, 1 = full block of key).",
                    },
                ),
                "shadow_softness": (
                    "FLOAT",
                    {
                        "default": 0.3,
                        "min": 0.0,
                        "max": 1.0,
                        "step": 0.05,
                        "tooltip": "Blur on the occlusion map (soft shadow edge).",
                    },
                ),
                "mask_enabled": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "tooltip": "When a mask is connected, build virtual-dome normals and blend them in.",
                    },
                ),
                "mask_blend": (
                    "FLOAT",
                    {
                        "default": 0.45,
                        "min": 0.0,
                        "max": 1.0,
                        "step": 0.05,
                        "tooltip": "0 = real normals only; 1 = virtual dome only (where mask is).",
                    },
                ),
            },
            "optional": {
                "mask": (
                    "MASK",
                    {
                        "tooltip": "Optional subject mask. Enables internal virtual normals when mask_enabled.",
                    },
                ),
            },
        }

    RETURN_TYPES = ("IMAGE", "MASK")
    RETURN_NAMES = ("image", "debug_mask")
    FUNCTION = "relight"
    CATEGORY = "LC123/image"
    DESCRIPTION = (
        "Spotlight relight: XYZ aims the beam (0,0,1 = front); light size = cone width (spot → flood). "
        "Optional screen-space cast shadows from depth. Optional mask → virtual-dome normals."
    )

    def relight(
        self,
        image,
        normal_map,
        depth_map,
        ambient_light,
        depth_scale,
        light1_x,
        light1_y,
        light1_z,
        light1_intensity,
        light1_size,
        enable_light_2,
        light2_x,
        light2_y,
        light2_z,
        light2_intensity,
        light2_size,
        cast_shadows,
        shadow_strength,
        shadow_softness,
        mask_enabled,
        mask_blend,
        mask=None,
        **_ignored,
    ):
        imgs = _image_np(image)
        norms_in = _image_np(normal_map)
        depths_in = _image_np(depth_map)
        b, h, w, _ = imgs.shape

        def batch_map(src):
            if src.shape[0] == b:
                return src
            if src.shape[0] == 1:
                return np.repeat(src, b, axis=0)
            return np.repeat(src[:1], b, axis=0)

        norms_in = batch_map(norms_in)
        depths_in = batch_map(depths_in)
        masks = _mask_np(mask, h, w) if mask is not None else None
        gamma = 1.0  # fixed; widget removed

        out_imgs = []
        out_masks = []

        for i in range(b):
            rgb = imgs[i]
            n_img = _resize_map(norms_in[i], h, w)
            d_img = _resize_map(depths_in[i], h, w)
            normals = _decode_normals(n_img)
            depth = _depth_hw(d_img)

            L = np.zeros((h, w), dtype=np.float32)

            def add_light(lx, ly, lz, intensity, size, nrm):
                if float(intensity) <= 1e-6:
                    return
                term = _light_map(
                    nrm, depth, lx, ly, lz, intensity, size, depth_scale, gamma
                )
                if cast_shadows and float(shadow_strength) > 1e-6:
                    occ = _cast_shadow_ss(depth, lx, ly, lz)
                    soft_r = int(round(max(0.0, float(shadow_softness)) * 3.0))
                    if soft_r > 0:
                        occ = np.clip(_box_blur(occ, soft_r), 0.0, 1.0)
                    s = float(np.clip(shadow_strength, 0.0, 1.0))
                    term = term * (1.0 - s * occ)
                return term

            t1 = add_light(
                light1_x, light1_y, light1_z,
                light1_intensity, light1_size, normals,
            )
            if t1 is not None:
                L = L + t1
            if enable_light_2:
                t2 = add_light(
                    light2_x, light2_y, light2_z,
                    light2_intensity, light2_size, normals,
                )
                if t2 is not None:
                    L = L + t2

            feather = np.zeros((h, w), dtype=np.float32)
            if masks is not None and mask_enabled:
                m = masks[i if i < masks.shape[0] else 0]
                if m.shape[0] != h or m.shape[1] != w:
                    m = _resize_map(m, h, w)[..., 0] if m.ndim == 2 else _resize_map(m[..., None], h, w)[..., 0]
                vnorm, feather = _virtual_normals_from_mask(m, 0.45)
                if feather.shape != (h, w):
                    feather = _resize_map(feather, h, w)[..., 0]
                if vnorm.shape[0] != h or vnorm.shape[1] != w:
                    vnorm = _resize_map(vnorm, h, w)
                    lens = np.linalg.norm(vnorm, axis=-1, keepdims=True)
                    vnorm = vnorm / np.maximum(lens, 1e-6)
                Lv = np.zeros((h, w), dtype=np.float32)
                tv1 = add_light(
                    light1_x, light1_y, light1_z,
                    light1_intensity, light1_size, vnorm,
                )
                if tv1 is not None:
                    Lv = Lv + tv1
                if enable_light_2:
                    tv2 = add_light(
                        light2_x, light2_y, light2_z,
                        light2_intensity, light2_size, vnorm,
                    )
                    if tv2 is not None:
                        Lv = Lv + tv2
                mb = float(mask_blend)
                mix = feather * mb
                L = L * (1.0 - mix) + Lv * mix

            relit = _apply_light_to_image(rgb, L, ambient_light)
            out_imgs.append(relit)
            out_masks.append(feather)

        img_t = torch.from_numpy(np.stack(out_imgs, axis=0))
        mask_t = torch.from_numpy(np.stack(out_masks, axis=0))
        return (img_t, mask_t)


NODE_CLASS_MAPPINGS = {
    "LCRelight": LCRelight,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LCRelight": "LC Lighting Control 🔦",
}
