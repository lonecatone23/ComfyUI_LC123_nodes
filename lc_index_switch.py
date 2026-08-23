"""
LC Any Index Switch — index widget (convert to input to wire) + any-type slots.
"""

from __future__ import annotations


class AnyType(str):
    def __ne__(self, __value: object) -> bool:
        return False


any_type = AnyType("*")


class LCIndexSwitch:
    @classmethod
    def INPUT_TYPES(cls):
        optional = {f"any_{i:02d}": (any_type,) for i in range(1, 21)}
        return {
            "required": {
                "index": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 19,
                        "step": 1,
                        "tooltip": "0-based slot. Right-click → Convert Widget to Input to wire INDEX here.",
                    },
                ),
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

    RETURN_TYPES = (any_type,)
    RETURN_NAMES = ("*",)
    FUNCTION = "switch"
    CATEGORY = "LC123/utils"
    DESCRIPTION = "Pass through input at index. Convert index widget to input to wire from LC Custom Combo."

    def switch(self, index: int, inputcount: int = 2, **kwargs):
        n = max(2, min(20, int(inputcount)))
        idx = max(0, min(n - 1, int(index)))
        return (kwargs.get(f"any_{idx + 1:02d}"),)


NODE_CLASS_MAPPINGS = {"LCIndexSwitch": LCIndexSwitch}
NODE_DISPLAY_NAME_MAPPINGS = {"LCIndexSwitch": "LC Any Index Switch"}
