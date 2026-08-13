"""
LC Basic Scheduler
------------------
Build a full SIGMAS curve from model + scheduler + steps (no denoise trim).
"""

import torch
import comfy.samplers


class LCBasicScheduler:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": (
                    "MODEL",
                    {
                        "tooltip": "Model whose sampling space defines the sigma range.",
                    },
                ),
                "scheduler": (
                    comfy.samplers.KSampler.SCHEDULERS,
                    {
                        "default": "normal",
                        "tooltip": "Noise schedule type (karras, beta, simple, …).",
                    },
                ),
                "steps": (
                    "INT",
                    {
                        "default": 20,
                        "min": 1,
                        "max": 10000,
                        "tooltip": "Number of sampling steps (full schedule, no denoise cut).",
                    },
                ),
            },
        }

    RETURN_TYPES = ("SIGMAS",)
    RETURN_NAMES = ("sigmas",)
    FUNCTION = "get_sigmas"
    CATEGORY = "LC123/sampling"
    DESCRIPTION = (
        "Basic scheduler → SIGMAS. Uses the full step count (no denoise parameter). "
        "Feed two of these into LC Split Sigmas (Advanced) for dual-scheduler dual-pass."
    )

    def get_sigmas(self, model, scheduler, steps):
        steps = max(int(steps), 1)
        sigmas = comfy.samplers.calculate_sigmas(
            model.get_model_object("model_sampling"),
            scheduler,
            steps,
        ).cpu()
        return (sigmas,)


NODE_CLASS_MAPPINGS = {
    "LCBasicScheduler": LCBasicScheduler,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LCBasicScheduler": "LC Basic Scheduler",
}
