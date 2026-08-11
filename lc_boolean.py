"""
LC Boolean
----------
Accepts BOOLEAN, INT, FLOAT (or other numeric-like values) on one input
and coerces to a clean BOOLEAN out (no invert).

Truthy: True, non-zero numbers
Falsy:  False, 0, 0.0, None

Class ID: LCBoolean
Display:  LC Boolean
"""

from __future__ import annotations


class AnyType(str):
    def __ne__(self, __value: object) -> bool:
        return False


any_type = AnyType("*")


def _to_bool(value) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        s = value.strip().lower()
        if s in ("", "0", "false", "no", "off", "none", "null"):
            return False
        if s in ("1", "true", "yes", "on"):
            return True
        try:
            return float(s) != 0.0
        except ValueError:
            return bool(s)
    return bool(value)


class LCBoolean:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "value": (
                    any_type,
                    {
                        "tooltip": "BOOLEAN, INT, FLOAT, or number → coerced to true/false (not inverted).",
                    },
                ),
            },
        }

    RETURN_TYPES = ("BOOLEAN",)
    RETURN_NAMES = ("BOOLEAN",)
    FUNCTION = "coerce"
    CATEGORY = "LC123/utils"
    DESCRIPTION = (
        "Coerces the input to a boolean without inverting. "
        "Accepts BOOLEAN, INT, FLOAT, or similar. "
        "Truthy = True or non-zero; falsy = False, 0, 0.0, empty."
    )

    def coerce(self, value):
        return (_to_bool(value),)


NODE_CLASS_MAPPINGS = {
    "LCBoolean": LCBoolean,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LCBoolean": "LC Boolean",
}
