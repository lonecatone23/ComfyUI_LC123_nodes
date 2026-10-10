"""
LC Image tools — self-contained adjustments with on-node preview.
No Darkroom package dependency.
"""

import inspect
import math
import numpy as np
import torch
import torch.nn.functional as F
from .lc_guided import guided as _guided, luma as _guided_luma
from nodes import PreviewImage

from .lc_image_helpers import (
    tensor_to_np, np_to_tensor, srgb_to_linear, linear_to_srgb, blend, luminance,
    _alpha_safe, attach_alpha, preview_frames,
)


def _load_looks():
    try:
        import json, os
        with open(os.path.join(os.path.dirname(__file__), "web", "lc_looks.json"), encoding="utf-8") as f:
            return list(json.load(f)["looks"])
    except Exception:
        return []


LOOKS = _load_looks() + ["Custom"]


def _look_input(default="Custom"):
    """The shared Look dropdown. Always added LAST so saved workflows keep their slider values."""
    return (LOOKS, {
        "default": default,
        "tooltip": "Pick the same look on LC Depth FX, Bloom, Lens Profile, Vignette, Film Stock and Film Grain "
                   "and they match. Custom = your own sliders. Moving a slider switches to Custom.",
    })


def _preview(self, result_tensor, source_tensor=None):
    """Attach after (and optional before) preview images for on-node compare wipe."""
    out = {"ui": {}, "result": (result_tensor,)}
    # An RGBA input is processed as RGB (see _alpha_safe below); put its alpha back on the
    # preview images so a cutout still looks like a cutout on the node.
    alpha = getattr(self, "_lc_alpha", None)

    def shown(t):
        if alpha is not None:
            t = attach_alpha(t, alpha)
        # the wipe shows the first frame, so only the first few frames of a batch are saved
        return preview_frames(t)

    try:
        after = self.save_images(shown(result_tensor), filename_prefix="lc_after")
        out["ui"]["lc_preview"] = after["ui"]["images"]
        if source_tensor is not None:
            before = self.save_images(shown(source_tensor), filename_prefix="lc_before")
            out["ui"]["lc_before"] = before["ui"]["images"]
    except Exception:
        pass
    return out


# ---------------------------------------------------------------------------
# LC Image Adjust (hue / sat / brightness / contrast / sharpness)
# ---------------------------------------------------------------------------
class LCImageAdjust(PreviewImage):
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "hue": ("FLOAT", {
                    "default": 0.0, "min": -1.0, "max": 1.0, "step": 0.05,
                    "tooltip": "Hue shift (−1..1 ≈ ±180°)",
                }),
                "saturation": ("FLOAT", {
                    "default": 0.0, "min": -1.0, "max": 1.0, "step": 0.05,
                    "tooltip": "Saturation offset (−1..1)",
                }),
                "brightness": ("FLOAT", {
                    "default": 0.0, "min": -1.0, "max": 1.0, "step": 0.05,
                    "tooltip": "Brightness offset (−1..1)",
                }),
                "contrast": ("FLOAT", {
                    "default": 0.0, "min": -1.0, "max": 1.0, "step": 0.05,
                    "tooltip": "Contrast offset (−1..1)",
                }),
                "sharpness": ("FLOAT", {
                    "default": 0.0, "min": -1.0, "max": 1.0, "step": 0.05,
                    "tooltip": "Sharpness (−1 soft … 1 sharp)",
                }),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "run"
    CATEGORY = "LC123/image"
    OUTPUT_NODE = True
    DESCRIPTION = (
        "Basic color grade: hue, saturation, brightness, contrast, mild sharpen/soften. Center values are neutral (0). On-node preview with before/after wipe."
    )

    def run(self, image, hue, saturation, brightness, contrast, sharpness):
        # Map −1..1 → internal scales
        hue_deg = float(hue) * 180.0
        sat = float(saturation) * 100.0
        bri = float(brightness) * 100.0
        con = float(contrast) * 100.0
        shp = float(sharpness) * 100.0

        arrays = tensor_to_np(image)
        out = []
        for img in arrays:
            x = np.clip(img, 0, 1).astype(np.float32)
            r, g, b = x[..., 0], x[..., 1], x[..., 2]
            mx = np.maximum(np.maximum(r, g), b)
            mn = np.minimum(np.minimum(r, g), b)
            df = mx - mn
            h = np.zeros_like(mx)
            mask_r = (mx == r) & (df > 1e-8)
            mask_g = (mx == g) & ~mask_r & (df > 1e-8)
            mask_b = (mx == b) & ~mask_r & ~mask_g & (df > 1e-8)
            h[mask_r] = (((g - b) / (df + 1e-8))[mask_r]) % 6
            h[mask_g] = ((b - r) / (df + 1e-8) + 2)[mask_g]
            h[mask_b] = ((r - g) / (df + 1e-8) + 4)[mask_b]
            h = h / 6.0
            s = np.where(mx <= 1e-8, 0.0, df / (mx + 1e-8))
            v = mx

            h = (h + hue_deg / 360.0) % 1.0
            s = np.clip(s + sat / 100.0, 0.0, 1.0)

            c = v * s
            xh = c * (1.0 - np.abs((h * 6.0) % 2.0 - 1.0))
            m = v - c
            z = np.zeros_like(c)
            hi = np.floor(h * 6.0).astype(np.int32) % 6
            rgb = np.zeros_like(x)
            sectors = [
                (c, xh, z), (xh, c, z), (z, c, xh),
                (z, xh, c), (xh, z, c), (c, z, xh),
            ]
            for i, (r0, g0, b0) in enumerate(sectors):
                sel = hi == i
                rgb[sel, 0] = r0[sel] + m[sel]
                rgb[sel, 1] = g0[sel] + m[sel]
                rgb[sel, 2] = b0[sel] + m[sel]

            # brightness
            rgb = np.clip(rgb + bri / 100.0, 0, 1)
            # contrast around 0.5
            f = (259.0 * (con + 255.0)) / (255.0 * (259.0 - con)) if abs(con) > 0.01 else 1.0
            if abs(con) > 0.01:
                rgb = np.clip(f * (rgb - 0.5) + 0.5, 0, 1)
            # mild unsharp / soft
            if abs(shp) > 0.5:
                # simple 3x3 average blur
                pad = np.pad(rgb, ((1, 1), (1, 1), (0, 0)), mode="edge")
                blur = (
                    pad[:-2, :-2] + pad[:-2, 1:-1] + pad[:-2, 2:] +
                    pad[1:-1, :-2] + pad[1:-1, 1:-1] + pad[1:-1, 2:] +
                    pad[2:, :-2] + pad[2:, 1:-1] + pad[2:, 2:]
                ) / 9.0
                if shp > 0:
                    rgb = np.clip(rgb + (rgb - blur) * (shp / 50.0), 0, 1)
                else:
                    t_amt = min(1.0, abs(shp) / 100.0)
                    rgb = np.clip(rgb * (1 - t_amt) + blur * t_amt, 0, 1)
            out.append(rgb.astype(np.float32))
        result = np_to_tensor(out)
        return _preview(self, result, image)



# ---------------------------------------------------------------------------
# LC Auto White Balance
# ---------------------------------------------------------------------------
class LCAutoWhiteBalance(PreviewImage):
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "method": (["Gray World", "White Patch", "Shades of Gray", "Gray Edge"],
                           {"default": "Shades of Gray", "tooltip": "White-balance algorithm."}),
                "minkowski_p": ("FLOAT", {"default": 6, "min": 1.0, "max": 16.0, "step": 0.5, "tooltip": "Minkowski norm p (used by Gray Edge / Shades of Gray)."}),
                "strength": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.05, "tooltip": "0 = original, 1 = full correction."}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "run"
    CATEGORY = "LC123/image"
    OUTPUT_NODE = True
    DESCRIPTION = (
        "Automatic white-balance correction. Pick an algorithm and blend with strength. On-node preview with before/after wipe."
    )

    def run(self, image, method, minkowski_p, strength):
        if strength <= 0:
            return _preview(self, image, image)
        arrays = tensor_to_np(image)
        out = []
        for img in arrays:
            original = img.copy()
            linear = srgb_to_linear(img)
            # Tested 2026-09-30: skipping clipped / near-black pixels (as ChromaGrade does) made the estimate worse on
            # warm and cool casts, with and without a blown highlight, so every pixel is still measured.
            e = np.empty(3, dtype=np.float64)
            for c in range(3):
                ch = linear[..., c]
                if method == "Gray World":
                    e[c] = float(np.mean(ch))
                elif method == "White Patch":
                    e[c] = float(np.percentile(ch, 97.0))
                elif method == "Shades of Gray":
                    v = np.abs(ch).astype(np.float64)
                    e[c] = float(np.mean(v ** minkowski_p) ** (1.0 / minkowski_p))
                else:  # Gray Edge
                    gy, gx = np.gradient(ch.astype(np.float64))
                    mag = np.sqrt(gx * gx + gy * gy)
                    e[c] = float(np.mean(np.abs(mag) ** minkowski_p) ** (1.0 / minkowski_p))
            e = np.clip(e, 1e-6, None)
            gains = (np.mean(e) / e).astype(np.float32)
            corrected = np.clip(linear * gains[None, None, :], 0, 1)
            result = linear_to_srgb(corrected)
            out.append(blend(original, result, strength))
        result = np_to_tensor(out)
        return _preview(self, result, image)


# ---------------------------------------------------------------------------
# LC Sharpen Pro (Clarity + Sharpen)
# ---------------------------------------------------------------------------
class LCClarity(PreviewImage):
    """
    Sharpen Pro. Three stages on luminance only (color is never touched):
      sharpen  = capture sharpening by deconvolution (undoes softness instead of drawing outlines)
      texture  = mid-size detail (pores, fabric, hair, hatching)
      clarity  = large-scale local contrast on an edge-aware base (no dark rings)
    halo caps how far any pixel may overshoot its neighbours. Flat areas are left alone
    based on the noise measured in each image, so gradients and flat anime fills stay clean.
    Presets fill widgets (JS).
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "preset": (
                    [
                        "Natural",
                        "Subtle",
                        "Portrait",
                        "Product",
                        "Landscape",
                        "Crisp",
                        "Lineart",
                        "Anime sharp",
                        "Illustration",
                        "Custom",
                    ],
                    {
                        "default": "Natural",
                        "tooltip": "Starting preset. Moving any slider switches this to Custom.",
                    },
                ),
                "clarity": ("FLOAT", {
                    "default": 0.20, "min": 0.0, "max": 1.0, "step": 0.01,
                    "tooltip": "Large-scale local contrast (punch, depth). 0 = off.",
                }),
                "sharpen": ("FLOAT", {
                    "default": 0.30, "min": 0.0, "max": 1.0, "step": 0.01,
                    "tooltip": "Capture sharpening. Undoes the softness measured in the picture (deconvolution) instead of drawing outlines, so an upscaled 4K image is not over-sharpened. 0 = off.",
                }),
                "strength": ("FLOAT", {
                    "default": 0.7, "min": 0.0, "max": 1.0, "step": 0.01,
                    "tooltip": "Mix with the original. 0 = original, 1 = full effect.",
                }),
                "halo": ("FLOAT", {
                    "default": 0.70, "min": 0.0, "max": 1.0, "step": 0.01,
                    "tooltip": "Halo control. 1 = edges can not overshoot their neighbours (no bright/dark rims). 0 = allow punchy overshoot.",
                }),
                "skin_protect": ("FLOAT", {
                    "default": 0.60, "min": 0.0, "max": 1.0, "step": 0.01,
                    "tooltip": "Less sharpening, texture and clarity on skin, and pores can not be dug into pits. Eyes, lashes and lips still get sharpened. 0 = off (use 0 for anime and lineart).",
                }),
                "radius": ("FLOAT", {
                    "default": 0.30, "min": 0.0, "max": 1.0, "step": 0.01,
                    "tooltip": "Detail size. Low = fine lines and hair. High = softer images and broader structure. Scales with resolution.",
                }),
                "blend_mode": (
                    ["Soft Light", "Hard Light", "Overlay", "Multiply", "Vivid Light", "Linear Light", "Addition"],
                    {"default": "Soft Light", "tooltip": "How clarity is blended. Soft Light is the most natural, Overlay and Hard Light punch harder."},
                ),
                "shadow_protect": ("FLOAT", {
                    "default": 0.25, "min": 0.0, "max": 1.0, "step": 0.01,
                    "tooltip": "Less effect in dark areas (keeps shadow noise down). 0 = full effect.",
                }),
                "highlight_protect": ("FLOAT", {
                    "default": 0.25, "min": 0.0, "max": 1.0, "step": 0.01,
                    "tooltip": "Less effect in bright areas. 0 = full effect.",
                }),
                "texture": ("FLOAT", {
                    "default": 0.15, "min": 0.0, "max": 1.0, "step": 0.01,
                    "tooltip": "Mid-size detail: pores, fabric, fur, pencil hatching. 0 = off.",
                }),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "run"
    CATEGORY = "LC123/image"
    OUTPUT_NODE = True
    DESCRIPTION = (
        "Sharpen Pro: capture sharpening (deconvolution), texture and clarity on luminance only. "
        "Halo control stops rims, flat areas stay clean. Presets fill the sliders."
    )

    @staticmethod
    def _smoothstep(edge0, edge1, x):
        t = torch.clamp((x - edge0) / (edge1 - edge0 + 1e-6), 0.0, 1.0)
        return t * t * (3.0 - 2.0 * t)

    @staticmethod
    def _gblur(t, sigma):
        """Separable gaussian on BCHW, replicate edges."""
        if sigma < 0.2:
            return t
        r = max(1, int(math.ceil(sigma * 3.0)))
        r = min(r, (min(t.shape[2], t.shape[3]) - 1) // 2 or 1)
        c = torch.arange(-r, r + 1, device=t.device, dtype=t.dtype)
        k = torch.exp(-(c * c) / (2.0 * sigma * sigma))
        k = k / k.sum()
        ch = t.shape[1]
        t = F.conv2d(F.pad(t, (r, r, 0, 0), mode="replicate"), k.view(1, 1, 1, -1).expand(ch, 1, 1, -1), groups=ch)
        return F.conv2d(F.pad(t, (0, 0, r, r), mode="replicate"), k.view(1, 1, -1, 1).expand(ch, 1, -1, 1), groups=ch)

    @staticmethod
    def _box(t, r):
        r = int(max(0, round(r)))
        if r < 1:
            return t
        return F.avg_pool2d(F.pad(t, (r, r, r, r), mode="replicate"), 2 * r + 1, stride=1)

    def _guided(self, p, r, eps):
        """Self-guided filter (He et al.): edge-preserving blur, the base for halo-free clarity."""
        mean = self._box(p, r)
        var = (self._box(p * p, r) - mean * mean).clamp(min=0.0)
        a = var / (var + eps)
        b = mean - a * mean
        return self._box(a, r) * p + self._box(b, r)

    @staticmethod
    def _edge_grad(t):
        """Gradient magnitude on B1HW (forward differences, same size)."""
        gx = F.pad(t[:, :, :, 1:] - t[:, :, :, :-1], (0, 1, 0, 0))
        gy = F.pad(t[:, :, 1:, :] - t[:, :, :-1, :], (0, 0, 0, 1))
        return (gx * gx + gy * gy).sqrt()

    def _measure_blur(self, lp):
        """Blur already in the picture, in pixels, per image (B,). Strongest edges are compared before and after an
        extra blur of 1 px: a gaussian edge of width b loses sqrt(b^2 + 1) / b of its slope, so b = 1 / sqrt(r^2 - 1).
        A native render reads about 0.35, a 2x to 4x upscale about 0.5 to 0.7."""
        g0 = self._edge_grad(lp)[:, :, ::2, ::2]
        g1 = self._edge_grad(self._gblur(lp, 1.0))[:, :, ::2, ::2]
        out = []
        for i in range(lp.shape[0]):
            a = g0[i].reshape(-1)
            k = max(16, a.numel() // 200)  # top 0.5 % of edges
            top = torch.topk(a, k).indices
            r = (a[top].mean() / g1[i].reshape(-1)[top].mean().clamp(min=1e-6)).clamp(min=1.02)
            out.append(float(1.0 / torch.sqrt(r * r - 1.0)))
        return out

    def _deconvolve(self, y, sigma, iters):
        """Richardson-Lucy with a gaussian blur model, on linear luminance."""
        obs = y.clamp(min=1e-4)
        est = obs
        for _ in range(iters):
            conv = self._gblur(est, sigma).clamp(min=1e-4)
            est = (est * self._gblur(obs / conv, sigma)).clamp(0.0, 2.0)
        return est

    @staticmethod
    def _to_lin(x):
        return torch.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055).clamp(min=0) ** 2.4)

    @staticmethod
    def _to_srgb(x):
        x = x.clamp(min=0)
        return torch.where(x <= 0.0031308, x * 12.92, 1.055 * x ** (1 / 2.4) - 0.055)

    @staticmethod
    def _blend_clarity(luma, layer, blend_mode):
        if blend_mode == "Soft Light":
            return torch.where(
                layer < 0.5,
                2 * luma * layer + luma ** 2 * (1 - 2 * layer),
                torch.sqrt(luma.clamp(min=1e-6)) * (2 * layer - 1) + 2 * luma * (1 - layer),
            )
        if blend_mode == "Overlay":
            return torch.where(luma < 0.5, 2 * luma * layer, 1 - 2 * (1 - luma) * (1 - layer))
        if blend_mode == "Hard Light":
            return torch.where(layer < 0.5, 2 * luma * layer, 1 - 2 * (1 - luma) * (1 - layer))
        if blend_mode == "Multiply":
            return torch.clamp(2 * luma * layer, 0, 1)
        if blend_mode == "Vivid Light":
            return torch.where(
                layer < 0.5,
                1 - (1 - luma) / (2 * layer + 1e-6),
                luma / (2 * (1 - layer) + 1e-6),
            ).clamp(0, 1)
        if blend_mode == "Linear Light":
            return torch.clamp(luma + 2.0 * layer - 1.0, 0, 1)
        return torch.clamp(luma + layer - 0.5, 0, 1)

    def run(
        self,
        image,
        preset="Natural",
        clarity=0.20,
        sharpen=0.30,
        strength=0.7,
        halo=0.70,
        skin_protect=0.60,
        radius=0.30,
        blend_mode="Soft Light",
        shadow_protect=0.25,
        highlight_protect=0.25,
        texture=0.15,
    ):
        cl = float(max(0.0, min(1.0, clarity)))
        sh = float(max(0.0, min(1.0, sharpen)))
        tx = float(max(0.0, min(1.0, texture)))
        st = float(max(0.0, min(1.0, strength)))
        rad = float(max(0.0, min(1.0, radius)))
        if st <= 0 or (cl <= 1e-6 and sh <= 1e-6 and tx <= 1e-6):
            return _preview(self, image, image)

        src_device = image.device
        try:
            import comfy.model_management as mm
            dev = mm.get_torch_device()
        except Exception:
            dev = src_device
        x = image.to(dev, torch.float32)
        b, h, w, _ = x.shape
        scale = max(0.5, min(h, w) / 1024.0)

        nchw = x.permute(0, 3, 1, 2)
        wts = torch.tensor([0.2126, 0.7152, 0.0722], device=dev).view(1, 3, 1, 1)
        y_lin = (self._to_lin(nchw) * wts).sum(1, keepdim=True)
        lp = self._to_srgb(y_lin)  # perceptual luminance, B1HW

        # Noise floor per image, from the finest band (robust MAD). Anything below it is left alone.
        fine = (lp - self._gblur(lp, 0.8))[:, :, ::2, ::2].abs().reshape(b, -1)
        sn = (fine.median(dim=1).values / 0.6745).clamp(min=0.0015).view(b, 1, 1, 1)
        s_loc = 1.5 * scale
        m1 = self._gblur(lp, s_loc)
        lstd = (self._gblur(lp * lp, s_loc) - m1 * m1).clamp(min=0).sqrt()
        detail_mask = self._smoothstep(1.5 * sn, 5.0 * sn, lstd)

        skin = None
        if skin_protect > 0 and (tx > 0 or cl > 0 or sh > 0):
            try:
                from .lc_skin_beauty import _auto_skin_mask
                arr = x.detach().cpu().numpy()
                skin = torch.from_numpy(np.stack([_auto_skin_mask(a, 0.55, 0.45) for a in arr])).to(dev).unsqueeze(1)
            except Exception:
                skin = None
        skin_keep = 1.0 if skin is None else (1.0 - float(skin_protect) * 0.85 * skin)

        new = lp
        # 1. Capture sharpening: deconvolution undoes the blur instead of adding outlines
        # The deconvolution size follows the blur measured in the picture, with the old size guess as a ceiling:
        # an upscaled 4K picture is not 4x blurrier than 1K, and undoing blur that is not there digs pores into pits.
        if sh > 0:
            parts = []
            for i, blur in enumerate(self._measure_blur(lp)):
                guess = max(0.6, (0.5 + 1.5 * rad) * scale)
                sigma = max(0.6, min(guess, (0.6 + 1.3 * blur) * (0.65 + rad)))
                iters = 4 + int(round(26 * sh))
                est = self._to_srgb(self._deconvolve(y_lin[i:i + 1], sigma, iters))
                d = (est - lp[i:i + 1]) * detail_mask[i:i + 1] * min(1.0, 0.5 + sh)
                # ceiling: the strongest edges may gain at most 60 % slope at sharpen 1 (less at lower settings)
                pick = self._edge_grad(lp[i:i + 1])[:, :, ::2, ::2].reshape(-1)
                top = torch.topk(pick, max(16, pick.numel() // 200)).indices
                g_after = self._edge_grad(lp[i:i + 1] + d)[:, :, ::2, ::2].reshape(-1)[top].mean()
                gain = float(g_after / pick[top].mean().clamp(min=1e-6))
                cap = 1.0 + 0.6 * sh
                if gain > cap:
                    d = d * ((cap - 1.0) / (gain - 1.0))
                parts.append(d)
            d = torch.cat(parts, 0)
            new = new + d * skin_keep

        # 2. Texture: mid band, noise-thresholded
        if tx > 0:
            s1 = 0.7 * scale
            s2 = (2.5 + 3.0 * rad) * scale
            band = self._gblur(new, s1) - self._gblur(new, s2)
            band = band * self._smoothstep(1.0 * sn, 3.0 * sn, band.abs())
            new = new + band * (2.2 * tx) * skin_keep

        # Pore guard: on skin, sharpening and texture may darken a spot by about 3 levels at most (deep pits read
        # as craters), brightening is left alone
        if skin is not None:
            d = new - lp
            dn = d.clamp(max=0.0)
            new = lp + d.clamp(min=0.0) + torch.lerp(dn, dn.clamp(min=-0.012), (float(skin_protect) * skin).clamp(0, 1))

        # Halo control: nothing may overshoot its neighbourhood by more than a set amount
        hr = max(1, int(round(1.0 * scale)))
        k = 2 * hr + 1
        lo = -F.max_pool2d(F.pad(-lp, (hr, hr, hr, hr), mode="replicate"), k, stride=1)
        hi = F.max_pool2d(F.pad(lp, (hr, hr, hr, hr), mode="replicate"), k, stride=1)
        over = 0.004 + 0.14 * (1.0 - float(halo))
        new = torch.maximum(torch.minimum(new, hi + over), lo - over)

        # 3. Clarity: local contrast against an edge-aware base, so no dark rings around subjects
        if cl > 0:
            rc = (6.0 + 34.0 * rad) * scale
            base = self._guided(new, rc, 4e-3)
            layer = (0.5 + (new - base) * 2.0).clamp(0.0, 1.0)
            blended = self._blend_clarity(new, layer, blend_mode)
            mid = (1.0 - (2.0 * new - 1.0) ** 2).clamp(0.25, 1.0)
            new = torch.lerp(new, blended, (cl * mid * skin_keep).clamp(0, 1))

        # Tonal protection
        sp = float(max(0.0, min(1.0, shadow_protect)))
        hp = float(max(0.0, min(1.0, highlight_protect)))
        region = (1.0 - sp * 0.9 * (1.0 - self._smoothstep(0.04, 0.34, lp))) * \
                 (1.0 - hp * 0.9 * self._smoothstep(0.66, 0.95, lp))
        delta = (new - lp) * region

        # Luminance-only: the same brightness change on all three channels keeps color untouched
        out = (nchw + delta).clamp(0.0, 1.0)
        if st < 1.0:
            out = torch.lerp(nchw, out, st)
        result = out.permute(0, 2, 3, 1).to(src_device, image.dtype)
        return _preview(self, result, image)



# ---------------------------------------------------------------------------
# LC Lens FX (CA + vignette + grain)
# ---------------------------------------------------------------------------
class LCLensFX(PreviewImage):
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "chromatic_aberration": ("FLOAT", {"default": 0.42, "min": 0.0, "max": 20.0, "step": 0.05}),
                "vignette": ("FLOAT", {"default": 0.28, "min": 0.0, "max": 2.0, "step": 0.05}),
                "grain_amount": ("FLOAT", {"default": 0.2, "min": 0.0, "max": 20.0, "step": 0.05}),
                "grain_scale": ("FLOAT", {"default": 0.7, "min": 0.5, "max": 20.0, "step": 0.1}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xFFFFFFFF}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "run"
    CATEGORY = "LC123/image"
    OUTPUT_NODE = True
    DEPRECATED = True  # hidden from search; saved workflows still load and run
    DESCRIPTION = (
        "Deprecated: use LC Lens Profile, LC Vignette and LC Film Grain. Still works in saved workflows."
    )

    def run(self, image, chromatic_aberration, vignette, grain_amount, grain_scale, seed):
        device = image.device
        dtype = image.dtype
        b, h, w, _ = image.shape
        x = image.permute(0, 3, 1, 2)
        yy, xx = torch.meshgrid(
            torch.linspace(-1, 1, h, device=device, dtype=dtype),
            torch.linspace(-1, 1, w, device=device, dtype=dtype),
            indexing="ij",
        )
        if chromatic_aberration > 0:
            xa, ya = xx.clone(), yy.clone()
            ar = w / max(h, 1)
            if ar > 1:
                xa = xa * ar
            else:
                ya = ya / ar
            r2 = xa * xa + ya * ya
            shift = chromatic_aberration * 0.005
            center = torch.stack((xx, yy), dim=-1)
            gr = (center * (1 - r2 * shift).unsqueeze(-1)).unsqueeze(0).expand(b, -1, -1, -1)
            gb = (center * (1 + r2 * shift).unsqueeze(-1)).unsqueeze(0).expand(b, -1, -1, -1)
            cr = F.grid_sample(x[:, 0:1], gr, mode="bilinear", padding_mode="border", align_corners=False)
            cg = x[:, 1:2]
            cb = F.grid_sample(x[:, 2:3], gb, mode="bilinear", padding_mode="border", align_corners=False)
            x = torch.cat([cr, cg, cb], dim=1)
        out = x.permute(0, 2, 3, 1)
        if vignette > 0:
            xa, ya = xx.clone(), yy.clone()
            ar = w / max(h, 1)
            if ar > 1:
                xa = xa * ar
            else:
                ya = ya / ar
            r = torch.sqrt(xa * xa + ya * ya)
            mask = (1.0 - r * vignette).clamp(0, 1)
            out = out * mask.view(1, h, w, 1)
        if grain_amount > 0:
            gen = torch.Generator(device=device)
            gen.manual_seed(int(seed) % 0x7FFFFFFFFFFFFFFF)
            gh = max(1, int(h / max(grain_scale, 0.01)))
            gw = max(1, int(w / max(grain_scale, 0.01)))
            grain = torch.rand(b, gh, gw, 1, generator=gen, device=device, dtype=dtype) * 2 - 1
            grain = F.interpolate(grain.permute(0, 3, 1, 2), size=(h, w), mode="bicubic", align_corners=False)
            grain = grain.permute(0, 2, 3, 1)
            out = out + grain * grain_amount * 0.1
        result = out.clamp(0, 1)
        return _preview(self, result, image)


# ---------------------------------------------------------------------------
# LC Lift Gamma Gain (simplified master + RGB)
# ---------------------------------------------------------------------------
class LCLiftGammaGain(PreviewImage):
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "lift": ("FLOAT", {"default": 0.01, "min": -1.0, "max": 1.0, "step": 0.01}),
                "gamma": ("FLOAT", {"default": 1.0, "min": 0.1, "max": 4.0, "step": 0.01}),
                "gain": ("FLOAT", {"default": 0.9, "min": 0.0, "max": 4.0, "step": 0.01}),
                "offset": ("FLOAT", {"default": 0.0, "min": -0.5, "max": 0.5, "step": 0.005}),
                "strength": ("FLOAT", {"default": 0.5, "min": 0.0, "max": 1.0, "step": 0.05}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "run"
    CATEGORY = "LC123/image"
    OUTPUT_NODE = True
    DESCRIPTION = (
        "Lift / gamma / gain style grade (shadows, midtones, highlights) plus offset. On-node preview with before/after wipe."
    )

    def run(self, image, lift, gamma, gain, offset, strength):
        if strength <= 0:
            return _preview(self, image, image)
        arrays = tensor_to_np(image)
        out = []
        for img in arrays:
            original = img.copy()
            lin = srgb_to_linear(img)
            # LGG: ((x + lift) ** gamma) * gain + offset  (per channel same)
            x = np.clip(lin + lift, 0, None)
            x = np.power(x + 1e-8, gamma) * gain + offset
            x = np.clip(x, 0, 1)
            result = linear_to_srgb(x.astype(np.float32))
            out.append(blend(original, result, strength))
        result = np_to_tensor(out)
        return _preview(self, result, image)



# ---------------------------------------------------------------------------
# LC Image RGB
# ---------------------------------------------------------------------------
class LCImageRGB(PreviewImage):
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "r": ("FLOAT", {"default": 0.0, "min": -1.0, "max": 1.0, "step": 0.01,
                               "tooltip": "Red channel offset (-1..1)"}),
                "g": ("FLOAT", {"default": 0.0, "min": -1.0, "max": 1.0, "step": 0.01,
                               "tooltip": "Green channel offset (-1..1)"}),
                "b": ("FLOAT", {"default": 0.0, "min": -1.0, "max": 1.0, "step": 0.01,
                               "tooltip": "Blue channel offset (-1..1)"}),
                "strength": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.05}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "run"
    CATEGORY = "LC123/image"
    OUTPUT_NODE = True
    DESCRIPTION = (
        "Per-channel RGB offset (−1…1) with overall strength. On-node preview + wipe."
    )

    def run(self, image, r, g, b, strength):
        if strength <= 0 or (abs(r) < 1e-6 and abs(g) < 1e-6 and abs(b) < 1e-6):
            return _preview(self, image, image)
        arrays = tensor_to_np(image)
        out = []
        offsets = np.array([r, g, b], dtype=np.float32)
        for img in arrays:
            result = np.clip(img + offsets[None, None, :] * strength, 0, 1).astype(np.float32)
            out.append(result)
        return _preview(self, np_to_tensor(out), image)


# ---------------------------------------------------------------------------
# LC Film Grain (resolution-aware stochastic grain)
# ---------------------------------------------------------------------------
class LCFilmGrain(PreviewImage):
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "grain_size": ("FLOAT", {
                    "default": 1.2, "min": 0.7, "max": 4.0, "step": 0.05,
                    "tooltip": "Grain radius at 1024px reference; scales with resolution.",
                }),
                "strength": ("FLOAT", {
                    "default": 0.5, "min": 0.0, "max": 1.0, "step": 0.05,
                }),
                "radius_variation": ("FLOAT", {
                    "default": 0.0, "min": 0.0, "max": 0.5, "step": 0.05,
                }),
                "color_grain": ("FLOAT", {
                    "default": 0.0, "min": 0.0, "max": 1.0, "step": 0.05,
                    "tooltip": "0 = mono grain, 1 = per-channel chroma grain",
                }),
                "seed": ("INT", {"default": 8675309, "min": 0, "max": 0xFFFFFFFF}),
            },
            "optional": {
                "softness": ("FLOAT", {
                    "default": 0.8, "min": 0.4, "max": 2.0, "step": 0.1,
                }),
                "look": _look_input(),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "run"
    CATEGORY = "LC123/image"
    OUTPUT_NODE = True
    DESCRIPTION = (
        "Film grain overlay with amount, contrast, scale, and mono vs color grain. On-node preview with before/after wipe."
    )

    def run(self, image, grain_size, strength, radius_variation, color_grain, seed, softness=0.8, look="Custom"):
        if strength <= 0:
            return _preview(self, image, image)
        device = image.device
        dtype = image.dtype
        b, h, w, c = image.shape
        # scale grain relative to 1024 reference
        ref = 1024.0
        scale = min(h, w) / ref
        sigma = max(0.3, float(grain_size) * scale * float(softness))
        gen = torch.Generator(device=device)
        gen.manual_seed(int(seed) % 0x7FFFFFFFFFFFFFFF)

        # multi-scale noise
        noise_m = torch.randn(b, 1, h, w, generator=gen, device=device, dtype=dtype)
        noise_c = torch.randn(b, 3, h, w, generator=gen, device=device, dtype=dtype)
        if radius_variation > 0:
            n2 = torch.randn(b, 1, h, w, generator=gen, device=device, dtype=dtype)
            noise_m = noise_m + n2 * radius_variation
            noise_c = noise_c + torch.randn(b, 3, h, w, generator=gen, device=device, dtype=dtype) * radius_variation

        # blur noise (soft grain)
        r = max(1, int(sigma * 2))
        coords = torch.arange(-r, r + 1, dtype=dtype, device=device)
        k = torch.exp(-(coords * coords) / (2 * sigma * sigma + 1e-6))
        k = k / k.sum()
        kh = k.view(1, 1, 1, -1)
        kv = k.view(1, 1, -1, 1)

        def blur(t):
            # t: B,C,H,W
            ch = t.shape[1]
            khc = kh.expand(ch, 1, 1, -1)
            kvc = kv.expand(ch, 1, -1, 1)
            t = F.conv2d(F.pad(t, (r, r, 0, 0), mode="replicate"), khc, groups=ch)
            t = F.conv2d(F.pad(t, (0, 0, r, r), mode="replicate"), kvc, groups=ch)
            return t

        noise_m = blur(noise_m)
        noise_c = blur(noise_c)
        mono = noise_m.permute(0, 2, 3, 1).expand(-1, -1, -1, 3)
        chroma = noise_c.permute(0, 2, 3, 1)
        grain = mono * (1.0 - color_grain) + chroma * color_grain
        # luminance-weighted amount (more visible in midtones)
        lum = image[..., 0:1] * 0.2126 + image[..., 1:2] * 0.7152 + image[..., 2:3] * 0.0722
        weight = (4.0 * lum * (1.0 - lum)).clamp(0.15, 1.0)
        out = (image + grain * strength * 0.18 * weight).clamp(0, 1)
        return _preview(self, out, image)





# ---------------------------------------------------------------------------
# LC Vibrance
# ---------------------------------------------------------------------------
class LCVibrance(PreviewImage):
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "vibrance": ("FLOAT", {
                    "default": 100.0, "min": -100.0, "max": 100.0, "step": 1.0,
                    "tooltip": "Smart saturation — protects already-saturated colors",
                }),
            },
            "optional": {
                "saturation": ("FLOAT", {
                    "default": 0.0, "min": -100.0, "max": 100.0, "step": 1.0,
                    "tooltip": "Uniform saturation (no protection)",
                }),
                "protect_skin": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "Reduce effect on skin-tone hues",
                }),
                "strength": ("FLOAT", {
                    "default": 1.0, "min": 0.0, "max": 1.0, "step": 0.05,
                }),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "run"
    CATEGORY = "LC123/image"
    OUTPUT_NODE = True
    DESCRIPTION = (
        "Smart saturation (vibrance) and optional plain saturation; skin-tone protection. On-node preview with before/after wipe."
    )

    def run(self, image, vibrance=0.0, saturation=0.0, protect_skin=True, strength=1.0):
        if strength <= 0 or (abs(vibrance) < 0.5 and abs(saturation) < 0.5):
            return _preview(self, image, image)
        from .lc_oklab import vibrance as _vibrance  # Oklab chroma scaling: hue never shifts, no clipped patches
        out = []
        for img in tensor_to_np(image):
            original = img.copy()
            result = _vibrance(img, vibrance, saturation, protect_skin)
            out.append(blend(original, result, strength))
        return _preview(self, np_to_tensor(out), image)


# ---------------------------------------------------------------------------
# LC Vignette
# ---------------------------------------------------------------------------
def _vignette_mask(h, w, midpoint, roundness, feather, use_cos4):
    cy, cx = h / 2.0, w / 2.0
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float64)
    dy = (yy - cy) / max(cy, 1e-6)
    dx = (xx - cx) / max(cx, 1e-6)
    if roundness != 1.0:
        dy = dy / max(roundness, 0.01)
    r = np.sqrt(dx * dx + dy * dy)
    if use_cos4:
        cos_theta = 1.0 / np.sqrt(1.0 + r * r)
        falloff = cos_theta ** 4
        transition = np.clip((r - midpoint * 0.8) / max(feather, 0.01), 0.0, 1.0)
        mask = 1.0 - transition * (1.0 - falloff)
    else:
        # print / old-photo vignette: a smooth edge that never reaches 0, so intensity (not a hard cut) decides
        # how dark it gets; high intensity takes it all the way to black
        outer = midpoint + feather * (1.414 - midpoint)
        t = np.clip((r - midpoint) / max(outer - midpoint, 0.01), 0.0, 1.0)
        mask = 1.0 - (t * t * (3.0 - 2.0 * t)) * 0.9
    return mask.astype(np.float32)


class LCVignette(PreviewImage):
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "intensity": ("FLOAT", {
                    "default": 0.25, "min": -1.0, "max": 2.0, "step": 0.05,
                    "tooltip": "Darken edges. Negative = brighten edges. 0.1 - 0.25 = a real lens. "
                               "1 - 2 with cos4 off = an old photo, up to black corners.",
                }),
            },
            "optional": {
                "midpoint": ("FLOAT", {"default": 0.55, "min": 0.0, "max": 1.0, "step": 0.05,
                                       "tooltip": "Where the darkening starts. Lower = closer to the middle."}),
                "roundness": ("FLOAT", {"default": 0.8, "min": 0.3, "max": 2.0, "step": 0.1}),
                "feather": ("FLOAT", {"default": 0.35, "min": 0.02, "max": 2.0, "step": 0.02,
                                      "tooltip": "How soft the edge is. Low = a hard oval, high = a long gentle fade."}),
                "cos4_falloff": ("BOOLEAN", {"default": True,
                                             "tooltip": "On: real lens light falloff. Off: a printed / old-photo vignette "
                                                        "with a smooth edge that can go all the way to black."}),
                "tint_r": ("FLOAT", {"default": 1.0, "min": 0.5, "max": 1.5, "step": 0.05}),
                "tint_g": ("FLOAT", {"default": 1.0, "min": 0.5, "max": 1.5, "step": 0.05}),
                "tint_b": ("FLOAT", {"default": 1.05, "min": 0.5, "max": 1.5, "step": 0.05}),
                "look": _look_input(),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "run"
    CATEGORY = "LC123/image"
    OUTPUT_NODE = True
    DESCRIPTION = (
        "Edge darkening or brightening vignette. On-node preview with before/after wipe."
    )

    def run(self, image, intensity, midpoint=0.55, roundness=0.8, feather=0.35,
            cos4_falloff=True, tint_r=1.0, tint_g=1.0, tint_b=1.05, look="Custom"):
        if abs(intensity) < 0.01:
            return _preview(self, image, image)
        arrays = tensor_to_np(image)
        out = []
        tint = np.array([tint_r, tint_g, tint_b], dtype=np.float32)
        for img in arrays:
            h, w = img.shape[:2]
            mask = _vignette_mask(h, w, midpoint, roundness, feather, cos4_falloff)
            if intensity > 0:
                vig = mask ** (intensity * 2)
            else:
                vig = 1.0 + (1.0 - mask) * abs(intensity)
            result = img.copy()
            for c in range(3):
                if intensity > 0:
                    ch = vig * (1.0 + (tint[c] - 1.0) * (1.0 - mask))
                    result[..., c] = img[..., c] * ch
                else:
                    result[..., c] = img[..., c] * vig * tint[c]
            out.append(np.clip(result, 0, 1).astype(np.float32))
        return _preview(self, np_to_tensor(out), image)


# ---------------------------------------------------------------------------
# LC Bloom
# ---------------------------------------------------------------------------
def _lin(x):
    return torch.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055).clamp(min=0) ** 2.4)


def _srgb(x):
    x = x.clamp(min=0)
    return torch.where(x <= 0.0031308, x * 12.92, 1.055 * x ** (1 / 2.4) - 0.055)


def _shoulder(x, knee=0.8):
    """Soft highlight roll-off instead of a hard clip (linear light)."""
    return torch.where(x < knee, x, knee + (1.0 - knee) * torch.tanh((x - knee) / (1.0 - knee)))


_LUMA_W = (0.2126, 0.7152, 0.0722)


def _luma(t):
    w = torch.tensor(_LUMA_W, device=t.device, dtype=t.dtype).view(1, 3, 1, 1)
    return (t * w).sum(1, keepdim=True)


def _glow_mask(x_srgb, threshold, smoothing):
    luma = _luma(x_srgb)
    lo = threshold * (1.0 - 0.5 * smoothing)
    hi = min(1.0, threshold + 0.5 * smoothing * (1.0 - threshold)) + 1e-4
    t = ((luma - lo) / (hi - lo)).clamp(0, 1)
    return t * t * (3 - 2 * t)


def _pro_mist(image, intensity, threshold, smoothing, radius, saturation, exposure):
    """Black Pro-Mist style diffusion: warm glow from highlights plus gently softened contrast."""
    blur = LCClarity._gblur
    x = image.permute(0, 3, 1, 2).float()
    lin = _lin(x)
    base = min(x.shape[2], x.shape[3])
    src = lin * _glow_mask(x, threshold, smoothing)
    glow = sum(wt * blur(src, s * base * radius) for wt, s in ((0.5, 0.004), (0.3, 0.012), (0.2, 0.03)))
    warm = torch.tensor([1.0, 0.93, 0.82], device=x.device).view(1, 3, 1, 1)
    glow = glow * (1.0 + (warm - 1.0) * min(1.0, saturation))
    gl = _luma(glow)
    glow = gl + (glow - gl) * saturation
    diffuse = blur(lin, 0.01 * base * radius)
    lin = torch.lerp(lin, diffuse, min(0.5, 0.12 * intensity))
    out = _shoulder(lin + glow * intensity * exposure * 0.6)
    return _srgb(out).clamp(0, 1).permute(0, 2, 3, 1).to(image.dtype)


def _halation(image, intensity, threshold, smoothing, radius, saturation, exposure):
    """Film halation: a red-orange glow AROUND bright edges, not a red wash over them (no pink skin)."""
    blur = LCClarity._gblur
    x = image.permute(0, 3, 1, 2).float()
    lin = _lin(x)
    base = min(x.shape[2], x.shape[3])
    mask = _glow_mask(x, threshold, smoothing)
    energy = _luma(lin) * mask
    glow = 0.6 * blur(energy, 0.006 * base * radius) + 0.4 * blur(energy, 0.015 * base * radius)
    glow = glow * (1.0 - mask) ** 0.5
    red = torch.tensor([1.0, 0.32, 0.10], device=x.device).view(1, 3, 1, 1)
    color = 1.0 + (red - 1.0) * max(0.0, min(1.5, saturation))
    out = _shoulder(lin + glow * color * intensity * exposure * 1.2, 0.9)
    return _srgb(out).clamp(0, 1).permute(0, 2, 3, 1).to(image.dtype)


class LCBloom(PreviewImage):
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "intensity": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 4.0, "step": 0.05}),
                "threshold": ("FLOAT", {"default": 0.65, "min": 0.0, "max": 1.0, "step": 0.01}),
                "smoothing": ("FLOAT", {"default": 0.3, "min": 0.0, "max": 1.0, "step": 0.01}),
                "radius": ("FLOAT", {"default": 1.0, "min": 0.1, "max": 5.0, "step": 0.1}),
                "saturation": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 2.0, "step": 0.05}),
                "exposure": ("FLOAT", {"default": 1.0, "min": 0.1, "max": 4.0, "step": 0.05}),
                "mode": (["Bloom", "Pro-Mist", "Halation"], {
                    "default": "Bloom",
                    "tooltip": "Bloom = glow from bright areas. Pro-Mist = a diffusion filter in front of the lens "
                               "(soft glow, gentler contrast). Halation = the red-orange glow film gets around bright edges.",
                }),
            },
            "optional": {
                "look": _look_input(),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "run"
    CATEGORY = "LC123/image"
    OUTPUT_NODE = True
    DESCRIPTION = (
        "Bloom / glow from bright areas. Threshold, radius, intensity. On-node preview + wipe."
    )

    def run(self, image, intensity, threshold, smoothing, radius, saturation, exposure, mode="Bloom", look="Custom"):
        if mode in ("Pro-Mist", "Halation") and intensity > 0:
            fx = _pro_mist if mode == "Pro-Mist" else _halation
            return _preview(self, fx(image, intensity, threshold, smoothing, radius, saturation, exposure), image)
        if intensity <= 0:
            return _preview(self, image, image)
        device = image.device
        dtype = image.dtype
        b, h, w, _ = image.shape
        weights = torch.tensor([0.2126, 0.7152, 0.0722], device=device, dtype=dtype).view(1, 3, 1, 1)
        x = image.permute(0, 3, 1, 2)
        luma = torch.sum(x * weights, dim=1, keepdim=True)
        soft_knee = threshold * smoothing + 1e-5
        soft = torch.clamp(luma - threshold + soft_knee, 0.0, soft_knee * 2.0)
        soft = (soft * soft) / (soft_knee * 4.0 + 1e-7)
        hard = torch.relu(luma - threshold)
        mask = soft + hard
        bloom_src = x * mask
        pyramid = []
        cur = bloom_src
        for _ in range(6):
            if cur.shape[2] < 4 or cur.shape[3] < 4:
                break
            cur = F.interpolate(cur, scale_factor=0.5, mode="bilinear", align_corners=False)
            pyramid.append(cur)
        if not pyramid:
            return _preview(self, image, image)

        def gblur(t, rad):
            if rad < 0.1:
                return t
            k = int(rad * 3.0) | 1
            md = min(t.shape[2], t.shape[3])
            if k > md:
                k = md if md % 2 else md - 1
            if k < 3:
                return t
            # separable approx with box cascade
            r = k // 2
            ch = t.shape[1]
            coords = torch.arange(-r, r + 1, device=device, dtype=dtype)
            ker = torch.exp(-(coords * coords) / (2 * rad * rad + 1e-6))
            ker = ker / ker.sum()
            kh = ker.view(1, 1, 1, -1).expand(ch, 1, 1, -1)
            kv = ker.view(1, 1, -1, 1).expand(ch, 1, -1, 1)
            t = F.conv2d(F.pad(t, (r, r, 0, 0), mode="replicate"), kh, groups=ch)
            t = F.conv2d(F.pad(t, (0, 0, r, r), mode="replicate"), kv, groups=ch)
            return t

        last = gblur(pyramid[-1], radius)
        for j in range(len(pyramid) - 2, -1, -1):
            up = F.interpolate(last, size=(pyramid[j].shape[2], pyramid[j].shape[3]),
                               mode="bilinear", align_corners=False)
            last = gblur(up + pyramid[j], radius)
        bloom = F.interpolate(last, size=(h, w), mode="bilinear", align_corners=False)
        if saturation != 1.0:
            bl = torch.sum(bloom * weights, dim=1, keepdim=True)
            bloom = torch.lerp(bl, bloom, saturation)
        bloom = bloom * intensity * exposure
        final = 1.0 - (1.0 - x) * (1.0 - bloom)
        result = final.permute(0, 2, 3, 1).clamp(0, 1)
        return _preview(self, result, image)




# ---------------------------------------------------------------------------
# LC Image Denoise (edge-preserving)
# ---------------------------------------------------------------------------
class LCImageDenoise(PreviewImage):
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "blur_strength": ("FLOAT", {
                    "default": 1.0, "min": 0.001, "max": 8.0, "step": 0.001,
                    "tooltip": "Gaussian blur strength (sigma)",
                }),
                "edge_preservation": ("FLOAT", {
                    "default": 0.05, "min": 0.001, "max": 0.25, "step": 0.001,
                    "tooltip": "Higher keeps more edges/detail",
                }),
                "radius_multiplier": ("FLOAT", {
                    "default": 1.0, "min": 0.0, "max": 3.0, "step": 0.01,
                    "tooltip": "Kernel radius scale relative to blur strength",
                }),
                "strength": ("FLOAT", {
                    "default": 0.75, "min": 0.0, "max": 1.0, "step": 0.05,
                    "tooltip": "Blend between original (0) and denoised (1)",
                }),
                "mode": (["smart", "legacy"], {
                    "default": "smart",
                    "tooltip": "smart = measures the noise in each image and cleans brightness and colour noise "
                               "separately, keeping pores and hair (uses luma / chroma / keep_detail). "
                               "legacy = the old edge-gated blur (uses blur_strength / edge_preservation / radius_multiplier).",
                }),
                "luma": ("FLOAT", {
                    "default": 1.0, "min": 0.0, "max": 3.0, "step": 0.05,
                    "tooltip": "smart: how hard brightness noise (grain) is cleaned, relative to the noise measured in "
                               "the image. 1 = tuned default, 0 = leave brightness alone.",
                }),
                "chroma": ("FLOAT", {
                    "default": 1.0, "min": 0.0, "max": 3.0, "step": 0.05,
                    "tooltip": "smart: how hard colour noise (blotches, rainbow speckle) is cleaned. Colour edges follow "
                               "the brightness edges, so they stay sharp. 0 = leave colour alone.",
                }),
                "keep_detail": ("FLOAT", {
                    "default": 0.5, "min": 0.0, "max": 1.0, "step": 0.05,
                    "tooltip": "smart: how much of the original texture comes back where it stands clearly above the "
                               "noise (pores, hair, fabric). Smooth areas stay clean either way.",
                }),
            }
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("image", "noise_report")
    OUTPUT_TOOLTIPS = ("The denoised image.", "smart mode: the noise measured in each image (brightness and colour, out of 255).")
    FUNCTION = "run"
    CATEGORY = "LC123/image"
    OUTPUT_NODE = True
    DESCRIPTION = (
        "Denoise. smart: measures the noise in each image, cleans brightness and colour noise separately and keeps "
        "pores and hair. legacy: the old edge-gated blur. On-node preview with before/after wipe."
    )

    def run(self, image, blur_strength, edge_preservation, radius_multiplier, strength=0.75, mode="smart",
            luma=1.0, chroma=1.0, keep_detail=0.5):
        out = self._denoise(image, blur_strength, edge_preservation, radius_multiplier, strength, mode, luma, chroma,
                            keep_detail)
        res, report = out
        p = _preview(self, res, image)
        p["result"] = (res, report)
        return p

    def _denoise(self, image, blur_strength, edge_preservation, radius_multiplier, strength, mode, luma, chroma,
                 keep_detail):
        if mode == "smart":
            from .lc_denoise_smart import smart_denoise
            try:
                import comfy.model_management as mm
                dev = mm.get_torch_device()
            except Exception:
                dev = image.device
            den, reports = smart_denoise(image[..., :3], luma, chroma, keep_detail, device=dev)
            den = torch.lerp(image[..., :3].float(), den, float(strength)).clamp(0, 1)
            if image.shape[-1] == 4:
                den = torch.cat([den, image[..., 3:4]], -1)
            return den, "\n".join(f"image {i + 1}: {r}" for i, r in enumerate(reports))
        if strength <= 0:
            return image, ""
        x = image.permute(0, 3, 1, 2)
        device, dtype = x.device, x.dtype
        sigma = max(float(blur_strength), 1e-3)
        radius = int(round(max(0.0, radius_multiplier) * sigma * 2.0))
        if radius <= 0:
            return image.clamp(0, 1), ""
        max_r = max(1, min(x.shape[-2], x.shape[-1]) // 2)
        radius = min(radius, max_r)

        coords = torch.arange(-radius, radius + 1, device=device, dtype=dtype)
        ker = torch.exp(-(coords * coords) / (2.0 * sigma * sigma + 1e-6))
        ker = ker / ker.sum()
        ch = x.shape[1]
        kh = ker.view(1, 1, 1, -1).expand(ch, 1, 1, -1)
        kv = ker.view(1, 1, -1, 1).expand(ch, 1, -1, 1)
        blurred = F.conv2d(F.pad(x, (radius, radius, 0, 0), mode="replicate"), kh, groups=ch)
        blurred = F.conv2d(F.pad(blurred, (0, 0, radius, radius), mode="replicate"), kv, groups=ch)

        detail = (x - blurred).abs().mean(dim=1, keepdim=True)
        thr = max(float(edge_preservation), 1e-6)
        edge = torch.exp(-(detail * detail) / (2.0 * thr * thr))
        denoised = torch.lerp(x, blurred, edge)
        if strength < 1.0:
            denoised = torch.lerp(x, denoised, float(strength))
        result = denoised.permute(0, 2, 3, 1).clamp(0, 1)
        return result, ""




# ---------------------------------------------------------------------------
# LC Color Match 🎨 (AdaIN / mean-std transfer)
# ---------------------------------------------------------------------------

def _rgb_to_hsv_np(rgb):
    """rgb HxWx3 float 0-1 → h (0-360), s, v"""
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    cmax = np.maximum(np.maximum(r, g), b)
    cmin = np.minimum(np.minimum(r, g), b)
    delta = cmax - cmin
    h = np.zeros_like(r)
    s = np.zeros_like(r)
    m = delta > 1e-7
    mr = m & (cmax == r)
    mg = m & (cmax == g) & ~mr
    mb = m & ~mr & ~mg
    h[mr] = 60.0 * (((g[mr] - b[mr]) / (delta[mr] + 1e-10)) % 6)
    h[mg] = 60.0 * (((b[mg] - r[mg]) / (delta[mg] + 1e-10)) + 2)
    h[mb] = 60.0 * (((r[mb] - g[mb]) / (delta[mb] + 1e-10)) + 4)
    s[m] = delta[m] / (cmax[m] + 1e-10)
    return h, s, cmax


def _hsv_to_rgb_np(h, s, v):
    h = np.mod(h, 360.0)
    c = v * s
    x = c * (1.0 - np.abs((h / 60.0) % 2 - 1.0))
    m = v - c
    z = np.zeros_like(h)
    rgb = np.zeros(h.shape + (3,), dtype=np.float32)
    i = (h // 60.0).astype(np.int32) % 6
    sectors = [
        (c, x, z), (x, c, z), (z, c, x), (z, x, c), (x, z, c), (c, z, x)
    ]
    for idx, (rc, gc, bc) in enumerate(sectors):
        sel = i == idx
        if not np.any(sel):
            continue
        rgb[sel, 0] = rc[sel] + m[sel]
        rgb[sel, 1] = gc[sel] + m[sel]
        rgb[sel, 2] = bc[sel] + m[sel]
    return np.clip(rgb, 0, 1).astype(np.float32)


def _skin_membership_hsv(h, s, v):
    """Soft weight 0-1 for skin-like hues (approx 0–50°), mid sat, not too dark."""
    # circular distance to skin center ~25°
    center, half = 25.0, 28.0
    dh = np.abs(((h - center + 180) % 360) - 180)
    hue_w = np.clip(1.0 - dh / half, 0, 1)
    sat_w = np.clip((s - 0.08) / 0.25, 0, 1) * np.clip((0.75 - s) / 0.25, 0, 1)
    val_w = np.clip((v - 0.12) / 0.25, 0, 1)
    return (hue_w * sat_w * val_w).astype(np.float32)


def apply_skin_protect(original, matched, amount=0.5, max_chroma_gain=1.15):
    """Hold original hue on skin; cap chroma gain. amount 0=off, 1=full protect."""
    amount = float(np.clip(amount, 0, 1))
    if amount <= 1e-4:
        return matched
    h0, s0, v0 = _rgb_to_hsv_np(original)
    h1, s1, v1 = _rgb_to_hsv_np(matched)
    w = _skin_membership_hsv(h0, s0, v0) * amount
    if float(w.max()) < 1e-4:
        return matched
    # circular hue lerp toward original
    d = ((h0 - h1 + 180) % 360) - 180
    h = (h1 + d * w) % 360
    # chroma (sat) cap: don't boost skin sat much past original
    s_cap = np.minimum(s1, s0 * max_chroma_gain + 0.02)
    s = s1 * (1.0 - w) + s_cap * w
    # keep matched value (lightness-ish)
    return _hsv_to_rgb_np(h, s, v1)


class LCColorMatch(PreviewImage):
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE", {
                    "tooltip": "Image to recolor (content)",
                }),
                "method": (["oklab", "oklab + distribution", "adain", "mean_std"], {
                    "default": "oklab",
                    "tooltip": "oklab = matches the whole colour cloud (how the colours relate, not each channel on its "
                               "own) in a colour space built for the eye; out-of-range colours roll off instead of "
                               "clipping. oklab + distribution = also matches the cloud's shape (separate colour "
                               "groups, different tints in shadows and highlights); slower. "
                               "adain = old per-channel mean/std match; mean_std = the same in linear light.",
                }),
                "strength": ("FLOAT", {
                    "default": 1.0, "min": 0.0, "max": 1.0, "step": 0.05,
                    "tooltip": "Blend between original (0) and matched (1)",
                }),
            },
            "optional": {
                "reference": ("IMAGE", {
                    "tooltip": "Color reference (style). If empty, node bypasses and passes image through. oklab methods: "
                               "a reference batch the same size as the image batch matches frame to frame; any other batch "
                               "is pooled into one look (adain / mean_std use only the first reference).",
                }),
                "skin_protect": ("FLOAT", {
                    "default": 0.5,
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.05,
                    "tooltip": "Hold original skin hue and cap skin chroma gain after match (0=off, 1=full). Lightness still follows the match.",
                }),
                "mask": ("MASK", {
                    "tooltip": "White = apply match. Black = keep image. Leave empty for full frame (old graphs unchanged).",
                }),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "run"
    CATEGORY = "LC123/image"
    OUTPUT_NODE = True
    DESCRIPTION = (
        "Match colors to a reference (Oklab full-colour match, or the old AdaIN / mean-std). Optional skin_protect holds face hue. "
        "Optional mask: white = match, black = keep image. No reference = bypass. On-node preview + wipe."
    )

    def run(self, image, method="adain", strength=1.0, reference=None, skin_protect=0.5, mask=None):
        if reference is None:
            out = _preview(self, image, image)
            out["ui"]["lc_bypass"] = ["1"]
            return out
        if strength <= 0:
            return _preview(self, image, image)

        if method.startswith("oklab"):
            from .lc_oklab import match as _oklab_match
            matched = _oklab_match(image[..., :3], reference[..., :3], distribution=(method != "oklab"),
                                   skin_protect=float(skin_protect))
            result = torch.lerp(image[..., :3].float(), matched.float(), float(strength)).clamp(0, 1)
            return self._finish(image, reference, result, mask)

        ref = reference[0:1, ..., :3]  # an RGBA reference: match its color, not its alpha
        arrays = tensor_to_np(image)
        ref_np = tensor_to_np(ref)[0]
        out = []

        def stats(x):
            flat = x.reshape(-1, 3).astype(np.float64)
            mu = flat.mean(axis=0)
            sigma = flat.std(axis=0) + 1e-5
            return mu, sigma

        if method == "mean_std":
            ref_lin = srgb_to_linear(ref_np)
            mu_r, sig_r = stats(ref_lin)
            for img in arrays:
                original = img.copy()
                lin = srgb_to_linear(img)
                mu_s, sig_s = stats(lin)
                matched = (lin - mu_s) * (sig_r / sig_s) + mu_r
                matched = linear_to_srgb(np.clip(matched, 0, 1).astype(np.float32))
                matched = apply_skin_protect(original, matched, skin_protect)
                out.append(blend(original, matched, strength))
        else:
            mu_r, sig_r = stats(ref_np)
            for img in arrays:
                original = img.copy()
                mu_s, sig_s = stats(img)
                matched = (img.astype(np.float64) - mu_s) * (sig_r / sig_s) + mu_r
                matched = np.clip(matched, 0, 1).astype(np.float32)
                matched = apply_skin_protect(original, matched, skin_protect)
                out.append(blend(original, matched, strength))

        return self._finish(image, reference, np_to_tensor(out), mask)

    def _finish(self, image, reference, result, mask):
        """Mask (white = matched, black = original), then the on-node preview."""
        if mask is not None:
            nchw = result[..., :3].movedim(-1, 1)
            m = _mask_to_nchw(mask, nchw)
            if m is not None:
                src = image[..., :3].movedim(-1, 1).to(nchw.device, nchw.dtype)
                if src.shape[-2:] != nchw.shape[-2:]:
                    src = F.interpolate(src, size=nchw.shape[-2:], mode="bilinear", align_corners=False)
                if src.shape[0] != nchw.shape[0]:
                    src = src[:1].expand(nchw.shape[0], -1, -1, -1)
                nchw = nchw * m + src * (1.0 - m)
                result = nchw.clamp(0.0, 1.0).movedim(1, -1)
        return _preview(self, result, image)


# ---------------------------------------------------------------------------
# LC Tone Match — frequency lock (H3 Detail Tone Lock + mask / skin)
# ---------------------------------------------------------------------------
def _gaussian_blur_nchw(image: torch.Tensor, radius: int) -> torch.Tensor:
    height, width = image.shape[-2:]
    radius = int(max(1, min(int(radius), max(1, height - 1), max(1, width - 1))))
    positions = torch.arange(-radius, radius + 1, device=image.device, dtype=image.dtype)
    sigma = max(1.0, radius / 3.0)
    kernel = torch.exp(-(positions * positions) / (2.0 * sigma * sigma))
    kernel = kernel / kernel.sum()
    channels = image.shape[1]
    horizontal = kernel.view(1, 1, 1, -1).expand(channels, 1, 1, -1)
    vertical = kernel.view(1, 1, -1, 1).expand(channels, 1, -1, 1)
    padding_mode = "reflect" if height > radius and width > radius else "replicate"
    blurred = F.conv2d(
        F.pad(image, (radius, radius, 0, 0), mode=padding_mode),
        horizontal,
        groups=channels,
    )
    return F.conv2d(
        F.pad(blurred, (0, 0, radius, radius), mode=padding_mode),
        vertical,
        groups=channels,
    )


def _mask_to_nchw(mask, like_nchw: torch.Tensor) -> torch.Tensor:
    """MASK → NCHW 0..1, resized to like_nchw spatial, batch-matched."""
    if mask is None:
        return None
    m = mask
    if m.ndim == 2:
        m = m.unsqueeze(0)
    if m.ndim == 4:
        m = m.mean(dim=-1) if m.shape[-1] in (1, 3, 4) else m[:, 0]
    m = m.float()
    if m.shape[0] == 1 and like_nchw.shape[0] > 1:
        m = m.expand(like_nchw.shape[0], -1, -1)
    elif m.shape[0] != like_nchw.shape[0]:
        m = m[:1].expand(like_nchw.shape[0], -1, -1)
    if m.shape[-2:] != like_nchw.shape[-2:]:
        m = F.interpolate(
            m.unsqueeze(1), size=like_nchw.shape[-2:], mode="bilinear", align_corners=False
        ).squeeze(1)
    return m.unsqueeze(1).clamp(0.0, 1.0)


class LCToneMatch(PreviewImage):
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE", {
                    "tooltip": "The refined / generated image (Krea2, Klein, Qwen, etc.). High-frequency is taken from here.",
                }),
                "reference": ("IMAGE", {
                    "tooltip": "Original / H3 still. Authority for size, broad lighting, and color.",
                }),
                "tone_match": ("FLOAT", {
                    "default": 0.85, "min": 0.0, "max": 1.0, "step": 0.05,
                    "tooltip": "How hard to restore source low-frequency lighting/color. 0 = off, 1 = full lock.",
                }),
                "refinement_strength": ("FLOAT", {
                    "default": 0.55, "min": 0.0, "max": 1.0, "step": 0.05,
                    "tooltip": "How much of the tone-locked refine is mixed over the source. Lower = less identity drift.",
                }),
                "detail_radius": ("INT", {
                    "default": 32, "min": 2, "max": 64, "step": 2,
                    "tooltip": "Blur radius splitting broad tone from fine detail. ~32 for 1–2 MP.",
                }),
                "skin_protect": ("FLOAT", {
                    "default": 0.5, "min": 0.0, "max": 1.0, "step": 0.05,
                    "tooltip": "Hold reference skin hue after the lock (0 = off). Same idea as Color Match.",
                }),
                "split": (["guided (no halos)", "blur (old)"], {
                    "default": "guided (no halos)",
                    "tooltip": "How broad tone is separated from detail. guided follows the image's own edges: where the two "
                               "images line up (a refined copy of the same picture) there is no bright or dark rim along hard "
                               "edges. If the refiner moved edges a lot, the two are about even. blur is the old Gaussian split.",
                }),
            },
            "optional": {
                "mask": ("MASK", {
                    "tooltip": "White = apply lock. Black = keep image as-is (use for a new head / edited region).",
                }),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "run"
    CATEGORY = "LC123/image"
    OUTPUT_NODE = True
    DESCRIPTION = (
        "Frequency tone lock: reference keeps broad lighting/color, image keeps micro-detail. "
        "Optional mask (white = lock, black = keep image). skin_protect holds reference face hue. "
        "Same job as H3 Detail Tone Lock, for any two images. On-node preview + wipe vs reference."
    )

    def run(self, image, reference, tone_match, refinement_strength, detail_radius, skin_protect=0.5,
            split="guided (no halos)", mask=None):
        source = reference[..., :3].movedim(-1, 1)
        refined = image[..., :3].movedim(-1, 1)
        if refined.shape[0] > source.shape[0]:
            # more images than references: every image is kept, the last reference covers the extra frames
            extra = source[-1:].expand(refined.shape[0] - source.shape[0], -1, -1, -1)
            source = torch.cat([source, extra], dim=0)
        if refined.shape[0] == 1 and source.shape[0] > 1:
            refined = refined.expand(source.shape[0], -1, -1, -1)
        elif source.shape[0] != refined.shape[0]:
            refined = refined[:1].expand(source.shape[0], -1, -1, -1)
        if source.shape[-2:] != refined.shape[-2:]:
            refined = F.interpolate(refined, size=source.shape[-2:], mode="bicubic", align_corners=False)

        if split == "blur (old)":
            source_low = _gaussian_blur_nchw(source, int(detail_radius))
            refined_low = _gaussian_blur_nchw(refined, int(detail_radius))
        else:
            # both split on the image's own luminance: the two low layers share its edges, so no halo
            # box radius half the blur radius covers the same scale; eps 0.01 keeps fine detail out of the low layer
            g = _guided_luma(refined)
            r = max(2, int(detail_radius) // 2)
            source_low = _guided(g, source, r, 1e-2)
            refined_low = _guided(g, refined, r, 1e-2)
        tone_locked = refined + float(tone_match) * (source_low - refined_low)
        mixed = source + float(refinement_strength) * (tone_locked - source)

        m = _mask_to_nchw(mask, source)
        if m is not None:
            mixed = mixed * m + refined * (1.0 - m)

        out = mixed.clamp(0.0, 1.0).movedim(1, -1)
        src_hwc = source.clamp(0.0, 1.0).movedim(1, -1)

        sk = float(skin_protect)
        if sk > 1e-4:
            src_np = tensor_to_np(src_hwc)
            out_np = tensor_to_np(out)
            protected = [
                apply_skin_protect(src_np[min(i, len(src_np) - 1)], frame, sk)
                for i, frame in enumerate(out_np)
            ]
            out = np_to_tensor(protected)

        return _preview(self, out, reference)


# ---------------------------------------------------------------------------
# Built-in film / lens presets (no Darkroom data dependency)
# ---------------------------------------------------------------------------
_BW_STOCKS = {
    "Ilford HP5 Plus 400": dict(w=(0.25, 0.45, 0.30), fog=0.02, toe=1.2, shoulder=1.1, slope=1.0),
    "Ilford Delta 100": dict(w=(0.28, 0.48, 0.24), fog=0.015, toe=1.1, shoulder=1.15, slope=1.05),
    "Kodak Tri-X 400": dict(w=(0.30, 0.42, 0.28), fog=0.03, toe=1.25, shoulder=1.05, slope=0.95),
    "Kodak T-Max 100": dict(w=(0.27, 0.50, 0.23), fog=0.01, toe=1.05, shoulder=1.2, slope=1.1),
    "Fuji Acros 100": dict(w=(0.26, 0.49, 0.25), fog=0.012, toe=1.08, shoulder=1.18, slope=1.08),
    "Ilford Pan F Plus 50": dict(w=(0.29, 0.47, 0.24), fog=0.01, toe=1.0, shoulder=1.2, slope=1.12),
}
_BW_FILTERS = {
    "None": (1.0, 1.0, 1.0),
    "Yellow": (1.0, 0.85, 0.4),
    "Orange": (1.0, 0.55, 0.2),
    "Red": (1.0, 0.25, 0.1),
    "Green": (0.4, 1.0, 0.4),
    "Blue": (0.3, 0.4, 1.0),
}

_COLOR_STOCKS = {
    "Neg / Kodak Portra 400": dict(sat=0.92, toe=1.15, shoulder=1.25, slope=0.95, shadow=(0.02, 0.01, -0.01), highlight=(-0.01, 0.0, 0.02)),
    "Neg / Kodak Portra 160": dict(sat=0.90, toe=1.1, shoulder=1.3, slope=0.92, shadow=(0.015, 0.01, -0.005), highlight=(-0.005, 0.0, 0.015)),
    "Neg / Kodak Gold 200": dict(sat=1.08, toe=1.2, shoulder=1.15, slope=1.0, shadow=(0.03, 0.01, -0.02), highlight=(0.02, 0.01, -0.01)),
    "Neg / Fuji Superia 400": dict(sat=1.05, toe=1.18, shoulder=1.2, slope=0.98, shadow=(-0.01, 0.01, 0.02), highlight=(0.0, 0.01, 0.02)),
    "Neg / Cinestill 800T": dict(sat=0.95, toe=1.25, shoulder=1.1, slope=0.9, shadow=(-0.02, 0.0, 0.04), highlight=(0.03, 0.01, -0.02)),
    "Slide / Fuji Velvia 50": dict(sat=1.25, toe=1.3, shoulder=1.35, slope=1.15, shadow=(0.02, 0.0, -0.02), highlight=(0.03, 0.02, -0.01)),
    "Slide / Kodak Ektachrome E100": dict(sat=1.05, toe=1.15, shoulder=1.25, slope=1.05, shadow=(0.0, 0.0, 0.01), highlight=(0.01, 0.0, 0.0)),
    "Slide / Fuji Provia 100F": dict(sat=1.0, toe=1.1, shoulder=1.2, slope=1.0, shadow=(0.0, 0.005, 0.01), highlight=(0.0, 0.0, 0.01)),
}

_LENS_PROFILES = {
    "Canon EF 50mm f/1.8": dict(k1=-0.08, k2=0.02, ca_r=-1.2, ca_b=1.0, vig=0.35, vig_mid=0.55),
    "Canon EF 24-70mm f/2.8": dict(k1=-0.12, k2=0.04, ca_r=-1.5, ca_b=1.3, vig=0.45, vig_mid=0.5),
    "Nikon AF-S 35mm f/1.8": dict(k1=-0.1, k2=0.025, ca_r=-1.0, ca_b=0.9, vig=0.3, vig_mid=0.55),
    "Nikon AF-S 85mm f/1.4": dict(k1=0.04, k2=-0.01, ca_r=-0.6, ca_b=0.5, vig=0.2, vig_mid=0.6),
    "Sony FE 55mm f/1.8": dict(k1=-0.06, k2=0.015, ca_r=-0.8, ca_b=0.7, vig=0.25, vig_mid=0.55),
    "Sony FE 24-70mm f/2.8": dict(k1=-0.14, k2=0.05, ca_r=-1.6, ca_b=1.4, vig=0.5, vig_mid=0.48),
    "Sigma 35mm f/1.4 Art": dict(k1=-0.09, k2=0.02, ca_r=-0.9, ca_b=0.8, vig=0.28, vig_mid=0.55),
    "Vintage Helios 44-2": dict(k1=-0.18, k2=0.06, ca_r=-2.5, ca_b=2.2, vig=0.55, vig_mid=0.45),
}


def _char_curve(x, toe, shoulder, slope, pivot=0.5):
    x = np.clip(x, 0, 1).astype(np.float64)
    # simple toe/shoulder around pivot
    below = x < pivot
    out = np.empty_like(x)
    out[below] = pivot * np.power(x[below] / pivot, toe) * slope
    out[~below] = 1.0 - (1.0 - pivot) * np.power((1.0 - x[~below]) / (1.0 - pivot), shoulder) / max(slope, 0.3)
    # soft normalize
    out = out / max(out.max(), 1e-6) if out.max() > 1 else out
    return np.clip(out, 0, 1).astype(np.float32)


# ---------------------------------------------------------------------------
# LC Film Stock B&W
# ---------------------------------------------------------------------------
class LCFilmStockBW(PreviewImage):
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "film_stock": (list(_BW_STOCKS.keys()), {"default": "Fuji Acros 100"}),
                "color_filter": (list(_BW_FILTERS.keys()), {"default": "None"}),
                "strength": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.05}),
            },
            "optional": {
                "contrast": ("FLOAT", {"default": 0.0, "min": -1.0, "max": 1.0, "step": 0.05}),
                "exposure_shift": ("FLOAT", {"default": 0.0, "min": -3.0, "max": 3.0, "step": 0.25}),
                "look": _look_input(),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "run"
    CATEGORY = "LC123/image"
    OUTPUT_NODE = True
    DESCRIPTION = (
        "Black-and-white film stock look from presets. Strength blends the effect. On-node preview + wipe."
    )

    def run(self, image, film_stock, color_filter, strength, contrast=0.0, exposure_shift=0.0, look="Custom"):
        if strength <= 0:
            return _preview(self, image, image)
        stock = _BW_STOCKS[film_stock]
        filt = _BW_FILTERS[color_filter]
        w = np.array(stock["w"], dtype=np.float32) * np.array(filt, dtype=np.float32)
        w = w / max(w.sum(), 1e-6)
        toe = stock["toe"] + (contrast * 0.2 if abs(contrast) > 0.01 else 0)
        shoulder = max(0.5, stock["shoulder"] - (contrast * 0.15 if abs(contrast) > 0.01 else 0))
        slope = max(0.3, stock["slope"] + (contrast * 0.3 if abs(contrast) > 0.01 else 0))
        out = []
        for img in tensor_to_np(image):
            original = img.copy()
            lin = srgb_to_linear(img)
            bw = lin[..., 0] * w[0] + lin[..., 1] * w[1] + lin[..., 2] * w[2]
            if abs(exposure_shift) > 0.01:
                bw = np.clip(bw * (2.0 ** exposure_shift), 0, 1)
            bw = _char_curve(bw, toe, shoulder, slope)
            bw = linear_to_srgb(bw)
            # fog is a small base density on the print, so it goes on in display space
            # (added in linear it became 10-19% grey and blacks could never reach black)
            fog = stock["fog"]
            if fog > 0:
                bw = bw * (1.0 - fog) + fog
            result = np.stack([bw, bw, bw], axis=-1).astype(np.float32)
            out.append(blend(original, result, strength))
        return _preview(self, np_to_tensor(out), image)


# ---------------------------------------------------------------------------
# LC Film Stock Color
# ---------------------------------------------------------------------------
class LCFilmStockColor(PreviewImage):
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "film_stock": (list(_COLOR_STOCKS.keys()), {"default": "Slide / Kodak Ektachrome E100"}),
                "strength": ("FLOAT", {"default": 0.8, "min": 0.0, "max": 1.0, "step": 0.05}),
            },
            "optional": {
                "override_toe": ("FLOAT", {"default": -1.0, "min": -1.0, "max": 5.0, "step": 0.1}),
                "override_shoulder": ("FLOAT", {"default": -1.0, "min": -1.0, "max": 5.0, "step": 0.1}),
                "override_gamma": ("FLOAT", {"default": -1.0, "min": -1.0, "max": 3.0, "step": 0.05}),
                "look": _look_input(),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "run"
    CATEGORY = "LC123/image"
    OUTPUT_NODE = True
    DESCRIPTION = (
        "Color film stock look from presets (toe/shoulder/gamma). Strength blends. On-node preview + wipe."
    )

    def run(self, image, film_stock, strength, override_toe=-1.0, override_shoulder=-1.0, override_gamma=-1.0, look="Custom"):
        if strength <= 0:
            return _preview(self, image, image)
        s = _COLOR_STOCKS[film_stock]
        toe = override_toe if override_toe > -0.5 else s["toe"]
        shoulder = override_shoulder if override_shoulder > -0.5 else s["shoulder"]
        slope = override_gamma if override_gamma > -0.5 else s["slope"]
        out = []
        for img in tensor_to_np(image):
            original = img.copy()
            lin = srgb_to_linear(img)
            curved = np.empty_like(lin)
            for c in range(3):
                curved[..., c] = _char_curve(lin[..., c], toe, shoulder, slope)
            # saturation
            lum = luminance(curved)
            curved = lum[..., None] + s["sat"] * (curved - lum[..., None])
            # split tone
            sh = np.array(s["shadow"], dtype=np.float32)
            hi = np.array(s["highlight"], dtype=np.float32)
            w_sh = np.clip(1.0 - lum * 2.0, 0, 1)[..., None]
            w_hi = np.clip(lum * 2.0 - 1.0, 0, 1)[..., None]
            curved = curved + sh * w_sh + hi * w_hi
            from .lc_oklab import linear_to_srgb_safe  # over-range colours keep their hue instead of clipping per channel
            result = linear_to_srgb_safe(curved)
            out.append(blend(original, result, strength))
        return _preview(self, np_to_tensor(out), image)


# ---------------------------------------------------------------------------
# LC Lens Profile
# ---------------------------------------------------------------------------
class LCLensProfile(PreviewImage):
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "lens": (list(_LENS_PROFILES.keys()), {"default": list(_LENS_PROFILES.keys())[0]}),
                "mode": (["Add Aberrations", "Correct Aberrations"], {"default": "Add Aberrations", "tooltip": "Add character or try to correct it."}),
            },
            "optional": {
                "strength": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 2.0, "step": 0.1}),
                "look": _look_input(),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "run"
    CATEGORY = "LC123/image"
    OUTPUT_NODE = True
    DESCRIPTION = (
        "Apply or correct a named lens profile (aberrations character). Strength scales the effect. On-node preview with before/after wipe."
    )

    def run(self, image, lens, mode, strength=1.0, look="Custom"):
        if strength < 0.01:
            return _preview(self, image, image)
        p = _LENS_PROFILES[lens]
        sign = 1.0 if mode == "Add Aberrations" else -1.0
        k1 = p["k1"] * strength * sign
        k2 = p["k2"] * strength * sign
        ca_r = p["ca_r"] * strength * sign
        ca_b = p["ca_b"] * strength * sign
        vig = p["vig"] * strength
        vig_mid = p["vig_mid"]
        # every frame of a batch has the same size, so the sampling grids and the vignette are built once
        h, w = image.shape[1], image.shape[2]
        cy, cx = h / 2.0, w / 2.0
        scale = min(h, w) / 1024.0
        device = image.device
        yy = torch.arange(h, dtype=torch.float32, device=device)
        xx = torch.arange(w, dtype=torch.float32, device=device)
        yy, xx = torch.meshgrid(yy, xx, indexing="ij")
        ny = (yy - cy) / max(cy, 1e-6)
        nx = (xx - cx) / max(cx, 1e-6)
        r2 = nx * nx + ny * ny
        r4 = r2 * r2
        r = torch.sqrt(r2 + 1e-8)
        max_r = math.sqrt(cx * cx + cy * cy) + 1e-6
        shifts = [ca_r * scale, 0.0, ca_b * scale]
        grids = []
        for c in range(3):
            distort = 1.0 + k1 * r2 + k2 * r4
            ca = shifts[c]
            total = distort * (1.0 + (ca / max_r) * r) if abs(ca) > 0.01 else distort
            src_x = nx * total * cx + cx
            src_y = ny * total * cy + cy
            # normalize to grid_sample [-1,1]
            gx = (src_x / max(w - 1, 1)) * 2 - 1
            gy = (src_y / max(h - 1, 1)) * 2 - 1
            grids.append(torch.stack((gx, gy), dim=-1).unsqueeze(0))
        vig_mul = None
        if vig > 0.01:
            cos_th = 1.0 / torch.sqrt(1.0 + r2)
            falloff = cos_th ** 4
            transition = ((r - vig_mid * 0.8) / 0.4).clamp(0, 1)
            if mode == "Add Aberrations":
                vig_mul = (1.0 - transition * (1.0 - falloff) * vig * 2).clamp(0, 1).unsqueeze(-1)
            else:
                vig_mul = (1.0 + transition * (1.0 / falloff.clamp(0.3, 1.0) - 1.0) * vig).unsqueeze(-1)
        results = []
        for i in range(image.shape[0]):
            # the grids are float32, so bf16/fp16 frames are sampled in float32
            img = image[i].float()
            out = torch.empty_like(img)
            for c in range(3):
                ch = img[..., c].unsqueeze(0).unsqueeze(0)
                sampled = F.grid_sample(ch, grids[c], mode="bilinear", padding_mode="reflection", align_corners=True)
                out[..., c] = sampled.squeeze()
            if vig_mul is not None:
                out = out * vig_mul
            results.append(out.clamp(0, 1))
        # back to the input dtype, like the other torch nodes here (Depth FX, Desaturate)
        return _preview(self, torch.stack(results, dim=0).to(image.dtype), image)




# ---------------------------------------------------------------------------
# LC Chromatic Aberration
# ---------------------------------------------------------------------------
class LCChromaticAberration(PreviewImage):
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "red_shift": ("INT", {"default": -3, "min": -20, "max": 20, "step": 1, "tooltip": "Red channel shift in pixels."}),
                "red_direction": (["horizontal", "vertical"], {"default": "horizontal", "tooltip": "Red shift axis."}),
                "green_shift": ("INT", {"default": -2, "min": -20, "max": 20, "step": 1, "tooltip": "Green channel shift in pixels."}),
                "green_direction": (["horizontal", "vertical"], {"default": "horizontal", "tooltip": "Green shift axis."}),
                "blue_shift": ("INT", {"default": -7, "min": -20, "max": 20, "step": 1, "tooltip": "Blue channel shift in pixels."}),
                "blue_direction": (["horizontal", "vertical"], {"default": "horizontal", "tooltip": "Blue shift axis."}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "run"
    CATEGORY = "LC123/image"
    OUTPUT_NODE = True
    DESCRIPTION = (
        "RGB channel shift for chromatic aberration (pixels + direction per channel). On-node preview with before/after wipe."
    )

    def run(self, image, red_shift, red_direction, green_shift, green_direction,
            blue_shift, blue_direction):
        if red_shift == 0 and green_shift == 0 and blue_shift == 0:
            return _preview(self, image, image)

        def get_shift(direction, shift):
            # invert vertical so positive shifts up (match source node)
            shift = -shift if direction == "vertical" else shift
            return (shift, 0) if direction == "vertical" else (0, shift)

        x = image.permute(0, 3, 1, 2)
        dirs = [red_direction, green_direction, blue_direction]
        shs = [red_shift, green_shift, blue_shift]
        shifts = [get_shift(d, s) for d, s in zip(dirs, shs)]
        def shift_edge(ch, sy, sx):
            # same as torch.roll inside the frame, but the uncovered strip repeats the edge pixel
            # (roll wrapped a strip from the opposite side of the image in)
            h, w = ch.shape[-2], ch.shape[-1]
            sy = max(-(h - 1), min(h - 1, int(sy)))
            sx = max(-(w - 1), min(w - 1, int(sx)))
            py, px = abs(sy), abs(sx)
            padded = torch.nn.functional.pad(ch[:, None], (px, px, py, py), mode="replicate")[:, 0]
            return padded[:, py - sy : py - sy + h, px - sx : px - sx + w]

        channels = [shift_edge(x[:, i, :, :], *shifts[i]) for i in range(3)]
        out = torch.stack(channels, dim=1).permute(0, 2, 3, 1).clamp(0, 1)
        return _preview(self, out, image)




# ---------------------------------------------------------------------------
# LC Image Desaturate
# ---------------------------------------------------------------------------
class LCImageDesaturate(PreviewImage):
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "factor": ("FLOAT", {
                    "default": 1.0, "min": 0.0, "max": 1.0, "step": 0.05,
                    "tooltip": "0 = full color, 1 = fully desaturated",
                }),
                "method": ([
                    "luminance (Rec.709)",
                    "luminance (Rec.601)",
                    "average",
                    "lightness",
                    "max",
                    "min",
                ], {
                    "default": "luminance (Rec.709)",
                    "tooltip": "How grayscale is computed",
                }),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "run"
    CATEGORY = "LC123/image"
    OUTPUT_NODE = True
    DESCRIPTION = (
        "Desaturate toward grayscale (Essentials-style). Factor and luminance method. On-node preview with before/after wipe."
    )

    def run(self, image, factor, method):
        if factor <= 0:
            return _preview(self, image, image)
        r, g, b = image[..., 0:1], image[..., 1:2], image[..., 2:3]
        if method == "luminance (Rec.709)":
            gray = 0.2126 * r + 0.7152 * g + 0.0722 * b
        elif method == "luminance (Rec.601)":
            gray = 0.299 * r + 0.587 * g + 0.114 * b
        elif method == "average":
            gray = (r + g + b) / 3.0
        elif method == "lightness":
            gray = (torch.maximum(torch.maximum(r, g), b) + torch.minimum(torch.minimum(r, g), b)) / 2.0
        elif method == "max":
            gray = torch.maximum(torch.maximum(r, g), b)
        else:
            gray = torch.minimum(torch.minimum(r, g), b)
        gray3 = gray.expand_as(image)
        result = torch.lerp(image, gray3, float(factor)).clamp(0, 1)
        return _preview(self, result, image)


NODE_CLASS_MAPPINGS = {
    "LCImageAdjust": LCImageAdjust,
    "LCAutoWhiteBalance": LCAutoWhiteBalance,
    "LCClarity": LCClarity,
    "LCLensFX": LCLensFX,
    "LCLiftGammaGain": LCLiftGammaGain,
    "LCImageRGB": LCImageRGB,
    "LCFilmGrain": LCFilmGrain,
    "LCVibrance": LCVibrance,
    "LCVignette": LCVignette,
    "LCBloom": LCBloom,
    "LCImageDenoise": LCImageDenoise,
    "LCColorMatch": LCColorMatch,
    "LCToneMatch": LCToneMatch,
    "LCFilmStockBW": LCFilmStockBW,
    "LCFilmStockColor": LCFilmStockColor,
    "LCLensProfile": LCLensProfile,
    "LCChromaticAberration": LCChromaticAberration,
    "LCImageDesaturate": LCImageDesaturate,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LCImageAdjust": "LC Image Adjust",
    "LCAutoWhiteBalance": "LC Auto White Balance",
    "LCClarity": "LC Sharpen Pro",
    "LCLensFX": "LC Lens FX (deprecated)",
    "LCLiftGammaGain": "LC Lift Gamma Gain",
    "LCImageRGB": "LC Image RGB",
    "LCFilmGrain": "LC Film Grain",
    "LCVibrance": "LC Vibrance",
    "LCVignette": "LC Vignette",
    "LCBloom": "LC Bloom",
    "LCImageDenoise": "LC Image Denoise",
    "LCColorMatch": "LC Color Match 🎨",
    "LCToneMatch": "LC Tone Match",
    "LCFilmStockBW": "LC Film Stock (B&W)",
    "LCFilmStockColor": "LC Film Stock (Color)",
    "LCLensProfile": "LC Lens Profile",
    "LCChromaticAberration": "LC Chromatic Aberration",
    "LCImageDesaturate": "LC Image Desaturate",
}


# ---------------------------------------------------------------------------
# RGBA safety: these tools work on RGB. If an image comes in with an alpha channel
# (a cutout, for example) they process the color and hand the alpha back untouched.
# _alpha_safe lives in lc_image_helpers so the other LC image nodes can share it.
# ---------------------------------------------------------------------------
for _cls in NODE_CLASS_MAPPINGS.values():
    _params = list(inspect.signature(_cls.run).parameters)
    if len(_params) > 1 and _params[1] == "image":
        _cls.run = _alpha_safe(_cls.run)
