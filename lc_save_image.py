"""
LC Save Image + LC Save Metadata
--------------------------------
Save IMAGE with Comfy workflow chunks and optional Civitai parameters.

Metadata lives on a separate node (pipe-in, no pipe-out).
Model 1 and Model 2 names share one comma-separated widget.
Primary Civitai field is a single AIR or URL (CiviScribe-style, no lookup).
"""

from __future__ import annotations

import json
import os
import re

import numpy as np
from PIL import Image
from PIL.PngImagePlugin import PngInfo

import folder_paths

from .lc_pipe_io import PIPE_TYPE
from .lc_civitai_hashes import collect_hashes, format_hash_fields, civitai_resources_payload


META_TYPE = "LC_SAVE_META"


def _tensor_to_pil(image) -> Image.Image:
    t = image
    if hasattr(t, "cpu"):
        t = t.detach().cpu()
    arr = np.asarray(t)
    if arr.ndim == 4:
        arr = arr[0]
    if arr.ndim != 3:
        raise ValueError("LC Save Image: expected IMAGE [B,H,W,C] or [H,W,C].")
    if arr.shape[-1] > 4:
        arr = arr[..., :4]
    pixels = np.clip(arr.astype(np.float32) * 255.0, 0, 255).astype(np.uint8)
    if pixels.shape[-1] == 1:
        return Image.fromarray(pixels[..., 0], mode="L")
    if pixels.shape[-1] == 3:
        return Image.fromarray(pixels, mode="RGB")
    return Image.fromarray(pixels, mode="RGBA")


def _txt(v) -> str:
    if v is None:
        return ""
    return str(v).strip()


def _pipe_get(pipe, *keys):
    if not isinstance(pipe, dict):
        return None
    for k in keys:
        if k in pipe and pipe[k] is not None and pipe[k] != "":
            return pipe[k]
    return None


def _join_path(*parts: str) -> str:
    chunks = []
    for p in parts:
        s = _txt(p).replace("\\", "/").strip("/")
        if s:
            chunks.append(s)
    return "/".join(chunks)


def _build_parameters(meta: dict, width: int, height: int, hash_bits=None) -> str:
    positive = _txt(meta.get("positive"))
    negative = _txt(meta.get("negative"))
    steps = meta.get("steps")
    sampler = _txt(meta.get("sampler"))
    scheduler = _txt(meta.get("scheduler"))
    cfg = meta.get("cfg")
    seed = meta.get("seed")
    models = _txt(meta.get("models"))
    extra = _txt(meta.get("extra_params"))
    air = _txt(meta.get("civitai_air"))
    denoise = meta.get("denoise")

    lines = []
    if positive:
        lines.append(positive)
    if negative:
        lines.append(f"Negative prompt: {negative}")
    bits = []
    if steps not in (None, "", 0, "0"):
        try:
            bits.append(f"Steps: {int(steps)}")
        except (TypeError, ValueError):
            bits.append(f"Steps: {steps}")
    if sampler:
        bits.append(f"Sampler: {sampler}")
    if scheduler:
        bits.append(f"Schedule type: {scheduler}")
    if cfg not in (None, "", 0, 0.0, "0"):
        try:
            bits.append(f"CFG scale: {float(cfg):g}")
        except (TypeError, ValueError):
            bits.append(f"CFG scale: {cfg}")
    if seed not in (None, "", -1, "-1"):
        try:
            bits.append(f"Seed: {int(seed)}")
        except (TypeError, ValueError):
            bits.append(f"Seed: {seed}")
    bits.append(f"Size: {int(width)}x{int(height)}")
    if models:
        bits.append(f"Model: {models}")
    if denoise not in (None, "", 0, 0.0, "0"):
        try:
            bits.append(f"Denoising strength: {float(denoise):g}")
        except (TypeError, ValueError):
            pass
    if air:
        resources = civitai_resources_payload(air)
        if resources:
            bits.append("Civitai resources: " + json.dumps(resources, separators=(",", ":")))
    if extra:
        bits.append(extra.lstrip(", "))
    if hash_bits:
        for piece in hash_bits:
            if piece:
                bits.append(piece)
    if bits:
        lines.append(", ".join(bits))
    return "\n".join(lines).strip()


def _as_meta(metadata) -> dict:
    if isinstance(metadata, dict):
        out = dict(metadata)
        out["_type"] = META_TYPE
        return out
    return {"_type": META_TYPE}


class LCSaveImageMetadata:
    """Collect save metadata. Optional LC_PIPE in; widgets override. No pipe out."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {},
            "optional": {
                "pipe": (
                    PIPE_TYPE,
                    {
                        "tooltip": "LC_PIPE in. Fills prompts, seed, steps, CFG, sampler, scheduler, size, denoise. Widgets override.",
                    },
                ),
                "positive": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "tooltip": "Override pipe positive prompt.",
                    },
                ),
                "negative": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "tooltip": "Override pipe negative prompt.",
                    },
                ),
                "seed_value": (
                    "INT",
                    {
                        "default": -1,
                        "min": -1,
                        "max": 0xFFFFFFFFFFFFFFFF,
                        "control_after_generate": False,
                        "tooltip": "Seed. -1 = use pipe seed if present. Plain INT — no control-after-generate.",
                    },
                ),
                "steps": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 10000,
                        "tooltip": "0 = use pipe total_steps.",
                    },
                ),
                "cfg": (
                    "FLOAT",
                    {
                        "default": 0.0,
                        "min": 0.0,
                        "max": 100.0,
                        "step": 0.05,
                        "tooltip": "0 = use pipe cfg_1.",
                    },
                ),
                "sampler": (
                    "STRING",
                    {"default": "", "tooltip": "Empty = use pipe sampler_name."},
                ),
                "scheduler": (
                    "STRING",
                    {"default": "", "tooltip": "Empty = use pipe scheduler."},
                ),
                "models": (
                    "STRING",
                    {
                        "default": "",
                        "tooltip": "Checkpoint names. Model 1 and Model 2 in one field, comma-separated.",
                    },
                ),
                "civitai_air": (
                    "STRING",
                    {
                        "default": "",
                        "tooltip": "Primary Civitai AIR or model URL only. No hash lookup.",
                    },
                ),
                "width": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 65536,
                        "tooltip": "0 = use pipe width (save node still writes the real pixel size).",
                    },
                ),
                "height": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 65536,
                        "tooltip": "0 = use pipe height.",
                    },
                ),
                "denoise": (
                    "FLOAT",
                    {
                        "default": 0.0,
                        "min": 0.0,
                        "max": 1.0,
                        "step": 0.01,
                        "tooltip": "0 = use pipe denoise if set.",
                    },
                ),
                "extra_params": (
                    "STRING",
                    {
                        "default": "",
                        "tooltip": "Appended to the parameters line (LoRAs, hashes, notes).",
                    },
                ),
            },
        }

    RETURN_TYPES = (META_TYPE, "STRING")
    RETURN_NAMES = ("metadata", "parameters")
    FUNCTION = "build"
    CATEGORY = "LC123/io"
    DESCRIPTION = (
        "Save metadata for LC Save Image. Optional LC_PIPE in (no pipe out). "
        "Models are one comma-separated string. civitai_air is the primary AIR or URL only."
    )

    def build(
        self,
        pipe=None,
        positive="",
        negative="",
        seed_value=-1,
        steps=0,
        cfg=0.0,
        sampler="",
        scheduler="",
        models="",
        civitai_air="",
        width=0,
        height=0,
        denoise=0.0,
        extra_params="",
    ):
        meta = {"_type": META_TYPE}

        pos = _txt(positive) or _txt(_pipe_get(pipe, "positive_prompt"))
        neg = _txt(negative) or _txt(_pipe_get(pipe, "negative_prompt"))
        if pos:
            meta["positive"] = pos
        if neg:
            meta["negative"] = neg

        seed = int(seed_value) if seed_value is not None else -1
        if seed < 0:
            pseed = _pipe_get(pipe, "seed")
            try:
                seed = int(pseed) if pseed is not None else -1
            except (TypeError, ValueError):
                seed = -1
        if seed >= 0:
            meta["seed"] = seed

        st = int(steps or 0)
        if st <= 0:
            pst = _pipe_get(pipe, "total_steps", "steps")
            try:
                st = int(pst) if pst is not None else 0
            except (TypeError, ValueError):
                st = 0
        if st > 0:
            meta["steps"] = st

        cf = float(cfg or 0.0)
        if cf == 0.0:
            pcf = _pipe_get(pipe, "cfg_1", "cfg")
            try:
                cf = float(pcf) if pcf is not None else 0.0
            except (TypeError, ValueError):
                cf = 0.0
        if cf:
            meta["cfg"] = cf

        samp = _txt(sampler) or _txt(_pipe_get(pipe, "sampler_name", "sampler"))
        if samp:
            meta["sampler"] = samp
        sched = _txt(scheduler) or _txt(_pipe_get(pipe, "scheduler", "scheduler_name"))
        if sched:
            meta["scheduler"] = sched

        mods = _txt(models)
        if mods:
            parts = [p.strip() for p in mods.split(",") if p.strip()]
            meta["models"] = ", ".join(parts)

        air = _txt(civitai_air)
        if air:
            meta["civitai_air"] = air

        w = int(width or 0)
        h = int(height or 0)
        if w <= 0:
            try:
                w = int(_pipe_get(pipe, "width") or 0)
            except (TypeError, ValueError):
                w = 0
        if h <= 0:
            try:
                h = int(_pipe_get(pipe, "height") or 0)
            except (TypeError, ValueError):
                h = 0
        if w > 0:
            meta["width"] = w
        if h > 0:
            meta["height"] = h

        dn = float(denoise or 0.0)
        if dn == 0.0:
            pdn = _pipe_get(pipe, "denoise")
            try:
                dn = float(pdn) if pdn is not None else 0.0
            except (TypeError, ValueError):
                dn = 0.0
        if dn:
            meta["denoise"] = dn

        extra = _txt(extra_params)
        if extra:
            meta["extra_params"] = extra

        params = _build_parameters(meta, meta.get("width") or 0, meta.get("height") or 0)
        meta["parameters"] = params
        return (meta, params)


class LCSaveImage:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE", {"tooltip": "Batch to save. Each frame is a file."}),
                "filename": (
                    "STRING",
                    {
                        "default": "LC123",
                        "tooltip": "File stem. Easy Folder can still be wired if you prefer one combined prefix.",
                    },
                ),
                "path": (
                    "STRING",
                    {
                        "default": "",
                        "tooltip": "Subfolder under Comfy output. Empty = output root. Separators normalized.",
                    },
                ),
                "format": (
                    ["png", "jpeg", "webp"],
                    {
                        "default": "png",
                        "tooltip": "PNG keeps workflow + Civitai text chunks. JPEG/WebP only get a short comment.",
                    },
                ),
                "quality": (
                    "INT",
                    {
                        "default": 95,
                        "min": 1,
                        "max": 100,
                        "tooltip": "JPEG / WebP quality. Ignored for PNG.",
                    },
                ),
                "embed_workflow": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "label_on": "workflow",
                        "label_off": "no workflow",
                        "tooltip": "Write Comfy prompt + workflow JSON into the PNG.",
                    },
                ),
                "embed_civitai": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "label_on": "parameters",
                        "label_off": "no parameters",
                        "tooltip": "Write A1111-style parameters from the metadata socket.",
                    },
                ),
                "hash_resources": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "label_on": "hash files",
                        "label_off": "no hashes",
                        "tooltip": "SHA-256 AutoV2 of checkpoints, UNET, CLIP, VAE, LoRAs found in the graph. Civitai lists resources from these hashes, not from names.",
                    },
                ),
            },
            "optional": {
                "metadata": (
                    META_TYPE,
                    {
                        "tooltip": "From LC Save Metadata. Prompts, seed, models, Civitai AIR/URL.",
                    },
                ),
                "filename_prefix": (
                    "STRING",
                    {
                        "default": "",
                        "tooltip": "Optional combined prefix (Easy Folder). Used when filename is left as default and this is wired.",
                    },
                ),
            },
            "hidden": {
                "prompt": "PROMPT",
                "extra_pnginfo": "EXTRA_PNGINFO",
            },
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("images", "saved_as")
    FUNCTION = "save"
    CATEGORY = "LC123/io"
    OUTPUT_NODE = True
    DESCRIPTION = (
        "Save images with Comfy workflow metadata. Wire LC Save Metadata for "
        "Civitai parameters. filename + path widgets; PNG recommended."
    )

    def save(
        self,
        images,
        filename="LC123",
        path="",
        format="png",
        quality=95,
        embed_workflow=True,
        embed_civitai=True,
        hash_resources=True,
        metadata=None,
        filename_prefix="",
        prompt=None,
        extra_pnginfo=None,
    ):
        fmt = str(format or "png").lower().strip()
        if fmt in ("jpg", "jpeg"):
            fmt = "jpeg"
            ext = "jpg"
        elif fmt == "webp":
            ext = "webp"
        else:
            fmt = "png"
            ext = "png"
        quality = int(max(1, min(100, quality)))

        meta = _as_meta(metadata)
        prefix = _txt(filename_prefix)
        stem = _txt(filename) or "LC123"
        folder = _txt(path)
        if prefix and (not _txt(filename) or filename == "LC123"):
            combined = prefix
        else:
            combined = _join_path(folder, stem) if folder else stem

        output_dir = folder_paths.get_output_directory()
        batch = images
        if hasattr(batch, "cpu"):
            batch = batch.detach().cpu()
        n = int(batch.shape[0]) if hasattr(batch, "shape") else len(batch)

        first = _tensor_to_pil(batch[0])
        full_dir, file_stem, counter, subfolder, _pfx = folder_paths.get_save_image_path(
            combined or "LC123", output_dir, first.size[0], first.size[1]
        )
        os.makedirs(full_dir, exist_ok=True)

        results = []
        last_path = ""

        for i in range(n):
            pil = _tensor_to_pil(batch[i])
            width, height = pil.size
            params = ""
            hash_bits = None
            buckets = None
            if hash_resources or embed_civitai:
                try:
                    buckets = collect_hashes(prompt, extra_pnginfo)
                    hash_bits = format_hash_fields(buckets)
                except Exception as e:
                    print(f"[LC123] resource hash skip: {e}")
                    hash_bits = None
            if embed_civitai:
                params = _build_parameters(meta, width, height, hash_bits)

            fname = f"{file_stem}_{counter:05d}.{ext}"
            dest = os.path.join(full_dir, fname)
            while os.path.exists(dest):
                counter += 1
                fname = f"{file_stem}_{counter:05d}.{ext}"
                dest = os.path.join(full_dir, fname)
            counter += 1

            save_kwargs = {}
            if fmt == "png":
                info = PngInfo()
                if embed_workflow:
                    if prompt is not None:
                        info.add_text("prompt", json.dumps(prompt))
                    if extra_pnginfo is not None:
                        for k, v in extra_pnginfo.items():
                            if v is None:
                                continue
                            info.add_text(k, json.dumps(v) if not isinstance(v, str) else v)
                if params:
                    info.add_text("parameters", params)
                air = _txt(meta.get("civitai_air"))
                resources = civitai_resources_payload(air)
                if resources:
                    info.add_text("civitaiResources", json.dumps(resources))
                    info.add_text("civitai_air", air)
                if buckets and buckets.get("hashes_json"):
                    info.add_text("hashes", json.dumps(buckets["hashes_json"]))
                save_kwargs["pnginfo"] = info
            else:
                if pil.mode == "RGBA":
                    pil = pil.convert("RGB")
                save_kwargs["quality"] = quality
                if fmt == "webp":
                    save_kwargs["method"] = 4
                if params:
                    save_kwargs["comment"] = params[:20000]

            try:
                pil.save(dest, format="JPEG" if fmt == "jpeg" else fmt.upper(), **save_kwargs)
            except TypeError:
                save_kwargs.pop("comment", None)
                pil.save(dest, format="JPEG" if fmt == "jpeg" else fmt.upper(), **save_kwargs)
            last_path = dest
            results.append({
                "filename": fname,
                "subfolder": subfolder,
                "type": "output",
            })

        rel = last_path
        try:
            rel = os.path.relpath(last_path, output_dir)
        except Exception:
            pass

        return {
            "ui": {"images": results},
            "result": (images, rel.replace("\\", "/")),
        }


NODE_CLASS_MAPPINGS = {
    "LCSaveImage": LCSaveImage,
    "LCSaveImageMetadata": LCSaveImageMetadata,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "LCSaveImage": "LC Save Image 💾",
    "LCSaveImageMetadata": "LC Save Metadata 🏷️",
}
