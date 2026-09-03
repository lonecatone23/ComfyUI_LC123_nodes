"""
Local AutoV2 hashes for Civitai resource linking.

Civitai does not credit a checkpoint / CLIP / LoRA from the filename alone.
It matches the first 10 hex chars of SHA-256 (AutoV2) in the PNG ``parameters``
chunk: Model hash, Lora hashes, and the Hashes JSON object.
"""

from __future__ import annotations

import hashlib
import os
import re

import folder_paths

_FILE_EXT = re.compile(r"\.(safetensors|sft|gguf|ckpt|pt|bin|pth)$", re.I)
_LORA_TAG = re.compile(r"<lora:([^:>]+)(?::[^>]+)?>", re.I)

# folder_paths keys to try, in order, per guessed kind
_FOLDERS = (
    "checkpoints",
    "diffusion_models",
    "unet",
    "loras",
    "text_encoders",
    "clip",
    "clip_vision",
    "vae",
    "controlnet",
    "embeddings",
    "style_models",
    "photomaker",
)

_KIND_BY_FOLDER = {
    "checkpoints": "model",
    "diffusion_models": "unet",
    "unet": "unet",
    "loras": "lora",
    "text_encoders": "clip",
    "clip": "clip",
    "clip_vision": "clip",
    "vae": "vae",
    "controlnet": "controlnet",
    "embeddings": "embed",
    "style_models": "style",
    "photomaker": "photomaker",
}

_WIDGET_HINT = {
    "ckpt_name": "checkpoints",
    "ckpt_name_1": "checkpoints",
    "ckpt_name_2": "checkpoints",
    "unet_name": "diffusion_models",
    "model_name": "checkpoints",
    "lora_name": "loras",
    "clip_name": "text_encoders",
    "clip_name1": "text_encoders",
    "clip_name2": "text_encoders",
    "clip_name3": "text_encoders",
    "t5_name": "text_encoders",
    "vae_name": "vae",
    "control_net_name": "controlnet",
    "controlnet_name": "controlnet",
}


def autov2(path: str) -> str | None:
    """Return AutoV2 (sha256[:10].upper()). Cache full hex next to the file."""
    if not path or not os.path.isfile(path):
        return None
    sidecar = os.path.splitext(path)[0] + ".sha256"
    digest = None
    if os.path.isfile(sidecar):
        try:
            with open(sidecar, "r", encoding="utf-8", errors="replace") as f:
                digest = f.read().strip().split()[0]
        except OSError:
            digest = None
    if not digest or len(digest) < 10:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        digest = h.hexdigest()
        try:
            with open(sidecar, "w", encoding="utf-8") as f:
                f.write(digest)
        except OSError:
            pass
    return digest[:10].upper()


def _resolve(name: str, prefer: str | None = None) -> tuple[str | None, str | None]:
    """Return (full_path, kind) for a model filename."""
    name = (name or "").strip().replace("\\", "/")
    if not name or name.lower() in ("none", "undefined"):
        return None, None
    folders = []
    if prefer:
        folders.append(prefer)
        # unet vs diffusion_models alias
        if prefer == "diffusion_models":
            folders.append("unet")
        if prefer == "unet":
            folders.append("diffusion_models")
        if prefer == "text_encoders":
            folders.extend(["clip", "clip_vision"])
        if prefer == "clip":
            folders.append("text_encoders")
    for f in _FOLDERS:
        if f not in folders:
            folders.append(f)
    for folder in folders:
        try:
            path = folder_paths.get_full_path(folder, name)
        except Exception:
            path = None
        if path and os.path.isfile(path):
            return path, _KIND_BY_FOLDER.get(folder, "model")
        # basename fallback
        base = os.path.basename(name)
        if base != name:
            try:
                path = folder_paths.get_full_path(folder, base)
            except Exception:
                path = None
            if path and os.path.isfile(path):
                return path, _KIND_BY_FOLDER.get(folder, "model")
    return None, None


def _walk_strings(obj, out: list):
    if isinstance(obj, str):
        if _FILE_EXT.search(obj) or obj.startswith("<lora:"):
            out.append(obj)
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("prompt", "extra_pnginfo", "workflow"):
                _walk_strings(v, out)
            else:
                _walk_strings(v, out)
        return
    if isinstance(obj, (list, tuple)):
        for v in obj:
            _walk_strings(v, out)


def _hint_for_key(key: str) -> str | None:
    k = str(key or "").lower()
    if k in _WIDGET_HINT:
        return _WIDGET_HINT[k]
    if "lora" in k:
        return "loras"
    if "unet" in k or k.endswith("dit_name"):
        return "diffusion_models"
    if "clip" in k or "text_encod" in k or k.startswith("t5"):
        return "text_encoders"
    if "vae" in k:
        return "vae"
    if "control" in k:
        return "controlnet"
    if "ckpt" in k or k == "ckpt_name":
        return "checkpoints"
    if "embed" in k:
        return "embeddings"
    return None


def _lora_enabled(entry) -> bool:
    """Power Lora / similar slot: honor on/enabled and skip zero strength."""
    if not isinstance(entry, dict):
        return True
    if "on" in entry and not entry.get("on"):
        return False
    if "enabled" in entry and not entry.get("enabled"):
        return False
    for k in ("strength", "strength_model", "strength_clip"):
        if k in entry:
            try:
                if float(entry.get(k) or 0) == 0.0:
                    return False
            except (TypeError, ValueError):
                pass
    return True


def _hint_from_class(class_type: str) -> str | None:
    low = (class_type or "").lower()
    if "lora" in low:
        return "loras"
    if "unet" in low or "diffusion" in low or "gguf" in low and "clip" not in low and "vae" not in low:
        return "diffusion_models"
    if "clip" in low or "textencod" in low or "text_encod" in low:
        return "text_encoders"
    if "vae" in low:
        return "vae"
    if "controlnet" in low or "control_net" in low:
        return "controlnet"
    if "checkpoint" in low:
        return "checkpoints"
    return None


def _collect_from_prompt(prompt, skip_ids=None) -> list[tuple[str, str | None]]:
    """List of (filename, folder_hint). Honors LoRA on/off. Skips muted/bypassed ids."""
    found: list[tuple[str, str | None]] = []
    seen = set()
    skip_ids = skip_ids or set()

    def add(name: str, hint: str | None):
        name = (name or "").strip()
        if not name or name in seen:
            return
        if name.lower() in ("none", "undefined"):
            return
        seen.add(name)
        found.append((name, hint))

    def take_value(val, hint):
        if isinstance(val, str):
            if _FILE_EXT.search(val):
                add(val, hint)
            for m in _LORA_TAG.finditer(val):
                add(m.group(1), "loras")
            return
        if isinstance(val, dict):
            if not _lora_enabled(val):
                return
            lname = val.get("lora") or val.get("lora_name") or val.get("name")
            if isinstance(lname, str) and lname:
                add(lname, "loras")
            elif isinstance(val.get("model"), str) and _FILE_EXT.search(val["model"]):
                add(val["model"], hint)

    if not isinstance(prompt, dict):
        return found

    for nid, node in prompt.items():
        if not isinstance(node, dict):
            continue
        if str(nid) in skip_ids:
            continue
        class_type = str(node.get("class_type") or node.get("type") or "")
        hint_node = _hint_from_class(class_type)
        inputs = node.get("inputs") if isinstance(node.get("inputs"), dict) else {}
        for key, val in inputs.items():
            take_value(val, _hint_for_key(key) or hint_node)
        widgets = node.get("widgets_values")
        if isinstance(widgets, (list, tuple)):
            for val in widgets:
                take_value(val, hint_node)
        elif isinstance(widgets, dict):
            for key, val in widgets.items():
                take_value(val, _hint_for_key(key) or hint_node)
    return found


def collect_hashes(prompt=None, extra_pnginfo=None) -> dict:
    """
    Return {
      'model': [(name, autov2), ...],
      'lora': [...],
      'clip': [...],
      'unet': [...],
      'vae': [...],
      'controlnet': [...],
      'embed': [...],
      'hashes_json': {key: autov2},
    }
    """
    buckets = {
        "model": [],
        "lora": [],
        "clip": [],
        "unet": [],
        "vae": [],
        "controlnet": [],
        "embed": [],
        "style": [],
        "photomaker": [],
    }
    hashes_json = {}

    skip_ids = set()
    wf = None
    if isinstance(extra_pnginfo, dict):
        wf = extra_pnginfo.get("workflow")
    if isinstance(wf, dict) and isinstance(wf.get("nodes"), list):
        for n in wf["nodes"]:
            if not isinstance(n, dict):
                continue
            # 2 = mute, 4 = bypass
            if n.get("mode") in (2, 4):
                skip_ids.add(str(n.get("id", "")))

    candidates = _collect_from_prompt(prompt, skip_ids)
    if isinstance(wf, dict) and isinstance(wf.get("nodes"), list):
        fake_prompt = {}
        for i, n in enumerate(wf["nodes"]):
            if not isinstance(n, dict):
                continue
            if n.get("mode") in (2, 4):
                continue
            fake_prompt[str(n.get("id", i))] = {
                "class_type": n.get("type"),
                "widgets_values": n.get("widgets_values"),
                "inputs": {},
            }
        candidates.extend(_collect_from_prompt(fake_prompt, skip_ids))

    seen_path = set()
    for name, hint in candidates:
        path, kind = _resolve(name, hint)
        if not path or path in seen_path:
            continue
        seen_path.add(path)
        digest = autov2(path)
        if not digest:
            continue
        kind = kind or "model"
        label = os.path.splitext(os.path.basename(path))[0]
        buckets.setdefault(kind, []).append((label, digest))
        if kind == "model":
            hashes_json.setdefault("model", digest)
            # extra models get model:Name
            if "model" in hashes_json and hashes_json["model"] != digest:
                hashes_json[f"model:{label}"] = digest
        elif kind == "lora":
            hashes_json[f"lora:{label}"] = digest
        elif kind == "clip":
            hashes_json[f"clip:{label}"] = digest
        elif kind == "unet":
            hashes_json[f"unet:{label}"] = digest
        elif kind == "vae":
            hashes_json.setdefault("vae", digest)
            hashes_json[f"vae:{label}"] = digest
        elif kind == "embed":
            hashes_json[f"embed:{label}"] = digest
        else:
            hashes_json[f"{kind}:{label}"] = digest

    buckets["hashes_json"] = hashes_json
    return buckets


def civitai_resources_payload(air: str) -> list:
    """Civitai reads this JSON (PNG chunk + parameters line), not 'AIR: ...'."""
    air = (air or "").strip()
    if not air:
        return []
    item = {"air": air}
    if air.lower().startswith("http"):
        item = {"url": air}
    return [item]


def format_hash_fields(buckets: dict) -> tuple[str, str, str]:
    """
    Model hash line fragment, Lora hashes fragment, Hashes JSON fragment.
    Empty strings when nothing found.
    """
    models = buckets.get("model") or []
    unets = buckets.get("unet") or []
    primary = models[0][1] if models else (unets[0][1] if unets else "")
    model_hash = f"Model hash: {primary}" if primary else ""

    loras = buckets.get("lora") or []
    lora_part = ""
    if loras:
        inner = ", ".join(f"{name}: {digest}" for name, digest in loras)
        lora_part = f'Lora hashes: "{inner}"'

    import json

    hj = buckets.get("hashes_json") or {}
    hashes_part = f"Hashes: {json.dumps(hj, separators=(',', ':'))}" if hj else ""
    return model_hash, lora_part, hashes_part
