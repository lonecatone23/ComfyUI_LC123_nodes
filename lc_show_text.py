"""LC Show Text — display a string on the node (preserves newlines; pretty-prints JSON)."""

import json


def _as_text(text):
    if text is None:
        return ""
    if isinstance(text, (list, tuple)):
        return "\n".join("" if x is None else str(x) for x in text)
    return str(text)


def _pretty_if_json(s: str) -> str:
    """
    If s is JSON (object/array), return indented pretty form.
    Otherwise return unchanged (including intentional newlines / regex-like text).
    """
    if s is None:
        return ""
    t = s.strip()
    if not t:
        return s
    # Only attempt for clear JSON containers
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
    """
    Pass-through string display node.
    JSON objects/arrays are pretty-printed (indent=2). Other text is unchanged.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": ("STRING", {"forceInput": True, "multiline": True, "default": ""}),
            },
            "optional": {
                "pretty_json": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "tooltip": "When on, valid JSON objects/arrays are shown with indent=2.",
                    },
                ),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    FUNCTION = "show"
    CATEGORY = "LC123/utils"
    OUTPUT_NODE = True
    DESCRIPTION = (
        "Show text on the node. Valid JSON is pretty-printed when enabled; "
        "otherwise newlines and content are kept as-is."
    )

    def show(self, text=None, pretty_json=True):
        out = _as_text(text)
        if pretty_json:
            out = _pretty_if_json(out)
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
