"""
LC Node Snapshot 📋
Wire **source** from the node to inspect (preferred), or set **target** title/id.

widget_name is a STRING so any real widget name validates.
JS fills a dropdown of **widget names** — not the options inside those widgets.
"""

from __future__ import annotations

import json


class LCNodeSnapshot:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "widget_name": (
                    "STRING",
                    {
                        "default": "",
                        "tooltip": "Name of a parameter widget on the target (e.g. preset, strength).",
                    },
                ),
            },
            "optional": {
                "source": (
                    "*",
                    {
                        "tooltip": "Wire any output from the node you want to inspect. Takes priority over target text.",
                    },
                ),
                "target": (
                    "STRING",
                    {
                        "default": "",
                        "tooltip": "Fallback: node title (exact) or numeric id if source is not connected.",
                    },
                ),
            },
            # Not shown on the node face — filled by JS into the prompt at queue time
            "hidden": {
                "selected_value": ("STRING", {"default": ""}),
                "lines_dump": ("STRING", {"default": ""}),
                "json_dump": ("STRING", {"default": ""}),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("selected", "lines", "json")
    FUNCTION = "run"
    CATEGORY = "LC123/utils"
    DESCRIPTION = (
        "Snapshot another node's widgets. Connect **source** (or target title/id). "
        "Dropdown lists **widget names**. Outputs: selected, lines, json."
    )

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")

    def run(
        self,
        widget_name,
        source=None,
        target="",
        selected_value="",
        lines_dump="",
        json_dump="",
        **kwargs,
    ):
        sel = "" if selected_value is None else str(selected_value)
        lines = "" if lines_dump is None else str(lines_dump)
        js = "" if json_dump is None else str(json_dump)
        if not lines and (target or source is not None):
            lines = f"node_id: \nnode_type: \nnode_title: {target or ''}\n"
        if not js:
            js = json.dumps(
                {
                    "node_id": None,
                    "node_type": None,
                    "node_title": target or "",
                    "widgets": {},
                },
                indent=2,
            )
        return (sel, lines, js)


NODE_CLASS_MAPPINGS = {
    "LCNodeSnapshot": LCNodeSnapshot,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LCNodeSnapshot": "LC Node Snapshot 📋",
}
