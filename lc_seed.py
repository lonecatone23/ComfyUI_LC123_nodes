"""
🌱LC Seed — standalone INT seed with seed_mode (fixed / randomize / increment / decrement).
Works on partial node runs. Widget is base_seed so ComfyUI does not inject control_after_generate.
"""

from __future__ import annotations

import random
import time


def _resolve_seed(seed: int, seed_mode: str) -> int:
    mode = (seed_mode or "fixed").lower().strip()
    s = int(seed) & 0xFFFFFFFFFFFFFFFF
    if mode == "randomize":
        return random.randint(0, 0xFFFFFFFFFFFFFFFF)
    if mode == "increment":
        return (s + 1) & 0xFFFFFFFFFFFFFFFF
    if mode == "decrement":
        return (s - 1) & 0xFFFFFFFFFFFFFFFF
    return s


class LCSeed:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "base_seed": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 0xFFFFFFFFFFFFFFFF,
                    "tooltip": "Base seed value. seed_mode decides how it changes each run.",
                }),
                "seed_mode": (["fixed", "randomize", "increment", "decrement"], {
                    "default": "randomize",
                    "tooltip": "fixed: reuse base_seed. randomize / increment / decrement: every run "
                               "(full queue or this node only).",
                }),
            },
        }

    RETURN_TYPES = ("INT",)
    RETURN_NAMES = ("seed",)
    FUNCTION = "emit"
    CATEGORY = "LC123/utils"
    DESCRIPTION = "Utility seed. seed_mode works when you queue only this node."

    @classmethod
    def IS_CHANGED(cls, base_seed, seed_mode="fixed"):
        mode = (seed_mode or "fixed").lower().strip()
        if mode == "randomize":
            return time.time()
        return f"{int(base_seed)}:{mode}"

    def emit(self, base_seed, seed_mode="fixed"):
        used = _resolve_seed(base_seed, seed_mode)
        return {
            "ui": {"seed": [used]},
            "result": (used,),
        }


NODE_CLASS_MAPPINGS = {
    "LCSeed": LCSeed,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LCSeed": "🌱LC Seed",
}
