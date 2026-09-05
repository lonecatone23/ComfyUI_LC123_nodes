"""
LC Sigma Resample
-----------------
Same sigma path, new real step count. Endpoints stay put.

  new_steps = round(old_steps * multiplier) + adder
"""

from __future__ import annotations

import torch


def _as_list(sigmas) -> list[float]:
    if sigmas is None:
        return []
    if isinstance(sigmas, torch.Tensor):
        return [float(x) for x in sigmas.flatten().tolist()]
    try:
        return [float(x) for x in sigmas]
    except TypeError:
        return [float(sigmas)]


def _lerp_curve(sigmas: list[float], new_steps: int) -> list[float]:
    if len(sigmas) < 2 or new_steps < 1:
        return sigmas[:]
    old_steps = len(sigmas) - 1
    out = []
    for i in range(new_steps + 1):
        x = 0.0 if new_steps == 0 else i / new_steps
        if x <= 0:
            out.append(sigmas[0])
            continue
        if x >= 1:
            out.append(sigmas[-1])
            continue
        pos = (len(sigmas) - 1) * x
        idx = int(pos)
        frac = pos - idx
        if idx >= len(sigmas) - 1:
            out.append(sigmas[-1])
        else:
            out.append((1.0 - frac) * sigmas[idx] + frac * sigmas[idx + 1])
    return out


class LCSigmaResample:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "sigmas": ("SIGMAS",),
                "multiplier": (
                    "FLOAT",
                    {
                        "default": 1.0,
                        "min": 0.05,
                        "max": 20.0,
                        "step": 0.05,
                        "tooltip": "Multiply the current step count first.",
                    },
                ),
                "adder": (
                    "INT",
                    {
                        "default": 0,
                        "min": -100,
                        "max": 200,
                        "tooltip": "Then add (or subtract) this many steps.",
                    },
                ),
            },
        }

    RETURN_TYPES = ("SIGMAS",)
    RETURN_NAMES = ("sigmas",)
    FUNCTION = "resample"
    CATEGORY = "LC123/sampling"
    DESCRIPTION = (
        "Resample a sigma curve onto a new step grid. "
        "The sampler really runs the new count. Start and end sigma stay put. "
        "new_steps = round(old_steps * multiplier) + adder. "
        "Put this on a split slice (high or low), not in front of the splitter."
    )

    def resample(self, sigmas, multiplier=1.0, adder=0):
        src = _as_list(sigmas)
        if len(src) < 2:
            return (torch.FloatTensor(src),)
        old_steps = max(len(src) - 1, 1)
        new_steps = int(round(old_steps * float(multiplier))) + int(adder)
        new_steps = max(1, new_steps)
        out = _lerp_curve(src, new_steps)
        return (torch.FloatTensor(out),)


NODE_CLASS_MAPPINGS = {
    "LCSigmaResample": LCSigmaResample,
    "LCChangeStepCount": LCSigmaResample,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "LCSigmaResample": "LC Sigma Resample",
    "LCChangeStepCount": "LC Sigma Resample",
}
