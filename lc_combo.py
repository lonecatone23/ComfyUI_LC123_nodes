"""
LC Combo Selector
-----------------
Remote dropdown that reads options from the connected target combo
(scheduler, sampler name, upscale method, etc.).

1. Convert the target combo widget → input
2. Wire LC Combo Selector into that input
3. Dropdown fills with the target’s real option list
4. Selected value is sent through on queue

Output type is * so it can connect to combo inputs.

Class ID: LCComboSelector
Display:  LC Combo Selector
"""

from __future__ import annotations


class LCComboSelector:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "value": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                    },
                ),
            },
        }

    RETURN_TYPES = ("*",)
    RETURN_NAMES = ("value",)
    FUNCTION = "emit"
    CATEGORY = "LC123/utils"
    DESCRIPTION = (
        "Wire into a converted combo input. Dropdown is filled from that "
        "node’s option list (scheduler names, etc.)."
    )

    def emit(self, value: str):
        return (value if value is not None else "",)


NODE_CLASS_MAPPINGS = {
    "LCComboSelector": LCComboSelector,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LCComboSelector": "LC Combo Selector",
}

print("[LC123] registered LCComboSelector")
