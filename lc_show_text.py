"""LC Show Text — display a string on the node (ShowText-style)."""

import json


def _as_text(text):
    if text is None:
        return ""
    if isinstance(text, (list, tuple)):
        return "\n".join("" if x is None else str(x) for x in text)
    return str(text)


def _pretty_if_json(s: str) -> str:
    if s is None:
        return ""
    t = s.strip()
    if not t:
        return s
    if not (
        (t.startswith("{") and t.endswith("}"))
        or (t.startswith("[") and t.endswith("]"))
    ):
        return s
    try:
        data = json.loads(t)
    except (json.JSONDecodeError, TypeError, ValueError):
        return s
    if not isinstance(data, (dict, list)):
        return s
    return json.dumps(data, indent=2, ensure_ascii=False)


class LCShowText:
    """Same idea as ShowText 🐍: forceInput STRING in, show on node, pass through."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": ("STRING", {"forceInput": True}),
            },
            "hidden": {
                "unique_id": "UNIQUE_ID",
                "extra_pnginfo": "EXTRA_PNGINFO",
            },
        }

    INPUT_IS_LIST = True
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    FUNCTION = "show"
    CATEGORY = "LC123/utils"
    OUTPUT_NODE = True
    DESCRIPTION = (
        "Show a string on the node (ShowText-style). Keeps newlines; JSON pretty-prints. "
        "Pass-through STRING out."
    )

    def show(self, text, unique_id=None, extra_pnginfo=None):
        # text arrives as a list when INPUT_IS_LIST
        if text is None:
            text = [""]
        if not isinstance(text, list):
            text = [text]

        parts = [_pretty_if_json(_as_text(t)) for t in text]
        display = "\n".join(parts)

        # Keep workflow widget value in sync (same approach as ShowText 🐍)
        try:
            if unique_id is not None and extra_pnginfo is not None:
                uid = unique_id[0] if isinstance(unique_id, list) else unique_id
                info = extra_pnginfo[0] if isinstance(extra_pnginfo, list) else extra_pnginfo
                if isinstance(info, dict) and "workflow" in info:
                    for node in info["workflow"].get("nodes", []):
                        if str(node.get("id")) == str(uid):
                            node["widgets_values"] = [display]
                            break
        except Exception:
            pass

        # ui.text as list — frontend joins for display
        return {"ui": {"text": [display]}, "result": (parts if len(parts) > 1 else [display],)}


NODE_CLASS_MAPPINGS = {
    "LCShowText": LCShowText,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LCShowText": "LC Show Text 🔤",
}
