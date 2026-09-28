"""
Local AutoV2 hashes for CivitAI resource linking.

CivitAI does not credit a checkpoint / CLIP / LoRA from the filename alone.
It matches the first 10 hex chars of SHA-256 (AutoV2) in the PNG ``parameters``
chunk: Model hash, Lora hashes, and the Hashes JSON object.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from urllib.parse import parse_qs, urlparse

import folder_paths

from .lc_lora_metadata import parse_lc_lora_rows, _image_ancestors, _resolve as _resolve_input
from .lc_lora_weights import row_strengths

_FILE_EXT = re.compile(r"\.(safetensors|sft|gguf|ckpt|pt|bin|pth)$", re.I)
_LORA_TAG = re.compile(r"<lora:([^:>]+)(?::[^>]+)?>", re.I)

# folder_paths keys to try, in order, per guessed kind
_FOLDERS = (
    "checkpoints",
    "diffusion_models",
    "unet",
    "unet_gguf",
    "loras",
    "text_encoders",
    "clip",
    "clip_gguf",
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
    "unet_gguf": "unet",
    "loras": "lora",
    "text_encoders": "clip",
    "clip": "clip",
    "clip_gguf": "clip",
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


# In-process AutoV2 cache: (path, size, mtime) -> AutoV2. A changed file gets a
# new key, so a stale entry is never returned.
_AUTOV2_CACHE: dict = {}
_AUTOV2_CACHE_MAX = 512


def autov2(path: str) -> str | None:
    """Return AutoV2 (sha256[:10].upper()). Cache full hex next to the file."""
    if not path or not os.path.isfile(path):
        return None
    try:
        st = os.stat(path)
        key = (os.path.normcase(os.path.abspath(path)), st.st_size, st.st_mtime_ns)
    except OSError:
        return None
    cached = _AUTOV2_CACHE.get(key)
    if cached:
        return cached
    sidecar = os.path.splitext(path)[0] + ".sha256"
    digest = None
    if os.path.isfile(sidecar):
        try:
            # model file newer than its sidecar = sidecar is stale, rehash
            if os.path.getmtime(sidecar) >= st.st_mtime:
                with open(sidecar, "r", encoding="utf-8", errors="replace") as f:
                    digest = f.read().strip().split()[0]
        except (OSError, IndexError):
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
    result = digest[:10].upper()
    if len(_AUTOV2_CACHE) >= _AUTOV2_CACHE_MAX:
        _AUTOV2_CACHE.clear()
    _AUTOV2_CACHE[key] = result
    return result


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
            folders.extend(["unet", "unet_gguf"])
        if prefer == "unet":
            folders.extend(["diffusion_models", "unet_gguf"])
        if prefer == "text_encoders":
            folders.extend(["clip", "clip_vision", "clip_gguf"])
        if prefer == "clip":
            folders.extend(["text_encoders", "clip_gguf"])
        # ComfyUI-GGUF registers .gguf files under separate "unet_gguf"/"clip_gguf"
        # folder_paths keys (same directory, different extension whitelist) -- a
        # .gguf file never resolves through the vanilla key it reuses the path of.
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
    """Power Lora / similar slot: honor on/enabled and skip only when every
    strength present is zero (model 0 + clip 1 still applies the LoRA)."""
    if not isinstance(entry, dict):
        return True
    if "on" in entry and not entry.get("on"):
        return False
    if "enabled" in entry and not entry.get("enabled"):
        return False
    if 'strength' in entry:
        weights = [entry['strength'], entry.get('strengthTwo') if entry.get('strengthTwo') is not None else entry['strength']]
    else:
        weights = [entry[k] for k in ('strength_model', 'strength_clip') if k in entry]
    try:
        if weights and all(float(v) == 0.0 for v in weights):
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
            # LC LoRA Loader (and LC LoRA Loader Stack) keep their whole row list in ONE STRING
            # widget as a JSON array -- e.g. '[{"on": true, "lora": "x.safetensors", ...}]' --
            # unlike rgthree's Power Lora Loader, which stores each row as its own real dict in
            # widgets_values. Neither pattern above matches a JSON-encoded string (it doesn't end
            # in a model extension, and it isn't an A1111 <lora:...> tag), so without this, every
            # LoRA picked in LC LoRA Loader was invisible here: no hash, no CivitAI resource entry.
            stripped = val.strip()
            if stripped[:1] in ("[", "{"):
                try:
                    parsed = json.loads(stripped)
                except (ValueError, TypeError):
                    parsed = None
                if parsed is not None:
                    take_value(parsed, hint)
            return
        if isinstance(val, (list, tuple)):
            for item in val:
                take_value(item, hint)
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
        if class_type in ('LCLoraLoader', 'LCGroupLoraLoader', 'LCGroupLoraLoaderStack'):
            widgets = node.get('widgets_values')
            values = [inputs.get('lora_rows')]
            if isinstance(widgets, dict):
                values.append(widgets.get('lora_rows'))
            elif isinstance(widgets, (list, tuple)):
                values.extend(widgets)
            for value in values:
                for row in parse_lc_lora_rows(value):
                    name = row.get('lora')
                    weights = row_strengths(row) if class_type != 'LCLoraLoader' else (row['strength'],)
                    if row.get('on') and any(weight != 0.0 for weight in weights) and isinstance(name, str):
                        add(name, 'loras')
            continue
        if not _lora_enabled(inputs):
            continue
        for key, val in inputs.items():
            if key in ('text', 'prompt', 'positive', 'negative', 'positive_prompt', 'negative_prompt'):
                continue
            hint = _hint_for_key(key) or hint_node
            if hint is not None:
                take_value(_resolve_input(val, prompt), hint)
        widgets = node.get("widgets_values")
        if isinstance(widgets, (list, tuple)):
            for val in widgets:
                take_value(val, hint_node)
        elif isinstance(widgets, dict):
            for key, val in widgets.items():
                take_value(val, _hint_for_key(key) or hint_node)
    return found


def collect_hashes(prompt=None, extra_pnginfo=None, save_node_id=None, *, lora_metadata=None, excluded_lora_paths=()) -> dict:
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

    # A save node only describes its image ancestry, never unrelated canvas branches.
    # Without a known save root, retain the standalone helper's legacy scan.
    scope = _image_ancestors(prompt or {}, save_node_id) if save_node_id is not None else None
    if save_node_id is not None and scope is None:
        scope = set()
    scoped_prompt = prompt if scope is None else {k: v for k, v in (prompt or {}).items() if str(k) in scope}
    candidates = _collect_from_prompt(scoped_prompt, skip_ids)
    if isinstance(wf, dict) and isinstance(wf.get("nodes"), list):
        # only workflow nodes that actually run (their id is in the prompt);
        # nodes cut off from any output are not in the prompt
        run_ids = {str(k) for k in prompt.keys()} if isinstance(prompt, dict) else None
        fake_prompt = {}
        for i, n in enumerate(wf["nodes"]):
            if not isinstance(n, dict):
                continue
            if n.get("mode") in (2, 4):
                continue
            if (scope is not None and str(n.get("id", i)) not in scope) or (run_ids is not None and str(n.get("id", i)) not in run_ids):
                continue
            fake_prompt[str(n.get("id", i))] = {
                "class_type": n.get("type"),
                "widgets_values": n.get("widgets_values"),
                "inputs": {},
            }
        candidates.extend(_collect_from_prompt(fake_prompt, skip_ids))

    active_loras = None
    if lora_metadata is not None:
        active_loras = {row['filename'] for row in lora_metadata.get('loras', [])
                        if row['scope'] == 'image_upstream' and row['nonzero_or_unresolved']}
        candidates.extend((name, 'loras') for name in sorted(active_loras))
    excluded = {os.path.normcase(os.path.abspath(path)) for path in excluded_lora_paths}
    seen_path = set()
    seen_hash = set()
    for name, hint in candidates:
        path, kind = _resolve(name, hint)
        if not path or path in seen_path:
            continue
        if kind == 'lora' and (os.path.normcase(os.path.abspath(path)) in excluded
                               or (active_loras is not None and name not in active_loras)):
            continue
        seen_path.add(path)
        digest = autov2(path)
        if not digest:
            continue
        kind = kind or "model"
        identity = ("model" if kind == "unet" else kind, digest)
        if identity in seen_hash:
            continue
        seen_hash.add(identity)
        label = os.path.splitext(os.path.basename(path))[0]
        buckets.setdefault(kind, []).append((label, digest))
        if kind in ("model", "unet"):
            if "model" not in hashes_json:
                hashes_json["model"] = digest
                buckets['primary_model'] = label
            elif hashes_json['model'] != digest:
                hashes_json[f"model:{label}"] = digest
        elif kind == "lora":
            hashes_json[f"lora:{label}"] = digest
        elif kind == "clip":
            hashes_json[f"clip:{label}"] = digest
        elif kind == "vae":
            if "vae" not in hashes_json:
                hashes_json['vae'] = digest
            elif hashes_json['vae'] != digest:
                hashes_json[f"vae:{label}"] = digest
        elif kind == "embed":
            hashes_json[f"embed:{label}"] = digest
        else:
            hashes_json[f"{kind}:{label}"] = digest

    buckets["hashes_json"] = hashes_json
    return buckets


_AIR_RE = re.compile(
    r"^(?:urn:air:|air:)?(?P<ecosystem>[^:]+):(?P<type>[^:]+):(?P<source>[^:]+):(?P<rest>.+)$"
)
_MODEL_URL_RE = re.compile(
    r"^https://(?:www\.)?civitai\.com/models/(\d+)(?:/[^/?#]*)?/?(?:\?(.*))?$", re.I
)
_CIVITAI_TYPE_ALIASES = {
    "diffusion_model": "diffusionmodel",
    "embed": "embedding",
    "hypernetwork": "hypernet",
    "textual_inversion": "embedding",
    "textualinversion": "embedding",
    "text_encoder": "text_encoders",
    "textencoder": "text_encoders",
    "aestheticgradient": "ag",
    "motionmodule": "motion",
}


def _positive_int(value) -> int | None:
    try:
        n = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


def civitai_resources_payload(air: str) -> list:
    """
    Build the ``CivitAI resources`` array CivitAI's parser actually reads:
    ``[{"type": "checkpoint", "modelVersionId": 128713, "air": "urn:air:..."}]``.
    A bare AIR or URL string on its own (the old shape here -- ``{"air": ...}``
    or ``{"url": ...}``) isn't a field CivitAI's parser recognizes: it keys a
    resource off ``type`` + ``modelVersionId``, so without those two an entry
    is worse than useless and gets silently ignored -- which is exactly why a
    custom merge with no CivitAI-known hash could never get credited before.

    Accepts a full AIR URN (``urn:air:<eco>:<type>:civitai:<modelId>@<versionId>``),
    a CivitAI model URL with ``?modelVersionId=``, or a bare model-version ID.
    """
    air = (air or "").strip()
    if not air:
        return []

    if air.isdecimal():
        version_id = _positive_int(air)
        return [{"type": "checkpoint", "modelVersionId": version_id}] if version_id else []

    if air.lower().startswith("https://"):
        parsed = urlparse(air)
        if parsed.hostname not in ("civitai.com", "www.civitai.com"):
            return []
        m = _MODEL_URL_RE.match(air)
        if not m:
            return []
        model_id = int(m.group(1))
        versions = parse_qs(m.group(2) or "").get("modelVersionId", [])
        version_id = _positive_int(versions[0]) if len(versions) == 1 else None
        if version_id is None:
            return []
        return [{"type": "checkpoint", "modelId": model_id, "modelVersionId": version_id}]

    m = _AIR_RE.match(air)
    if not m or m.group("source").lower() != "civitai":
        return []
    res_type = m.group("type").strip().lower()
    res_type = _CIVITAI_TYPE_ALIASES.get(res_type, res_type)
    rest = m.group("rest").split("+", 1)[0]  # drop optional +fileId(.format) tail
    model_id_s, sep, version_s = rest.partition("@")
    if not sep:
        return []
    if "." in version_s:
        version_s = version_s.rsplit(".", 1)[0]  # drop optional .format suffix
    version_id = _positive_int(version_s)
    if version_id is None:
        return []
    item = {"type": res_type, "modelVersionId": version_id, "air": air}
    model_id = _positive_int(model_id_s)
    if model_id is not None:
        item["modelId"] = model_id
    return [item]


# Identity is cached only while both the model file and its sidecar are unchanged.
_LORA_RESOURCE_CACHE = {}


def _lora_version(path):
    for sidecar in (os.path.splitext(path)[0] + '.civitai.info', path + '.civitai.info'):
        try:
            model_stat, info_stat = os.stat(path), os.stat(sidecar)
            signature = (model_stat.st_size, model_stat.st_mtime_ns, info_stat.st_size, info_stat.st_mtime_ns)
            cached = _LORA_RESOURCE_CACHE.get((path, sidecar))
            if cached and cached[0] == signature:
                return cached[1]
            with open(sidecar, encoding='utf-8-sig') as stream:
                info = json.load(stream)
            if not isinstance(info, dict) or str(info.get('model', {}).get('type', '')).lower() not in ('lora', 'locon'):
                continue
            version_id = _positive_int(info.get('id'))
            model_id = _positive_int(info.get('modelId'))
            if not version_id or not model_id:
                continue
            digest = hashlib.sha256()
            with open(path, 'rb') as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                    digest.update(chunk)
            sha = digest.hexdigest().lower()
            if not any(isinstance(f, dict) and str((f.get('hashes') or {}).get('SHA256', '')).lower() == sha
                       for f in info.get('files', [])):
                continue
            result = {'type': 'lora', 'modelId': model_id, 'modelVersionId': version_id}
            _LORA_RESOURCE_CACHE[(path, sidecar)] = (signature, result)
            return result
        except (OSError, ValueError, TypeError, AttributeError):
            continue
    return None


def lora_resources_payload(metadata, resolved_paths=None):
    """Offline, hash-verified Civitai version identities for this image's active LoRAs."""
    resources = {}
    for row in metadata.get('loras', []):
        if row['scope'] != 'image_upstream' or not row['nonzero_or_unresolved']:
            continue
        path, kind = _resolve(row['filename'], 'loras')
        if not path or kind != 'lora':
            continue
        identity = _lora_version(path)
        if identity is not None:
            if resolved_paths is not None:
                resolved_paths.add(path)
            key = (identity['type'], identity['modelVersionId'])
            item = dict(identity)
            if row['strength_model'] is not None:
                item['weight'] = row['strength_model']
            if key not in resources:
                resources[key] = item
            elif resources[key].get('weight') != item.get('weight'):
                # One scalar cannot represent repeated applications with different weights.
                # Keep the version identity; per-slot strengths remain in lora_metadata.
                resources[key].pop('weight', None)
    return list(resources.values())


def format_hash_fields(buckets: dict) -> tuple[str, str, str, str]:
    """
    Model hash, VAE hash, Lora hashes, and Hashes JSON line fragments.
    Empty strings when nothing found.
    """
    primary = (buckets.get("hashes_json") or {}).get("model", "")
    model_hash = f"Model hash: {primary}" if primary else ""

    # Classic A1111/CivitAI field, same status as "Model hash:" -- never emitted before,
    # so a custom/non-CivitAI-known VAE had no way to get credited even though its hash
    # was already sitting in the Hashes JSON blob.
    vaes = buckets.get("vae") or []
    vae_hash = f"VAE hash: {vaes[0][1]}" if vaes else ""

    loras = buckets.get("lora") or []
    lora_part = ""
    if loras:
        inner = ", ".join(f"{name}: {digest}" for name, digest in loras)
        lora_part = f'Lora hashes: "{inner}"'

    hj = buckets.get("hashes_json") or {}
    hashes_part = f"Hashes: {json.dumps(hj, separators=(',', ':'))}" if hj else ""
    return model_hash, vae_hash, lora_part, hashes_part
