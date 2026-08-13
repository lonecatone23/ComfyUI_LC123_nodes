"""LC Show Text — display a string on the node (preserves newlines; auto pretty-prints JSON)."""

import json


def _as_text(text):
    if text is None:
        return ""
    if isinstance(text, (list, tuple)):
        return "\n".join("" if x is None else str(x) for x in text)
    return str(text)


def _pretty_if_json(s: str) -> str:
    """If s is a JSON object/array, return indent=2 form; otherwise leave unchanged."""
    if s is None:
        return ""
    t = s.strip()
    if not t:
        return s
    if not ((t.startswith("{") and t.endswith("}")) or (t.startswith("[") and t.endswith("]"))):
        return s
    try:
        data = json.loads(t)
    except (json.JSONDecodeError, TypeError, ValueError):
        return s
    if not isinstance(data, (dict, list)):
        return s
    return json.dumps(data, indent=2, ensure_ascii=False)


class LCShowText:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": ("STRING", {"forceInput": True, "multiline": True, "default": ""}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    FUNCTION = "show"
    CATEGORY = "LC123/utils"
    OUTPUT_NODE = True
    DESCRIPTION = (
        "Show a string on the node. Keeps newlines. "
        "JSON objects/arrays are pretty-printed automatically. Pass-through string output."
    )

    def show(self, text=None):
        out = _pretty_if_json(_as_text(text))
        return {
            "ui": {"text": [out]},
            "result": (out,),
        }


NODE_CLASS_MAPPINGS = {
    "LCShowText": LCShowText,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LCShowText": "LC Show Text 🔤",
}
