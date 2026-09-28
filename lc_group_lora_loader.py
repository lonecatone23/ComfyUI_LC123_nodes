"""LC Group LoRA Loader: independent grouped UI and model/CLIP row strengths.

The visual library and group editor live in web/lc_group_lora_loader.js. Groups
are workflow properties; the hidden lora_rows input carries ordered rows with
on/lora/strength and optional strengthTwo (CLIP, defaulting to model strength).
This module is separate from the original LC loader to simplify upstream updates.
"""

from __future__ import annotations

import json

import folder_paths

import comfy.sd
import comfy.utils

from server import PromptServer

from .lc_lora_library import register_routes
from .lc_lora_weights import row_strengths

NODE_NAME = "LCGroupLoraLoader"


class LCGroupLoraLoader:
    CATEGORY = "LC123/loaders"
    RETURN_TYPES = ("MODEL", "CLIP")
    RETURN_NAMES = ("model", "clip")
    FUNCTION = "load"
    DESCRIPTION = (
        "Apply any number of LoRAs to a model/clip from one node: enable, name and shared or separate Model/CLIP strengths per row, drag to "
        "reorder, an Info button with cached previews and trigger words. model and clip are both optional, so "
        "you can use this for a model-only or clip-only chain. Disabled rows or rows with both strengths at 0 are skipped."
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {},
            "optional": {
                "model": ("MODEL", {"tooltip": "Diffusion model to apply the enabled LoRAs to. Optional: leave unconnected for a clip-only chain."}),
                "clip": ("CLIP", {"tooltip": "CLIP to apply the enabled LoRAs to. Optional: leave unconnected for a model-only chain."}),
                "lora_rows": ("STRING", {"default": "[]", "multiline": True, "tooltip": "Internal: the row list (on/lora/strength), maintained by the node's own face. Not meant to be typed by hand."}),
            },
        }

    def load(self, model=None, clip=None, lora_rows="[]"):
        try:
            rows = json.loads(lora_rows)
        except (TypeError, ValueError):
            rows = []
        if not isinstance(rows, list):
            return (model, clip)

        out_model, out_clip = model, clip
        cache: dict[str, tuple] = {}

        for row in rows:
            if not isinstance(row, dict) or not row.get("on"):
                continue
            name = row.get("lora")
            strength_model, strength_clip = row_strengths(row)
            if not isinstance(name, str) or not name or name.lower() == "none" or (strength_model == 0.0 and strength_clip == 0.0):
                continue
            path = folder_paths.get_full_path("loras", name)
            if not path:
                # a saved row can outlive the file it points at (renamed/deleted lora); skip it rather than
                # failing the whole graph, same as the referenced LoRA-file-missing case in the stock loader
                continue

            if path in cache:
                lora, lora_metadata = cache[path]
            else:
                lora, lora_metadata = comfy.utils.load_torch_file(path, safe_load=True, return_metadata=True)
                cache[path] = (lora, lora_metadata)

            out_model, out_clip = comfy.sd.load_lora_for_models(out_model, out_clip, lora, strength_model, strength_clip, lora_metadata=lora_metadata)

        return (out_model, out_clip)


register_routes(PromptServer.instance.routes)


NODE_CLASS_MAPPINGS = {NODE_NAME: LCGroupLoraLoader}
NODE_DISPLAY_NAME_MAPPINGS = {NODE_NAME: "LC Group LoRA Loader 🎚️"}
