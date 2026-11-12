"""
LC Natural Look 🍃
------------------
Tones down what makes a render read as generated, without making it dull:
  loud colours pulled back (only the loudest), orange skin made a touch more neutral, highlights rolled off
  instead of clipped, the glossy large-scale glow calmed while fine texture (not flat skin) is lifted, then the original black
  point, contrast and brightness are given back, with a whisper of grain.
"""

import torch
import torch.nn.functional as F
from nodes import PreviewImage

from .lc_image_tools import _preview
from .lc_temporal import segments, smooth


def _luma(x):
    return x[..., 0:1] * 0.2126 + x[..., 1:2] * 0.7152 + x[..., 2:3] * 0.0722


def _blur(x, r):
    """(B,H,W,C) box blur x3 (close to gaussian). Large radii run on a smaller copy."""
    if r < 1:
        return x
    t = x.movedim(-1, 1)
    h, w = t.shape[-2:]
    f = max(1, int(r) // 6)
    if f > 1:
        t = F.interpolate(t, size=(max(1, h // f), max(1, w // f)), mode="area")
    k = max(1, int(round(r / f)))
    for _ in range(3):
        t = F.avg_pool2d(F.pad(t, (k, k, k, k), mode="replicate"), 2 * k + 1, 1)
    if f > 1:
        t = F.interpolate(t, size=(h, w), mode="bilinear", align_corners=False)
    return t.movedim(1, -1)


def _smoothstep(e0, e1, x):
    t = ((x - e0) / (e1 - e0)).clamp(0, 1)
    return t * t * (3 - 2 * t)


def _skin(x):
    """Soft skin mask from YCbCr (works on light to dark skin)."""
    r, b = x[..., 0:1], x[..., 2:3]
    y = _luma(x)
    cb = 0.5 + (b - y) * 0.5389
    cr = 0.5 + (r - y) * 0.6350
    m = _smoothstep(0.30, 0.34, cb) * (1 - _smoothstep(0.50, 0.54, cb))
    m = m * _smoothstep(0.52, 0.56, cr) * (1 - _smoothstep(0.68, 0.72, cr))
    return m * _smoothstep(0.12, 0.2, y) * (1 - _smoothstep(0.92, 0.98, y))


def _q(l, q):
    flat = l.reshape(l.shape[0], -1)
    if flat.shape[1] > 250_000:
        flat = flat[:, :: flat.shape[1] // 250_000 + 1]
    return torch.quantile(flat, q, dim=1).view(-1, 1, 1, 1)


def natural_look(img, strength, skin_amount, seed):
    k = float(strength)
    x0 = img[..., :3].float()
    x = x0.clone()
    B, H, W, _ = x.shape
    side = min(H, W)
    l0 = _luma(x0)

    # 1) only the loudest colours are pulled toward grey
    chroma = x.max(-1, keepdim=True).values - x.min(-1, keepdim=True).values
    x = x + (_luma(x) - x) * _smoothstep(0.40, 1.0, chroma) * 0.32 * k

    # 2) skin: less orange (red over green), a little less saturated
    skin = _blur(_skin(x), max(1, side // 350))
    s = skin * k * float(skin_amount)
    warm = (x[..., 0:1] - x[..., 1:2]).clamp(min=0)
    x = x + s * torch.cat([-0.18 * warm, 0.04 * warm, 0.08 * warm], -1)
    x = x + (_luma(x) - x) * s * 0.08

    # 3) highlights roll off instead of clipping
    knee = 0.82
    over = (x - knee).clamp(min=0)
    rolled = knee + (1 - knee) * torch.tanh(over / (1 - knee) * 1.4) / torch.tanh(torch.tensor(1.4))
    x = torch.where(x > knee, x + (rolled - x) * min(1.0, 0.85 * k), x)

    # 4) calm the glossy large-scale glow, lift the fine texture. Flat skin is left out (sharpened, a plain neck turns to
    # leather); brows, lashes and hair inside the skin mask have strong fine detail and keep the lift
    x = x - (x - _blur(x, max(3, side // 55))) * 0.07 * k
    fine = x - _blur(x, 1)
    detail = _blur(_luma(fine).square(), 3).clamp_min(0).sqrt() / _blur(_luma(x), 6).clamp_min(0.03)
    flat = 1 - _smoothstep(0.02, 0.04, detail)
    x = x + fine * 0.32 * k * (1 - skin * flat * min(1.0, float(skin_amount)))  # skin 0 = sharpened like the rest

    # 5) give the punch back: black point, contrast and brightness of the original
    l = _luma(x)
    seg = segments(x0)  # a video clip shares these corrections over nearby frames, so it does not pump
    lift = smooth((_q(l, 0.01) - _q(l0, 0.01)).clamp(min=0), seg)
    x = x - lift * (1 - l)
    l = _luma(x)
    m0, m1 = l0.mean((1, 2, 3), keepdim=True), l.mean((1, 2, 3), keepdim=True)
    s0, s1 = l0.std((1, 2, 3), keepdim=True), l.std((1, 2, 3), keepdim=True)
    gain = smooth((s0 / s1.clamp(min=1e-4)).clamp(1.0, 1.2), seg)
    x = x + (l - m1) * (gain - 1) + smooth(m0 - m1, seg) * 0.75

    # 6) a whisper of grain so flat areas do not look airbrushed
    gen = torch.Generator().manual_seed(int(seed))
    x = x + torch.randn(B, H, W, 1, generator=gen) * 0.004 * k
    x = x.clamp(0, 1)
    return torch.cat([x, img[..., 3:]], -1) if img.shape[-1] > 3 else x


class LCNaturalLook(PreviewImage):
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "strength": ("FLOAT", {"default": 0.5, "min": 0.0, "max": 2.0, "step": 0.01,
                                       "tooltip": "How much of the AI look is taken out. 0.4 - 0.75 for most renders "
                                                  "(1 = what 0.5 was before 1.53.15)."}),
                "skin": ("FLOAT", {"default": 0.7, "min": 0.0, "max": 2.0, "step": 0.01,
                                   "tooltip": "How much orange / plastic skin is calmed, and how much flat skin is left out of the "
                                              "fine-texture lift, on top of strength. 0 = skin untouched and sharpened like the "
                                              "rest. 0.75 tested best, even after LC Skin Master."}),
                "seed": ("INT", {"default": 8675309, "min": 0, "max": 0xFFFFFFFF, "control_after_generate": "fixed",
                                 "tooltip": "Seed for the faint grain."}),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "run"
    CATEGORY = "LC123/image"
    OUTPUT_NODE = True
    DESCRIPTION = (
        "Takes the AI look out: loud colours and orange skin calmed, highlights rolled off, glossy glow reduced and "
        "fine texture lifted, with the original black point, contrast and brightness kept. Before/after wipe on the node."
    )

    def run(self, image, strength=1.0, skin=1.0, seed=0):
        strength = float(strength) * 0.5  # doubled scale (old 0.5 = 1.0)
        if strength <= 0:
            return _preview(self, image, image)
        out = natural_look(image.cpu(), strength, skin, seed)
        return _preview(self, out, image)


NODE_CLASS_MAPPINGS = {"LCNaturalLook": LCNaturalLook}
NODE_DISPLAY_NAME_MAPPINGS = {"LCNaturalLook": "LC Natural Look 🍃"}
