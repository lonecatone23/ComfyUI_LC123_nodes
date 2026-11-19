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
import logging
import os
import struct

import folder_paths

import comfy.sd
import comfy.utils

NODE_NAME = "LCLoraLoader"

def _moved_lora(name: str):
    """The LoRA a saved row means after its file moved to another subfolder: the only one with the same file name."""
    want = os.path.basename(name.replace("\\", "/")).lower()
    hits = [f for f in folder_paths.get_filename_list("loras") if os.path.basename(f.replace("\\", "/")).lower() == want]
    return hits[0] if len(hits) == 1 else None


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



# ---------------------------------------------------------------- does this LoRA fit the loaded model?
# Asked of the model itself, not a list of model families: ComfyUI's own key map says which of the LoRA's layers land
# on this model (the ones that don't are the "lora key not loaded" console spam), and the sizes of the ones that land
# must match the weights they patch (that catches a LoRA for a same-named but different-size model).
_DOWN_ENDS = (".lora_down.weight", ".lora_A.weight", ".lora.down.weight", ".lora_linear_layer.down.weight",
              ".lokr_w1", ".lokr_w1_a", ".hada_w1_a", ".diff", ".oft_blocks", ".oft_diag")
_TE_STARTS = ("lora_te", "text_encoder", "te_", "te1", "te2", "te3", "clip_", "lora_te1", "lora_te2")


_ST_DTYPES = {"F64": "float64", "F32": "float32", "F16": "float16", "BF16": "bfloat16", "I64": "int64", "I32": "int32",
              "I16": "int16", "I8": "int8", "U8": "uint8", "BOOL": "bool", "F8_E4M3": "float8_e4m3fn", "F8_E5M2": "float8_e5m2"}


def _header_lora(path: str):
    """A LoRA file as empty 'meta' tensors (names and sizes from the safetensors header, no weights read) + its
    metadata: enough for the fit check on a row that is switched off."""
    import torch

    with open(path, "rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        if n <= 0 or n > 64 * 1024 * 1024:
            raise ValueError("unreadable header")
        header = json.loads(f.read(n))
    meta = header.pop("__metadata__", None) or {}
    sd = {}
    for k, v in header.items():
        if not isinstance(v, dict) or "shape" not in v:
            continue
        dt = getattr(torch, _ST_DTYPES.get(v.get("dtype"), "float16"), torch.float16)
        n = 1
        for s in v["shape"]:
            n *= s
        # alphas and other tiny tensors are read as numbers (.item()), so they get real (dummy) values
        sd[k] = torch.ones(v["shape"], dtype=dt) if n <= 16 else torch.empty(v["shape"], dtype=dt, device="meta")
    return sd, meta


def _real_shape(base_model, name: str, w):
    """The size a weight really has. A layer's own in/out features first: 4-bit formats (nvfp4, w4a8, ConvRot w4a4)
    store two weights per byte, so the stored tensor is half as wide as the layer. Then GGUF's tensor_shape, then the
    stored shape."""
    if name.endswith(".weight"):
        mod = base_model
        try:
            for part in name[: -len(".weight")].split("."):
                mod = getattr(mod, part)
            out_f, in_f = getattr(mod, "out_features", None), getattr(mod, "in_features", None)
            if isinstance(out_f, int) and isinstance(in_f, int):
                return (out_f, in_f)
        except AttributeError:
            pass
    return getattr(w, "tensor_shape", None) or getattr(w, "shape", None)


def _lora_fit(model, clip, lora: dict, meta: dict | None) -> dict | None:
    """{"warn": bool, "tip": str} for one LoRA on this model / clip, or None when there is nothing to judge."""
    import comfy.lora
    import comfy.lora_convert

    if model is None:
        return None
    key_map = comfy.lora.model_lora_keys_unet(model.model, {})
    if clip is not None:
        key_map = comfy.lora.model_lora_keys_clip(clip.cond_stage_model, key_map)
    conv = comfy.lora_convert.convert_lora(lora)
    layers = [k for k in conv if k.endswith(_DOWN_ENDS) and (clip is not None or not k.lower().startswith(_TE_STARTS))]
    if not layers:
        return None  # a format we can't count: say nothing rather than guess
    # ComfyUI's own "lora key not loaded" list, caught instead of printed, is exactly the layers that miss
    missed: list = []

    class _Catch(logging.Filter):
        def filter(self, rec):
            msg = rec.getMessage()
            if msg.startswith("lora key not loaded: "):
                missed.append(msg[len("lora key not loaded: "):])
                return False
            return True

    catch, root = _Catch(), logging.getLogger()
    root.addFilter(catch)
    try:
        loaded = comfy.lora.load_lora(conv, key_map, log_missing=True)
    finally:
        root.removeFilter(catch)
    missed_layers = {k for k in missed if k in set(layers)}
    landed = len(layers) - len(missed_layers)
    sd = model.model.state_dict()
    wrong_size = checked = 0
    for key, adapter in loaded.items():
        name = key[0] if isinstance(key, tuple) else key
        if not str(name).startswith("diffusion_model."):
            continue  # clip side: sizes not checked
        ws = _real_shape(model.model, name, sd.get(name))
        weights = getattr(adapter, "weights", None)
        if ws is None or not weights or type(adapter).__name__ != "LoRAAdapter" or isinstance(key, tuple):
            continue
        up, down = weights[0], weights[1]
        if len(ws) >= 2 and getattr(up, "ndim", 0) >= 2 and getattr(down, "ndim", 0) >= 2:
            checked += 1
            if up.shape[0] != ws[0] or down.shape[1] != ws[1]:
                wrong_size += 1
    total = len(layers)
    made_for = ""
    for k in ("ss_base_model_version", "modelspec.architecture", "ss_sd_model_name"):
        if (meta or {}).get(k):
            made_for = f" Its file says it was made for: {meta[k]}."
            break
    model_name = type(model.model).__name__
    if landed == 0:
        return {"warn": True, "tip": f"Wrong base model: none of this LoRA's {total} layers fit the loaded {model_name} "
                                     f"model, so it does nothing here.{made_for}"}
    if wrong_size > max(2, checked // 4):
        names = (f"the layer names match the loaded {model_name} model" if landed >= total
                 else f"{landed} of this LoRA's {total} layers have names that match the loaded {model_name} model")
        return {"warn": True, "tip": f"Wrong base model: {names}, but {wrong_size} of {checked} have the wrong size "
                                     f"(a different size or version of this model).{made_for}"}
    if landed < total * 0.5:
        return {"warn": True, "tip": f"Probably the wrong base model: only {landed} of this LoRA's {total} layers fit "
                                     f"the loaded {model_name} model.{made_for}"}
    return {"warn": False, "tip": f"Fits the loaded {model_name} model ({landed} of {total} layers)."}


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
        fits: dict = {}  # lora name -> {"warn", "tip"}: the ⚠️ and its hover tip on the row

        for row in rows:
            if not isinstance(row, dict):
                continue
            name = row.get("lora")
            try:
                strength = float(row.get("strength", 1.0))
            except (TypeError, ValueError):
                strength = 0.0
            if not name or name in ("None", "NONE"):
                continue
            if not row.get("on") or strength == 0.0:
                # not applied, but still checked (from the file header only, no weights read): you want the ⚠️
                # before you switch a row on
                path = folder_paths.get_full_path("loras", name) or (
                    folder_paths.get_full_path("loras", _moved_lora(name)) if _moved_lora(name) else None)
                try:
                    fit = _lora_fit(model, clip, *_header_lora(path)) if path else None
                    if fit:
                        fits[name] = fit
                        if fit["warn"]:
                            print(f"[LC LoRA Loader] ⚠️ {name} (switched off): {fit['tip']}")
                except Exception as e:
                    print(f"[LC LoRA Loader] fit check skipped for {name}: {e}")
                continue
            path = folder_paths.get_full_path("loras", name)
            if not path:
                moved = _moved_lora(name)
                if moved:
                    print(f"[LC LoRA Loader] {name} moved: using {moved} (pick it again to save the new place)")
                    path = folder_paths.get_full_path("loras", moved)
            if not path:
                # a saved row can outlive the file it points at (renamed/deleted lora); skip it rather than
                # failing the whole graph, same as the referenced LoRA-file-missing case in the stock loader
                print(f"[LC LoRA Loader] LoRA not found, row skipped: {name} (renamed or deleted? pick it again)")
                continue

            lora, lora_metadata = _cached_lora(prev, used, path)
            try:
                fit = _lora_fit(model, clip, lora, lora_metadata)
                if fit:
                    fits[name] = fit
                    if fit["warn"]:
                        print(f"[LC LoRA Loader] ⚠️ {name}: {fit['tip']}")
            except Exception as e:  # the check must never stop a run
                print(f"[LC LoRA Loader] fit check skipped for {name}: {e}")

            out_model, out_clip = comfy.sd.load_lora_for_models(out_model, out_clip, lora, strength, strength, lora_metadata=lora_metadata)

        # keep only the LoRAs used in this run (bounded by the node's own rows)
        self._lora_cache = used
        return {"ui": {"lc_lora_fit": [json.dumps(fits)]}, "result": (out_model, out_clip)}


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


# ---------------------------------------------------------------- pick-time check: no run, no weights
# The model file picked upstream is built EMPTY from its header (ComfyUI's own model detection, every tensor on the
# 'meta' device: names and sizes only), so the same fit check runs the moment a LoRA is picked.
_META_MODELS: dict = {}  # (path, mtime) -> the empty model (one per model file, a handful kept)
_MODEL_FOLDERS = ("diffusion_models", "unet", "unet_gguf", "checkpoints")
_QUANT_KEYS = ("comfy_quant", "weight_scale", "scale_weight", "input_scale", "scale_input", "scaled_fp8")


class _Shim:
    """What _lora_fit needs from a ModelPatcher: .model."""

    def __init__(self, m):
        self.model = m


def _header_gguf(path: str):
    """A GGUF diffusion model's tensor names and real sizes as empty tensors, read the way ComfyUI-GGUF reads them
    (its comfy.gguf.orig_shape field, else the reversed ggml shape), without dequantizing anything. (None, None)
    when the gguf package is missing or the file is an sd.cpp-style one ComfyUI-GGUF has to guess the layout of."""
    import torch

    try:
        import gguf
    except Exception:
        return None, None
    reader = gguf.GGUFReader(path)
    arch = reader.get_field("general.architecture")
    if arch is None:
        return None, None
    names = [t.name for t in reader.tensors]
    pre = "model.diffusion_model."
    strip = any(n.startswith(pre) for n in names)
    sd = {}
    for t in reader.tensors:
        name = t.name
        if strip:
            if not name.startswith(pre):
                continue
            name = name[len(pre):]
        shape = None
        field = reader.get_field(f"comfy.gguf.orig_shape.{t.name}")
        if field is not None:
            shape = [int(field.parts[i][0]) for i in field.data]
        if shape is None:
            shape = [int(v) for v in reversed(t.shape)]
        n = 1
        for s in shape:
            n *= s
        sd[name] = torch.ones(shape, dtype=torch.float16) if n <= 16 else torch.empty(shape, dtype=torch.float16, device="meta")
    return sd, {}


def _meta_model(path: str):
    import torch
    import comfy.model_detection

    try:
        key = (path, os.path.getmtime(path))
    except OSError:
        return None
    if key in _META_MODELS:
        return _META_MODELS[key]
    import comfy.utils

    # the same steps as ComfyUI's own comfy.sd.load_diffusion_model_state_dict, minus loading any weights
    sd, metadata = _header_gguf(path) if path.lower().endswith(".gguf") else _header_lora(path)
    if sd is None:
        return None
    # quantized files (fp8 scaled, int8 ConvRot...) carry scale / quant-config entries that make ComfyUI build
    # quantized layers; the names and sizes the check needs are the plain layers', so those entries are dropped
    sd = {k: v for k, v in sd.items() if not any(t in k for t in _QUANT_KEYS)}
    metadata = {k: v for k, v in (metadata or {}).items() if "quant" not in k.lower()}
    prefix = comfy.model_detection.unet_prefix_from_state_dict(sd)
    temp = comfy.utils.state_dict_prefix_replace(sd, {prefix: ""}, filter_keys=True)
    if len(temp) > 0:
        sd = temp
    cfg = comfy.model_detection.model_config_from_unet(sd, "", metadata=metadata)
    if cfg is None:
        conv = comfy.model_detection.convert_diffusers_mmdit(sd, "")
        if conv is not None:
            sd = conv
            cfg = comfy.model_detection.model_config_from_unet(sd, "", metadata=metadata)
    m = None
    if cfg is not None:
        with torch.device("meta"):
            m = cfg.get_model(sd, "", device=torch.device("meta"))
        # ComfyUI's dynamic-VRAM layers only create their weights when a file is loaded into them, so the empty
        # model's own state_dict misses most layers; the file's own names and sizes are exactly what a real load
        # ends up with, so the model reports those instead (the class, and so ComfyUI's LoRA key mapping, stays)
        names = {"diffusion_model." + k: v for k, v in sd.items()}
        m.state_dict = lambda *a, **kw: names
    while len(_META_MODELS) >= 4:
        _META_MODELS.pop(next(iter(_META_MODELS)))
    _META_MODELS[key] = m
    return m


def _optimizer_model_path(opt: dict):
    """The model file an LC Optimizer node will load, from its widgets (base model, goal, model file), resolved with
    the Optimizer's own resolver. Never downloads: a download pick, or a file not on disk, gives None."""
    from . import lc_optimizer_engine as E
    from . import lc_optimizer_node as N

    cls = N.NODE_CLASS_MAPPINGS.get(str(opt.get("class") or ""))
    value = str(opt.get("model_file") or "")
    if cls is None or not value or value.startswith(E.DOWNLOAD):
        return None
    base = E.LEGACY_BASE.get(opt.get("base_model"), opt.get("base_model"))
    pid = next((p for p, name in E.base_names(cls.KIND) if name == base), None)
    if pid is None:
        return None
    try:
        got = E.resolve(pid, "model", value, str(opt.get("goal") or ""))
    except Exception:
        return None  # not on disk / needs a download: the run says so itself
    return folder_paths.get_full_path(got[0], got[1]) if got else None


def pick_time_fits(model_name: str, loras: list, optimizer: dict | None = None) -> dict:
    """{lora name: {"warn", "tip"}} for these LoRAs on this model file, from headers only. {} when the model file
    can't be read this way (GGUF, unknown format): the run-time check still covers it."""
    path = None
    if optimizer:
        path = _optimizer_model_path(optimizer)
    for folder in (() if optimizer else _MODEL_FOLDERS):
        try:
            path = folder_paths.get_full_path(folder, model_name)
        except Exception:
            path = None
        if path:
            break
    if not path or not path.lower().endswith((".safetensors", ".gguf")):
        return {}
    m = _meta_model(path)
    if m is None:
        return {}
    out = {}
    for name in loras:
        if not name or name in ("None", "NONE") or name in out:
            continue
        lp = folder_paths.get_full_path("loras", name) or (
            folder_paths.get_full_path("loras", _moved_lora(name)) if _moved_lora(name) else None)
        if not lp or not lp.lower().endswith(".safetensors"):
            continue
        try:
            fit = _lora_fit(_Shim(m), None, *_header_lora(lp))
            if fit:
                out[name] = fit
        except Exception as e:
            print(f"[LC LoRA Loader] pick-time check skipped for {name}: {e}")
    return out


try:
    from server import PromptServer
    from aiohttp import web

    @PromptServer.instance.routes.post("/lc123/lora_loader/fit")
    async def lc_lora_loader_fit(request):
        import asyncio

        try:
            body = await request.json()
            fits = await asyncio.get_running_loop().run_in_executor(
                None, pick_time_fits, str(body.get("model") or ""), list(body.get("loras") or []), body.get("optimizer"))
            return web.json_response({"fits": fits})
        except Exception as e:
            return web.json_response({"fits": {}, "error": str(e)[:300]})

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


class LCLoraLoaderSingle(LCLoraLoader):
    """LC LoRA Loader with one row and no clip: the same row (on / off, the folder picker, strength, Info), the same
    rules (a moved LoRA is found again, a missing one is skipped), no add / remove. For a turbo or style LoRA on its
    own spot. Model only: MOSS Image's LoRAs (and most new models') leave the text encoder alone."""

    RETURN_TYPES = ("MODEL",)
    RETURN_NAMES = ("model",)
    DESCRIPTION = ("One LoRA on the model: the LC LoRA Loader row (on / off, folders, strength, Info) without add or "
                   "remove. For a turbo or style LoRA on its own spot. Model only.")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {"model": ("MODEL",)},
            "optional": {
                "lora_rows": ("STRING", {"default": "[]", "multiline": True, "tooltip": "Internal: the one row (on/lora/strength), maintained by the node's own face."}),
            },
        }

    def load(self, model=None, clip=None, lora_rows="[]"):
        try:
            rows = (json.loads(lora_rows) or [])[:1]
        except Exception:
            rows = []
        res = LCLoraLoader.load(self, model=model, clip=None, lora_rows=json.dumps(rows))
        return {"ui": res["ui"], "result": (res["result"][0],)}


NODE_CLASS_MAPPINGS = {NODE_NAME: LCLoraLoader, "LCLoraLoaderSingle": LCLoraLoaderSingle}
NODE_DISPLAY_NAME_MAPPINGS = {NODE_NAME: "LC LoRA Loader 🎚️", "LCLoraLoaderSingle": "LC LoRA Loader (single) 🎚️"}
