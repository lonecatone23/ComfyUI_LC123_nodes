"""
LC Int Split
------------
Split a total into two parts. split_point is a fraction 0.0–1.0 of total.
"""

from __future__ import annotations


class LCIntSplit:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "total": (
                    "INT",
                    {
                        "default": 20,
                        "min": 0,
                        "max": 0x7FFFFFFF,
                        "tooltip": "Whole value to split (steps, frames, pixels, …).",
                    },
                ),
                "split_point": (
                    "FLOAT",
                    {
                        "default": 0.5,
                        "min": 0.0,
                        "max": 1.0,
                        "step": 0.01,
                        "tooltip": "Fraction of total. 0 = all in b, 1 = all in a, 0.5 = half.",
                    },
                ),
            },
        }

    RETURN_TYPES = ("INT", "INT", "INT")
    RETURN_NAMES = ("a", "b", "total")
    FUNCTION = "split"
    CATEGORY = "LC123/utils"
    DESCRIPTION = (
        "Split total into a + b. split_point is a fraction 0–1 (0.5 = half). "
        "a + b always equals total."
    )

    def split(self, total, split_point):
        total = int(total)
        if total < 0:
            total = 0
        sp = float(split_point)
        if sp < 0.0:
            sp = 0.0
        if sp > 1.0:
            sp = 1.0
        first = int(round(total * sp))
        first = max(0, min(total, first))
        return (first, total - first, total)


NODE_CLASS_MAPPINGS = {"LCIntSplit": LCIntSplit}
NODE_DISPLAY_NAME_MAPPINGS = {"LCIntSplit": "LC Int Split"}
