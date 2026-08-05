"""
LC Invert Boolean
-----------------
BOOLEAN in → inverted BOOLEAN out.
Socket-only (no on-node toggle). UI shows a small true/false readout.

Class ID: LCInvertBoolean
Display:  LC Invert Boolean
"""

from __future__ import annotations


class LCInvertBoolean:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "value": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "forceInput": True,
                    },
                ),
            },
        }

    RETURN_TYPES = ("BOOLEAN",)
    RETURN_NAMES = ("BOOLEAN",)
    FUNCTION = "invert"
    CATEGORY = "LC123/utils"
    DESCRIPTION = (
        "Inverts a boolean. Input is socket-only; a small true/false "
        "readout shows the output state on the node."
    )

    def invert(self, value):
        return (not bool(value),)


NODE_CLASS_MAPPINGS = {
    "LCInvertBoolean": LCInvertBoolean,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LCInvertBoolean": "LC Invert Boolean",
}
