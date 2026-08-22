"""
LC Boolean utilities — switch + sources
---------------------------------------
1) LCBooleanSwitch  — pick on_true / on_false by a boolean widget (any-type passthrough)
2) LCBooleanFlip    — boolean widget inverted → BOOLEAN out (False→True, True→False)
3) LCBooleanValue   — boolean widget → BOOLEAN out (display: LC Boolean Value)

Utility color #28281E, width 270 (see web/lc_boolean_switch.js)
"""

from __future__ import annotations


class AnyType(str):
    def __ne__(self, __value: object) -> bool:
        return False


any_type = AnyType("*")


class LCBooleanSwitch:
    """Route on_true or on_false to the output based on state."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "state": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "tooltip": "True → on_true, False → on_false.",
                    },
                ),
            },
            "optional": {
                "on_true": (any_type, {"tooltip": "Passed through when state is true."}),
                "on_false": (any_type, {"tooltip": "Passed through when state is false."}),
            },
        }

    RETURN_TYPES = (any_type,)
    RETURN_NAMES = ("*",)
    FUNCTION = "switch"
    CATEGORY = "LC123/utils"
    DESCRIPTION = "Boolean switch: state picks on_true or on_false (any type)."

    def switch(self, state, on_true=None, on_false=None):
        return (on_true if bool(state) else on_false,)


class LCBooleanFlip:
    """Widget boolean, inverted on output (False→True, True→False)."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "boolean": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "tooltip": "Inverted on output: off→True, on→False.",
                    },
                ),
            },
        }

    RETURN_TYPES = ("BOOLEAN",)
    RETURN_NAMES = ("boolean",)
    FUNCTION = "emit"
    CATEGORY = "LC123/utils"
    DESCRIPTION = "Boolean flip: widget False → output True; widget True → output False."

    def emit(self, boolean):
        return (not bool(boolean),)


class LCBooleanValue:
    """Simple boolean source (widget → BOOLEAN), same idea as core PrimitiveBoolean."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "value": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "tooltip": "Boolean value to output.",
                    },
                ),
            },
        }

    RETURN_TYPES = ("BOOLEAN",)
    RETURN_NAMES = ("BOOLEAN",)
    FUNCTION = "emit"
    CATEGORY = "LC123/utils"
    DESCRIPTION = "Boolean widget source (primitive-style)."

    def emit(self, value):
        return (bool(value),)


NODE_CLASS_MAPPINGS = {
    "LCBooleanSwitch": LCBooleanSwitch,
    "LCBooleanFlip": LCBooleanFlip,
    "LCBooleanValue": LCBooleanValue,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LCBooleanSwitch": "LC Boolean Switch",
    "LCBooleanFlip": "LC Boolean Flip",
    "LCBooleanValue": "LC Boolean Value",
}
