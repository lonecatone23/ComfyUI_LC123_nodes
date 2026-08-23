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
    Soft point light in a centered frame:
      x,y,z ∈ [-1, 1]  — (0,0,1) front, (0,1,0) overhead, (0,-1,0) below

    Distance falloff is absolute (no image-wide peak normalize), so:
      ambient=0 + small size → far depth goes near black; near stays lit.
    depth_scale stretches surface Z so deep pixels are farther from the light.
    """
    h, w = depth.shape
    xs = (np.arange(w, dtype=np.float32) + 0.5) / w * 2.0 - 1.0
    ys = 1.0 - (np.arange(h, dtype=np.float32) + 0.5) / h * 2.0
    xx, yy = np.meshgrid(xs, ys)
    # Depth 0 near → 1 far. Moderate Z so the subject stays in the beam;
    # far background still drops when ambient is 0.
    z_extent = 0.35 + 1.25 * float(depth_scale)
    sz = -depth.astype(np.float32) * z_extent
    light = np.array([float(lx), float(ly), float(lz)], dtype=np.float32)
    vx = light[0] - xx
    vy = light[1] - yy
    vz = light[2] - sz
    dist = np.sqrt(vx * vx + vy * vy + vz * vz + 1e-6)
    soft = max(float(point_size), 0.05)
    # 0.05 ≈ tight spot, 0.45 ≈ face coverage, 1.0+ ≈ soft fill
    eff = 0.08 + soft * 0.55 + (soft * soft) * 0.35
    # Cubic falloff — sharp outside the beam without zeroing the subject
    atten = 1.0 / (1.0 + (dist / max(eff, 1e-4)) ** 3)
    ref = max(float(np.linalg.norm(light)), 0.35)
    ref_atten = 1.0 / (1.0 + (ref / max(eff, 1e-4)) ** 3)
    atten = atten / max(ref_atten, 1e-12)
    atten = np.clip(atten, 0.0, 3.0)
    dx, dy, dz = vx / dist, vy / dist, vz / dist
    ndotl = (
        normals[..., 0] * dx
        + normals[..., 1] * dy
        + normals[..., 2] * dz
    )
    ndotl = np.clip(ndotl, 0.0, 1.0)
    g = max(float(gamma), 0.05)
    term = (ndotl ** g) * atten * float(intensity)
    return term.astype(np.float32)


def _cast_shadow_ss(
    depth: np.ndarray,
    lx: float,
    ly: float,
    lz: float,
    steps: int = 24,
    max_range: float = 0.40,
    bias: float = 0.02,
    thickness: float = 0.08,
) -> np.ndarray:
    """
    Screen-space ray-march cast shadows from a camera depth map (0=near, 1=far).

    From each pixel, step toward the light in image space. If a sample is
    closer to the camera than the receiver by more than bias (and within a
    thickness band), treat it as an occluder. Produces head→torso / body→wall
    style occlusion when depth has separation — not true 3D ray tracing.

    Returns occlusion HW in 0..1 (1 = fully blocked).
    """
    h, w = depth.shape
    d = depth.astype(np.float32)
    steps = int(max(4, min(int(steps), 64)))
    max_range = float(np.clip(max_range, 0.05, 1.0))
    bias = float(max(bias, 1e-4))
    thickness = float(max(thickness, bias))

    # Pixel centers in same centered frame as the light
    xs = (np.arange(w, dtype=np.float32) + 0.5) / w * 2.0 - 1.0
    ys = 1.0 - (np.arange(h, dtype=np.float32) + 0.5) / h * 2.0
    xx, yy = np.meshgrid(xs, ys)

    # Direction toward light in the image plane
    to_x = float(lx) - xx
    to_y = float(ly) - yy
    plane = np.sqrt(to_x * to_x + to_y * to_y + 1e-8)
    # Pixel-space direction: +X right, +Y overhead → toward top (decreasing row)
    dir_px = (to_x / plane) * (w * 0.5)
    dir_py = -(to_y / plane) * (h * 0.5)
    len_p = np.sqrt(dir_px * dir_px + dir_py * dir_py + 1e-8)
    upx = dir_px / len_p
    upy = dir_py / len_p

    march_px = max_range * float(np.hypot(h, w))
    yy_i, xx_i = np.meshgrid(
        np.arange(h, dtype=np.float32),
        np.arange(w, dtype=np.float32),
        indexing="ij",
    )
    occ = np.zeros((h, w), dtype=np.float32)
    d0 = d

    for s in range(1, steps + 1):
        t = s / float(steps)
        sx = xx_i + upx * march_px * t
        sy = yy_i + upy * march_px * t
        valid = (sx >= 0) & (sx <= w - 1) & (sy >= 0) & (sy <= h - 1)
        si = np.clip(np.rint(sy), 0, h - 1).astype(np.int32)
        sj = np.clip(np.rint(sx), 0, w - 1).astype(np.int32)
        d_s = d[si, sj]
        # Sample nearer to camera than receiver → occluder
        # (head depth << torso depth is a large delta — do not cap it away)
        delta = d0 - d_s
        hit = valid & (delta > bias)
        # Ramp 0→1 over `thickness`, then stay at 1 for larger separations
        wgt = np.clip((delta - bias) / max(thickness, 1e-4), 0.0, 1.0)
        wgt = np.where(hit, wgt, 0.0).astype(np.float32)
        occ = np.maximum(occ, wgt)

    return np.clip(occ, 0.0, 1.0).astype(np.float32)


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
                "gamma": (
                    "FLOAT",
                    {
                        "default": 1.0,
                        "min": 0.2,
                        "max": 2.0,
                        "step": 0.1,
                        "tooltip": "Highlight falloff. Higher = tighter highlights.",
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
                    {"default": -0.85, "min": -1.0, "max": 1.0, "step": 0.05,
                     "tooltip": "Light 1 Y: -1 below (under-light), 0 midline, +1 overhead."},
                ),
                "light1_z": (
                    "FLOAT",
                    {"default": 0.90, "min": -1.0, "max": 1.0, "step": 0.05,
                     "tooltip": "Light 1 Z: +1 in front (camera side), 0 plane, -1 behind."},
                ),
                "light1_intensity": (
                    "FLOAT",
                    {"default": 1.50, "min": 0.0, "max": 2.0, "step": 0.05,
                     "tooltip": "Light 1 key. Try 2.0 + ambient 0 for hard under/side light like a studio key."},
                ),
                "light1_size": (
                    "FLOAT",
                    {"default": 0.45, "min": 0.05, "max": 2.0, "step": 0.05,
                     "tooltip": "Light 1 softness / size. Smaller = harder shadow edge."},
                ),
                "enable_light_2": (
                    "BOOLEAN",
                    {"default": False, "tooltip": "Enable second light (fill / rim)."},
                ),
                "light2_x": (
                    "FLOAT",
                    {"default": 0.55, "min": -1.0, "max": 1.0, "step": 0.05,
                     "tooltip": "Light 2 X: -1 left … +1 right."},
                ),
                "light2_y": (
                    "FLOAT",
                    {"default": 0.15, "min": -1.0, "max": 1.0, "step": 0.05,
                     "tooltip": "Light 2 Y: -1 below … +1 overhead."},
                ),
                "light2_z": (
                    "FLOAT",
                    {"default": 0.45, "min": -1.0, "max": 1.0, "step": 0.05,
                     "tooltip": "Light 2 Z: +1 front … -1 back."},
                ),
                "light2_intensity": (
                    "FLOAT",
                    {"default": 0.55, "min": 0.0, "max": 2.0, "step": 0.05, "tooltip": "Light 2 brightness."},
                ),
                "light2_size": (
                    "FLOAT",
                    {"default": 0.45, "min": 0.05, "max": 2.0, "step": 0.05, "tooltip": "Light 2 softness / size."},
                ),
                "cast_shadows": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "tooltip": "Screen-space cast shadows from depth. Leave OFF until form lighting looks right.",
                    },
                ),
                "shadow_strength": (
                    "FLOAT",
                    {
                        "default": 0.55,
                        "min": 0.0,
                        "max": 1.0,
                        "step": 0.05,
                        "tooltip": "How hard cast shadows darken the key (0 = off, 1 = full block of key).",
                    },
                ),
                "shadow_softness": (
                    "FLOAT",
                    {
                        "default": 0.40,
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
        "Directional highlight/shadow relight from normal + depth maps. "
        "Optional screen-space cast shadows from depth. Optional mask → virtual-dome normals."
    )

    def relight(
        self,
        image,
        normal_map,
        depth_map,
        ambient_light,
        gamma,
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

        out_imgs = []
        out_masks = []

        for i in range(b):
            rgb = imgs[i]
            n_img = _resize_map(norms_in[i], h, w)
            d_img = _resize_map(depths_in[i], h, w)
            normals = _decode_normals(n_img)
            depth = _depth_hw(d_img)

            L_real = _light_map(
                normals, depth,
                light1_x, light1_y, light1_z,
                light1_intensity, light1_size,
                depth_scale, gamma,
            )
            if enable_light_2:
                L_real = L_real + _light_map(
                    normals, depth,
                    light2_x, light2_y, light2_z,
                    light2_intensity, light2_size,
                    depth_scale, gamma,
                )

            feather = np.zeros((h, w), dtype=np.float32)
            L = L_real
            if masks is not None and mask_enabled:
                m = masks[i if i < masks.shape[0] else 0]
                if m.shape[0] != h or m.shape[1] != w:
                    m = _resize_map(m, h, w)[..., 0] if m.ndim == 2 else _resize_map(m[..., None], h, w)[..., 0]
                # Fixed mild dome softness (was a separate widget)
                vnorm, feather = _virtual_normals_from_mask(m, 0.45)
                if feather.shape != (h, w):
                    feather = _resize_map(feather, h, w)[..., 0]
                if vnorm.shape[0] != h or vnorm.shape[1] != w:
                    vnorm = _resize_map(vnorm, h, w)
                    lens = np.linalg.norm(vnorm, axis=-1, keepdims=True)
                    vnorm = vnorm / np.maximum(lens, 1e-6)
                L_virt = _light_map(
                    vnorm, depth,
                    light1_x, light1_y, light1_z,
                    light1_intensity, light1_size,
                    depth_scale, gamma,
                )
                if enable_light_2:
                    L_virt = L_virt + _light_map(
                        vnorm, depth,
                        light2_x, light2_y, light2_z,
                        light2_intensity, light2_size,
                        depth_scale, gamma,
                    )
                mb = float(mask_blend)
                mix = feather * mb
                L = L_real * (1.0 - mix) + L_virt * mix

            # Screen-space cast shadows (range/bias baked to solid defaults)
            if cast_shadows and float(shadow_strength) > 1e-6:
                occ = _cast_shadow_ss(
                    depth,
                    light1_x, light1_y, light1_z,
                    steps=24,
                    max_range=0.40,
                    bias=0.02,
                    thickness=0.12,
                )
                soft_r = int(max(0, min(h, w) * 0.02 * float(shadow_softness) * 8))
                if soft_r > 0:
                    occ = _box_blur(occ, soft_r)
                    occ = np.clip(occ, 0.0, 1.0)
                L = L * (1.0 - float(shadow_strength) * occ)

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
