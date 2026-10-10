"""
LC LoRA Loader
--------------
A multi-row LoRA loader modeled on rgthree's Power Lora Loader, rebuilt to fix three problems in that node:
it does not render in Nodes 2.0, it loses its position on a cross-page paste, and its "Info" menu item never
showed anything. All of the row UI (add, remove, drag to reorder, per-row enable/name/strength, and the fixed
Info popover) lives in web/lc_lora_loader.js; this file loads the enabled rows and applies them like a chain of
stock LoraLoader nodes.

The row list itself is carried in the hidden `lora_rows` STRING widget as a JSON array of
{"on": bool, "lora": filename, "strength": float}, mirroring the pattern LC Slider uses for its hidden config
widgets: the JS face is the real UI, the widget is just what gets serialized and sent to Python.
"""

from __future__ import annotations

import json
import os
import struct

import folder_paths

import comfy.sd
import comfy.utils

NODE_NAME = "LCLoraLoader"

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



class LCLoraLoader:
    CATEGORY = "LC123/loaders"
    RETURN_TYPES = ("MODEL", "CLIP")
    RETURN_NAMES = ("model", "clip")
    FUNCTION = "load"
    DESCRIPTION = (
        "Apply any number of LoRAs to a model/clip from one node: enable, name and strength per row, drag to "
        "reorder, an Info button that reads the LoRA's own trigger words. model and clip are both optional, so "
        "you can use this for a model-only or clip-only chain. Rows disabled or at 0 strength are skipped."
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
            rows = json.loads(lora_rows) or []
        except Exception:
            rows = []

        out_model, out_clip = model, clip
        prev = getattr(self, "_lora_cache", None) or {}
        used: dict = {}

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
            path = folder_paths.get_full_path("loras", name)
            if not path:
                # a saved row can outlive the file it points at (renamed/deleted lora); skip it rather than
                # failing the whole graph, same as the referenced LoRA-file-missing case in the stock loader
                print(f"[LC LoRA Loader] LoRA not found, row skipped: {name} (renamed or deleted? pick it again)")
                continue

            lora, lora_metadata = _cached_lora(prev, used, path)

            out_model, out_clip = comfy.sd.load_lora_for_models(out_model, out_clip, lora, strength, strength, lora_metadata=lora_metadata)

        # keep only the LoRAs used in this run (bounded by the node's own rows)
        self._lora_cache = used
        return (out_model, out_clip)


# ---------------------------------------------------------------- Info: trigger words from the file's own header
# Local file read only, no network call, per the safetensors header the same way LC Lighting/quantization
# verification reads a header in this pack -- struct-unpack the 8-byte length, json-load that many bytes.

def _read_safetensors_metadata(path: str) -> dict:
    with open(path, "rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        if n <= 0 or n > 64 * 1024 * 1024:  # sanity cap; a header this large means something is wrong
            return {}
        header = json.loads(f.read(n))
    return header.get("__metadata__", {}) or {}


def _trigger_words_from_metadata(meta: dict) -> list[str]:
    # Kohya-trained LoRAs bundle a per-dataset tag-frequency table; the most common tags are the trigger words.
    freq_raw = meta.get("ss_tag_frequency")
    if freq_raw:
        try:
            freq = json.loads(freq_raw)
            counts: dict[str, int] = {}
            for _dataset, tags in freq.items():
                if not isinstance(tags, dict):
                    continue
                for tag, count in tags.items():
                    counts[tag] = counts.get(tag, 0) + int(count)
            if counts:
                return [t for t, _ in sorted(counts.items(), key=lambda kv: -kv[1])][:25]
        except Exception:
            pass
    # A handful of other conventions some trainers/exporters use for a single trigger phrase.
    for key in ("modelspec.trigger_phrase", "trigger_phrase", "ss_trigger_word", "ss_output_name"):
        v = meta.get(key)
        if v:
            return [str(v)]
    return []


try:
    from server import PromptServer
    from aiohttp import web

    @PromptServer.instance.routes.get("/lc123/lora_loader/info")
    async def lc_lora_loader_info(request):
        name = request.rel_url.query.get("lora", "")
        if not name:
            return web.json_response({"error": "no lora given"}, status=400)
        path = folder_paths.get_full_path("loras", name)
        if not path or not os.path.isfile(path):
            return web.json_response({"error": "file not found"}, status=404)
        try:
            meta = _read_safetensors_metadata(path)
        except Exception as e:
            return web.json_response({"error": f"could not read file header: {e}"}, status=500)
        words = _trigger_words_from_metadata(meta)
        base_model = (
            meta.get("ss_base_model_version")
            or meta.get("modelspec.architecture")
            or meta.get("ss_sd_model_name")
        )
        return web.json_response({
            "lora": name,
            "trigger_words": words,
            "base_model": base_model,
            "has_metadata": bool(meta),
        })

except Exception:  # pragma: no cover - route registration is best-effort, the node works without it
    pass


NODE_CLASS_MAPPINGS = {NODE_NAME: LCLoraLoader}
NODE_DISPLAY_NAME_MAPPINGS = {NODE_NAME: "LC LoRA Loader 🎚️"}
