"""
LC Dimension Resize
-------------------------
Apply the same arithmetic op to width and height with one operand.
Returns rounded integer width and height.
"""

from __future__ import annotations

import math


def _to_number(value) -> float:
    if value is None:
        return 0.0
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return 0.0
        return float(s)
    if isinstance(value, (list, tuple)) and value:
        return _to_number(value[0])
    return float(value)


def _apply(op: str, a: float, b: float) -> float:
    if op == "add":
        return a + b
    if op == "subtract":
        return a - b
    if op == "multiply":
        return a * b
    if op == "divide":
        if b == 0:
            raise ValueError("LC Dimension Resize: divide by zero")
        return a / b
    raise ValueError(f"Unknown operation: {op}")


class AlwaysEqualProxy(str):
    def __eq__(self, _):
        return True

    def __ne__(self, _):
        return False


any_number = AlwaysEqualProxy("*")


class LCDimensionResize:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "width": (
                    "INT",
                    {
                        "default": 1024,
                        "min": 1,
                        "max": 65536,
                        "tooltip": "Source width in pixels.",
                    },
                ),
                "height": (
                    "INT",
                    {
                        "default": 1024,
                        "min": 1,
                        "max": 65536,
                        "tooltip": "Source height in pixels.",
                    },
                ),
                "value": (
                    any_number,
                    {
                        "tooltip": "INT / FLOAT / number applied to both width and height.",
                    },
                ),
                "operation": (
                    ["add", "subtract", "multiply", "divide"],
                    {
                        "default": "multiply",
                        "tooltip": "Same operation applied to width and height with value.",
                    },
                ),
            },
        }

    RETURN_TYPES = ("INT", "INT")
    RETURN_NAMES = ("width", "height")
    FUNCTION = "run"
    CATEGORY = "LC123/image"
    DESCRIPTION = (
        "Apply add / subtract / multiply / divide to width and height with one value, "
        "then round both results to integers."
    )

    def run(self, width, height, value, operation="multiply"):
        v = _to_number(value)
        w = int(round(_apply(operation, float(width), v)))
        h = int(round(_apply(operation, float(height), v)))
        # Keep at least 1px
        w = max(1, w)
        h = max(1, h)
        return (w, h)


NODE_CLASS_MAPPINGS = {
    "LCDimensionResize": LCDimensionResize,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LCDimensionResize": "LC Dimension Resize 📐",
}
