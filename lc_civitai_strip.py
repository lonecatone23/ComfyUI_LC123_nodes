"""
Civitai 🚩🔪
------------
Strip terms from a prompt using an external list file under assets/lists/.
Default list: civitai_compliance_remove.txt
"""

from __future__ import annotations

import os
import re

_ASSETS_LISTS = os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "assets", "lists"
)
_DEFAULT_LIST = "civitai_compliance_remove.txt"


def _list_files():
    files = []
    if os.path.isdir(_ASSETS_LISTS):
        for name in sorted(os.listdir(_ASSETS_LISTS)):
            low = name.lower()
            if low.endswith((".txt", ".csv", ".list")) and not name.upper().startswith(
                "README"
            ):
                files.append(name)
    if _DEFAULT_LIST not in files:
        files.insert(0, _DEFAULT_LIST)
    return files or [_DEFAULT_LIST]


def _load_terms(filename: str):
    path = os.path.join(_ASSETS_LISTS, os.path.basename(filename or _DEFAULT_LIST))
    terms = []
    if not os.path.isfile(path):
        return terms
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            terms.append(line)
    # longest first so multi-word phrases win
    terms.sort(key=len, reverse=True)
    return terms


def _strip_terms(text: str, terms: list) -> str:
    if not text:
        return text
    out = text
    for term in terms:
        if not term:
            continue
        # case-insensitive substring remove
        pattern = re.compile(re.escape(term), re.IGNORECASE)
        out = pattern.sub("", out)
    # tidy leftover commas / spaces
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r" *, *", ", ", out)
    out = re.sub(r",\s*,+", ", ", out)
    out = re.sub(r"^\s*,\s*", "", out)
    out = re.sub(r"\s*,\s*$", "", out)
    return out.strip()


class LCCivitaiStrip:
    @classmethod
    def INPUT_TYPES(cls):
        lists = _list_files()
        return {
            "required": {
                "text": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "forceInput": True,
                        "tooltip": "Prompt / text to strip.",
                    },
                ),
                "list_file": (
                    lists,
                    {
                        "default": lists[0],
                        "tooltip": "List file under assets/lists/ (one term per line, # comments ok).",
                    },
                ),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    FUNCTION = "strip"
    CATEGORY = "LC123/text"
    DESCRIPTION = (
        "Civitai 🚩🔪 — strip terms from assets/lists/*. "
        "For compliance assistance only! YOUR responsibility to abide by CivitAi TOS. "
        "Review assets/lists/civitai_compliance_remove.txt. "
        "No guarantee it is complete, current, or enough for Civitai approval."
    )

    def strip(self, text, list_file=_DEFAULT_LIST):
        terms = _load_terms(list_file)
        cleaned = _strip_terms(text if text is not None else "", terms)
        return (cleaned,)


NODE_CLASS_MAPPINGS = {
    "LCCivitaiStrip": LCCivitaiStrip,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LCCivitaiStrip": "Civitai 🚩🔪",
}
