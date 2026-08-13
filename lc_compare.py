"""LC Int Compare / LC Float Compare — pick larger or smaller of two values."""


class LCIntCompare:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "a": (
                    "INT",
                    {
                        "default": 0,
                        "min": -0xFFFFFFFF,
                        "max": 0xFFFFFFFF,
                        "forceInput": True,
                        "tooltip": "First integer.",
                    },
                ),
                "b": (
                    "INT",
                    {
                        "default": 0,
                        "min": -0xFFFFFFFF,
                        "max": 0xFFFFFFFF,
                        "forceInput": True,
                        "tooltip": "Second integer.",
                    },
                ),
                "mode": (
                    ["largest", "smallest"],
                    {
                        "default": "largest",
                        "tooltip": "Return the larger or smaller of a and b.",
                    },
                ),
            },
        }

    RETURN_TYPES = ("INT",)
    RETURN_NAMES = ("value",)
    FUNCTION = "compare"
    CATEGORY = "LC123/utils"
    DESCRIPTION = (
        "Compare two integers and output the largest or smallest (mode switch)."
    )

    def compare(self, a, b, mode="largest"):
        a, b = int(a), int(b)
        if mode == "smallest":
            return (a if a <= b else b,)
        return (a if a >= b else b,)


class LCFloatCompare:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "a": (
                    "FLOAT",
                    {
                        "default": 0.0,
                        "min": -1e9,
                        "max": 1e9,
                        "step": 0.01,
                        "forceInput": True,
                        "tooltip": "First float.",
                    },
                ),
                "b": (
                    "FLOAT",
                    {
                        "default": 0.0,
                        "min": -1e9,
                        "max": 1e9,
                        "step": 0.01,
                        "forceInput": True,
                        "tooltip": "Second float.",
                    },
                ),
                "mode": (
                    ["largest", "smallest"],
                    {
                        "default": "largest",
                        "tooltip": "Return the larger or smaller of a and b.",
                    },
                ),
            },
        }

    RETURN_TYPES = ("FLOAT",)
    RETURN_NAMES = ("value",)
    FUNCTION = "compare"
    CATEGORY = "LC123/utils"
    DESCRIPTION = (
        "Compare two floats and output the largest or smallest (mode switch)."
    )

    def compare(self, a, b, mode="largest"):
        a, b = float(a), float(b)
        if mode == "smallest":
            return (a if a <= b else b,)
        return (a if a >= b else b,)


NODE_CLASS_MAPPINGS = {
    "LCIntCompare": LCIntCompare,
    "LCFloatCompare": LCFloatCompare,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LCIntCompare": "LC Int Compare",
    "LCFloatCompare": "LC Float Compare",
}
