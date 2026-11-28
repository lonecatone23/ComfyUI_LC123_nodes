"""
Colour science for the LC image nodes, written for LC123 from the published methods:

- Oklab: Björn Ottosson, "A perceptual color space for image processing" (2020), https://bottosson.github.io/posts/oklab/
  (public domain). sRGB transfer curves: IEC 61966-2-1.
- Gamut mapping that keeps hue and lightness and gives up chroma: after Björn Ottosson,
  https://bottosson.github.io/posts/gamutclipping/ .
- Linear Monge-Kantorovich colour mapping: François Pitié, Anil Kokaram, "The linear Monge-Kantorovitch linear colour
  mapping for example-based colour transfer", CVMP 2007.
- Iterative distribution transfer: François Pitié, Anil Kokaram, Rozenn Dahyot, "Automated colour grading using colour
  distribution transfer", CVIU 107(1), 2007.
- Monotone cubic curves: F. N. Fritsch, R. E. Carlson, "Monotone Piecewise Cubic Interpolation", SIAM J. Numer. Anal.
  17(2), 1980.
- Skin hue range: derived from Google's Monk Skin Tone Scale (Ellis Monk; skintone.google, CC BY 4.0).

Everything works on torch tensors with colour in the last dimension.
"""

from __future__ import annotations

import math

import torch

# ---------------------------------------------------------------- Oklab (Ottosson 2020)
_LIN_TO_LMS = ((0.4122214708, 0.5363325363, 0.0514459929),
               (0.2119034982, 0.6806995451, 0.1073969566),
               (0.0883024619, 0.2817188376, 0.6299787005))
_LMS_TO_LAB = ((0.2104542553, 0.7936177850, -0.0040720468),
               (1.9779984951, -2.4285922050, 0.4505937099),
               (0.0259040371, 0.7827717662, -0.8086757660))
_LAB_TO_LMS = ((1.0, 0.3963377774, 0.2158037573),
               (1.0, -0.1055613458, -0.0638541728),
               (1.0, -0.0894841775, -1.2914855480))
_LMS_TO_LIN = ((4.0767416621, -3.3077115913, 0.2309699292),
               (-1.2684380046, 2.6097574011, -0.3413193965),
               (-0.0041960863, -0.7034186147, 1.7076147010))


def _apply(m, x):
    return x @ torch.tensor(m, dtype=x.dtype, device=x.device).T


def srgb_to_linear(x):
    return torch.where(x <= 0.04045, x / 12.92, ((x.clamp_min(0.0) + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(x):
    return torch.where(x <= 0.0031308, x * 12.92, 1.055 * x.clamp_min(0.0) ** (1.0 / 2.4) - 0.055)


def linear_to_oklab(x):
    lms = _apply(_LIN_TO_LMS, x)
    return _apply(_LMS_TO_LAB, torch.sign(lms) * lms.abs() ** (1.0 / 3.0))


def oklab_to_linear(lab):
    lms = _apply(_LAB_TO_LMS, lab)
    return _apply(_LMS_TO_LIN, lms * lms * lms)


def srgb_to_oklab(x):
    return linear_to_oklab(srgb_to_linear(x))


def _chroma(lab):
    return (lab[..., 1:2].square() + lab[..., 2:3].square()).sqrt()


# ---------------------------------------------------------------- gamut mapping (after Ottosson)
def _soft_ceiling(v, knee_start, room):
    """Identity below knee_start, then a tanh approach to knee_start + room (same value and slope at the knee, so no
    crease)."""
    if room <= 1e-6:
        return v
    return torch.where(v > knee_start, knee_start + room * torch.tanh((v - knee_start) / room), v)


def _inside(lin, tol=1e-4):
    return ((lin >= -tol) & (lin <= 1.0 + tol)).all(-1, keepdim=True)


def gamut_map_to_linear(lab, steps=18, max_room=0.15):
    """Oklab -> linear sRGB inside 0..1. Lightness past 0 or 1 is rolled in smoothly (the roll-off is only as wide
    as the overshoot, so an image that stays in range keeps an exact white and black). A colour the screen can't
    show keeps its hue and lightness and loses just enough chroma, found by bisection. In-gamut colours pass
    through untouched."""
    lum = lab[..., 0:1]
    hi = min(max_room, max(0.0, float(lum.max()) - 1.0))
    lo = min(max_room, max(0.0, -float(lum.min())))
    if hi > 0:
        lum = _soft_ceiling(lum, 1.0 - hi, hi)
    if lo > 0:
        lum = -_soft_ceiling(-lum, -lo, lo)
    lab = torch.cat([lum.clamp(0.0, 1.0), lab[..., 1:3]], -1)
    lin = oklab_to_linear(lab)
    bad = ~_inside(lin)
    if not bool(bad.any()):
        return lin.clamp(0.0, 1.0)
    flat_lab, flat_lin = lab.reshape(-1, 3), lin.reshape(-1, 3).clamp(0.0, 1.0)
    idx = bad.reshape(-1).nonzero().squeeze(-1)
    sub = flat_lab[idx]
    keep = torch.zeros_like(sub[:, :1])  # chroma scale known to fit (0 = the grey at this lightness)
    lose = torch.ones_like(keep)  # chroma scale known not to fit
    for _ in range(steps):
        mid = (keep + lose) * 0.5
        fits = _inside(oklab_to_linear(torch.cat([sub[:, :1], sub[:, 1:] * mid], -1)))
        keep = torch.where(fits, mid, keep)
        lose = torch.where(fits, lose, mid)
    flat_lin[idx] = oklab_to_linear(torch.cat([sub[:, :1], sub[:, 1:] * keep], -1)).clamp(0.0, 1.0)
    return flat_lin.reshape(lin.shape)


# ---------------------------------------------------------------- linear Monge-Kantorovich (Pitie & Kokaram 2007)
def mean_cov(pts):
    """Mean and covariance of (N, 3) points, in float64, with a tiny ridge relative to the average variance so a flat
    plate still gives an invertible matrix."""
    p = pts.to(torch.float64)
    mu = p.mean(0)
    c = p - mu
    cov = c.T @ c / max(1, p.shape[0])
    cov = (cov + cov.T) * 0.5
    ridge = float(torch.diagonal(cov).mean().clamp_min(1e-12)) * 1e-6 + 1e-12
    return mu, cov + torch.eye(3, dtype=cov.dtype, device=cov.device) * ridge


def _sym_pow(m, power, floor_rel=0.0):
    vals, vecs = torch.linalg.eigh((m + m.T) * 0.5)
    vals = vals.clamp_min(float(vals.max().clamp_min(1e-12)) * floor_rel if floor_rel else 0.0)
    if power < 0:
        vals = vals.clamp_min(1e-300)
    return vecs @ torch.diag(vals ** power) @ vecs.T


def mkl(mu_s, cov_s, mu_d, cov_d, max_gain=6.0):
    """(A, b) for x -> x @ A.T + b, carrying a Gaussian fit of the source cloud onto the destination's:
    A = S^-1/2 (S^1/2 D S^1/2)^1/2 S^-1/2. Its stretch is limited to max_gain (and 1/max_gain), so a direction with
    almost no colour in the source can't blow sensor noise up into colour blotches."""
    s_half = _sym_pow(cov_s, 0.5)
    s_inv_half = _sym_pow(cov_s, -0.5, floor_rel=1e-8)
    a = s_inv_half @ _sym_pow(s_half @ cov_d @ s_half, 0.5) @ s_inv_half
    vals, vecs = torch.linalg.eigh((a + a.T) * 0.5)
    a = vecs @ torch.diag(vals.clamp(1.0 / max_gain, max_gain)) @ vecs.T
    if not bool(torch.isfinite(a).all()):
        a = torch.eye(3, dtype=a.dtype, device=a.device)
    b = mu_d - mu_s @ a.T
    if not bool(torch.isfinite(b).all()):
        b = torch.zeros_like(b)
    return a, b


# ---------------------------------------------------------------- monotone curves (Fritsch & Carlson 1980)
class MonotoneCurve:
    """Monotone piecewise cubic through (x, y) knots, straight lines past the ends."""

    def __init__(self, x, y):
        x, y = x.to(torch.float32), y.to(torch.float32)
        h = (x[1:] - x[:-1]).clamp_min(1e-12)
        sec = (y[1:] - y[:-1]) / h
        m = torch.empty_like(x)
        m[0], m[-1] = sec[0], sec[-1]
        if x.numel() > 2:
            m[1:-1] = torch.where(sec[:-1] * sec[1:] > 0, (sec[:-1] + sec[1:]) * 0.5, torch.zeros_like(sec[1:]))
        # Fritsch-Carlson step: flat segments get flat ends, and tangents are scaled into the monotone region
        flat = sec.abs() < 1e-12
        alpha = torch.where(flat, torch.zeros_like(sec), m[:-1] / sec.masked_fill(flat, 1.0))
        beta = torch.where(flat, torch.zeros_like(sec), m[1:] / sec.masked_fill(flat, 1.0))
        r = (alpha.square() + beta.square()).sqrt()
        tau = torch.where(r > 3.0, 3.0 / r.clamp_min(1e-12), torch.ones_like(r))
        m0 = torch.where(flat, torch.zeros_like(sec), tau * alpha * sec)
        m1 = torch.where(flat, torch.zeros_like(sec), tau * beta * sec)
        m_left = torch.cat([m0, m[-1:]])
        m_right = torch.cat([m[:1], m1])
        m = torch.minimum(m_left.abs(), m_right.abs()) * torch.sign(m_left)  # both neighbours' limits hold
        self.x, self.y, self.m, self.h = x, y, m, h

    def __call__(self, t):
        x, y, m, h = (v.to(t.device, t.dtype) for v in (self.x, self.y, self.m, self.h))
        shape = t.shape
        t = t.reshape(-1)
        k = (torch.searchsorted(x.contiguous(), t.contiguous(), right=True) - 1).clamp(0, x.numel() - 2)
        hk = h[k]
        s = ((t - x[k]) / hk).clamp(0.0, 1.0)
        s2, s3 = s * s, s * s * s
        val = ((2 * s3 - 3 * s2 + 1) * y[k] + (s3 - 2 * s2 + s) * hk * m[k] + (-2 * s3 + 3 * s2) * y[k + 1]
               + (s3 - s2) * hk * m[k + 1])
        val = torch.where(t < x[0], y[0] + (t - x[0]) * m[0], val)
        val = torch.where(t > x[-1], y[-1] + (t - x[-1]) * m[-1], val)
        return val.reshape(shape)


def _quantiles(v, q):
    s, _ = torch.sort(v.reshape(-1).to(torch.float32))
    pos = q.to(s.device) * (s.numel() - 1)
    i0 = pos.floor().long().clamp(0, s.numel() - 1)
    i1 = (i0 + 1).clamp(max=s.numel() - 1)
    return torch.lerp(s[i0], s[i1], (pos - i0.to(pos.dtype)))


def transfer_curve(src, dst, knots=33, tail=0.002, slopes=(0.25, 4.0)):
    """1-D curve taking src's distribution to dst's: matched quantiles (the extreme tails left out, they are single
    pixels), the correction smoothed once, every segment's slope kept between slopes[0] and slopes[1] (no crushed
    shadows, no blown highlights), and re-centred on the median so the slope limit can't shift the level."""
    q = torch.linspace(tail, 1.0 - tail, knots, device=src.device)
    xs = torch.cummax(_quantiles(src, q), 0).values
    xs = xs + torch.arange(knots, device=xs.device, dtype=xs.dtype) * max(float(xs[-1] - xs[0]), 1e-3) * 1e-4
    ys = _quantiles(dst, q)
    corr = ys - xs
    corr = torch.cat([corr[:1], corr, corr[-1:]])
    corr = corr[:-2] * 0.25 + corr[1:-1] * 0.5 + corr[2:] * 0.25
    ys = torch.cummax(xs + corr, 0).values
    step = xs[1:] - xs[:-1]
    rise = ((ys[1:] - ys[:-1]) / step).clamp(*slopes) * step
    ys2 = torch.cat([ys.new_zeros(1), torch.cumsum(rise, 0)])
    mid = knots // 2
    return MonotoneCurve(xs, ys2 - ys2[mid] + ys[mid])


def _rotations(n, device, dtype):
    """n fixed orthonormal bases, the same on every machine. Their first axes are spread evenly over a half sphere
    (golden-angle spiral; a direction and its opposite give the same projection), each turned a little further about
    itself so the other two axes don't repeat."""
    golden = math.pi * (3.0 - math.sqrt(5.0))
    out = []
    for k in range(n):
        z = 1.0 - (k + 0.5) / n
        r = math.sqrt(max(0.0, 1.0 - z * z))
        a = torch.tensor([r * math.cos(golden * k), r * math.sin(golden * k), z], dtype=torch.float64)
        helper = torch.tensor([1.0, 0.0, 0.0] if abs(z) > 0.9 else [0.0, 0.0, 1.0], dtype=torch.float64)
        u = torch.nn.functional.normalize(helper - a * (helper @ a), dim=0)
        v = torch.linalg.cross(a, u)
        spin = golden * k * 0.5
        u, v = u * math.cos(spin) + v * math.sin(spin), v * math.cos(spin) - u * math.sin(spin)
        out.append(torch.stack([a, u, v]))
    return torch.stack(out).to(device=device, dtype=dtype)


class DistributionTransfer:
    """Iterative distribution transfer (Pitie, Kokaram & Dahyot 2007): rotate the colour cloud, match each axis's
    distribution with a 1-D curve, rotate back, repeat. Stored as a chain, so it is a function of colour that can be
    applied to every pixel after fitting on a sample."""

    def __init__(self, steps):
        self.steps = steps

    @classmethod
    def fit(cls, src, dst, iterations=10):
        if src.shape[0] < 16 or dst.shape[0] < 16:
            return cls([])
        steps, cur = [], src
        for rot in _rotations(iterations, src.device, src.dtype):
            ps, pd = cur @ rot.T, dst @ rot.T
            curves = [transfer_curve(ps[:, c], pd[:, c]) for c in range(3)]
            cur = torch.stack([curves[c](ps[:, c]) for c in range(3)], -1) @ rot
            steps.append((rot, curves))
        return cls(steps)

    def __call__(self, pts):
        for rot, curves in self.steps:
            rot = rot.to(pts.device, pts.dtype)
            p = pts @ rot.T
            pts = torch.stack([curves[c](p[:, c]) for c in range(3)], -1) @ rot
        return pts


# ---------------------------------------------------------------- skin and neutral protection
# Monk Skin Tone Scale, tones 1-10 (Ellis Monk / Google, skintone.google, CC BY 4.0): the skin hue range is the span of
# these hues, widened a little.
_MONK = ("f6ede4", "f3e7db", "f7ead0", "eadaba", "d7bd96", "a07e56", "825c43", "604134", "3a312a", "292420")
_SKIN = None


def _skin_range():
    global _SKIN
    if _SKIN is None:
        rgb = torch.tensor([[int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)] for h in _MONK])
        lab = srgb_to_oklab(rgb)
        hues = torch.atan2(lab[:, 2], lab[:, 1])
        _SKIN = (float(hues.min()) - 0.20, float(hues.max()) + 0.20)
    return _SKIN


def _ramp(v, a, b):
    t = ((v - a) / (b - a)).clamp(0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def skin_membership(lab):
    """0..1 per pixel: how much this colour looks like skin (hue inside the Monk range, a moderate chroma, not black
    or white)."""
    lo, hi = _skin_range()
    h = torch.atan2(lab[..., 2:3], lab[..., 1:2])
    mid, half = (lo + hi) * 0.5, (hi - lo) * 0.5
    off = (torch.remainder(h - mid + math.pi, 2 * math.pi) - math.pi).abs() - half
    w_hue = torch.where(off > 0, torch.cos((off / 0.6).clamp(max=1.0) * math.pi * 0.5) ** 2, torch.ones_like(off))
    c = _chroma(lab)
    w_c = _ramp(c, 0.008, 0.03) * (1.0 - _ramp(c, 0.12, 0.20))
    w_l = _ramp(lab[..., 0:1], 0.12, 0.28) * (1.0 - _ramp(lab[..., 0:1], 0.92, 0.99))
    return (w_hue * w_c * w_l).clamp(0.0, 1.0)


def protect_skin(lab_in, lab_out, amount, chroma_gain=1.35):
    """Skin keeps its own hue (turned back the short way round the colour wheel) and can't gain more than
    chroma_gain times its chroma, in proportion to amount x skin membership. Lightness stays as graded."""
    w = skin_membership(lab_in) * float(amount)
    if not bool((w > 1e-4).any()):
        return lab_out
    h_in = torch.atan2(lab_in[..., 2:3], lab_in[..., 1:2])
    h_out = torch.atan2(lab_out[..., 2:3], lab_out[..., 1:2])
    turn = torch.remainder(h_in - h_out + math.pi, 2 * math.pi) - math.pi
    h = h_out + turn * w
    c_in, c_out = _chroma(lab_in), _chroma(lab_out)
    c = torch.lerp(c_out, torch.minimum(c_out, c_in * chroma_gain + 1e-4), w)
    return torch.cat([lab_out[..., 0:1], c * torch.cos(h), c * torch.sin(h)], -1)


def guard_neutrals(lab_in, lab_out, per_chroma=3.0, cast=0.055):
    """A grey may take a cast but never turn into a colour: chroma is held under cast + per_chroma x the input's
    chroma. Past an input chroma of about 0.09 the limit is outside the sRGB gamut and does nothing."""
    c_in, c_out = _chroma(lab_in), _chroma(lab_out)
    limit = cast + per_chroma * c_in
    scale = torch.where(c_out > limit, limit / c_out.clamp_min(1e-9), torch.ones_like(c_out))
    return torch.cat([lab_out[..., 0:1], lab_out[..., 1:3] * scale], -1)
