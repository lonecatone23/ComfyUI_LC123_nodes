"""
LC Any Index Switch — index widget (convert to input to wire) + any-type slots.

INPUT_IS_LIST / OUTPUT_IS_LIST so Comfy does not zip every wired slot to the
longest connected list. Output length follows the selected slot only.
"""

from __future__ import annotations


class AnyType(str):
    def __ne__(self, __value: object) -> bool:
        return False


any_type = AnyType("*")


def _first(value, default=None):
    if value is None:
        return default
    if isinstance(value, (list, tuple)):
        return value[0] if value else default
    return value


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
    DESCRIPTION = (
        "Pass through the input at index. Other wired slots are ignored and "
        "do not change the output length. Convert index widget to input to "
        "wire from LC Custom Combo."
    )
    # Do not let Comfy map this node over every list input (that made
    # output length = longest connected prompt list).
    INPUT_IS_LIST = True
    OUTPUT_IS_LIST = (True,)

    def switch(self, index, inputcount=2, **kwargs):
        n = int(_first(inputcount, 2) or 2)
        n = max(2, min(20, n))
        idx = int(_first(index, 0) or 0)
        idx = max(0, min(n - 1, idx))
        val = kwargs.get(f"any_{idx + 1:02d}")
        if val is None:
            return ([],)
        if not isinstance(val, list):
            return ([val],)
        return (val,)


NODE_CLASS_MAPPINGS = {"LCIndexSwitch": LCIndexSwitch}
NODE_DISPLAY_NAME_MAPPINGS = {"LCIndexSwitch": "LC Any Index Switch"}
