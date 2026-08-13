"""LC Text Replace — sequential find/replace pairs (1–20), expands with entry count."""

import re


def _as_str(v):
    if v is None:
        return ""
    if isinstance(v, (list, tuple)):
        if not v:
            return ""
        return _as_str(v[0])
    return str(v)


class LCTextReplace:
    """
    Apply up to 20 find → replace pairs in order.
    Empty find slots are skipped.
    """

    @classmethod
    def INPUT_TYPES(cls):
        optional = {}
        for i in range(1, 21):
            optional[f"find_{i}"] = (
                "STRING",
                {
                    "default": "",
                    "multiline": False,
                    "tooltip": f"Find string #{i} (skipped if empty).",
                },
            )
            optional[f"replace_{i}"] = (
                "STRING",
                {
                    "default": "",
                    "multiline": False,
                    "tooltip": f"Replacement for find #{i}.",
                },
            )
        return {
            "required": {
                "text": (
                    "STRING",
                    {
                        "forceInput": True,
                        "tooltip": "Source text to transform.",
                    },
                ),
                "entrycount": (
                    "INT",
                    {
                        "default": 1,
                        "min": 1,
                        "max": 20,
                        "step": 1,
                        "tooltip": "Number of find/replace pairs to show and apply.",
                    },
                ),
                "use_regex": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "tooltip": "Treat find as a regular expression.",
                    },
                ),
                "count": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 99999,
                        "step": 1,
                        "tooltip": "Max replacements per pair. 0 = replace all.",
                    },
                ),
            },
            "optional": optional,
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    FUNCTION = "replace"
    CATEGORY = "LC123/utils"
    DESCRIPTION = (
        "Text find/replace with 1–20 sequential pairs. "
        "Raise entrycount to add rows; lower it to remove them. "
        "Empty find entries are skipped. Optional regex."
    )

    def replace(
        self,
        text="",
        entrycount=1,
        use_regex=False,
        count=0,
        **kwargs,
    ):
        out = _as_str(text)
        n = max(1, min(20, int(entrycount or 1)))
        max_n = int(count or 0)  # 0 = all

        for i in range(1, n + 1):
            find = _as_str(kwargs.get(f"find_{i}"))
            if find == "":
                continue
            repl = _as_str(kwargs.get(f"replace_{i}"))
            if use_regex:
                try:
                    flags = 0
                    pattern = re.compile(find, flags)
                    out = pattern.sub(repl, out, count=max_n if max_n > 0 else 0)
                except re.error:
                    # Invalid pattern: leave text unchanged for this pair
                    continue
            else:
                if max_n <= 0:
                    out = out.replace(find, repl)
                else:
                    out = out.replace(find, repl, max_n)
        return (out,)


NODE_CLASS_MAPPINGS = {
    "LCTextReplace": LCTextReplace,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LCTextReplace": "LC Text Replace ✂️",
}
