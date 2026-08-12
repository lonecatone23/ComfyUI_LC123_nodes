"""
LC Split Sigma Scheduler
------------------------
Builds sigma schedules for dual-pass SamplerCustomAdvanced.

  Model      → high-sigma (1st pass) schedule
  2nd model  → optional; low-sigma (2nd pass) schedule
               falls back to Model when not connected
"""

import torch
import comfy.samplers


def _build_sigmas(model, scheduler, total_steps, denoise):
    total_steps = max(int(total_steps), 1)
    denoise = float(denoise)
    if denoise > 1.0:
        denoise = 1.0
    if denoise <= 0.0:
        return torch.FloatTensor([])

    steps = total_steps
    if denoise < 1.0:
        steps = int(total_steps / denoise)

    sigmas = comfy.samplers.calculate_sigmas(
        model.get_model_object("model_sampling"),
        scheduler,
        steps,
    ).cpu()

    if denoise < 1.0 and len(sigmas) > 0:
        sigmas = sigmas[-(int(total_steps * denoise) + 1):]

    return sigmas


class LCSplitSigmaScheduler:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "Model": ("MODEL", {
                    "tooltip": "Primary model — builds the high-sigma (1st pass) schedule.",
                }),
                "scheduler": (
                    comfy.samplers.KSampler.SCHEDULERS,
                    {
                        "default": "simple",
                        "tooltip": "Scheduler type for both sigma curves.",
                    },
                ),
                "total_steps": (
                    "INT",
                    {
                        "default": 40,
                        "min": 1,
                        "max": 10000,
                        "tooltip": "Total steps in the full schedule.",
                    },
                ),
                "step_swap": (
                    "INT",
                    {
                        "default": 30,
                        "min": 0,
                        "max": 10000,
                        "tooltip": "Handoff step. high_sigmas = 0..swap, low_sigmas = swap..end.",
                    },
                ),
                "denoise": (
                    "FLOAT",
                    {
                        "default": 1.0,
                        "min": 0.0,
                        "max": 1.0,
                        "step": 0.05,
                        "tooltip": "Denoise strength for building the full schedule (1.0 = full).",
                    },
                ),
            },
            "optional": {
                "2nd model": ("MODEL", {
                    "tooltip": "Optional 2nd model for the low-sigma (2nd pass) schedule. Falls back to Model when empty.",
                }),
            },
        }

    RETURN_TYPES = ("SIGMAS", "SIGMAS", "INT")
    RETURN_NAMES = ("sigmas_high", "sigmas_low", "step_swap")
    FUNCTION = "get_sigmas"
    CATEGORY = "LC123/sampling"
    DESCRIPTION = (
        "Dual-model sigma split for SamplerCustomAdvanced. "
        "sigmas_high from Model; sigmas_low from 2nd model (or Model if unset)."
    )

    def get_sigmas(self, **kwargs):
        model = kwargs["Model"]
        model_2nd = kwargs.get("2nd model", None)
        scheduler = kwargs["scheduler"]
        total_steps = kwargs["total_steps"]
        step_swap = kwargs["step_swap"]
        denoise = kwargs["denoise"]

        low_model = model_2nd if model_2nd is not None else model

        sigmas_from_high = _build_sigmas(model, scheduler, total_steps, denoise)
        if low_model is model:
            sigmas_from_low = sigmas_from_high
        else:
            sigmas_from_low = _build_sigmas(low_model, scheduler, total_steps, denoise)

        n = len(sigmas_from_high)
        step = int(step_swap)
        step = max(0, min(step, max(n - 1, 0)))

        high = sigmas_from_high[: step + 1]

        n_low = len(sigmas_from_low)
        step_low = max(0, min(step, max(n_low - 1, 0)))
        low = sigmas_from_low[step_low:]

        return (high, low, step)


NODE_CLASS_MAPPINGS = {
    "LCSplitSigmaScheduler": LCSplitSigmaScheduler,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LCSplitSigmaScheduler": "LC Split Sigma Scheduler",
}
