"""
LC Lighting Control
----------
Post-process relight using a normal map + depth map, with optional subject mask
→ internal virtual-dome normals. Clean-room implementation (no third-party relight code).

Axis convention (widget / light stage):
  +X = light from the RIGHT of the frame (key on the right)
  +Y = light from ABOVE
  +Z = toward camera (0 = side plane, 1 = front). Z is floored at 0.

Estimated / DirectX-style normal maps often store X inverted vs OpenGL.
N·L therefore uses -X. Screen-space cone aim and cast-shadow march use
the widget axes directly so shadows fall on the OPPOSITE side of the key.

Each enabled light (intensity > 0) has its own N·L term and its own
screen-space shadows. Light 1 at intensity 0 does not contribute shadows.
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
    lens = np.linalg.norm(n, axis=-1, keepdims=True)
    lens = np.maximum(lens, 1e-6)
    return n / lens


def _depth_hw(depth_img: np.ndarray) -> np.ndarray:
    """Return depth HW with 0 = near, 1 = far."""
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
    c = np.zeros((mp.shape[0] + 1, mp.shape[1]), dtype=np.float64)
    c[1:] = np.cumsum(mp, axis=0)
    vert = (c[k : k + h] - c[0:h]) / float(k)
    c2 = np.zeros((vert.shape[0], vert.shape[1] + 1), dtype=np.float64)
    c2[:, 1:] = np.cumsum(vert, axis=1)
    out = (c2[:, k : k + w] - c2[:, 0:w]) / float(k)
    return out.astype(np.float32)


def _virtual_normals_from_mask(mask_hw: np.ndarray, softness: float) -> tuple[np.ndarray, np.ndarray]:
    h, w = mask_hw.shape
    radius = int(max(0, min(h, w) * 0.02 * float(softness) * 10))
    feather = _box_blur(mask_hw, max(radius, 0))
    feather = np.clip(feather, 0.0, 1.0)
    height = _box_blur(feather, max(radius + 1, 1))
    gy = np.zeros_like(height)
    gx = np.zeros_like(height)
    gy[1:-1, :] = (height[2:, :] - height[:-2, :]) * 0.5
    gx[:, 1:-1] = (height[:, 2:] - height[:, :-2]) * 0.5
    scale = 2.5
    nx = -gx * scale
    ny = -gy * scale
    nz = np.ones_like(height)
    n = np.stack([nx, ny, nz], axis=-1)
    lens = np.linalg.norm(n, axis=-1, keepdims=True)
    n = n / np.maximum(lens, 1e-6)
    return n, feather


def _light_axes(lx: float, ly: float, lz: float) -> tuple[np.ndarray, np.ndarray]:
    """Return (L_n, L_ss).

    L_n  = direction used for N·L (X flipped for estimated normal maps)
    L_ss = direction used for screen-space cone aim + shadow march
           (+X = right of frame, +Y = up)
    """
    lz = max(float(lz), 0.0)
    raw = np.array([float(lx), float(ly), lz], dtype=np.float32)
    nrm = float(np.linalg.norm(raw))
    if nrm < 1e-6:
        raw = np.array([0.0, 0.0, 1.0], dtype=np.float32)
        nrm = 1.0
    ss = raw / nrm
    # Estimated maps: R channel is typically opposite OpenGL +X
    ln = np.array([-ss[0], ss[1], ss[2]], dtype=np.float32)
    ln = ln / max(float(np.linalg.norm(ln)), 1e-6)
    return ln, ss


def _light_map(
    normals: np.ndarray,
    depth: np.ndarray,
    lx: float,
    ly: float,
    lz: float,
    intensity: float,
    point_size: float,
    depth_scale: float,
    gamma: float = 1.0,
) -> np.ndarray:
    """Spotlight + directional form shading. XYZ = widget aim."""
    h, w = depth.shape
    xs = (np.arange(w, dtype=np.float32) + 0.5) / w * 2.0 - 1.0
    ys = 1.0 - (np.arange(h, dtype=np.float32) + 0.5) / h * 2.0
    xx, yy = np.meshgrid(xs, ys)

    ln, ss = _light_axes(lx, ly, lz)
    ax_n, ay_n, az_n = float(ln[0]), float(ln[1]), float(ln[2])
    ax_s, ay_s = float(ss[0]), float(ss[1])

    soft = float(np.clip(point_size, 0.02, 1.5))
    cone_r = 0.12 + soft * 1.10 + (soft * soft) * 0.40

    # Cone follows the widget in SCREEN space (not the flipped N·L axis)
    aim_x = ax_s * 0.22 * min(soft, 1.0)
    aim_y = ay_s * 0.22 * min(soft, 1.0)
    rho = np.sqrt((xx - aim_x) ** 2 + (yy - aim_y) ** 2 + 1e-8)

    inner = cone_r * 0.35
    outer = cone_r * 1.05
    tcone = np.clip((rho - inner) / max(outer - inner, 1e-4), 0.0, 1.0)
    cone = 1.0 - (tcone * tcone * tcone * (tcone * (tcone * 6.0 - 15.0) + 10.0))

    ndotl = (
        normals[..., 0] * ax_n
        + normals[..., 1] * ay_n
        + normals[..., 2] * az_n
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
    steps: int = 28,
    max_range: float = 0.32,
    bias: float = 0.04,
    thickness: float = 0.85,
    softness: float = 0.3,
) -> np.ndarray:
    """
    Screen-space contact shadows from a camera depth map (0=near, 1=far).

    March TOWARD the light in screen space using the widget axes
    (+X = right, +Y = up) so occlusion lands on the side AWAY from the key.
    """
    h, w = depth.shape
    d = depth.astype(np.float32)
    d_lo = float(np.quantile(d, 0.02))
    d_hi = float(np.quantile(d, 0.98))
    span = max(d_hi - d_lo, 1e-4)
    d_n = np.clip((d - d_lo) / span, 0.0, 1.0)

    _ln, ss = _light_axes(lx, ly, lz)
    ax, ay = float(ss[0]), float(ss[1])
    lat = float(np.hypot(ax, ay))
    if lat < 0.08:
        ax, ay = 0.0, 0.35
        lat = 0.35
    ax, ay = ax / lat, ay / lat

    steps = int(max(6, min(int(steps), 48)))
    max_range = float(np.clip(max_range, 0.06, 0.6))
    bias_n = max(float(bias), 0.02)
    thickness_n = max(float(thickness), 0.35)
    soft = float(np.clip(softness, 0.0, 1.0))

    y_idx, x_idx = np.indices((h, w), dtype=np.float32)
    occ = np.zeros((h, w), dtype=np.float32)

    for i in range(1, steps + 1):
        dist = (i / float(steps)) * max_range
        # +X widget → +pixel x (right). +Y widget → -pixel y (up).
        xs = x_idx + ax * dist * (w * 0.5)
        ys = y_idx - ay * dist * (h * 0.5)
        xs_i = np.clip(np.rint(xs).astype(np.int32), 0, w - 1)
        ys_i = np.clip(np.rint(ys).astype(np.int32), 0, h - 1)
        d_samp = d_n[ys_i, xs_i]
        # Occluder nearer than this pixel (0=near). No tight thickness cap —
        # a body vs bed/curtain is a large depth jump and should still shadow.
        delta = d_n - d_samp
        hit = delta > bias_n
        # nearer samples weigh more; fade with march distance
        fade = 1.0 - 0.35 * (i / float(steps))
        occ = np.maximum(occ, hit.astype(np.float32) * fade)

    occ = np.clip(occ, 0.0, 1.0)
    occ = occ * occ
    r = int(round(soft * min(h, w) * 0.012))
    if r > 0:
        occ = _box_blur(occ, r)
        occ = np.clip(occ, 0.0, 1.0)
    # Drop a faint haze floor so only real contact remains
    floor = 0.04
    occ = np.clip((occ - floor) / max(1.0 - floor, 1e-4), 0.0, 1.0)
    return occ.astype(np.float32)


def _one_light(
    normals: np.ndarray,
    depth: np.ndarray,
    lx: float,
    ly: float,
    lz: float,
    intensity: float,
    size: float,
    depth_scale: float,
    cast_shadows: bool,
    shadow_strength: float,
    shadow_softness: float,
) -> np.ndarray:
    if float(intensity) <= 1e-6:
        return np.zeros(depth.shape, dtype=np.float32)
    term = _light_map(
        normals, depth, lx, ly, lz, intensity, size, depth_scale, 1.0
    )
    if cast_shadows and float(shadow_strength) > 1e-6:
        occ = _cast_shadow_ss(
            depth, lx, ly, lz, softness=float(shadow_softness)
        )
        term = term * (1.0 - occ * float(np.clip(shadow_strength, 0.0, 1.0)))
    return term


class LCRelight:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "normal_map": ("IMAGE", {"tooltip": "Normal map (RGB). Same subject framing as the image."}),
                "depth_map": ("IMAGE", {"tooltip": "Depth map. Same subject framing as the image."}),
                "ambient_light": (
                    "FLOAT",
                    {"default": 0.25, "min": 0.0, "max": 1.5, "step": 0.01,
                     "tooltip": "Shadow floor. 0 = pure key."},
                ),
                "depth_scale": (
                    "FLOAT",
                    {"default": 0.5, "min": 0.0, "max": 2.0, "step": 0.01,
                     "tooltip": "Far pixels fall off inside the beam (0 = no depth falloff)."},
                ),
                "light1_x": (
                    "FLOAT",
                    {"default": 0.0, "min": -1.0, "max": 1.0, "step": 0.05,
                     "tooltip": "+X = from the right of the frame."},
                ),
                "light1_y": (
                    "FLOAT",
                    {"default": 0.5, "min": -1.0, "max": 1.0, "step": 0.05,
                     "tooltip": "+Y = from above."},
                ),
                "light1_z": (
                    "FLOAT",
                    {"default": 0.9, "min": 0.0, "max": 1.0, "step": 0.05,
                     "tooltip": "0 = side plane, 1 = front. Negative is ignored."},
                ),
                "light1_intensity": (
                    "FLOAT",
                    {"default": 1.0, "min": 0.0, "max": 4.0, "step": 0.01},
                ),
                "light1_size": (
                    "FLOAT",
                    {"default": 1.0, "min": 0.05, "max": 1.5, "step": 0.01,
                     "tooltip": "Cone width: small = spot, large = flood."},
                ),
                "enable_light_2": ("BOOLEAN", {"default": False}),
                "light2_x": (
                    "FLOAT",
                    {"default": -1.0, "min": -1.0, "max": 1.0, "step": 0.05},
                ),
                "light2_y": (
                    "FLOAT",
                    {"default": 0.0, "min": -1.0, "max": 1.0, "step": 0.05},
                ),
                "light2_z": (
                    "FLOAT",
                    {"default": 0.5, "min": 0.0, "max": 1.0, "step": 0.05},
                ),
                "light2_intensity": (
                    "FLOAT",
                    {"default": 1.0, "min": 0.0, "max": 4.0, "step": 0.01},
                ),
                "light2_size": (
                    "FLOAT",
                    {"default": 0.5, "min": 0.05, "max": 1.5, "step": 0.01},
                ),
                "cast_shadows": ("BOOLEAN", {"default": True}),
                "shadow_strength": (
                    "FLOAT",
                    {"default": 0.5, "min": 0.0, "max": 1.0, "step": 0.01},
                ),
                "shadow_softness": (
                    "FLOAT",
                    {"default": 0.3, "min": 0.0, "max": 1.0, "step": 0.01},
                ),
                "mask_enabled": ("BOOLEAN", {"default": True}),
                "mask_blend": (
                    "FLOAT",
                    {"default": 0.45, "min": 0.0, "max": 1.0, "step": 0.01},
                ),
            },
            "optional": {
                "mask": ("MASK", {"tooltip": "Optional subject mask. Enables virtual-dome normals when mask_enabled."}),
            },
        }

    RETURN_TYPES = ("IMAGE", "MASK")
    RETURN_NAMES = ("image", "debug_mask")
    FUNCTION = "relight"
    CATEGORY = "LC123"

    def relight(
        self,
        image,
        normal_map,
        depth_map,
        ambient_light=0.25,
        depth_scale=0.5,
        light1_x=0.0,
        light1_y=0.5,
        light1_z=0.9,
        light1_intensity=1.0,
        light1_size=1.0,
        enable_light_2=False,
        light2_x=-1.0,
        light2_y=0.0,
        light2_z=0.5,
        light2_intensity=1.0,
        light2_size=0.5,
        cast_shadows=True,
        shadow_strength=0.5,
        shadow_softness=0.3,
        mask_enabled=True,
        mask_blend=0.45,
        mask=None,
        **_ignored,
    ):
        img = _image_np(image)
        norms_in = _image_np(normal_map)
        depths_in = _image_np(depth_map)
        b, h, w, _ = img.shape

        out_frames = []
        debug = []
        for i in range(b):
            rgb = img[i]
            n_img = _resize_map(norms_in[min(i, norms_in.shape[0] - 1)], h, w)
            d_img = _resize_map(depths_in[min(i, depths_in.shape[0] - 1)], h, w)
            normals = _decode_normals(n_img)
            depth = _depth_hw(d_img)

            dbg = np.ones((h, w), dtype=np.float32)
            if mask is not None and mask_enabled:
                mb = _mask_np(mask, h, w)
                if mb is not None:
                    m = mb[min(i, mb.shape[0] - 1)]
                    vnorm, feather = _virtual_normals_from_mask(m, 0.45)
                    mix = float(np.clip(mask_blend, 0.0, 1.0)) * feather[..., None]
                    normals = normals * (1.0 - mix) + vnorm * mix
                    nlen = np.linalg.norm(normals, axis=-1, keepdims=True)
                    normals = normals / np.maximum(nlen, 1e-6)
                    dbg = feather

            term = _one_light(
                normals, depth,
                light1_x, light1_y, light1_z,
                light1_intensity, light1_size, depth_scale,
                bool(cast_shadows), shadow_strength, shadow_softness,
            )
            if enable_light_2:
                term = term + _one_light(
                    normals, depth,
                    light2_x, light2_y, light2_z,
                    light2_intensity, light2_size, depth_scale,
                    bool(cast_shadows), shadow_strength, shadow_softness,
                )

            lit = float(ambient_light) + term
            frame = np.clip(rgb * lit[..., None], 0.0, 1.0)
            out_frames.append(frame)
            debug.append(dbg)

        out = torch.from_numpy(np.stack(out_frames, axis=0).astype(np.float32))
        dbg_t = torch.from_numpy(np.stack(debug, axis=0).astype(np.float32))
        return (out, dbg_t)


NODE_CLASS_MAPPINGS = {"LCRelight": LCRelight}
NODE_DISPLAY_NAME_MAPPINGS = {"LCRelight": "LC Lighting Control 🔦"}
