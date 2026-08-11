"""
LC Image tools — self-contained adjustments with on-node preview.
No Darkroom package dependency.
"""

import math
import numpy as np
import torch
import torch.nn.functional as F
from nodes import PreviewImage

from .lc_image_helpers import (
    tensor_to_np, np_to_tensor, srgb_to_linear, linear_to_srgb, blend, luminance,
)


def _preview(self, result_tensor, source_tensor=None):
    """Attach after (and optional before) preview images for on-node compare wipe."""
    out = {"ui": {}, "result": (result_tensor,)}
    try:
        after = self.save_images(result_tensor, filename_prefix="lc_after")
        out["ui"]["lc_preview"] = after["ui"]["images"]
        if source_tensor is not None:
            before = self.save_images(source_tensor, filename_prefix="lc_before")
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
    DESCRIPTION = "Hue, saturation, brightness, contrast, sharpness (−1..1)."

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
                           {"default": "Shades of Gray"}),
                "minkowski_p": ("FLOAT", {"default": 6, "min": 1.0, "max": 16.0, "step": 0.5}),
                "strength": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.05}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "run"
    CATEGORY = "LC123/image"
    OUTPUT_NODE = True

    def run(self, image, method, minkowski_p, strength):
        if strength <= 0:
            return _preview(self, image, image)
        arrays = tensor_to_np(image)
        out = []
        for img in arrays:
            original = img.copy()
            linear = srgb_to_linear(img)
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
# LC Clarity
# ---------------------------------------------------------------------------
class LCClarity(PreviewImage):
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "radius": ("INT", {"default": 3, "min": 0, "max": 4, "step": 1}),
                "offset": ("FLOAT", {"default": 2.0, "min": 1.0, "max": 5.0, "step": 0.01}),
                "strength": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 2.0, "step": 0.01}),
                "blend_mode": ([
                    "Hard Light", "Soft Light", "Overlay", "Multiply",
                    "Vivid Light", "Linear Light", "Addition",
                ], {"default": "Hard Light"}),
                "blend_if_dark": ("INT", {"default": 50, "min": 0, "max": 255, "step": 5,
                                          "tooltip": "Limit effect in dark areas (0–255)"}),
                "blend_if_light": ("INT", {"default": 150, "min": 0, "max": 255, "step": 5,
                                           "tooltip": "Limit effect in light areas (0–255)"}),
                "dark_intensity": ("FLOAT", {"default": 0.4, "min": 0.0, "max": 1.0, "step": 0.01}),
                "light_intensity": ("FLOAT", {"default": 0.1, "min": 0.0, "max": 1.0, "step": 0.01}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "run"
    CATEGORY = "LC123/image"
    OUTPUT_NODE = True
    DESCRIPTION = "Clarity / midtone structure (Clarity FX style) with blend-if controls."

    def _smoothstep(self, edge0, edge1, x):
        t = torch.clamp((x - edge0) / (edge1 - edge0 + 1e-6), 0.0, 1.0)
        return t * t * (3.0 - 2.0 * t)

    def run(self, image, radius, offset, strength, blend_mode,
            blend_if_dark=50, blend_if_light=205, dark_intensity=0.4, light_intensity=0.0):
        if strength <= 0:
            return _preview(self, image, image)
        device = image.device
        dtype = image.dtype
        luma = (
            image[..., 0] * 0.32786885
            + image[..., 1] * 0.655737705
            + image[..., 2] * 0.0163934436
        ).unsqueeze(-1)
        chroma = image / (luma + 1e-6)
        luma_c = luma.permute(0, 3, 1, 2)
        sigma = (radius + 1) * offset
        if sigma > 0:
            r = max(1, int(sigma * 2))
            coords = torch.arange(-r, r + 1, dtype=dtype, device=device)
            kernel = torch.exp(-(coords * coords) / (2 * sigma ** 2))
            kernel = kernel / kernel.sum()
            kh = kernel.view(1, 1, 1, -1)
            kv = kernel.view(1, 1, -1, 1)
            h = F.conv2d(F.pad(luma_c, (r, r, 0, 0), mode="replicate"), kh)
            blurred = F.conv2d(F.pad(h, (0, 0, r, r), mode="replicate"), kv)
        else:
            blurred = luma_c
        blurred = blurred.permute(0, 2, 3, 1)

        sharp = 0.5 * (luma + 1.0 - blurred)
        clamped = sharp.clamp(0.0, 1.0)
        sharp_min = torch.lerp(sharp, clamped, dark_intensity)
        sharp_max = torch.lerp(sharp, clamped, light_intensity)
        sharp = torch.where(sharp > 0.5, sharp_max, sharp_min)

        if blend_mode == "Soft Light":
            sharp = torch.where(
                sharp < 0.5,
                2 * luma * sharp + luma ** 2 * (1 - 2 * sharp),
                torch.sqrt(luma.clamp(min=0)) * (2 * sharp - 1) + 2 * luma * (1 - sharp),
            )
        elif blend_mode == "Overlay":
            sharp = torch.where(luma < 0.5, 2 * luma * sharp, 1 - 2 * (1 - luma) * (1 - sharp))
        elif blend_mode == "Hard Light":
            sharp = torch.where(sharp < 0.5, 2 * luma * sharp, 1 - 2 * (1 - luma) * (1 - sharp))
        elif blend_mode == "Multiply":
            sharp = torch.clamp(2 * luma * sharp, 0, 1)
        elif blend_mode == "Vivid Light":
            sharp = torch.where(
                sharp < 0.5,
                1 - (1 - luma) / (2 * sharp + 1e-6),
                luma / (2 * (1 - sharp) + 1e-6),
            )
        elif blend_mode == "Linear Light":
            sharp = torch.clamp(luma + 2.0 * sharp - 1.0, 0, 1)
        else:  # Addition
            sharp = torch.clamp(luma + sharp - 0.5, 0, 1)

        if blend_if_dark > 0 or blend_if_light < 255:
            mix_val = torch.mean(image, dim=-1, keepdim=True)
            mask = torch.ones_like(mix_val)
            if blend_if_dark > 0:
                d = blend_if_dark / 255.0
                mask = self._smoothstep(d - d * 0.2, d + d * 0.2, mix_val)
            if blend_if_light < 255:
                l = blend_if_light / 255.0
                mask = mask * (1.0 - self._smoothstep(l - l * 0.2, l + l * 0.2, mix_val))
            sharp = torch.lerp(luma, sharp, mask)

        final = torch.lerp(luma, sharp, strength)
        result = (final * chroma).clamp(0, 1)
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
    DESCRIPTION = "Per-channel RGB offset with on-node preview."

    def run(self, image, r, g, b, strength):
        if strength <= 0 or (abs(r) < 1e-6 and abs(g) < 1e-6 and abs(b) < 1e-6):
            return _preview(self, image, image)
        arrays = tensor_to_np(image)
        out = []
        offsets = np.array([r, g, b], dtype=np.float32)
        for img in arrays:
            original = img.copy()
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
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "run"
    CATEGORY = "LC123/image"
    OUTPUT_NODE = True
    DESCRIPTION = "Resolution-aware film grain with mono/chroma mix and on-node preview."

    def run(self, image, grain_size, strength, radius_variation, color_grain, seed, softness=0.8):
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

    def run(self, image, vibrance=0.0, saturation=0.0, protect_skin=True, strength=1.0):
        if strength <= 0 or (abs(vibrance) < 0.5 and abs(saturation) < 0.5):
            return _preview(self, image, image)
        arrays = tensor_to_np(image)
        out = []
        for img in arrays:
            original = img.copy()
            linear = srgb_to_linear(img)
            result = linear.copy()
            if abs(vibrance) > 0.5:
                r, g, b = result[..., 0], result[..., 1], result[..., 2]
                lum = luminance(result)
                cmax = np.maximum(np.maximum(r, g), b)
                cmin = np.minimum(np.minimum(r, g), b)
                chroma = cmax - cmin
                weight = (1.0 - np.clip(chroma * 2.0, 0.0, 1.0)).astype(np.float32)
                if protect_skin:
                    delta = cmax - cmin
                    h = np.zeros_like(r)
                    m = delta > 1e-7
                    mr = m & (cmax == r)
                    mg = m & (cmax == g) & ~mr
                    mb = m & ~mr & ~mg
                    h[mr] = 60.0 * (((g[mr] - b[mr]) / (delta[mr] + 1e-10)) % 6)
                    h[mg] = 60.0 * (((b[mg] - r[mg]) / (delta[mg] + 1e-10)) + 2)
                    h[mb] = 60.0 * (((r[mb] - g[mb]) / (delta[mb] + 1e-10)) + 4)
                    h = h % 360.0
                    diff = np.abs(h - 30.0)
                    diff = np.minimum(diff, 360.0 - diff)
                    skin = np.clip((1.0 + np.cos(np.pi * diff / 30.0)) * 0.5, 0.0, 1.0)
                    skin[diff > 30.0] = 0.0
                    weight *= (1.0 - 0.7 * skin)
                vib = 1.0 + (vibrance / 100.0) * weight
                result = lum[..., None] + vib[..., None] * (result - lum[..., None])
            if abs(saturation) > 0.5:
                lum = luminance(result)
                result = lum[..., None] + (1.0 + saturation / 100.0) * (result - lum[..., None])
            result = linear_to_srgb(np.clip(result, 0, 1).astype(np.float32))
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
        outer = midpoint + feather * (1.414 - midpoint)
        mask = 1.0 - np.clip((r - midpoint) / max(outer - midpoint, 0.01), 0.0, 1.0)
        mask = mask ** 1.5
    return mask.astype(np.float32)


class LCVignette(PreviewImage):
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "intensity": ("FLOAT", {
                    "default": 0.25, "min": -1.0, "max": 1.0, "step": 0.05,
                    "tooltip": "Darken edges. Negative = brighten edges",
                }),
            },
            "optional": {
                "midpoint": ("FLOAT", {"default": 0.55, "min": 0.1, "max": 1.0, "step": 0.05}),
                "roundness": ("FLOAT", {"default": 0.8, "min": 0.3, "max": 2.0, "step": 0.1}),
                "feather": ("FLOAT", {"default": 0.35, "min": 0.05, "max": 1.0, "step": 0.05}),
                "cos4_falloff": ("BOOLEAN", {"default": True}),
                "tint_r": ("FLOAT", {"default": 1.0, "min": 0.5, "max": 1.5, "step": 0.05}),
                "tint_g": ("FLOAT", {"default": 1.0, "min": 0.5, "max": 1.5, "step": 0.05}),
                "tint_b": ("FLOAT", {"default": 1.05, "min": 0.5, "max": 1.5, "step": 0.05}),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "run"
    CATEGORY = "LC123/image"
    OUTPUT_NODE = True

    def run(self, image, intensity, midpoint=0.5, roundness=1.0, feather=0.4,
            cos4_falloff=True, tint_r=1.0, tint_g=1.0, tint_b=1.0):
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
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "run"
    CATEGORY = "LC123/image"
    OUTPUT_NODE = True

    def run(self, image, intensity, threshold, smoothing, radius, saturation, exposure):
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
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "run"
    CATEGORY = "LC123/image"
    OUTPUT_NODE = True
    DESCRIPTION = "Edge-preserving denoise with on-node preview."

    def run(self, image, blur_strength, edge_preservation, radius_multiplier, strength=1.0):
        if strength <= 0:
            return _preview(self, image, image)
        x = image.permute(0, 3, 1, 2)
        device, dtype = x.device, x.dtype
        sigma = max(float(blur_strength), 1e-3)
        radius = int(round(max(0.0, radius_multiplier) * sigma * 2.0))
        if radius <= 0:
            return _preview(self, image.clamp(0, 1), image)
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
        return _preview(self, result, image)




# ---------------------------------------------------------------------------
# LC Color Match 🎨 (AdaIN / mean-std transfer)
# ---------------------------------------------------------------------------
class LCColorMatch(PreviewImage):
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE", {
                    "tooltip": "Image to recolor (content)",
                }),
                "method": (["adain", "mean_std"], {
                    "default": "adain",
                    "tooltip": "adain = channel mean/std match; mean_std = same in linear light",
                }),
                "strength": ("FLOAT", {
                    "default": 1.0, "min": 0.0, "max": 1.0, "step": 0.05,
                    "tooltip": "Blend between original (0) and matched (1)",
                }),
            },
            "optional": {
                "reference": ("IMAGE", {
                    "tooltip": "Color reference (style). If empty, node bypasses and passes image through.",
                }),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "run"
    CATEGORY = "LC123/image"
    OUTPUT_NODE = True
    DESCRIPTION = "Match colors of an image to a reference (AdaIN / mean-std). No reference = bypass."

    def run(self, image, method="adain", strength=1.0, reference=None):
        # No reference → pass-through, flag bypass for UI
        if reference is None:
            out = _preview(self, image, image)
            out["ui"]["lc_bypass"] = ["1"]
            return out
        if strength <= 0:
            return _preview(self, image, image)

        # Use first frame of reference if batch
        ref = reference[0:1]
        # Resize ref stats over full tensor; match per-image against ref[0]
        arrays = tensor_to_np(image)
        ref_np = tensor_to_np(ref)[0]
        out = []

        def stats(x):
            # x HxWx3
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
                out.append(blend(original, matched, strength))
        else:  # adain in display space
            mu_r, sig_r = stats(ref_np)
            for img in arrays:
                original = img.copy()
                mu_s, sig_s = stats(img)
                matched = (img.astype(np.float64) - mu_s) * (sig_r / sig_s) + mu_r
                matched = np.clip(matched, 0, 1).astype(np.float32)
                out.append(blend(original, matched, strength))

        return _preview(self, np_to_tensor(out), image)




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
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "run"
    CATEGORY = "LC123/image"
    OUTPUT_NODE = True

    def run(self, image, film_stock, color_filter, strength, contrast=0.0, exposure_shift=0.0):
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
            fog = stock["fog"]
            if fog > 0:
                bw = bw * (1.0 - fog) + fog
            bw = linear_to_srgb(bw)
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
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "run"
    CATEGORY = "LC123/image"
    OUTPUT_NODE = True

    def run(self, image, film_stock, strength, override_toe=-1.0, override_shoulder=-1.0, override_gamma=-1.0):
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
            result = linear_to_srgb(np.clip(curved, 0, 1).astype(np.float32))
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
                "mode": (["Add Aberrations", "Correct Aberrations"], {"default": "Add Aberrations"}),
            },
            "optional": {
                "strength": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 2.0, "step": 0.1}),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "run"
    CATEGORY = "LC123/image"
    OUTPUT_NODE = True

    def run(self, image, lens, mode, strength=1.0):
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
        results = []
        for i in range(image.shape[0]):
            img = image[i]
            h, w = img.shape[:2]
            cy, cx = h / 2.0, w / 2.0
            scale = min(h, w) / 1024.0
            device = img.device
            yy = torch.arange(h, dtype=torch.float32, device=device)
            xx = torch.arange(w, dtype=torch.float32, device=device)
            yy, xx = torch.meshgrid(yy, xx, indexing="ij")
            ny = (yy - cy) / max(cy, 1e-6)
            nx = (xx - cx) / max(cx, 1e-6)
            r2 = nx * nx + ny * ny
            r4 = r2 * r2
            r = torch.sqrt(r2 + 1e-8)
            max_r = math.sqrt(cx * cx + cy * cy) + 1e-6
            out = torch.empty_like(img)
            shifts = [ca_r * scale, 0.0, ca_b * scale]
            for c in range(3):
                distort = 1.0 + k1 * r2 + k2 * r4
                ca = shifts[c]
                total = distort * (1.0 + (ca / max_r) * r) if abs(ca) > 0.01 else distort
                src_x = nx * total * cx + cx
                src_y = ny * total * cy + cy
                # normalize to grid_sample [-1,1]
                gx = (src_x / max(w - 1, 1)) * 2 - 1
                gy = (src_y / max(h - 1, 1)) * 2 - 1
                grid = torch.stack((gx, gy), dim=-1).unsqueeze(0)
                ch = img[..., c].unsqueeze(0).unsqueeze(0)
                sampled = F.grid_sample(ch, grid, mode="bilinear", padding_mode="reflection", align_corners=True)
                out[..., c] = sampled.squeeze()
            if vig > 0.01:
                cos_th = 1.0 / torch.sqrt(1.0 + r2)
                falloff = cos_th ** 4
                transition = ((r - vig_mid * 0.8) / 0.4).clamp(0, 1)
                if mode == "Add Aberrations":
                    mask = (1.0 - transition * (1.0 - falloff) * vig * 2).clamp(0, 1)
                    out = out * mask.unsqueeze(-1)
                else:
                    correction = 1.0 + transition * (1.0 / falloff.clamp(0.3, 1.0) - 1.0) * vig
                    out = out * correction.unsqueeze(-1)
            results.append(out.clamp(0, 1))
        return _preview(self, torch.stack(results, dim=0), image)




# ---------------------------------------------------------------------------
# LC Chromatic Aberration
# ---------------------------------------------------------------------------
class LCChromaticAberration(PreviewImage):
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "red_shift": ("INT", {"default": -3, "min": -20, "max": 20, "step": 1}),
                "red_direction": (["horizontal", "vertical"], {"default": "horizontal"}),
                "green_shift": ("INT", {"default": -2, "min": -20, "max": 20, "step": 1}),
                "green_direction": (["horizontal", "vertical"], {"default": "horizontal"}),
                "blue_shift": ("INT", {"default": -7, "min": -20, "max": 20, "step": 1}),
                "blue_direction": (["horizontal", "vertical"], {"default": "horizontal"}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "run"
    CATEGORY = "LC123/image"
    OUTPUT_NODE = True
    DESCRIPTION = "Per-channel RGB shift for chromatic aberration."

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
        channels = [
            torch.roll(x[:, i, :, :], shifts=shifts[i], dims=(1, 2)) for i in range(3)
        ]
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
    DESCRIPTION = "Desaturate toward grayscale (Essentials-style)."

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
    "LCLensFX": "LC Lens Effects",
    "LCLiftGammaGain": "LC Lift Gamma Gain",
    "LCImageRGB": "LC Image RGB",
    "LCFilmGrain": "LC Film Grain",
    "LCVibrance": "LC Vibrance",
    "LCVignette": "LC Vignette",
    "LCBloom": "LC Bloom",
    "LCImageDenoise": "LC Image Denoise",
    "LCColorMatch": "LC Color Match 🎨",
    "LCFilmStockBW": "LC Film Stock (B&W)",
    "LCFilmStockColor": "LC Film Stock (Color)",
    "LCLensProfile": "LC Lens Profile",
    "LCChromaticAberration": "LC Chromatic Aberration",
    "LCImageDesaturate": "LC Image Desaturate",
}
