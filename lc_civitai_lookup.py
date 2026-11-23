"""
CivitAI links for videos.

CivitAI links a picture's models and LoRAs by the file hashes in its parameters, but from a video it reads only the
ComfyUI prompt + workflow tags, and those carry no hashes. The only link a video can carry is a CivitAI AIR. This
module turns the hashes LC already computes into AIRs with CivitAI's public by-hash lookup, one call per file, kept
in a cache in the ComfyUI user folder. Only runs when the civitai_lookup switch on LC Save Video is on.
"""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.request

import folder_paths

from .lc_civitai_hashes import collect_hashes

_URL = "https://civitai.com/api/v1/model-versions/by-hash/{}"
_TIMEOUT = 6
_MISS_DAYS = 7  # a file not found on CivitAI is asked again after a week (it may have been uploaded since)
_LOCK = threading.Lock()
_CACHE = None


def _cache_path() -> str:
    try:
        base = folder_paths.get_user_directory()
    except Exception:
        base = os.path.join(os.path.dirname(folder_paths.__file__), "user")
    return os.path.join(base, "LC", "civitai_air_cache.json")


def _load() -> dict:
    global _CACHE
    if _CACHE is None:
        try:
            with open(_cache_path(), encoding="utf-8") as f:
                _CACHE = json.load(f)
        except (OSError, ValueError):
            _CACHE = {}
    return _CACHE


def _save() -> None:
    path = _cache_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(_CACHE, f, indent=1)
        os.replace(tmp, path)
    except OSError as e:
        print(f"[LC CivitAI lookup] cache not saved: {e}")


def air_for_hash(autov2: str) -> str | None:
    """CivitAI AIR for an AutoV2 hash, or None when the file is not on CivitAI (or CivitAI can't be reached)."""
    key = (autov2 or "").upper()
    if not key:
        return None
    with _LOCK:
        cache = _load()
        hit = cache.get(key)
        if hit and (hit.get("air") or time.time() - hit.get("t", 0) < _MISS_DAYS * 86400):
            return hit.get("air")
    req = urllib.request.Request(_URL.format(key), headers={"User-Agent": "ComfyUI-LC-nodes"})
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
            data = json.loads(r.read().decode("utf-8"))
        air = data.get("air") if isinstance(data, dict) else None
    except urllib.error.HTTPError as e:
        if e.code != 404:
            print(f"[LC CivitAI lookup] {key}: HTTP {e.code}, skipped this time")
            return None
        air = None
    except Exception as e:  # offline, timeout, bad answer: not cached, tried again next save
        print(f"[LC CivitAI lookup] {key}: {e}, skipped this time")
        return None
    with _LOCK:
        _load()[key] = {"air": air, "t": int(time.time())}
        _save()
    return air


def _strengths(prompt) -> dict:
    """LoRA file stem -> model strength, read from the loaders in the graph."""
    out = {}

    def note(name, value):
        if isinstance(name, str) and name:
            stem = os.path.splitext(os.path.basename(name.replace("\\", "/")))[0].lower()
            try:
                out.setdefault(stem, float(value))
            except (TypeError, ValueError):
                pass

    def rows(val):
        if isinstance(val, str) and val.strip()[:1] == "[":
            try:
                val = json.loads(val)
            except ValueError:
                return
        if isinstance(val, dict) and isinstance(val.get("__value__"), list):
            val = val["__value__"]
        if isinstance(val, list):
            for r in val:
                rows(r)
        elif isinstance(val, dict):
            name = val.get("lora") or val.get("lora_name") or val.get("name")
            note(name, val.get("strength", val.get("strength_model", 1.0)))

    for node in (prompt or {}).values():
        inputs = node.get("inputs") if isinstance(node, dict) else None
        if not isinstance(inputs, dict):
            continue
        if "lora_name" in inputs:
            note(inputs["lora_name"], inputs.get("strength_model", inputs.get("strength", 1.0)))
        for v in inputs.values():
            rows(v)
    return out


def lookup_links(prompt, extra_pnginfo=None) -> list:
    """[{air, name, kind, strength}] for every model, LoRA, VAE, encoder... in the graph that CivitAI knows."""
    try:
        buckets = collect_hashes(prompt, extra_pnginfo)
    except Exception as e:
        print(f"[LC CivitAI lookup] hashes failed: {e}")
        return []
    strengths = _strengths(prompt)
    links, seen = [], set()
    for kind, items in buckets.items():
        if kind == "hashes_json" or not isinstance(items, list):
            continue
        for label, digest in items:
            air = air_for_hash(digest)
            if not air or air in seen:
                continue
            seen.add(air)
            links.append({"air": air, "name": label, "kind": kind,
                          "strength": strengths.get(label.lower(), 1.0) if kind == "lora" else 1.0})
    return links
