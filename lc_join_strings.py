"""LC Join Strings — null-safe multi-string join (skips empty slots in delimiter)."""


def _as_str(v):
    if v is None:
        return ""
    if isinstance(v, (list, tuple)):
        if not v:
            return ""
        return _as_str(v[0])
    return str(v)


class LCJoinStrings:
    """
    Join N strings with a delimiter.
    Null / missing / empty inputs are skipped (no bare delimiters).
    Example: a, (null), c  + delim=","  →  "a,c"  not  "a,,c"
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "inputcount": (
                    "INT",
                    {
                        "default": 2,
                        "min": 2,
                        "max": 32,
                        "step": 1,
                        "tooltip": "Number of string inputs to show and join.",
                    },
                ),
                "delimiter": ("STRING", {"default": " "}),
            },
            "optional": {
                **{
                    f"string_{i}": ("STRING", {"forceInput": True, "default": ""})
                    for i in range(1, 33)
                },
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("string",)
    FUNCTION = "join"
    CATEGORY = "LC123/utils"
    DESCRIPTION = (
        "Join multiple strings with a delimiter. "
        "Null, disconnected, or empty inputs are skipped so you do not get double delimiters."
    )

    def join(self, inputcount=2, delimiter=" ", **kwargs):
        n = max(2, min(32, int(inputcount or 2)))
        delim = "" if delimiter is None else str(delimiter)
        parts = []
        for i in range(1, n + 1):
            s = _as_str(kwargs.get(f"string_{i}"))
            if s != "":
                parts.append(s)
        return (delim.join(parts),)


NODE_CLASS_MAPPINGS = {
    "LCJoinStrings": LCJoinStrings,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LCJoinStrings": "LC Join Strings 🔗",
}
