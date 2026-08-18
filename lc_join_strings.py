"""LC Join Strings — null-safe multi-string join (skips empty slots in delimiter)."""


def _as_str(v):
    if v is None:
        return ""
    if isinstance(v, (list, tuple)):
        if not v:
            return ""
        return _as_str(v[0])
    return str(v)


def _unescape_delimiter(s: str) -> str:
    """Always interpret \\n \\r \\t \\\\ in the delimiter string."""
    if not s:
        return s
    out = []
    i = 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s):
            n = s[i + 1]
            if n == "n":
                out.append("\n")
                i += 2
                continue
            if n == "r":
                out.append("\r")
                i += 2
                continue
            if n == "t":
                out.append("\t")
                i += 2
                continue
            if n == "\\":
                out.append("\\")
                i += 2
                continue
        out.append(s[i])
        i += 1
    return "".join(out)


class LCJoinStrings:
    """
    Join N strings with a delimiter.
    Null / missing / empty inputs are skipped (no bare delimiters).
    Delimiter supports escapes: \\n newline, \\n\\n blank line, \\t tab, \\\\ backslash.
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
                "delimiter": (
                    "STRING",
                    {
                        "default": " ",
                        "tooltip": "Between non-empty parts. Use \\n for newline, \\n\\n for a blank line, \\t for tab.",
                    },
                ),
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
        "Join multiple strings with a delimiter. Null/empty inputs skipped. "
        "Delimiter: \\n = newline, \\n\\n = blank line."
    )

    def join(self, inputcount=2, delimiter=" ", **kwargs):
        n = max(2, min(32, int(inputcount or 2)))
        delim = "" if delimiter is None else _unescape_delimiter(str(delimiter))
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
