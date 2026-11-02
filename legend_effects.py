"""
Legend Effects
--------------
In homage to Legendaer (civitai.com/user/Legendaer), whose Anima workflow carries these looks as GLSL shader nodes:
VHS TV, Pixelation, Digital Glitch, Night Vision, Blueprint, Frosted Glass, Gameboy and the Edge-Preserving Blur,
plus core Morphology and Quantize. Here they are one node: pick a look, only its settings show (web/legend_effects.js),
strength blends with the original, and the on-node wipe compares.

The shaders are ported to torch (GPU when there is one), same math as the GLSL: the numbers the shaders hard-code
("TWEAK THESE") are the settings, with the shader's own value as the default. Morphology and Quantize call ComfyUI's
own nodes, so they match them exactly.
"""

import math

import torch
import torch.nn.functional as F

import comfy.model_management
from nodes import PreviewImage

from .lc_image_helpers import _alpha_safe
from .lc_image_tools import _preview

EFFECTS = ["VHS TV", "Pixelation", "Digital Glitch", "Night Vision", "Blueprint", "Frosted Glass", "Gameboy",
           "Edge-Preserving Blur", "Morphology", "Quantize"]
MORPH_OPS = ["erode", "dilate", "open", "close", "gradient", "top_hat", "bottom_hat"]
DITHER = ["none", "floyd-steinberg", "bayer-2", "bayer-4", "bayer-8", "bayer-16"]
LUMA = (0.299, 0.587, 0.114)


def _hex(s, fallback):
    s = str(s or "").strip().lstrip("#")
    try:
        if len(s) == 3:
            s = "".join(c * 2 for c in s)
        return tuple(int(s[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    except ValueError:
        return fallback


def _uv(h, w, dev):
    """Pixel-centre texture coordinates, exactly like the shaders' v_texCoord: u left to right, v bottom to top
    (GL's way round: scanline phase, block grids and glitch rows line up with the GLSL node), both 0..1."""
    v = 1.0 - (torch.arange(h, device=dev, dtype=torch.float32) + 0.5) / h
    u = (torch.arange(w, device=dev, dtype=torch.float32) + 0.5) / w
    return u.view(1, 1, w).expand(1, h, w), v.view(1, h, 1).expand(1, h, w)


def _sample(img, u, v):
    """texture(u_image0, uv): bilinear, edges clamped. img (1, 3, H, W), u / v (1, H, W)."""
    grid = torch.stack((u * 2 - 1, 1 - v * 2), dim=-1)  # v counts up from the bottom, the grid down from the top
    return F.grid_sample(img, grid, mode="bilinear", padding_mode="border", align_corners=False)


def _rand(a, b):
    """The shaders' fract(sin(dot(st, vec2(12.9898, 78.233))) * 43758.5453), in float32 like the GPU runs it."""
    x = torch.sin(a.float() * 12.9898 + b.float() * 78.233) * 43758.5453
    return x - torch.floor(x)


def _luma(img):
    return img[:, 0] * LUMA[0] + img[:, 1] * LUMA[1] + img[:, 2] * LUMA[2]


def _col(rgb, dev):
    return torch.tensor(rgb, device=dev, dtype=torch.float32).view(1, 3, 1, 1)


# ---------------------------------------------------------------- the looks (img: 1 x 3 x H x W, 0..1)
def vhs_tv(img, p):
    _, _, h, w = img.shape
    u, v = _uv(h, w, img.device)
    c = p["vhs_curve"]
    x, y = (u - 0.5) * 2 * (1 + 0.05 * c), (v - 0.5) * 2 * (1 + 0.05 * c)  # zoom out a little to show the TV borders
    x2 = x * (1 + c * (y.abs() / 6) ** 2)
    y2 = y * (1 + c * (x2.abs() / 5) ** 2)
    u, v = x2 / 2 + 0.5, y2 / 2 + 0.5
    s = p["vhs_rgb_shift"]
    r = _sample(img, u + s, v)[:, 0]
    g = _sample(img, u, v)[:, 1]
    b = _sample(img, u - s, v)[:, 2]
    col = torch.stack((r, g, b), 1) - (torch.sin(v * h * 1.5) * p["vhs_scanlines"]).unsqueeze(1)
    vig = (u * v * (1 - u) * (1 - v)).clamp(min=0)
    col = col * torch.pow(vig * 15.0, p["vhs_vignette"]).unsqueeze(1)
    inside = ((u >= 0) & (u <= 1) & (v >= 0) & (v <= 1)).unsqueeze(1)
    return torch.where(inside, col, torch.zeros_like(col))


def _blocks(img, pixels):
    _, _, h, w = img.shape
    u, v = _uv(h, w, img.device)
    gx, gy = float(pixels), float(pixels) * h / w
    return u, v, gx, gy, _sample(img, torch.floor(u * gx) / gx, torch.floor(v * gy) / gy)


def pixelation(img, p):
    return _blocks(img, p["pixel_blocks"])[4]


def digital_glitch(img, p):
    _, _, h, w = img.shape
    u, v = _uv(h, w, img.device)
    row = torch.floor(v * p["glitch_rows"]) + p["glitch_pattern"] * 97.0
    offset = (_rand(row, torch.ones_like(row)) - 0.5) * p["glitch_tear"]
    mask = (_rand(row, torch.full_like(row, 2.0)) >= 1.0 - p["glitch_share"]).float()  # step(0.8, ...) = 20 % of rows
    u = u + offset * mask
    s = p["glitch_rgb_split"] * mask
    r = _sample(img, u + s, v)[:, 0]
    g = _sample(img, u, v)[:, 1]
    b = _sample(img, u - s, v)[:, 2]
    return torch.stack((r, g, b), 1)


def night_vision(img, p):
    _, _, h, w = img.shape
    u, v = _uv(h, w, img.device)
    t = ((_luma(img) - 0.1) / 0.7).clamp(0, 1)
    luma = t * t * (3 - 2 * t)  # smoothstep(0.1, 0.8, luma)
    col = _col(_hex(p["nv_tint"], (0.1, 1.0, 0.2)), img.device) * luma.unsqueeze(1)
    col = col - (torch.sin(v * h * 2.0) * p["nv_scanlines"]).unsqueeze(1)
    vig = u * v * (1 - u) * (1 - v)
    return col * torch.pow(vig * 15.0, p["nv_vignette"]).unsqueeze(1)


def blueprint(img, p):
    _, _, h, w = img.shape
    u, v = _uv(h, w, img.device)
    lum = F.pad(_luma(img).unsqueeze(1), (1, 1, 1, 1), mode="replicate")
    kx = torch.tensor([[1.0, 0.0, -1.0], [2.0, 0.0, -2.0], [1.0, 0.0, -1.0]], device=img.device).view(1, 1, 3, 3)
    sx = F.conv2d(lum, kx)
    sy = F.conv2d(lum, kx.transpose(2, 3))
    edge = ((sx * sx + sy * sy).sqrt() * p["bp_edges"]).clamp(0, 1)
    bg = _col(_hex(p["bp_background"], (0.05, 0.20, 0.60)), img.device).expand(1, 3, h, w)
    cells = p["bp_grid"]
    if cells > 0:  # the engineering grid: thin lines every 1 / cells of the width, square cells
        gu = u * cells
        gv = v * cells * h / w
        grid = ((gu - torch.floor(gu)) >= 0.98).float() + ((gv - torch.floor(gv)) >= 0.98).float()
        bg = bg + (grid * 0.15).unsqueeze(1)
    line = _col(_hex(p["bp_lines"], (1.0, 1.0, 1.0)), img.device)
    return bg + (line - bg) * edge


def frosted_glass(img, p):
    _, _, h, w = img.shape
    u, v = _uv(h, w, img.device)
    k = p["frost_pattern"] * 0.731
    nx = _rand(u + k, v + k) * 2 - 1
    ny = _rand(u + 1 + k, v + 1 + k) * 2 - 1
    a = p["frost_amount"]
    return _sample(img, (u + nx * a).clamp(0, 1), (v + ny * a).clamp(0, 1))


def gameboy(img, p):
    u, v, gx, gy, col = _blocks(img, p["gb_pixels"])
    step = torch.floor(_luma(col) * 3.99).clamp(0, 3).long()
    pal = torch.tensor([[0.06, 0.22, 0.06], [0.19, 0.38, 0.19], [0.55, 0.67, 0.20], [0.61, 0.74, 0.20]], device=img.device)
    out = pal[step[0]].permute(2, 0, 1).unsqueeze(0)
    fx, fy = u * gx, v * gy
    border = ((fx - torch.floor(fx)) >= 0.05).float() * ((fy - torch.floor(fy)) >= 0.05).float()
    return out * (1 - p["gb_gaps"] * (1 - border)).unsqueeze(1)  # the shader's mix(0.7, 1.0, border) = gaps 0.3


def edge_preserving_blur(img, p):
    """The bilateral filter: a Gaussian blur that stops at edges (colour distance in perceptual weights)."""
    r = int(round(min(max(p["blur_radius"], 0.0), 20.0)))
    if r == 0:
        return img
    t = min(max(p["blur_edges"], 0.0), 100.0) / 100.0
    sc = 0.01 + (0.5 - 0.01) * t * t
    ss = max(r * 0.75, 0.5)
    step = max(int(p["blur_step"]), 1)
    _, _, h, w = img.shape
    pad = F.pad(img, (r, r, r, r), mode="replicate")
    wl = _col(LUMA, img.device)
    inv_s, inv_c = -0.5 / (ss * ss), -0.5 / (sc * sc + 1e-4)
    acc = torch.zeros_like(img)
    wsum = torch.zeros((1, 1, h, w), device=img.device)
    for dy in range(-r, r + 1):
        if abs(dy) % step:
            continue
        for dx in range(-r, r + 1):
            if abs(dx) % step or dx * dx + dy * dy > r * r:
                continue
            s = pad[:, :, r + dy:r + dy + h, r + dx:r + dx + w]
            cd = ((s - img) ** 2 * wl).sum(1, keepdim=True)
            wt = math.exp((dx * dx + dy * dy) * inv_s) * torch.exp(cd * inv_c)
            acc += s * wt
            wsum += wt
    return acc / wsum.clamp(min=1e-4)


GPU_LOOKS = {"VHS TV": vhs_tv, "Pixelation": pixelation, "Digital Glitch": digital_glitch, "Night Vision": night_vision,
             "Blueprint": blueprint, "Frosted Glass": frosted_glass, "Gameboy": gameboy,
             "Edge-Preserving Blur": edge_preserving_blur}


def _core(image, effect, p):
    """Morphology and Quantize: ComfyUI's own nodes, so the result matches them exactly."""
    if effect == "Morphology":
        from comfy_extras.nodes_morphology import Morphology

        out = Morphology.execute(image, p["morph_operation"], int(p["morph_kernel"]))
    else:
        from comfy_extras.nodes_post_processing import Quantize

        out = Quantize.execute(image, int(p["quant_colors"]), p["quant_dither"])
    return (out.result if hasattr(out, "result") else out)[0].to(image.device, image.dtype)


def _f(default, lo, hi, step, tip):
    return ("FLOAT", {"default": default, "min": lo, "max": hi, "step": step, "tooltip": tip})


def _i(default, lo, hi, tip):
    return ("INT", {"default": default, "min": lo, "max": hi, "step": 1, "tooltip": tip})


def _c(default, tip):
    return ("STRING", {"default": default, "tooltip": tip})


SETTINGS = {
    "vhs_curve": _f(0.75, 0.0, 3.0, 0.05, "How much the old TV screen bulges. 0 = flat, 1 = the original shader's bulge."),
    "vhs_rgb_shift": _f(0.003, 0.0, 0.02, 0.001, "Red and blue pulled apart sideways (share of the width)."),
    "vhs_scanlines": _f(0.18, 0.0, 0.3, 0.01, "How dark the scanlines are."),
    "vhs_vignette": _f(0.45, 0.0, 1.0, 0.05, "How dark the curved screen gets toward the edges. 0 = none."),
    "pixel_blocks": _i(120, 4, 1024, "How many blocks across the picture. Lower = chunkier."),
    "glitch_tear": _f(0.12, 0.0, 0.2, 0.005, "How far a glitched row slides sideways (share of the width)."),
    "glitch_rows": _i(300, 2, 400, "How many horizontal bands the picture is cut into."),
    "glitch_rgb_split": _f(0.02, 0.0, 0.05, 0.001, "Red and blue split apart on the glitched rows."),
    "glitch_share": _f(0.3, 0.0, 1.0, 0.05, "Share of the rows that glitch. 0.2 = about one in five."),
    "glitch_pattern": _i(11, 0, 9999, "A different set of glitched rows. 0 = the original shader's pattern."),
    "nv_tint": _c("#1AFF66", "Phosphor colour (hex)."),
    "nv_scanlines": _f(0.41, 0.0, 0.5, 0.01, "How dark the scanlines are."),
    "nv_vignette": _f(0.75, 0.0, 1.0, 0.05, "The goggle darkening around the edges. 0 = none."),
    "bp_background": _c("#0D3399", "Paper colour (hex). Classic blueprint blue."),
    "bp_lines": _c("#FFFFFF", "Line colour (hex)."),
    "bp_edges": _f(2.5, 0.0, 10.0, 0.1, "How strongly edges turn into lines. Higher = more detail drawn."),
    "bp_grid": _i(20, 0, 200, "Grid cells across the width. 0 = no grid."),
    "frost_amount": _f(0.015, 0.0, 0.1, 0.001, "How thick the frosted glass is (share of the width)."),
    "frost_pattern": _i(0, 0, 9999, "A different frost pattern. 0 = the original."),
    "gb_pixels": _i(160, 16, 1024, "Pixels across. The original Game Boy screen was 160."),
    "gb_gaps": _f(0.3, 0.0, 1.0, 0.05, "How dark the LCD gaps between pixels are. 0 = no gaps."),
    "blur_radius": _f(20.0, 0.0, 20.0, 1.0, "Blur size in pixels (up to 20). Bigger is slower."),
    "blur_edges": _f(50.0, 0.0, 100.0, 1.0, "How strong an edge must be to stay sharp. Low = only soft areas blur, high = almost everything does."),
    "blur_step": _i(1, 1, 8, "Skip pixels for speed. 1 = every pixel (best), 2+ = faster and grainier."),
    "morph_operation": (MORPH_OPS, {"default": "erode", "tooltip": "erode shrinks bright areas, dilate grows them, open / close clean small specks, gradient keeps the outlines."}),
    "morph_kernel": _i(3, 3, 99, "Size of the shape that does the work, in pixels."),
    "quant_colors": _i(256, 1, 256, "How many colours are left. Low numbers give a poster look."),
    "quant_dither": (DITHER, {"default": "none", "tooltip": "How the leftover colours are mixed: none = flat areas, floyd-steinberg = fine noise, bayer = a regular pattern."}),
}


class LegendEffects(PreviewImage):
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "effect": (EFFECTS, {"default": "VHS TV", "tooltip": "The look. Only its settings show below."}),
                "strength": _f(1.0, 0.0, 1.0, 0.05, "Blend toward the effect. 1 = full look, 0 = original image."),
                **SETTINGS,
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "run"
    CATEGORY = "LC123/image"
    OUTPUT_NODE = True
    DESCRIPTION = ("Legend Effects, in homage to Legendaer: VHS TV, Pixelation, Digital Glitch, Night Vision, Blueprint, "
                   "Frosted Glass, Gameboy, Edge-Preserving Blur, Morphology and Quantize on one node. Pick a look, dial "
                   "strength, drag the on-node wipe to compare.")

    @_alpha_safe
    def run(self, image, effect, strength, **p):
        if strength <= 0 or effect not in EFFECTS:
            return _preview(self, image, image)
        rgb = image[..., :3]
        if effect in GPU_LOOKS:
            dev = comfy.model_management.get_torch_device()
            look = GPU_LOOKS[effect]
            frames = []
            for i in range(rgb.shape[0]):
                comfy.model_management.throw_exception_if_processing_interrupted()
                x = rgb[i:i + 1].to(dev, torch.float32).permute(0, 3, 1, 2)
                frames.append(look(x, p).clamp(0, 1).permute(0, 2, 3, 1).to(image.device, image.dtype))
            out = torch.cat(frames, 0)
        else:
            out = _core(rgb, effect, p).clamp(0, 1)
        if strength < 1:
            out = rgb + (out - rgb) * strength
        return _preview(self, out, image)


NODE_CLASS_MAPPINGS = {"LegendEffects": LegendEffects}
NODE_DISPLAY_NAME_MAPPINGS = {"LegendEffects": "Legend Effects 🪄"}
