"""Grouped LoRA selection emitting the standard (name, model, CLIP) stack."""

import json

from .lc_lora_weights import row_strengths


class LCGroupLoraLoaderStack:
    CATEGORY = "LC123/loaders"
    RETURN_TYPES = ("LORA_STACK",)
    RETURN_NAMES = ("lora_stack",)
    FUNCTION = "build"
    DESCRIPTION = (
        "Build a LoRA stack with groups, batch selection and separate Model/CLIP strengths. "
        "Connect to LC Apply LoRA Stack or another compatible LORA_STACK consumer."
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {},
            "optional": {
                "lora_rows": ("STRING", {
                    "default": "[]", "multiline": True,
                    "tooltip": "Internal row settings maintained by the node interface.",
                }),
            },
        }

    def build(self, lora_rows="[]"):
        try:
            rows = json.loads(lora_rows)
        except (TypeError, ValueError):
            rows = []
        if not isinstance(rows, list):
            return ([],)
        stack = []
        for row in rows:
            if not isinstance(row, dict) or not row.get("on"):
                continue
            name = row.get("lora")
            model, clip = row_strengths(row)
            if not isinstance(name, str) or not name or name.lower() == "none" or (model == 0 and clip == 0):
                continue
            stack.append((name, model, clip))
        return (stack,)


NODE_CLASS_MAPPINGS = {"LCGroupLoraLoaderStack": LCGroupLoraLoaderStack}
NODE_DISPLAY_NAME_MAPPINGS = {"LCGroupLoraLoaderStack": "LC Group LoRA Loader Stack 🎚️"}
