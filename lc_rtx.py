"""
NVIDIA RTX Video Super Resolution as a resize method for LC nodes.

rtx_resize(bchw, width, height) enlarges with RTX VSR when it can and falls back to lanczos when it can't
(no nvidia-vfx, no CUDA, or the target is smaller than the source: RTX VSR only upscales). Works with both the
old nvidia-vfx API (0.1.x: nvvfx.effects.QualityLevel) and the newer one (nvvfx.QualityLevel).
"""

from __future__ import annotations

import torch

import comfy.model_management
import comfy.utils

RTX_METHOD = "nvidia_rtx_vsr"
MAX_BATCH_PIXELS = 1024 * 1024 * 16
_WARNED = set()


def _warn(key: str, msg: str):
    if key not in _WARNED:
        _WARNED.add(key)
        print(f"[LC123] {msg}")


def _nvvfx():
    try:
        import nvvfx
    except Exception as e:
        _warn("import", f"RTX upscale unavailable ({e}). Install nvidia-vfx on an RTX card. Using lanczos.")
        return None, None
    quality = getattr(nvvfx, "QualityLevel", None) or getattr(getattr(nvvfx, "effects", None), "QualityLevel", None)
    if quality is None:
        _warn("api", "RTX upscale: unknown nvidia-vfx version. Using lanczos.")
        return None, None
    return nvvfx, quality


# One loaded RTX VSR effect per (device, quality, output size), reused and never closed: closing one hung the
# whole node on an RTX 5060 laptop (drivers 610 and 621), and reuse also skips the ~1.5 s load on every call.
_EFFECTS = {}


def _effect(nv, level, key):
    effect = _EFFECTS.get(key)
    if effect is None:
        index, _, ow, oh = key
        try:
            ctx = nv.VideoSuperRes(quality=level, device=index)
        except TypeError:
            ctx = nv.VideoSuperRes(level)
        effect = ctx.__enter__()
        effect.output_width, effect.output_height = ow, oh
        effect.load()
        _EFFECTS[key] = effect
    return effect


def available() -> bool:
    nv, _ = _nvvfx()
    return nv is not None and comfy.model_management.get_torch_device().type == "cuda"


def rtx_resize(samples: torch.Tensor, width: int, height: int, quality: str = "ULTRA", strict: bool = False) -> torch.Tensor:
    """BCHW float 0..1 (3 or 4 channels) -> BCHW at width x height. Alpha / extra channels are resized bilinear.
    strict: raise instead of falling back to lanczos (a node that promises RTX must not quietly do something else)."""
    b, c, h, w = samples.shape
    if strict and (width < w or height < h):
        raise ValueError("[LC RTX] RTX Video Super Resolution only enlarges (or keeps the size).")
    if width < w or height < h:
        _warn("down", "RTX upscale only enlarges; smaller targets use lanczos.")
        return comfy.utils.common_upscale(samples, width, height, "lanczos", "disabled")
    nv, levels = _nvvfx()
    device = comfy.model_management.get_torch_device()
    if nv is None or device.type != "cuda" or c < 3:
        if strict:
            raise RuntimeError("[LC RTX] RTX Video Super Resolution isn't available here (needs nvidia-vfx on an RTX card).")
        return comfy.utils.common_upscale(samples, width, height, "lanczos", "disabled")
    # RTX VSR wants sizes in steps of 8: run it at the next multiple of 8 up, then snap to the exact size
    # (rounding down could land below the source: scale 1.0 on a 1001 px image asked for 1000)
    ow, oh = max(8, -(-width // 8) * 8), max(8, -(-height // 8) * 8)
    same = quality.startswith(("DENOISE", "DEBLUR"))
    if same:
        # same-size modes: output must equal input, and a width off the 8-grid comes back row-skewed,
        # so pad the edges out to the grid, run, then crop back
        ow, oh = -(-w // 8) * 8, -(-h // 8) * 8
    index = device.index if device.index is not None else torch.cuda.current_device()
    # one frame at a time on the GPU, results collected in RAM: a long clip at 2x is tens of GB, which spilled into
    # shared memory and looked like a freeze
    out = torch.empty((b, 3, height, width), device=samples.device if b == 1 else "cpu", dtype=samples.dtype)

    def frame(k):
        x = samples[k, :3].to(device=device, dtype=torch.float32).clamp(0, 1)
        if same and (ow, oh) != (w, h):
            x = torch.nn.functional.pad(x[None], (0, ow - w, 0, oh - h), mode="replicate")[0]
        return x.contiguous()

    def finish(y):
        y = y[None]
        if same:
            y = y[:, :, :h, :w]
        elif (ow, oh) != (width, height):
            y = comfy.utils.common_upscale(y, width, height, "bicubic", "disabled")
        return y[0].clamp(0, 1).to(out.device, out.dtype)

    if quality not in levels.__members__:
        if strict:
            raise ValueError(f"[LC RTX] This nvidia-vfx version has no {quality} mode. Update nvidia-vfx.")
        quality = "ULTRA"
    key = (index, quality, ow, oh)
    try:
        with torch.cuda.device(device):
            effect = _effect(nv, levels[quality], key)
            pbar = comfy.utils.ProgressBar(b) if b > 1 else None
            for k in range(b):
                comfy.model_management.throw_exception_if_processing_interrupted()  # Cancel works between frames
                # keep the input alive until RTX is done with it: a temporary freed mid-run hung 8 GB laptops
                x = frame(k)
                res = effect.run(x)
                out[k] = finish(torch.from_dlpack(res.image).clone())
                del res, x
                if pbar is not None:
                    pbar.update(1)
    except comfy.model_management.InterruptProcessingException:
        raise
    except Exception as e:
        _EFFECTS.pop(key, None)
        if strict:
            raise RuntimeError(f"[LC RTX] RTX Video Super Resolution failed: {e}") from e
        _warn("run", f"RTX upscale failed ({e}). Using lanczos.")
        return comfy.utils.common_upscale(samples, width, height, "lanczos", "disabled")
    out = out.to(samples.device)
    if c > 3:
        extra = torch.nn.functional.interpolate(samples[:, 3:].float(), size=(height, width), mode="bilinear",
                                                align_corners=False).to(samples.dtype)
        out = torch.cat([out, extra], dim=1)
    return out


def resize(samples: torch.Tensor, width: int, height: int, method: str, crop: str = "disabled") -> torch.Tensor:
    """Drop-in for comfy.utils.common_upscale that also understands nvidia_rtx_vsr."""
    if method != RTX_METHOD:
        return comfy.utils.common_upscale(samples, width, height, method, crop)
    if crop == "center":  # same crop as common_upscale
        ow, oh = samples.shape[-1], samples.shape[-2]
        old_aspect, new_aspect = ow / oh, width / height
        if old_aspect > new_aspect:
            x = round((ow - ow * (new_aspect / old_aspect)) / 2)
            samples = samples[..., :, x:ow - x]
        elif old_aspect < new_aspect:
            y = round((oh - oh * (old_aspect / new_aspect)) / 2)
            samples = samples[..., y:oh - y, :]
    return rtx_resize(samples, width, height)
