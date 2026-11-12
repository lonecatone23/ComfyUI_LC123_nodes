"""
LC Skin Master
--------------
The whole skin chain in one node, every band touched once, in order, on one skin map:
1. clean + pores (fine band): grit out, the skin's own pores crisped or eased, real pore relief added where it is missing
2. even (mid band): blotches evened, lines softened, the pores and the face's shape kept
3. character: freckles where the sun lands, the lines already there deepened, brows and lashes
4. tone + colour (low band, last, on the finished skin): warmth, brightness, rosiness, saturation, shadow lift
Everything is sized to the face width (pores are a fixed share of a face, not of the picture).

Built from an audit of every LC skin node (2026-10-23): one skin finder instead of five, no node undoing the last.
Retouch and skin finding adapted from sd-living-skin by sca-285 (lib_ls/retouch.py and lib_ls/masks.py), MIT License.
Pore relief from LC Skin Texture (texture synthesis adapted from ComfyUI-SkinDetailer, MIT). Tone math from LC Skin
Beauty. Skin finding uses facexlib (MIT): RetinaFace, BiSeNet face parsing and MODNet person matting, about 80 MB
downloaded into models/facexlib on the first run.
"""

from __future__ import annotations

import math
import os

import numpy as np
import torch
import torch.nn.functional as F
from nodes import PreviewImage

from .lc_image_tools import _preview
from .lc_skin_beauty_gpu import _lab_to_rgb, _rgb_to_lab
from .lc_skin_texture import _bundled_bank, _quilt

# ---------------------------------------------------------------- settings and presets
DEFAULTS = dict(strength=1.0, clean=0.3, pores=1.0, add_pores=0.0, pore_size=1.0, even_skin=0.3, wrinkles=-0.10,
                even_colour=0.2, warmth=-0.20, brightness=0.05, rosy=0.03, saturation=-0.05, shadow_lift=0.10,
                pigmentation=0.0, eye_detail=0.5)
_P = {  # anything with freckles keeps pores at 1 or more: crisp freckles on softened skin look painted on
    "Natural": {},
    "Clean Even Tone": dict(clean=0.4, even_skin=0.5, even_colour=0.4, wrinkles=-0.15, eye_detail=0.4),
    "Soft Beauty": dict(clean=0.5, pores=0.9, even_skin=0.6, even_colour=0.4, wrinkles=-0.35, warmth=-0.30, brightness=0.12,
                        shadow_lift=0.2),
    "Editorial Detail": dict(clean=0.2, pores=1.4, add_pores=0.2, even_skin=0.2, wrinkles=0.0, eye_detail=0.8),
    "Real Skin Restore": dict(clean=0.2, pores=1.2, add_pores=0.6, even_skin=0.05, even_colour=0.1, wrinkles=0.0,
                              pigmentation=0.3),
    "Mature Skin": dict(pores=1.1, even_skin=0.2, wrinkles=0.0, even_colour=0.25),
    "Weathered": dict(clean=0.1, pores=1.25, add_pores=0.2, even_skin=0.0, even_colour=0.0, wrinkles=0.6, warmth=0.10,
                      saturation=0.0, pigmentation=0.2, eye_detail=0.6),
    "Body Skin": dict(add_pores=0.3, even_skin=0.35, even_colour=0.3, pigmentation=0.1, eye_detail=0.0),
    "Sun-Kissed": dict(pores=1.05, add_pores=0.15, even_skin=0.25, even_colour=0.1, wrinkles=0.0, warmth=0.30, rosy=0.05,
                       saturation=0.05, pigmentation=0.6),
}
PRESETS = {name: {**DEFAULTS, **p} for name, p in _P.items()}
CUSTOM = "Custom"

# ---------------------------------------------------------------- the retouch (torch, (1, 3, H, W) 0..1)
LUMA = (0.299, 0.587, 0.114)


def _luma(x):
    return (x * x.new_tensor(LUMA).view(1, 3, 1, 1)).sum(1, keepdim=True)


def _gauss_small(x, sigma):
    r = max(1, int(math.ceil(3 * sigma)))
    t = torch.arange(-r, r + 1, device=x.device, dtype=x.dtype)
    k = torch.exp(-0.5 * (t / sigma) ** 2)
    k = k / k.sum()
    c = x.shape[1]
    mode = "reflect" if r < min(x.shape[-2:]) else "replicate"
    x = F.conv2d(F.pad(x, (r, r, 0, 0), mode=mode), k.view(1, 1, 1, -1).expand(c, 1, 1, -1), groups=c)
    return F.conv2d(F.pad(x, (0, 0, r, r), mode=mode), k.view(1, 1, -1, 1).expand(c, 1, -1, 1), groups=c)


def _blur(x, sigma):
    """Gaussian blur; big ones at a lower resolution (same look, a fraction of the cost)."""
    if sigma <= 0.3:
        return x
    if sigma <= 6:
        return _gauss_small(x, sigma)
    f = sigma / 3.0
    h, w = x.shape[-2:]
    small = F.interpolate(x, size=(max(1, int(h / f)), max(1, int(w / f))), mode="area")
    return F.interpolate(_gauss_small(small, 3.0), size=(h, w), mode="bilinear", align_corners=False)


def _band_noise(h, w, lo, hi, seed, device, dtype):
    g = torch.Generator(device="cpu").manual_seed(int(seed) & 0x7FFFFFFF)
    n = torch.randn((1, 1, h, w), generator=g).to(device, dtype)
    b = _blur(n, lo) - _blur(n, hi)
    return b / (b.std() + 1e-6)


def _clean(x, m, amount):
    """Grit out on the skin only: pixel-sized speckle smaller than the picture's own noise level is shrunk away,
    and colour speckle smoothed. Anything bigger or stronger than the noise (pores, freckles, edges) stays."""
    y = _luma(x)
    band = x - _gauss_small(x, 0.8)
    yb = _luma(band)
    local = _gauss_small(yb.square(), 2.0).clamp_min(0).sqrt()
    on = local[m > 0.5]
    if on.numel() < 64:
        return x
    # the noise level is read from the quietest skin: on detailed skin the typical wiggle is real texture, not grit
    sn = float(torch.quantile(on[:: max(1, on.numel() // 200000)].float(), 0.15)) + 1e-4
    grit = yb.clamp(-2.0 * sn, 2.0 * sn) * amount * m  # the small wiggles only
    chroma = x - y
    smooth_c = _gauss_small(chroma, 1.5)
    return x - grit + (smooth_c - chroma) * (amount * m)


def _add_pores(x, where, amount, ref, size, seed):
    """Real pore relief (LC Skin Texture's skin photo, quilted so it never tiles) laid on skin that has none,
    sized to the face. Skin that already has detail gets less."""
    _, _, h, w = x.shape
    ys, xs = torch.nonzero(where[0, 0] > 0.02, as_tuple=True)
    if ys.numel() < 64:
        return x
    y0, y1, x0, x1 = int(ys.min()), int(ys.max()) + 1, int(xs.min()), int(xs.max()) + 1
    ch, cw = y1 - y0, x1 - x0
    f = min(3.0, max(0.5, ref / 900.0 * size))  # the photo's pores are about right on a face 900 px wide
    qh, qw = max(48, int(round(ch / f))), max(48, int(round(cw / f)))
    relief = _quilt(_bundled_bank(1.0), qh, qw, seed)[0, ..., 0][None, None].to(x.device, x.dtype)
    relief = F.interpolate(relief, size=(ch, cw), mode="bicubic", align_corners=False)
    relief = relief - _blur(relief, 6.0 * f)
    wc = where[..., y0:y1, x0:x1]
    energy = (relief.square() * (wc > 0.5)).sum() / (wc > 0.5).sum().clamp_min(1)
    if float(energy) < 1e-8:
        return x
    relief = relief / energy.sqrt()
    yc = _luma(x[..., y0:y1, x0:x1])
    # skin in shadow shows its pores fainter: relief follows the skin's brightness (a dark neck would read as leather)
    local = _blur(yc, 6.0 * f).clamp_min(0.02)
    on = local[wc > 0.5]
    rel = (local / torch.quantile(on[:: max(1, on.numel() // 200000)].float(), 0.75)).clamp(0, 1)
    existing = _blur(yc, 0.6 * f) - _blur(yc, 2.0 * f)
    rms = _blur(existing.square(), 4.0 * f).clamp_min(0).sqrt() / rel.clamp_min(0.15)
    needs = 1.0 / (1.0 + (rms / 0.012).square())
    lit = ((yc - 0.04) / 0.1).clamp(0, 1) * ((0.97 - yc) / 0.1).clamp(0, 1)
    detail = 0.05 * torch.tanh(relief * 0.02 * amount / 0.05) * needs * lit * wc * rel
    out = x.clone()
    out[..., y0:y1, x0:x1] = (x[..., y0:y1, x0:x1] + detail).clamp(0, 1)  # one offset for all channels: tone stays
    return out


def _tone(out, mt, s):
    """Skin colour and light in CIELAB (LC Skin Beauty's maths): warmth, rosiness, brightness, shadow lift,
    saturation. Highlights are eased off so bright skin never blows out."""
    if max(abs(s["warmth"]), abs(s["rosy"]), abs(s["brightness"]), abs(s["saturation"]), s["shadow_lift"]) < 1e-4:
        return out
    rgb = out[0].permute(1, 2, 0)
    lab = _rgb_to_lab(rgb.float())
    L, a, b = lab[..., 0], lab[..., 1], lab[..., 2]
    m = mt[0, 0].float()
    hz = ((L - 68.0) / 28.0).clamp(0, 1)
    m_hl = m * (1.0 - 0.26 * hz)
    b = b + m_hl * s["warmth"] * 9.0  # half of Skin Beauty's coolness: its 1.0 turned skin purple
    a = a + m_hl * (s["warmth"] * 1.5 + s["rosy"] * 9.0)
    L = L + m_hl * s["brightness"] * 12.0 * (1.0 - 0.58 * hz)
    L = L + m_hl * s["shadow_lift"] * 10.0 * (1.0 - L / 100.0).clamp(0, 1) ** 2
    sat = 1.0 + s["saturation"] * 0.45
    a, b = a * (1 - m_hl) + a * sat * m_hl, b * (1 - m_hl) + b * sat * m_hl
    res = _lab_to_rgb(torch.stack([L.clamp(0, 100), a, b], -1)).to(out.dtype)
    return (rgb * (1 - m[..., None]) + res * m[..., None]).permute(2, 0, 1)[None]


def _pigment(x, out, m, ordinary, features, sun, amount, ref, k, seed):
    """LC: freckles and sun mottling that belong to this face. Densest where the sun lands (nose bridge, cheekbones,
    forehead), thicker around the freckles she already has, coloured from her own pigment and laid in as real pigment
    (darkening in linear light), so they shade with the face."""
    _, _, h, w = x.shape
    dev, dt = x.device, x.dtype
    y = _luma(x)
    fs = max(0.6, 0.0045 * ref * k)  # freckle radius
    where = ordinary * (1 - features.clamp(0, 1))
    # her own freckles: small dark spots
    spot = F.relu(_blur(y, 3.0 * fs) - _blur(y, 0.6 * fs))
    on = spot[m > 0.5]
    own = ((spot / (on.std() + 1e-6) - 1.5) / 2.0).clamp(0, 1) * m if on.numel() > 64 else torch.zeros_like(y)
    cluster = _blur(own, max(2.0, 0.06 * ref))
    cluster = cluster / (cluster.amax() + 1e-6)
    sunmap = sun if sun is not None else torch.full_like(y, 0.5)
    dens = (0.2 + 0.8 * sunmap) * (0.6 + 0.8 * cluster)  # body skin gets a light scatter
    # freckles: two sizes, broken up into clusters, each its own darkness
    n1 = _band_noise(h, w, 0.5 * fs, 1.5 * fs, seed + 3, dev, dt)
    n2 = _band_noise(h, w, 0.8 * fs, 2.5 * fs, seed + 4, dev, dt)
    clump = _band_noise(h, w, 3.0 * fs, 12.0 * fs, seed + 5, dev, dt)
    thr = 3.1 - 1.7 * amount ** 0.6 * dens - 0.45 * clump  # the low end shows too
    fr = F.relu(n1 - thr) + 0.7 * F.relu(n2 - thr - 0.15)
    fr = (_blur(fr, 0.3 * fs) / 0.5).clamp(0, 1)
    tone = 0.55 + 0.45 * torch.sigmoid(1.5 * _band_noise(h, w, 1.0 * fs, 4.0 * fs, seed + 6, dev, dt))
    patch = F.relu(_band_noise(h, w, 4.0 * fs, 16.0 * fs, seed + 7, dev, dt)) * dens * 0.18  # faint sun mottling
    a = ((fr * tone * 0.85 + patch) * amount * where).clamp(0, 1)
    # her pigment colour: her darkest spots against the skin around them, else a melanin brown
    lin = x.clamp(0, 1) ** 2.2
    sel = (own > 0.5)[0, 0]
    if int(sel.sum()) > 50:
        around = _blur(lin, 3.0 * fs)
        ratio = (lin[0][:, sel].mean(1) / (around[0][:, sel].mean(1) + 1e-6)).clamp(0.3, 0.97)
        ratio = ratio ** (0.62 / max(0.05, 1 - float(ratio.mean())))  # same hue, full freckle depth
    else:
        ratio = x.new_tensor([0.62, 0.48, 0.36])
    ratio = ratio.view(1, 3, 1, 1).clamp(0.2, 0.97)
    # darkening by f in linear light = multiplying by f ** (1 / 2.2) here; untouched pixels stay exactly as they were
    return out * (1 - a * (1 - ratio)) ** (1 / 2.2)


def _deepen_lines(x, out, where, base, amount, ref):
    """LC: the lines already in the skin become creases: long thin dark valleys (round pores and freckles don't count)
    get a deeper shadow and a faint highlight on the wall that faces the light."""
    y = _luma(x)
    sig = max(0.8, 0.005 * ref)  # crease half-width
    line = torch.zeros_like(y)
    dots = torch.zeros_like(y)
    for sg in (sig, 2.0 * sig, 3.0 * sig):  # fine lines and wider creases; the widest only finds freckles and moles
        b = _blur(y, sg)
        dxx = F.pad(b[..., :, 2:] - 2 * b[..., :, 1:-1] + b[..., :, :-2], (1, 1, 0, 0), mode="replicate")
        dyy = F.pad(b[..., 2:, :] - 2 * b[..., 1:-1, :] + b[..., :-2, :], (0, 0, 1, 1), mode="replicate")
        bx = F.pad(b[..., :, 2:] - b[..., :, :-2], (1, 1, 0, 0), mode="replicate") * 0.5
        dxy = F.pad(bx[..., 2:, :] - bx[..., :-2, :], (0, 0, 1, 1), mode="replicate") * 0.5
        half = torch.sqrt(((dxx - dyy) * 0.5) ** 2 + dxy ** 2)
        l1, l2 = (dxx + dyy) * 0.5 + half, (dxx + dyy) * 0.5 - half  # l1 = curvature across a valley
        if sg < 2.5 * sig:
            line = torch.maximum(line, F.relu(l1 - 2.0 * l2.abs()) * sg * sg)  # long, not round
        dots = torch.maximum(dots, F.relu(l2) * sg * sg)  # dark in every direction: a freckle or mole
    on = line[where > 0.5]
    if on.numel() < 64:
        return out
    p = torch.quantile(on[:: max(1, on.numel() // 200000)].float(), 0.98)
    # freckles and moles stay as they are: round dark dots, grown a little to cover their edges
    pd = torch.quantile(dots[where > 0.5][:: max(1, on.numel() // 200000)].float(), 0.95)
    pigment = ((dots / (pd + 1e-6) - 0.5) / 0.5).clamp(0, 1)
    rd = max(1, int(round(sig)))
    pigment = F.max_pool2d(pigment, 2 * rd + 1, stride=1, padding=rd)
    L = ((line / (p + 1e-6) - 0.1) / 0.6).clamp(0, 1) * where * (1 - pigment)
    L = _blur(L, 0.5 * sig)
    depth = F.relu(_blur(y, 3.0 * sig) - _blur(y, 0.7 * sig))  # how dark the line already is
    # only lines you can already see: faint shading on young skin is not a wrinkle waiting to happen
    L = L * ((depth / _luma(out).clamp(1e-3, 1) - 0.025) / 0.04).clamp(0, 1)
    # the light's direction across the face, from the broad shading
    yb = _luma(base)
    gx = F.pad(yb[..., :, 1:] - yb[..., :, :-1], (0, 1, 0, 0))
    gy = F.pad(yb[..., 1:, :] - yb[..., :-1, :], (0, 0, 0, 1))
    lx, ly = float((gx * where).sum()), float((gy * where).sum())
    n = math.hypot(lx, ly) + 1e-9
    off = max(1, int(round(1.6 * sig)))
    sx, sy = int(round(-lx / n * off)), int(round(-ly / n * off))
    lit = F.relu(torch.roll(L, shifts=(sy, sx), dims=(2, 3)) - L)  # the wall on the far side from the light
    yo = _luma(out).clamp(1e-4, 1)
    frac = (3.5 * depth / yo + 0.12).clamp(max=0.5)  # deeper where already a line, never more than half as bright
    ynew = yo * (1 - amount * frac * L) + amount * 0.05 * lit * where
    return (out * (ynew.clamp(0, 1) / yo)).clamp(0, 1)


def _sun_map(faces, h, w):
    """Where the sun lands on each face, from RetinaFace's eye, nose and mouth points: nose bridge, cheekbones,
    then the forehead. Follows the head's turn and tilt."""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    sun = np.zeros((h, w), np.float32)
    for f in faces:
        lm = np.array(f[4:14], np.float32).reshape(5, 2)
        le, re, nose, ml, mr = lm
        eye, mouth = (le + re) / 2, (ml + mr) / 2
        ed = float(np.linalg.norm(re - le)) + 1e-3
        r = (re - le) / ed
        u = eye - mouth
        u = u / (np.linalg.norm(u) + 1e-3)
        blobs = [(eye * 0.4 + nose * 0.6, 0.35, 0.50, 1.0)]
        for e in (le, re):
            blobs.append((e + (e - eye) * 0.25 - u * 0.6 * ed, 0.45, 0.35, 0.9))
        blobs.append((eye + u * 0.9 * ed, 0.8, 0.35, 0.5))
        for c, sr, su, wgt in blobs:
            dx, dy = xx - c[0], yy - c[1]
            pr, pu = dx * r[0] + dy * r[1], dx * u[0] + dy * u[1]
            sun = np.maximum(sun, wgt * np.exp(-0.5 * ((pr / (sr * ed)) ** 2 + (pu / (su * ed)) ** 2)))
    return sun


def _retouch(x0, skin, delicate, features, s, seed, scale, sun=None, tick=lambda: None, eyes=None):
    _, _, h, w = x0.shape
    ref = scale or 0.25 * min(h, w)
    k = s["pore_size"]
    s1, s2, s3 = max(0.7, 0.007 * ref), max(2.0, 0.035 * ref), max(6.0, 0.12 * ref)  # texture | blemish | tone | base
    m = skin
    d = delicate.clamp(0, 1) * m
    ordinary = (m - d).clamp(0, 1)
    x = _clean(x0, m, s["clean"]) if s["clean"] > 0 else x0  # 1. grit out first, so nothing below sharpens it
    g1, g2, g3 = _blur(x, s1), _blur(x, s2), _blur(x, s3)
    texture, blemish, tone, base = x - g1, g1 - g2, g2 - g3, g3

    def keep_edges(g, sig):
        # clear edges stay whole: only the strongest tenth of the skin's edges (eyelids, lips, nostrils, hair).
        # LC: the original guarded the top 45%, which locked half the face out of the retouch
        y = _luma(g)
        gx = F.pad(y[..., :, 1:] - y[..., :, :-1], (0, 1, 0, 0))
        gy = F.pad(y[..., 1:, :] - y[..., :-1, :], (0, 0, 0, 1))
        grad = torch.sqrt(gx * gx + gy * gy)
        on_skin = grad[m > 0.5]
        if on_skin.numel() > 64:
            sample = on_skin[:: max(1, on_skin.numel() // 200000)].float()
            lo, hi = torch.quantile(sample, 0.90), torch.quantile(sample, 0.98)
        else:
            lo, hi = grad.new_tensor(0.02), grad.new_tensor(0.05)
        edge = ((grad - lo) / (hi - lo + 1e-6)).clamp(0, 1)
        r = max(1, int(round(sig)))
        return 1.0 - _blur(F.max_pool2d(edge, 2 * r + 1, stride=1, padding=r), sig)

    keep_shape, keep_form = keep_edges(g1, s1), keep_edges(g2, s2)
    # smoothing stays inside the skin, clear of its outline
    rr = max(1, int(round(s2)))
    inner = _blur(-F.max_pool2d(-m, 2 * rr + 1, stride=1, padding=rr), s1)

    even = s["even_skin"] * inner * keep_shape  # blemish band: even it, soften dark lines more
    bl_y = _luma(blemish)
    bl_c = blemish - bl_y
    soften = max(0.0, -s["wrinkles"])
    bl_y = bl_y * (1 - even) - bl_y.clamp(max=0.0) * (soften * inner * keep_shape) * (1 - even)
    blemish = bl_y + bl_c * (1 - even)
    t_y = _luma(tone)  # tone band: colour towards the skin's own; delicate skin keeps its colour
    t_c = (tone - t_y) * (1 - s["even_colour"] * (ordinary * inner).clamp(0, 1))
    # LC: blotches bigger than the blemish band get their light and dark evened too (half as hard, real shape kept)
    t_y = t_y * (1 - 0.5 * s["even_skin"] * ordinary * inner * keep_form)
    tone = t_y + t_c
    texture = texture * (1.0 + (s["pores"] - 1.0) * (ordinary * inner + 0.4 * d))  # keep, crisp or ease the pores
    out = base + tone + blemish + texture

    out = out.clamp(0, 1)
    tick()  # bands done
    if s["add_pores"] > 0:  # real relief where the skin has none
        out = _add_pores(out, ordinary * inner * (1 - features.clamp(0, 1)), s["add_pores"], ref, k, seed)
    if s["wrinkles"] > 0:  # 3. character
        out = _deepen_lines(x, out, ordinary * inner * keep_form * (1 - features.clamp(0, 1)), g3, s["wrinkles"], ref)
    if s["pigmentation"] > 0:
        out = _pigment(x, out, m, ordinary, features, sun, s["pigmentation"], ref, k, seed)
    if s["eye_detail"] > 0:  # brows and lashes: crisper and a touch deeper (1 = what 0.5 was before 1.53.13)
        out = out + s["eye_detail"] * 0.6 * features * _luma(x - _blur(x, max(0.8, 0.004 * ref)))
        if eyes:  # LC: the iris ring lifted (eye bench 2026-11-12: the broad pass on the opening muddied iris vs pupil)
            out = _iris_lift(out, x0, eyes, min(1.0, s["eye_detail"]))  # 1 = the full lift
    tick()  # pores and character done
    out = _tone(out.clamp(0, 1), (ordinary + 0.3 * d).clamp(0, 1), s)  # 4. colour and light last, on the finished skin
    return torch.lerp(x0, out.clamp(0, 1), s["strength"])


def _iris_lift(out, x0, eyes, k):
    """The coloured ring around each pupil, lifted toward 0.30x the face's skin brightness (gain at most 1.8).
    The pupil stays dark, and no pixel goes past 0.75x the skin, so catchlights and light irises are left alone."""
    if k <= 0:
        return out
    H, W = out.shape[-2:]
    for cx, cy, R, op, ref in eyes["irises"]:
        ref = ref or eyes.get("ref")
        if not ref:
            continue
        pad = int(R * 2.5) + 4
        l, t, r_, b = max(0, int(cx) - pad), max(0, int(cy) - pad), min(W, int(cx) + pad + 1), min(H, int(cy) + pad + 1)
        if r_ - l < 4 or b - t < 4:
            continue
        yy, xx = torch.meshgrid(torch.arange(t, b, device=out.device, dtype=out.dtype),
                                torch.arange(l, r_, device=out.device, dtype=out.dtype), indexing="ij")
        m = torch.as_tensor(op[t:b, l:r_], dtype=out.dtype, device=out.device)[None, None]
        inner = -F.max_pool2d(-(m > 0.5).to(out.dtype), 3, stride=1, padding=1)  # the darkest spot, at full size
        if float(inner.sum()) > 0:
            bl = _blur(_luma(x0[..., t:b, l:r_]), max(R * 0.5, 0.6))
            i = int(torch.argmin(torch.where(inner > 0.5, bl, bl.new_tensor(9.0))))
            cy, cx = float(yy.flatten()[i]), float(xx.flatten()[i])
        rr = torch.sqrt((yy - cy) ** 2 + (xx - cx) ** 2)[None, None]
        mf = _blur(m, max(0.04 * R / 0.21, 0.7))
        pupil = _blur((rr <= 0.42 * R).to(out.dtype), 0.6)
        ring = (_blur((rr <= R).to(out.dtype), 0.8) - pupil).clamp(0, 1) * mf
        if int((ring > 0.5).sum()) <= 5:
            continue
        o = out[..., t:b, l:r_]
        L = _luma(o).clamp(min=1e-3)
        cur = float(L[ring > 0.5].median())
        g = min(1.8, max(1.0, 0.30 * ref / max(cur, 1e-3)))
        g = 1 + (g - 1) * k
        per_px = torch.minimum(L.new_tensor(g), (0.75 * ref / L).clamp(min=1.0))
        out[..., t:b, l:r_] = o * (1 + (per_px - 1) * ring)
    return out


# ---------------------------------------------------------------- finding the skin (facexlib)
_models = {}
SKIN, L_BROW, R_BROW, L_EYE, R_EYE, GLASSES, L_EAR, R_EAR, EARRING, NOSE, MOUTH, U_LIP, L_LIP, NECK, \
    NECKLACE, CLOTH, HAIR, HAT = range(1, 19)
FACE_SKIN = (SKIN, L_EAR, R_EAR, NOSE, NECK)
BROWS_EYES = (L_BROW, R_BROW, L_EYE, R_EYE)
NOT_SKIN = (L_BROW, R_BROW, L_EYE, R_EYE, GLASSES, EARRING, MOUTH, NECKLACE, CLOTH, HAIR, HAT)
LIPS = (U_LIP, L_LIP)


def _model_dir():
    try:
        import folder_paths
        d = os.path.join(folder_paths.models_dir, "facexlib")
    except Exception:
        d = os.path.join(os.path.dirname(__file__), "models", "facexlib")
    os.makedirs(d, exist_ok=True)
    return d


def _load(name, device):
    key = (name, str(device))
    if key not in _models:
        if name == "detect":
            from facexlib.detection import init_detection_model
            _models[key] = init_detection_model("retinaface_mobile0.25", device=device, model_rootpath=_model_dir())
        elif name == "parse":
            from facexlib.parsing import init_parsing_model
            _models[key] = init_parsing_model("bisenet", device=device, model_rootpath=_model_dir())
        else:
            from facexlib.matting import init_matting_model
            _models[key] = init_matting_model("modnet", device=device, model_rootpath=_model_dir())
    return _models[key]


def _resize(a, h, w):
    return F.interpolate(torch.as_tensor(a, dtype=torch.float32)[None, None], size=(h, w), mode="bilinear",
                         align_corners=False)[0, 0].numpy()


def _box(a, r):
    if r < 1:
        return a
    p = np.pad(a, r + 1, mode="edge")
    c = p.cumsum(0).cumsum(1)
    k = 2 * r + 1
    return (c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k])[: a.shape[0], : a.shape[1]] / (k * k)


def _guided(guide, src, r, eps=1e-3):
    mi, ms = _box(guide, r), _box(src, r)
    a = (_box(guide * src, r) - mi * ms) / (_box(guide * guide, r) - mi * mi + eps)
    b = ms - a * mi
    return _box(a, r) * guide + _box(b, r)


def _dilate(m, r):
    t = torch.as_tensor(m, dtype=torch.float32)[None, None]  # square max as two 1-D passes: big radii stay fast on the CPU
    t = F.max_pool2d(t, (1, 2 * r + 1), stride=1, padding=(0, r))
    return F.max_pool2d(t, (2 * r + 1, 1), stride=1, padding=(r, 0))[0, 0].numpy()


def _to_lab(rgb):
    c = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    m = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = c @ m.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def _prior(rgb):
    """Generic skin likelihood (YCrCb box, soft), for when there is no face."""
    y = rgb @ np.array(LUMA, np.float32)
    cr, cb = (rgb[..., 0] - y) * 0.713 + 0.5, (rgb[..., 2] - y) * 0.564 + 0.5
    s = np.clip(1 - np.abs(cr - 0.60) / 0.09, 0, 1) * np.clip(1 - np.abs(cb - 0.42) / 0.10, 0, 1)
    return s * np.clip((y - 0.08) / 0.1, 0, 1)


class _Gauss:
    def __init__(self, f, shift=None, widen=1.0):
        self.mu = f.mean(0) + (np.array(shift) if shift else 0.0)
        d = f - f.mean(0)
        self.icov = np.linalg.inv((d.T @ d / len(f) + np.eye(f.shape[1]) * 4.0) * widen ** 2)

    def __call__(self, f, tol):
        d = f - self.mu
        return np.exp(-0.5 * np.einsum("...i,ij,...j->...", d, self.icov, d) / (tol * tol))


@torch.no_grad()
def _skin_maps(rgb_full, device, tolerance=1.0, delicate=True, tick=lambda: None):
    """rgb_full (H, W, 3) 0..1 numpy. Skin, delicate share and brows/lashes as full-size 0..1 maps, plus the face width."""
    H, W = rgb_full.shape[:2]
    s = min(1.0, 1024 / max(W, H))
    h, w = max(1, int(H * s)), max(1, int(W * s))
    rgb = F.interpolate(torch.from_numpy(rgb_full).permute(2, 0, 1)[None], size=(h, w), mode="area")[0].permute(1, 2, 0).numpy() \
        if s < 1 else rgb_full
    rgb = np.ascontiguousarray(rgb, dtype=np.float32)
    rgb8 = (rgb * 255).round().clip(0, 255).astype(np.uint8)
    try:
        sc = 512 / max(h, w)
        rh, rw = max(32, int(round(h * sc / 32)) * 32), max(32, int(round(w * sc / 32)) * 32)
        x = F.interpolate((torch.from_numpy(rgb).permute(2, 0, 1)[None].to(device) - 0.5) / 0.5, size=(rh, rw), mode="area")
        _, _, matte = _load("matte", device)(x, True)
        person = F.interpolate(matte, size=(h, w), mode="bilinear", align_corners=False)[0, 0].clamp(0, 1).cpu().numpy()
    except Exception as exc:  # a missing matte only widens the search
        print(f"[LC Skin Master] person matte unavailable ({exc}); using colour alone")
        person = np.ones((h, w), np.float32)
    if person.mean() < 0.01:
        person = np.ones((h, w), np.float32)
    face_skin = np.zeros((h, w), bool)
    cloth = np.zeros((h, w), bool)
    excluded = np.zeros((h, w), np.float32)
    lips = np.zeros((h, w), np.float32)
    feats = np.zeros((h, w), np.float32)
    irises, irises_w, face_ref = [], [], np.zeros((h, w), bool)  # each iris (centre, radius, opening), for eye_detail
    luma_w = rgb @ np.array(LUMA, np.float32)
    faces = []
    try:
        tick()  # person matte done (or skipped)
        det = _load("detect", device).detect_faces(np.ascontiguousarray(rgb8[..., ::-1]), 0.8)
        # box, then the five face points (eyes, nose, mouth corners)
        faces = [tuple(float(v) for v in [*row[:4], *row[5:15]]) for row in (det if det is not None else [])
                 if min(row[2] - row[0], row[3] - row[1]) >= 24]
    except Exception as exc:
        print(f"[LC Skin Master] face detection unavailable ({exc})")
    for x1, y1, x2, y2, *_ in faces:
        cx, cy, side = (x1 + x2) / 2, (y1 + y2) / 2, max(x2 - x1, y2 - y1) * 1.7
        l, t = int(max(0, cx - side / 2)), int(max(0, cy - side / 2 - 0.05 * side))
        r, b = int(min(w, cx + side / 2)), int(min(h, cy + side / 2 + 0.05 * side))
        crop = torch.from_numpy(rgb[t:b, l:r]).permute(2, 0, 1)[None].float().to(device)
        xx = F.interpolate(crop, size=(512, 512), mode="bilinear", align_corners=False)
        xx = (xx - xx.new_tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1)) / xx.new_tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1)
        logits = F.interpolate(_load("parse", device)(xx)[0], size=(b - t, r - l), mode="bilinear", align_corners=False)
        lab_map = np.zeros((h, w), np.int64)
        lab_map[t:b, l:r] = logits.argmax(1)[0].cpu().numpy()
        face_skin |= np.isin(lab_map, FACE_SKIN)
        excluded = np.maximum(excluded, np.isin(lab_map, NOT_SKIN).astype(np.float32))
        cloth |= np.isin(lab_map, (CLOTH, HAIR, HAT))
        lips = np.maximum(lips, np.isin(lab_map, LIPS).astype(np.float32))
        feats = np.maximum(feats, _dilate(np.isin(lab_map, BROWS_EYES).astype(np.float32), max(1, int(0.04 * (x2 - x1)))))
        this_skin = lab_map == SKIN
        face_ref |= this_skin
        ref_f = float(np.median(luma_w[this_skin])) if this_skin.sum() > 100 else None  # each iris vs its own face
        from scipy import ndimage  # each eye opening on its own: the parser sometimes labels both eyes alike
        parts, n_parts = ndimage.label(np.isin(lab_map, (L_EYE, R_EYE)), np.ones((3, 3), bool))
        for j in range(1, n_parts + 1):
            op = parts == j
            if op.sum() < max(4, 30 * s * s):
                continue
            cols = np.nonzero(op.any(0))[0]
            ew = float(cols[-1] - cols[0] + 1) if len(cols) else 0.0
            if ew < 8 * s:
                continue
            R = 0.21 * ew
            inner = op & ~_dilate((~op).astype(np.float32), 1).astype(bool) if op.sum() > 9 else op
            bl = _box(luma_w, max(1, int(round(R * 0.5))))
            cy, cx = np.unravel_index(np.argmin(np.where(inner if inner.any() else op, bl, 9.0)), bl.shape)
            if any(op[int(round(c[1])), int(round(c[0]))] for c in irises_w):
                continue  # the same eye again, from a neighbouring face's crop
            irises_w.append((cx, cy))
            irises.append(((cx + 0.5) / s - 0.5, (cy + 0.5) / s - 0.5, R / s, op, ref_f))
    tick()  # faces found and parsed
    lab = _to_lab(rgb)
    L = np.maximum(lab[..., 0], 12.0)
    f = np.stack([lab[..., 1] / L * 50, lab[..., 2] / L * 50], -1)
    L = lab[..., 0]
    seed = face_skin & (excluded < 0.5)
    if seed.sum() < 300:
        seed = (_prior(rgb) * person) > 0.6
    if seed.sum() < 300:
        skin = _prior(rgb) * person
        dmap = np.zeros_like(skin)
    else:
        p_main = _Gauss(f[seed])(f, 2.0 * tolerance)
        chroma = np.hypot(f[..., 0], f[..., 1])  # skin always has some colour: grey cloth, grey hair and beards don't
        c_seed = float(np.median(chroma[seed]))
        colourful = np.clip((chroma - 0.35 * c_seed) / (0.25 * c_seed + 1e-6), 0, 1)
        Lm, Ls = float(L[seed].mean()), float(L[seed].std()) + 4.0
        p_main *= colourful * np.clip(1.0 - (np.abs(L - Lm) - 2.0 * Ls) / (15.0 * tolerance), 0, 1)
        if delicate:  # lips and thin skin: redder, a little less yellow, often darker; only near ordinary skin
            dark_ok = np.clip(1.0 - (np.abs(L - (Lm - 8.0)) - 2.5 * Ls) / (15.0 * tolerance), 0, 1)
            p_del = _Gauss(f[seed], shift=(8.0, -3.0), widen=1.4)(f, 2.0 * tolerance) * colourful * dark_ok
            r_near = max(2, int(0.03 * max(w, h)))
            near = np.clip(_box(_dilate((p_main > 0.5).astype(np.float32), r_near), r_near), 0, 1)
            p_del = np.maximum(p_del * (1 - p_main) * near, lips)
        else:
            p_del = np.zeros_like(p_main)
        y = lab[..., 0] / 100.0  # knit, hair, beards and lace are far rougher than skin at fine scale
        rough = _box(np.abs(y - _box(y, 1)), 2)
        smooth = np.clip(1.0 - (rough / (float(np.median(rough[seed])) + 1e-3) - 2.2) / 1.5, 0, 1)
        p_main, p_del = p_main * smooth, np.maximum(p_del * smooth, lips)
        # LC: the clothes and hair the parser found around the face teach a "not skin" model (colour and lightness),
        # so a skin-coloured parka or blonde hair outside the face crop stays out
        nots = cloth & ~seed
        if nots.sum() >= 300:
            f3 = np.concatenate([f, L[..., None] * 0.5], -1)
            p_s, p_n = _Gauss(f3[seed])(f3, 2.0 * tolerance), _Gauss(f3[nots])(f3, 2.0)
            keep = np.clip((p_s / (p_s + p_n + 1e-9) - 0.5) / 0.3, 0, 1)
            p_main, p_del = p_main * keep, np.maximum(p_del * keep, lips)
        p_main = np.clip((p_main - 0.25) / 0.45, 0, 1)  # LC: doubtful pixels out; skin is sure of itself
        skin = np.maximum(p_main, p_del)
        skin[face_skin & (excluded < 0.5)] = 1.0
        dmap = p_del
    tick()  # colour model done
    skin = skin * np.clip(person * 1.3, 0, 1) * (1 - excluded)
    luma = rgb @ np.array(LUMA, np.float32)
    rr = max(2, int(0.006 * max(w, h)))
    skin = np.clip(_guided(luma, skin.astype(np.float64), rr, 2e-3), 0, 1)
    dmap = np.clip(_guided(luma, dmap.astype(np.float64), rr, 2e-3), 0, 1) * skin
    tick()  # edges snapped
    widths = sorted((b[2] - b[0]) / s for b in faces)
    scale = float(widths[len(widths) // 2]) if widths else None
    sun = _resize(_sun_map(faces, h, w), H, W) if faces else None
    eyes = {"ref": float(np.median(luma_w[face_ref])) if face_ref.sum() > 100 else None,
            "irises": [(cx, cy, R, _resize(op.astype(np.float32), H, W) if s < 1 else op.astype(np.float32), rf)
                       for cx, cy, R, op, rf in irises]}
    return _resize(skin, H, W), _resize(dmap, H, W), _resize(feats, H, W), sun, scale, len(faces), eyes


def _outlined(image, masks):
    """The before picture for the on-node wipe, with the skin it worked on outlined (like the detailers' preview)."""
    try:
        import comfy.model_management
        dev = comfy.model_management.get_torch_device()
        frames = image[: min(4, image.shape[0]), ..., :3].float()
        h, w = frames.shape[1:3]
        m = F.interpolate(masks[: frames.shape[0]].unsqueeze(1).float().to(dev), size=(h, w), mode="bilinear", align_corners=False)
        inside = (m > 0.5).float()
        k = max(5, int(round(5 * max(h, w) / 768)) | 1)  # the outline keeps its look at any size
        # separable max filter on the GPU: a square k x k one on the CPU took 15 s on a 15 MP picture
        grown = F.max_pool2d(F.max_pool2d(inside, (k, 1), 1, (k // 2, 0)), (1, k), 1, (0, k // 2))
        edge = (grown - inside).clamp(0, 1).permute(0, 2, 3, 1).cpu()
        color = torch.tensor((0.25, 0.9, 1.0)).view(1, 1, 1, 3)
        return frames.cpu() * (1 - edge) + color * edge
    except Exception as e:
        print(f"[LC Skin Master] mask outline skipped: {e}")
        return image


def _frame_mask(mask, i, h, w):
    m = mask[min(i, mask.shape[0] - 1)] if mask.ndim == 3 else mask
    return F.interpolate(m[None, None].float().cpu(), size=(h, w), mode="bilinear", align_corners=False)[0, 0]


# ---------------------------------------------------------------- the node
# progress steps per picture, as (seconds, seconds per megapixel), timed in the node on a 5090 (2026-10-23, 3 and 15 MP):
# matte, faces + parsing, colour model, edge snap (these four run at 1024 px, so size barely matters), bands, character, tone
STEP_COST = ((0.25, 0.0), (0.3, 0.0), (0.65, 0.0), (0.2, 0.0), (0.01, 0.031), (0.01, 0.001), (0.0, 0.002))
PREVIEW_COST = (0.0, 0.1)  # outline + the two preview PNGs, per previewed picture
SLIDERS = [  # name, min, max, step, tooltip (in the order the node works)
    ("strength", 0.0, 1.0, 0.05, "0 = original, 1 = everything below at full."),
    ("clean", 0.0, 1.0, 0.05, "Grit out: pixel speckle and colour noise on the skin. Pores and freckles stay."),
    ("pores", 0.0, 2.0, 0.05, "The skin's own fine texture: 1 = as it is, higher = crisper, lower = softer. "
                              "Keep at 1 or more with pigmentation."),
    ("add_pores", 0.0, 1.0, 0.05, "Real pore relief from a skin photo, on skin that has none (plastic AI skin). "
                                  "Skin that already has detail gets less."),
    ("pore_size", 0.5, 2.0, 0.05, "Size of the added pores and freckles. 1 = sized to the face."),
    ("even_skin", 0.0, 1.0, 0.05, "Spots, blotches and uneven patches evened. The pores and the face's shape are kept."),
    ("wrinkles", -1.0, 1.0, 0.05, "Below 0 softens creases and lines. Above 0 deepens the lines already there into real creases."),
    ("even_colour", 0.0, 1.0, 0.05, "Redness and colour patches pulled towards the skin's own colour."),
    ("pigmentation", 0.0, 1.0, 0.05, "Freckles where the sun lands (nose, cheekbones, forehead), grown from the ones "
                                     "already there and in their colour."),
    ("eye_detail", 0.0, 1.0, 0.05, "Crisper lashes and brows, and the iris lifted around a dark pupil so the eyes look alive. "
                                   "0.5 for everyday use, 1 = the most. Needs a face."),
    ("warmth", -1.0, 1.0, 0.05, "Below 0 cooler (calms orange AI skin), above 0 warmer."),
    ("brightness", -0.5, 1.0, 0.05, "Lighter or darker skin. Highlights are eased off."),
    ("rosy", -0.5, 0.5, 0.05, "Pinker or less pink."),
    ("saturation", -0.5, 0.5, 0.05, "More or less colour in the skin."),
    ("shadow_lift", 0.0, 1.0, 0.05, "Opens up dark skin in shadow."),
]


class LCSkinMaster(PreviewImage):
    @classmethod
    def INPUT_TYPES(cls):
        req = {
            "image": ("IMAGE",),
            "preset": ([CUSTOM, *PRESETS], {"default": "Real Skin Restore", "tooltip": "Natural: grit out, blemishes evened, a touch "
                       "cooler, pores and character kept. Clean Even Tone, Soft Beauty, Editorial Detail (close-ups), Real Skin "
                       "Restore (plastic skin), Mature Skin (age kept), Weathered (lines deepened), Body Skin, Sun-Kissed "
                       "(freckles). Moving a slider switches to Custom."}),
        }
        for name, lo, hi, step, tip in SLIDERS:
            req[name] = ("FLOAT", {"default": DEFAULTS[name], "min": lo, "max": hi, "step": step, "tooltip": tip})
        req["seed"] = ("INT", {"default": 0, "min": 0, "max": 0xFFFFFFFF, "tooltip": "Changes the added pores and freckles."})
        return {
            "required": req,
            "optional": {
                "mask": ("MASK", {"tooltip": "Skin to work on (white). For body skin wire LC Person Mask (face + body). Unwired: faces "
                                             "are found for you, body skin only partly (facexlib, about 80 MB downloaded into "
                                             "models/facexlib on the first run)."}),
                "delicate_skin": ("BOOLEAN", {"default": True, "tooltip": "Lips and other delicate skin are found and treated "
                                                                          "lightly, their colour kept."}),
                "skin_match": ("FLOAT", {"default": 1.0, "min": 0.5, "max": 2.0, "step": 0.05,
                                         "tooltip": "Higher finds more skin (and more skin-coloured cloth)."}),
            },
        }

    RETURN_TYPES = ("IMAGE", "MASK")
    RETURN_NAMES = ("image", "skin_mask")
    FUNCTION = "run"
    CATEGORY = "LC123/image"
    OUTPUT_NODE = True
    DESCRIPTION = ("The whole skin chain in one node: grit out, pores, blemishes, lines, freckles, eyes, skin tone and colour, "
                   "each done once on one face-aware skin map. Presets from a light clean-up to plastic-skin restore, weathered and "
                   "sun-kissed. Outputs the skin_mask for other nodes. On-node before/after wipe.")

    def run(self, image, preset="Real Skin Restore", seed=0, mask=None, delicate_skin=True, skin_match=1.0, **sliders):
        s = dict(PRESETS[preset]) if preset in PRESETS else {k: float(sliders.get(k, v)) for k, v in DEFAULTS.items()}
        if preset in PRESETS:
            s["strength"] = float(sliders.get("strength", 1.0))  # strength is always the node's own
        import comfy.model_management
        device = comfy.model_management.get_torch_device()
        import comfy.utils
        # the bar across the top of the node fills by predicted time, so it does not sit at the end while previews save
        mp = image.shape[1] * image.shape[2] / 1e6
        costs = [a + b * mp for a, b in STEP_COST] * image.shape[0]
        costs.append((PREVIEW_COST[0] + PREVIEW_COST[1] * mp) * min(4, image.shape[0]))
        total = sum(costs)
        bar = comfy.utils.ProgressBar(1000)
        done = [0, 0.0]

        def tick():
            comfy.model_management.throw_exception_if_processing_interrupted()
            if done[0] < len(costs):
                done[1] += costs[done[0]]
                done[0] += 1
            bar.update_absolute(int(1000 * done[1] / total), 1000)
        out, masks = [], []
        for i in range(image.shape[0]):
            frame = image[i:i + 1, ..., :3].float()
            rgb = frame[0].cpu().numpy()
            h, w = rgb.shape[:2]
            skin, deli, feats, sun, scale, nfaces, eyes = _skin_maps(rgb, device, float(skin_match), bool(delicate_skin), tick)
            skin = torch.from_numpy(skin)
            if mask is not None:  # your mask decides where; the found maps still give delicate skin, brows and the face size
                skin = _frame_mask(mask, i, h, w).clamp(0, 1)
            x = frame.permute(0, 3, 1, 2).to(device)
            to = lambda a: torch.as_tensor(a, dtype=x.dtype)[None, None].to(device)
            res = _retouch(x, to(skin), to(deli), to(feats), s, int(seed), scale, None if sun is None else to(sun), tick, eyes)
            tick()  # tone done
            out.append(res.permute(0, 2, 3, 1).cpu())
            masks.append(skin[None].float())
            print(f"[LC Skin Master] {preset}: {nfaces} face(s), skin {float(skin.mean()) * 100:.0f}% of the picture")
        try:
            _models.clear()  # small models: free them between runs
        except Exception:
            pass
        res = _preview(self, torch.cat(out, 0), _outlined(image, torch.cat(masks, 0)))
        bar.update_absolute(1000, 1000)  # previews saved
        res["result"] = (res["result"][0], torch.cat(masks, 0))
        return res


NODE_CLASS_MAPPINGS = {"LCSkinMaster": LCSkinMaster}
NODE_DISPLAY_NAME_MAPPINGS = {"LCSkinMaster": "LC Skin Master ✨ (BETA)"}
