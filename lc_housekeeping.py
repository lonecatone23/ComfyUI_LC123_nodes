"""LC Settings ⚙️ > Housekeeping > Delete nuisance folders.

Other packs make folders in output / input every time ComfyUI starts (or the node list loads), used or not. With the
setting on, the browser calls /lc123/nuisance_folders once the node list has loaded. A folder is removed only when:
  - it sits right in output or input (never deeper, so project folders are out of reach),
  - it is empty (no files anywhere inside; empty subfolders don't count),
  - another pack's code names it (found by searching the installed packs' .py files, which also says which pack makes
    it), or it is on the known list below.
LC folders and ComfyUI's own folders are never touched. The packs make their folder again the moment a node needs it.
"""
import hashlib
import json
import os
import re
import threading

import folder_paths
from aiohttp import web
from server import PromptServer

# known makers, kept even if the code search can't run
KNOWN = {
    "MiniMaxH3_Presets": "ComfyUI-MiniMaxH3-TimelineDirector",
    "VRGDG_Model_Defaults": "comfyui-vrgamedevgirl",
    "VRGDG_TEMP": "comfyui-vrgamedevgirl",
    "VRGDG_AudioFiles": "comfyui-vrgamedevgirl",
    "VRGDG_LLM_Instruction_Presets": "comfyui-vrgamedevgirl",
    "VRGDG_VideoEnhancer": "comfyui-vrgamedevgirl",
    "VRGDG_AdjustPresets": "comfyui-vrgamedevgirl",
    "vrgdg_long_video_uploads": "comfyui-vrgamedevgirl",
}
# ComfyUI's own folders: never removed, whatever a pack's code says
CORE = {"3d", "clipspace", "pasted", "webcam", "temp", "audio", "video", "images", "_output_images_will_be_put_here"}
_LOCK = threading.Lock()
_CACHE_FILE = None
_last = {"removed": [], "kept": []}


def _is_lc(name: str) -> bool:
    return name.upper().startswith("LC")


def _has_files(path: str) -> bool:
    for _root, _dirs, files in os.walk(path):
        if files:
            return True
    return False


def _remove_empty_tree(path: str) -> None:
    """Remove a folder that holds only (empty) folders, deepest first."""
    for root, dirs, _files in os.walk(path, topdown=False):
        for d in dirs:
            os.rmdir(os.path.join(root, d))
    os.rmdir(path)


def _pack_files() -> list:
    """(pack, path) for every .py file of the installed packs except the LC ones."""
    out = []
    for base in folder_paths.get_folder_paths("custom_nodes"):
        if not os.path.isdir(base):
            continue
        for pack in os.listdir(base):
            root = os.path.join(base, pack)
            if _is_lc(pack.replace("ComfyUI_", "").replace("comfyui_", "")) or pack.startswith((".", "__")):
                continue
            if os.path.isfile(root) and pack.endswith(".py"):
                out.append((pack[:-3], root))
                continue
            if not os.path.isdir(root):
                continue
            for r, dirs, files in os.walk(root):
                dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", "node_modules", ".venv", "venv", "tests", "test")]
                out.extend((pack, os.path.join(r, f)) for f in files if f.endswith(".py"))
    return out


def _signature(files: list) -> str:
    h = hashlib.sha1()
    for _pack, p in sorted(files, key=lambda x: x[1]):
        try:
            st = os.stat(p)
            h.update(f"{p}|{st.st_mtime_ns}|{st.st_size}".encode("utf-8", "replace"))
        except OSError:
            pass
    return h.hexdigest()


def _cache_path() -> str:
    global _CACHE_FILE
    if _CACHE_FILE is None:
        _CACHE_FILE = os.path.join(folder_paths.get_user_directory(), "lc123_nuisance_folders.json")
    return _CACHE_FILE


def _makers(names: list) -> dict:
    """{folder name: pack} for the names a pack's code mentions as a quoted string or a path part ("VRGDG_TEMP",
    'presets/MiniMaxH3_Presets'). Results are cached until a pack is added, removed or updated."""
    files = _pack_files()
    sig = _signature(files)
    try:
        with open(_cache_path(), encoding="utf-8") as f:
            cache = json.load(f)
    except (OSError, ValueError):
        cache = {}
    if cache.get("sig") != sig:
        cache = {"sig": sig, "hits": {}}
    hits = cache["hits"]
    todo = [n for n in names if n not in hits]
    if todo:
        pats = {n: re.compile(r"""["'/\\]""" + re.escape(n) + r"""["'/\\]""") for n in todo}
        found = {n: "" for n in todo}
        for pack, p in files:
            if all(found.values()):
                break
            try:
                with open(p, encoding="utf-8", errors="ignore") as f:
                    text = f.read()
            except OSError:
                continue
            for n, pat in pats.items():
                if not found[n] and n in text and pat.search(text):
                    found[n] = pack
        hits.update(found)
        try:
            with open(_cache_path(), "w", encoding="utf-8") as f:
                json.dump(cache, f, indent=1)
        except OSError:
            pass
    return {n: hits.get(n) or "" for n in names}


def clean() -> dict:
    """Remove the empty nuisance folders. -> {"removed": ["output/X (pack)", ...], "kept": [...]}"""
    global _last
    with _LOCK:
        bases = {"output": folder_paths.get_output_directory(), "input": folder_paths.get_input_directory()}
        empty = []
        for where, base in bases.items():
            if not os.path.isdir(base):
                continue
            for name in os.listdir(base):
                path = os.path.join(base, name)
                if os.path.isdir(path) and not os.path.islink(path) and name not in CORE and not _is_lc(name) and not _has_files(path):
                    empty.append((where, name, path))
        try:
            makers = _makers(sorted({n for _w, n, _p in empty if n not in KNOWN}))
        except Exception as e:  # the search failed: only the known list counts this time
            print(f"[LC123] Nuisance folders: pack search skipped ({e})")
            makers = {}
        removed, kept = [], []
        for where, name, path in empty:
            pack = KNOWN.get(name) or makers.get(name)
            if not pack:
                continue  # no pack makes it: the user's own empty folder
            try:
                _remove_empty_tree(path)
                removed.append(f"{where}/{name} ({pack})")
            except OSError as e:  # in use, or a file appeared a moment ago: leave it
                kept.append(f"{where}/{name} ({e.strerror})")
        if removed:
            print(f"[LC123] Removed empty nuisance folders: {', '.join(removed)}")
        _last = {"removed": removed, "kept": kept}
        return _last


@PromptServer.instance.routes.post("/lc123/nuisance_folders")
async def nuisance_folders(request):
    import asyncio

    return web.json_response(await asyncio.get_running_loop().run_in_executor(None, clean))


@PromptServer.instance.routes.get("/lc123/nuisance_folders")
async def nuisance_folders_last(request):
    return web.json_response(_last)
