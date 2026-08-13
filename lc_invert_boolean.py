"""
LC Invert Boolean
-----------------
Accepts BOOLEAN, INT, FLOAT (or other numeric-like values) on one input,
coerces to true/false, then inverts.

Truthy: True, non-zero numbers
Falsy:  False, 0, 0.0, None

Class ID: LCInvertBoolean
Display:  LC Invert Boolean
"""

from __future__ import annotations


class AnyType(str):
    """Wildcard type so BOOLEAN / INT / FLOAT / NUMBER can all connect."""

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


class LCInvertBoolean:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "value": (
                    any_type,
                    {
                        "tooltip": "BOOLEAN, INT, FLOAT, or number. Non-zero / True → true, else false; then inverted.",
                    },
                ),
            },
        }

    RETURN_TYPES = ("BOOLEAN",)
    RETURN_NAMES = ("BOOLEAN",)
    FUNCTION = "invert"
    CATEGORY = "LC123/utils"
    DESCRIPTION = (
        "Same multi-type coercion as LC Boolean, then invert the result. Shows true/false on the face."
    )

    def invert(self, value):
        return (not _to_bool(value),)


NODE_CLASS_MAPPINGS = {
    "LCInvertBoolean": LCInvertBoolean,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LCInvertBoolean": "LC Invert Boolean",
}
