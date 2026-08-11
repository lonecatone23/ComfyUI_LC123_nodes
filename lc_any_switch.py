"""
LC AnySwitch
------------
Top-down priority switch (first connected input wins), any type.

Designed so cg-use-everywhere does NOT auto-wire into its inputs
(see companion web/lc_any_switch.js).

Class ID: LCAnySwitch
Display:  LC AnySwitch
"""

from __future__ import annotations


class LCAnySwitch:
    @classmethod
    def INPUT_TYPES(cls):
        # Fixed optional slots; JS trims visibility via inputcount widget
        optional = {
            f"any_{i:02d}": ("*",) for i in range(1, 21)
        }
        return {
            "required": {
                "inputcount": (
                    "INT",
                    {
                        "default": 2,
                        "min": 2,
                        "max": 20,
                        "step": 1,
                    },
                ),
            },
            "optional": optional,
        }

    RETURN_TYPES = ("*",)
    RETURN_NAMES = ("*",)
    FUNCTION = "switch"
    CATEGORY = "LC123/utils"
    DESCRIPTION = (
        "Top-down Any Switch: first connected input is passed through. "
        "Inputs are blocked from Use Everywhere auto-connect."
    )

    def switch(self, inputcount: int, **kwargs):
        n = max(2, min(20, int(inputcount)))
        for i in range(1, n + 1):
            key = f"any_{i:02d}"
            if key not in kwargs:
                continue
            val = kwargs[key]
            if val is not None:
                return (val,)
        # Nothing connected — return None; downstream may no-op or error
        return (None,)


NODE_CLASS_MAPPINGS = {
    "LCAnySwitch": LCAnySwitch,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LCAnySwitch": "LC AnySwitch",
}
