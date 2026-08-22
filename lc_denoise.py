"""
LC Denoise 💉
-------------
Inject Gaussian noise into a latent using the *complement* of denoise:

    noise_std = 1.0 - denoise

Matches: denoise 1.0 → no inject; denoise 0.6 → noise_std 0.4.
No seed widget — same idea as WAS Latent Noise Injection.
"""

from __future__ import annotations

import torch


class LCDenoise:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "samples": (
                    "LATENT",
                    {
                        "tooltip": "Latent to inject noise into.",
                    },
                ),
                "denoise": (
                    "FLOAT",
                    {
                        "default": 1.0,
                        "min": 0.0,
                        "max": 1.0,
                        "step": 0.01,
                        "round": 0.01,
                        "tooltip": "Denoise amount. Noise strength used is (1 - denoise). "
                                   "1.0 = no noise; 0.0 = noise_std 1.0.",
                    },
                ),
            },
        }

    RETURN_TYPES = ("LATENT",)
    RETURN_NAMES = ("latent",)
    FUNCTION = "inject"
    CATEGORY = "LC123/latent"
    DESCRIPTION = (
        "Latent noise injection with noise_std = 1 - denoise. "
        "Wire the same denoise value you use on the sampler."
    )

    def inject(self, samples, denoise):
        if not isinstance(samples, dict) or "samples" not in samples:
            return (samples,)

        dens = max(0.0, min(1.0, float(denoise)))
        noise_std = 1.0 - dens

        out = dict(samples)
        lat = samples["samples"]
        if noise_std <= 0.0 or not torch.is_tensor(lat):
            out["samples"] = lat
            return (out,)

        noise = torch.randn_like(lat)
        out["samples"] = lat + noise * noise_std
        return (out,)


NODE_CLASS_MAPPINGS = {
    "LCDenoise": LCDenoise,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LCDenoise": "LC Denoise 💉",
}
