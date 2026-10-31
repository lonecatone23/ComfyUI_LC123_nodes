"""
LC RTX Super Resolution
-----------------------
NVIDIA RTX Video Super Resolution on images and video frames: upscale, upscale a clean source, denoise or deblur.
Runs through the shared lc_rtx helper (old and new nvidia-vfx). Strength blends the RTX result with a plain
bicubic resize of the input (the installed SDK has no strength of its own). Sizes go to a multiple of 8 for the
SDK, then snap to the exact size. Ideas from Comfy-Org's ComfyUI_Nvidia_VFX_Nodes (Apache-2.0); written for LC123.
"""
from __future__ import annotations

import math

import torch

import comfy.utils

from . import lc_rtx

MODES = {
    "upscale": "",  # typical compressed sources
    "upscale (clean source)": "HIGHBITRATE_",  # lossless / high bitrate: no artifact clean-up
    "denoise": "DENOISE_",  # same size
    "deblur": "DEBLUR_",  # same size
}
QUALITY = ["LOW", "MEDIUM", "HIGH", "ULTRA"]


class LCRTXSuperResolution:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE", {"tooltip": "A picture or a batch of video frames."}),
                "mode": (list(MODES), {"default": "upscale", "tooltip": (
                    "upscale: AI upscale for typical (compressed) pictures and video.\n"
                    "upscale (clean source): for lossless or high-bitrate sources, without the artifact clean-up.\n"
                    "denoise: removes noise and compression blocks, same size.\n"
                    "deblur: sharpens soft pictures, same size.")}),
                "quality": (QUALITY, {"default": "ULTRA", "tooltip": "LOW is fastest, ULTRA keeps the most detail."}),
                "scale": ("FLOAT", {"default": 2.0, "min": 1.0, "max": 4.0, "step": 0.05,
                                    "tooltip": "Width and height multiplier for the upscale modes. Ignored by denoise and deblur."}),
                "megapixels": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 64.0, "step": 0.1,
                                         "tooltip": "Upscale to this size instead of using scale (shape kept, up to 4x). 0 = use scale."}),
                "strength": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.05,
                                       "tooltip": "1 = the full RTX result. Lower blends back toward a plain resize of the input."}),
            },
            "optional": {
                "mask": ("MASK", {"tooltip": "Resized along with the picture, so it still lines up."}),
            },
        }

    RETURN_TYPES = ("IMAGE", "MASK", "INT", "INT")
    RETURN_NAMES = ("image", "mask", "width", "height")
    OUTPUT_TOOLTIPS = ("The RTX result.", "The mask at the new size (empty when none is wired).", "Output width.", "Output height.")
    FUNCTION = "run"
    CATEGORY = "LC123/image"
    DESCRIPTION = (
        "NVIDIA RTX Video Super Resolution: upscale (up to 4x), upscale a clean source, denoise or deblur, on pictures "
        "or video frames. Fast: about half a second per 2x on an RTX card. Needs an NVIDIA RTX card and the nvidia-vfx "
        "package. Strength blends back toward a plain resize."
    )

    def run(self, image, mode, quality, scale, megapixels, strength, mask=None):
        if not lc_rtx.available():
            raise RuntimeError("[LC RTX Super Resolution] Needs an NVIDIA RTX card and the nvidia-vfx package. Install it in a "
                               f"terminal, then restart ComfyUI: {install_command()}")
        b, h, w, c = image.shape
        same = mode in ("denoise", "deblur")
        if same:
            ow, oh = w, h
        elif megapixels > 0:
            k = min(4.0, max(1.0, math.sqrt(megapixels * 1e6 / (w * h))))
            ow, oh = round(w * k), round(h * k)
        else:
            ow, oh = round(w * scale), round(h * scale)
        level = MODES[mode] + quality
        src = image.movedim(-1, 1)
        out = lc_rtx.rtx_resize(src, ow, oh, quality=level, strict=True)
        if strength < 1.0:
            plain = comfy.utils.common_upscale(src, ow, oh, "bicubic", "disabled") if (ow, oh) != (w, h) else src
            out = torch.lerp(plain.to(out.dtype), out, float(strength))
        out = out.clamp(0, 1).movedim(1, -1)
        if mask is not None:
            m = mask if mask.dim() == 3 else mask.unsqueeze(0)
            m = torch.nn.functional.interpolate(m.unsqueeze(1).float(), size=(oh, ow), mode="bilinear", align_corners=False).squeeze(1)
        else:
            m = torch.zeros((b, oh, ow), dtype=torch.float32)
        return (out, m, int(ow), int(oh))


NODE_CLASS_MAPPINGS = {"LCRTXSuperResolution": LCRTXSuperResolution}
NODE_DISPLAY_NAME_MAPPINGS = {"LCRTXSuperResolution": "LC RTX Super Resolution ⚡"}


# ---------------------------------------------------------------- RTX support: status and the install command
# nvidia-vfx (NVIDIA's VFX SDK bindings, about 800 MB) is the one dependency. Nothing installs from inside ComfyUI
# (the Comfy Registry does not allow runtime pip installs): the node face hands over the pip command for ComfyUI's
# own Python to run in a terminal, then a restart (the SDK loads at start-up).


def install_command():
    import sys

    return f'"{sys.executable or "python"}" -m pip install nvidia-vfx'


def rtx_status():
    import importlib.metadata as md

    try:
        version = md.version("nvidia-vfx")
    except Exception:
        version = None
    works = False
    try:
        works = lc_rtx.available()
    except Exception:
        works = False
    return {"installed": bool(version), "version": version, "works": works, "command": install_command()}


try:
    from aiohttp import web
    from server import PromptServer

    @PromptServer.instance.routes.get("/lc123/rtx/status")
    async def _rtx_status(_request):
        return web.json_response(rtx_status())
except Exception as e:  # no server (tests)
    print(f"[LC123] RTX routes not registered: {e}")
