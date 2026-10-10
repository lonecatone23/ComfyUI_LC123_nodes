"""
LC LoRA Loader Stack / LC Apply LoRA Stack
-------------------------------------------
A split version of LC LoRA Loader, modeled on Comfyroll's CR LoRA Stack / CR Apply LoRA Stack: the loader
just builds a list of (lora, strength) rows -- no MODEL/CLIP in, no MODEL/CLIP out -- and the Apply node
loads and applies that list to whichever model/clip pair it's wired to. Splitting them this way lets one
stack of LoRAs be applied to several different model/clip pairs from a single row list -- e.g. a multi-model
merge workflow -- instead of rebuilding the same rows on a loader per model.

LC LoRA Loader Stack shares its row UI with LC LoRA Loader (web/lc_lora_loader.js) -- same drag-to-reorder
rows, same subfolder-grouped dropdown, same Info button -- it's just added to that file's node list, so it
looks and behaves identically apart from having no sockets at all besides the one LORA_STACK output.

The stack itself is the standard community LORA_STACK shape: a list of (lora_name, strength_model,
strength_clip) tuples, so it also plugs into other packs' Apply LoRA Stack nodes (Comfyroll, Efficiency
Nodes, Impact Pack, ...) if one of those is ever wired in instead of LC Apply LoRA Stack.
"""

from __future__ import annotations

import json
import os

import folder_paths

import comfy.sd
import comfy.utils

STACK_NODE_NAME = "LCLoraLoaderStack"
APPLY_NODE_NAME = "LCApplyLoraStack"

def _cached_lora(prev: dict, used: dict, path: str):
    """Load a LoRA file, reusing the copy kept from the last run (like core LoraLoader's
    self.loaded_lora) so a strength change does not reload it from disk. Keyed by path + mtime,
    so an overwritten file is reloaded. Only entries used this run are carried forward."""
    try:
        key = (path, os.path.getmtime(path))
    except OSError:
        key = (path, None)
    hit = used.get(key) or prev.get(key)
    if hit is None:
        hit = comfy.utils.load_torch_file(path, safe_load=True, return_metadata=True)
    used[key] = hit
    return hit



class LCLoraLoaderStack:
    CATEGORY = "LC123/loaders"
    RETURN_TYPES = ("LORA_STACK",)
    RETURN_NAMES = ("lora_stack",)
    FUNCTION = "build"
    DESCRIPTION = (
        "Builds a LoRA list -- enable, name, strength per row, drag to reorder, the same face as LC LoRA "
        "Loader -- with no sockets in, just a LORA_STACK out. Wire it into one or more LC Apply LoRA Stack "
        "nodes to apply the same set of LoRAs to different model/clip pairs."
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {},
            "optional": {
                "lora_rows": (
                    "STRING",
                    {
                        "default": "[]",
                        "multiline": True,
                        "tooltip": "Internal: the row list (on/lora/strength), maintained by the node's own face. Not meant to be typed by hand.",
                    },
                ),
            },
        }

    def build(self, lora_rows="[]"):
        try:
            rows = json.loads(lora_rows) or []
        except Exception:
            rows = []

        out = []
        for row in rows:
            if not isinstance(row, dict) or not row.get("on"):
                continue
            name = row.get("lora")
            try:
                strength = float(row.get("strength", 1.0))
            except (TypeError, ValueError):
                strength = 0.0
            if not name or name in ("None", "NONE") or strength == 0.0:
                continue
            out.append((name, strength, strength))

        return (out,)


class LCApplyLoraStack:
    CATEGORY = "LC123/loaders"
    RETURN_TYPES = ("MODEL", "CLIP")
    RETURN_NAMES = ("model", "clip")
    FUNCTION = "apply"
    DESCRIPTION = (
        "Applies a LORA_STACK (from LC LoRA Loader Stack, or any other pack's LORA_STACK output) to model "
        "and/or clip. bypass on passes both straight through untouched -- nothing is loaded, nothing applied."
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "bypass": (
                    "BOOLEAN",
                    {"default": False, "tooltip": "On: skip every LoRA in the stack and pass model/clip through unchanged."},
                ),
            },
            "optional": {
                "model": ("MODEL", {"tooltip": "Optional: leave unconnected for a clip-only stack."}),
                "clip": ("CLIP", {"tooltip": "Optional: leave unconnected for a model-only stack."}),
                "lora_stack": ("LORA_STACK", {"tooltip": "From LC LoRA Loader Stack, or any other pack's LoRA stack output."}),
            },
        }

    def apply(self, bypass=False, model=None, clip=None, lora_stack=None):
        if bypass or not lora_stack:
            self._lora_cache = {}
            return (model, clip)

        out_model, out_clip = model, clip
        prev = getattr(self, "_lora_cache", None) or {}
        used: dict = {}

        for entry in lora_stack:
            try:
                name, strength_model, strength_clip = entry
            except (TypeError, ValueError):
                continue
            if not name or name in ("None", "NONE") or (strength_model == 0 and strength_clip == 0):
                continue
            path = folder_paths.get_full_path("loras", name)
            if not path:
                # a saved stack can outlive the file it points at (renamed/deleted lora) -- skip it rather
                # than failing the whole graph, same as LC LoRA Loader
                print(f"[LC LoRA Loader Stack] LoRA not found, row skipped: {name} (renamed or deleted? pick it again)")
                continue

            lora, lora_metadata = _cached_lora(prev, used, path)

            out_model, out_clip = comfy.sd.load_lora_for_models(
                out_model, out_clip, lora, strength_model, strength_clip, lora_metadata=lora_metadata
            )

        # keep only the LoRAs used in this run (bounded by the stack size)
        self._lora_cache = used
        return (out_model, out_clip)


NODE_CLASS_MAPPINGS = {
    STACK_NODE_NAME: LCLoraLoaderStack,
    APPLY_NODE_NAME: LCApplyLoraStack,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    STACK_NODE_NAME: "LC LoRA Loader Stack 🎚️",
    APPLY_NODE_NAME: "LC Apply LoRA Stack 🎚️",
}
