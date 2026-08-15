"""LC Text Remove — sequential find/remove (1–20), expands with entry count. No replacement value."""

import re


def _as_str(v):
    if v is None:
        return ""
    if isinstance(v, (list, tuple)):
        if not v:
            return ""
        return _as_str(v[0])
    return str(v)


def _tidy_spaces(s: str) -> str:
    """Collapse runs of spaces/tabs; keep newlines; strip edges of each line-ish."""
    if not s:
        return s
    # Protect newlines: collapse horizontal whitespace only
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r" *\n *", "\n", s)
    return s.strip()


class LCTextRemove:
    """
    Remove up to 20 find strings in order (replaced with empty).
    Empty find slots are skipped. Whitespace-only finds are skipped
    (they would glue the whole prompt into one word).
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
                    "tooltip": f"Text #{i} to remove (skipped if empty or only spaces).",
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
                        "tooltip": "Number of find rows to show and apply.",
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
                        "tooltip": "Max removals per find. 0 = remove all matches.",
                    },
                ),
            },
            "optional": optional,
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    FUNCTION = "remove"
    CATEGORY = "LC123/utils"
    DESCRIPTION = (
        "Remove substrings with 1–20 sequential finds (no replacement value). "
        "Whitespace-only finds are ignored so spaces are not stripped from the whole prompt. "
        "Leftover double spaces are collapsed after removals."
    )

    def remove(
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
            # Skip empty OR whitespace-only (prevents gluing words together)
            if find == "" or find.strip() == "":
                continue
            if use_regex:
                try:
                    pattern = re.compile(find)
                    out = pattern.sub("", out, count=max_n if max_n > 0 else 0)
                except re.error:
                    continue
            else:
                if max_n <= 0:
                    out = out.replace(find, "")
                else:
                    out = out.replace(find, "", max_n)

        out = _tidy_spaces(out)
        return (out,)


NODE_CLASS_MAPPINGS = {
    "LCTextRemove": LCTextRemove,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LCTextRemove": "LC Text Remove 🔪",
}
