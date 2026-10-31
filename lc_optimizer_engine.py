"""
LC Optimizer engine, shared by the four LC Optimizer nodes (image, image pipe, video, video pipe).

Picks the model files for a base model and goal (from the System & Model Optimization Report when it has been
run, Comfy's defaults otherwise), downloads missing ones on first use, loads them through ComfyUI's own loaders
(split files, AIO checkpoints, GGUF via ComfyUI-GGUF or the calcuis gguf pack), applies the speed-ups that tested
fine on this machine, and checks the picked files against the base model from their headers alone (hints, never
a block).
"""

from __future__ import annotations

import json
import os
import re
import struct
import threading

import folder_paths

from . import lc_model_calc

RECOMMENDED = "★ Recommended"
DOWNLOAD = "⬇ Download: "
FROM_CKPT = "From checkpoint"
NONE = "None"
GOALS = ["Quality", "Optimal", "Fast"]

# which ComfyUI model folder a loader reads from
FOLDER_BY_LOADER = {
    "UNETLoader": "diffusion_models", "UNETLoader x2": "diffusion_models", "UnetLoaderGGUF": "diffusion_models",
    "CheckpointLoaderSimple": "checkpoints", "CLIPLoader": "text_encoders", "CLIPLoaderGGUF": "text_encoders",
    "LTXAVTextEncoderLoader": "text_encoders", "VAELoader": "vae", "LoraLoaderModelOnly": "loras",
    "LatentUpscaleModelLoader": "latent_upscale_models",
}
ROLE_FOLDERS = {
    "model": ["diffusion_models", "checkpoints"], "clip": ["text_encoders"], "vae": ["vae"], "audio_vae": ["vae", "checkpoints"],
    "upscaler": ["latent_upscale_models"], "lora": ["loras"],
}

# what each base model expects, read from the files ComfyUI ships (layers, hidden size, vision tower) and
# (latent channels, conv dims) for the VAE. Used only for hints.
TE_EXPECTS = {
    "anima": ("Qwen3 0.6B", 28, 1024, False), "flux2_klein_9b": ("Qwen3 8B", 36, 4096, False),
    "flux2_klein_9b_distilled": ("Qwen3 8B", 36, 4096, False),
    "flux3_klein": ("Qwen3-VL 4B", 36, 2560, True), "flux3_klein_base": ("Qwen3-VL 4B", 36, 2560, True),
    "ideogram4": ("Qwen3-VL 8B", 36, 4096, True), "krea2": ("Qwen3-VL 4B", 36, 2560, True),
    "ltx23": ("Gemma 3 12B", 48, 3840, True), "ltx25": ("Gemma 4 12B", 48, 3840, True),
    "minimax_h3": ("Qwen3-VL 32B (H3)", 50, 5120, True), "minimax_h3_fl2va": ("Qwen3-VL 32B (H3)", 50, 5120, True), "qwen_image_21": ("Qwen3-VL 8B", 36, 4096, True),
    "z_image_turbo": ("Qwen3 4B", 36, 2560, False), "krea2_raw": ("Qwen3-VL 4B", 36, 2560, True),
    "moss_image": ("Qwen3.5 9B", 32, 4096, True), "moss_image_base": ("Qwen3.5 9B", 32, 4096, True),
    "fibo2_edit_turbo": ("Qwen3-VL 4B", 36, 2560, True),
}
TE_NAMES = {(28, 1024, False): "Qwen3 0.6B", (36, 2560, False): "Qwen3 4B", (36, 4096, False): "Qwen3 8B",
            (36, 2560, True): "Qwen3-VL 4B", (36, 4096, True): "Qwen3-VL 8B", (50, 5120, True): "Qwen3-VL 32B (H3)",
            (48, 3840, True): "Gemma 12B", (32, 4096, True): "Qwen3.5 9B", (32, 4096, False): "Llama 3.1 8B",
            (26, 2304, False): "Gemma 2 2B", (30, 5120, True): "Mistral Small 3", (35, 1536, True): "Gemma 4 E2B",
            (42, 2560, True): "Gemma 4 E4B"}
VAE_EXPECTS = {"anima": (16, 5), "krea2": (16, 5), "z_image_turbo": (16, 4), "flux2_klein_9b": (32, 4), "flux2_klein_9b_distilled": (32, 4), "flux3_klein": (32, 4), "flux3_klein_base": (32, 4), "ideogram4": (32, 4),
               "qwen_image_21": (64, 5), "ltx25": (128, 2), "krea2_raw": (16, 5), "sdxl": (4, 4), "illustrious": (4, 4), "pony": (4, 4),
               "moss_image": (32, 4), "moss_image_base": (32, 4), "fibo2_edit_turbo": (32, 4)}
VAE_NAMES = {(16, 4): "16-channel 2D (Flux 1 / Z-Image)", (16, 5): "16-channel 3D (Wan / Qwen-Image)", (32, 4): "32-channel (Flux 2)",
             (64, 5): "64-channel (Qwen-Image 2.1)", (4, 4): "4-channel (SD / SDXL)", (128, 2): "128-channel (LTX)"}
MODEL_CLASSES = {"anima": "Anima", "flux2_klein_9b": "Flux2", "flux2_klein_9b_distilled": "Flux2", "ideogram4": "Ideogram4", "krea2": "Krea2", "ltx23": "LTXAV",
                 "ltx25": "LTXAV", "minimax_h3": "MiniMaxH3", "minimax_h3_fl2va": "MiniMaxH3", "qwen_image_21": "QwenImage21", "z_image_turbo": "ZImage",
                 "krea2_raw": "Krea2", "sdxl": "SDXL", "illustrious": "SDXL", "pony": "SDXL"}


# the extra parts each base model uses (the nodes are static; this only decides which pickers matter)
EXTRAS = {
    "minimax_h3": [("audio_vae", "VAE")],
    "minimax_h3_fl2va": [("audio_vae", "VAE")],
    "ltx23": [("audio_vae", "VAE"), ("latent_upscaler", "LATENT_UPSCALE_MODEL")],
    "ltx25": [("audio_vae", "VAE"), ("latent_upscaler", "LATENT_UPSCALE_MODEL")],
    "ideogram4": [("model_2", "MODEL")],
}
MAX_EXTRAS = 2

# "Custom": any model and workflow. No files, numbers or checks are known for it, so those show as unsupported;
# the speed-ups from the report still apply.
CUSTOM = {"custom": "image", "custom_video": "video"}
CUSTOM_NAME = "Custom"
UNSUPPORTED = "unsupported"
CLIP_AUTO = "auto"


def is_custom(profile_id):
    return profile_id in CUSTOM


def checkpoint_only(profile_id):
    """Base models shipped as one checkpoint (the SDXL family): the text encoder and VAE come from it."""
    prof = profiles().get(profile_id) or {}
    vs = variants(prof, "model") if prof.get("components") else []
    return bool(vs) and all(v.get("loader") == "CheckpointLoaderSimple" for v in vs)


def roles_for(profile_id):
    """The file pickers this base model uses."""
    prof = profiles().get(profile_id) or {}
    roles = ["model", "clip", "vae"]
    if profile_id == "custom_video":
        return roles + ["audio_vae", "upscaler", "lora"]
    extras = [n for n, _ in EXTRAS.get(profile_id, [])]
    if "audio_vae" in extras:
        roles.append("audio_vae")
    if "latent_upscaler" in extras:
        roles.append("upscaler")
    if prof and variants(prof, "lora"):
        roles.append("lora")
    return roles


# ---------------------------------------------------------------- profiles, report, files on disk
def profiles(kind=None):
    out = dict(lc_model_calc.load_profiles())
    for pid, k in CUSTOM.items():
        out[pid] = {"id": pid, "name": CUSTOM_NAME, "kind": k, "custom": True, "components": {}, "notes": []}
    return {k: v for k, v in out.items() if kind is None or v.get("kind") == kind}


# base model names that changed: saved workflows keep loading
LEGACY_BASE = {"MiniMax H3": "MiniMax H3 Ref2VA", "Flux.2 Klein base 9B": "Flux.2 Klein 9B (Base)"}


def base_names(kind):
    """[(id, name)] for the base model dropdown, image or video. Custom goes last."""
    return sorted(((k, v["name"]) for k, v in profiles(kind).items()), key=lambda x: (is_custom(x[0]), x[1].lower()))


def clip_types(kind):
    """The text encoder types a Custom pick can use (CLIPLoader's list, plus LTX 2.3's own loader for video)."""
    try:
        import nodes

        types = list(nodes.NODE_CLASS_MAPPINGS["CLIPLoader"].INPUT_TYPES()["required"]["type"][0])
    except Exception:
        types = ["stable_diffusion"]
    if kind == "video":
        types.append("LTXAVTextEncoderLoader")
    return [CLIP_AUTO] + types


def auto_clip_type(path):
    """Custom + auto: the clip type of the known base models whose text encoder has this shape, when only one fits."""
    sig = te_signature(path) if path else None
    if sig is None:
        return None, []
    found = set()
    for pid, want in TE_EXPECTS.items():
        if want[1:] == sig:
            prof = profiles().get(pid) or {}
            found |= {c.get("clip_type") for c in prof.get("components", {}).values() if c.get("role") == "text_encoder" and c.get("clip_type")}
    return (found.pop() if len(found) == 1 else None), sorted(found)


def report():
    """The saved System & Model Optimization Report, or None when it has not been run."""
    try:
        from . import lc_system_check

        with open(lc_system_check.profile_path(), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _list(folder):
    names = []
    try:
        names += folder_paths.get_filename_list(folder)
    except Exception:
        pass
    gguf_key = {"diffusion_models": "unet_gguf", "text_encoders": "clip_gguf"}.get(folder)
    if gguf_key and gguf_key in folder_paths.folder_names_and_paths:
        try:
            names += [n for n in folder_paths.get_filename_list(gguf_key) if n not in names]
        except Exception:
            pass
    elif folder in ("diffusion_models", "text_encoders"):  # no GGUF pack: list the .gguf files ourselves
        seen = set()  # a junction pointing back up the tree would loop forever
        for root in folder_paths.get_folder_paths(folder):
            for dp, ds, fs in os.walk(root, followlinks=True):
                real = os.path.normcase(os.path.realpath(dp))
                if real in seen:
                    ds[:] = []
                    continue
                seen.add(real)
                for f in fs:
                    if f.lower().endswith(".gguf"):
                        rel = os.path.relpath(os.path.join(dp, f), root)
                        if rel not in names:
                            names.append(rel)
    return names


def local_files(role):
    """[(folder, relative name)] of everything a role can load, all subfolders."""
    out = []
    for folder in ROLE_FOLDERS[role]:
        out += [(folder, n) for n in _list(folder)]
    return out


_ALIAS_CACHE = {"stamp": None, "map": {}}


def _aliases():
    """{file: {other names}} from the profiles' "also" lists: the same file published under another name. Read again
    only when a profile file changes."""
    try:
        d = lc_model_calc.PROFILE_DIR
        stamp = tuple(sorted((f, os.path.getmtime(os.path.join(d, f))) for f in os.listdir(d) if f.endswith(".json")))
    except Exception:
        stamp = None
    if stamp is not None and stamp == _ALIAS_CACHE["stamp"]:
        return _ALIAS_CACHE["map"]
    out = {}
    try:
        for prof in lc_model_calc.load_profiles().values():
            for comp in (prof.get("components") or {}).values():
                for v in comp.get("variants") or []:
                    if v.get("also"):
                        out.setdefault(v["file"].lower(), set()).update(a.lower() for a in v["also"])
    except Exception:
        pass
    _ALIAS_CACHE.update(stamp=stamp, map=out)
    return out


def find_on_disk(filename, folders):
    base = filename.lower()
    names = {base} | _aliases().get(base, set())
    for folder in folders:
        for n in _list(folder):
            if os.path.basename(n.replace("\\", "/")).lower() in names:
                return folder, n
    return None


def full_path(folder, name):
    p = folder_paths.get_full_path(folder, name)
    if p:
        return p
    for root in folder_paths.get_folder_paths(folder):  # .gguf listed by us when no GGUF pack registered its folder
        cand = os.path.join(root, name)
        if os.path.exists(cand):
            return cand
    return None


# ---------------------------------------------------------------- roles per profile
def role_of(variant, comp_role):
    ld = variant.get("loader", "")
    if comp_role == "diffusion":
        return "model"
    if comp_role == "text_encoder":
        return "clip"
    if ld == "VAELoader":
        return "audio_vae" if "audio" in variant["file"].lower() else "vae"
    if ld == "LatentUpscaleModelLoader":
        return "upscaler"
    if ld == "LoraLoaderModelOnly":
        return "lora"
    return None


def variants(profile, role):
    out = []
    for comp in profile["components"].values():
        for v in comp["variants"]:
            if role_of(v, comp["role"]) == role:
                out.append(dict(v, clip_type=comp.get("clip_type")))
    return out


def recommended(profile, role, goal):
    """The file the report (or Comfy's default) picks for this role, with its details."""
    return _prefer_on_disk(role, _recommended(profile, role, goal), profile)


def _recommended(profile, role, goal):
    vs = variants(profile, role)
    if not vs:
        return None
    sysp = report()
    if sysp:
        try:
            rec = lc_model_calc.recommend(profile, sysp, goal)
            files = {p["file"]: p for p in rec["picks"]}
            for v in vs:
                if v["file"] in files:
                    return dict(v, pick=files[v["file"]], source="report")
        except Exception:
            pass
    v = next((v for v in vs if v.get("default") or v.get("always")), vs[0])
    return dict(v, source="default")


def _prefer_on_disk(role, rec, prof):
    """For the small fixed parts (VAEs), a variant already on disk beats downloading the default."""
    if not rec or role not in ("vae", "audio_vae"):
        return rec
    folder = FOLDER_BY_LOADER.get(rec["loader"], ROLE_FOLDERS[role][0])
    if find_on_disk(rec["file"], [folder]):
        return rec
    for v in variants(prof, role):
        if find_on_disk(v["file"], [FOLDER_BY_LOADER.get(v["loader"], folder)]):
            return dict(v, source="on disk")
    return rec


def choices(profile_id, role, goal):
    """What the picker shows: the recommended file, downloads for the profile's files not on disk, local files
    (files known for this base model first)."""
    prof = profiles().get(profile_id)
    out = {"recommended": None, "downloads": [], "local": [], "known": [], "unsupported": is_custom(profile_id)}
    if not prof:
        return out
    rec = recommended(prof, role, goal)
    folders = ROLE_FOLDERS[role]
    if rec:
        hit = find_on_disk(rec["file"], [FOLDER_BY_LOADER.get(rec["loader"], folders[0])])
        out["recommended"] = {"file": rec["file"], "gb": rec.get("gb"), "on_disk": bool(hit), "source": rec["source"]}
    known = set()
    for v in variants(prof, role):
        hit = find_on_disk(v["file"], [FOLDER_BY_LOADER.get(v["loader"], folders[0])])
        if hit:
            known.add(hit[1])
        elif not v.get("unconfirmed"):
            out["downloads"].append({"value": DOWNLOAD + v["file"], "file": v.get("display") or v["file"], "gb": v.get("gb"), "format": v.get("format"),
                                     "community": bool(v.get("community")), "gated": v["repo"].startswith(("black-forest-labs",))})
    if role == "model":  # Lonecat's featured models, after the base model's own files
        for m in shipped_all():
            if m.get("featured") and m.get("profile") == profile_id and not find_on_disk(m["file"], ROLE_FOLDERS[role]):
                out["downloads"].append({"value": DOWNLOAD + m["file"], "file": m["file"], "gb": m.get("gb"), "format": m.get("format"),
                                         "community": False, "gated": False, "featured": m["family"]})
    out["local"] = [n for _, n in local_files(role)]
    if role == "model":  # every version of Lonecat's own models made for this base model
        known.update(n for _, n in local_files(role) if own_profile(n) == profile_id)
    out["known"] = sorted(known)
    out["picks"] = pick_choices(profile_id, role, goal)
    out["groups"] = on_disk_groups(profile_id, role)
    return out


# ---------------------------------------------------------------- header checks (hints only, nothing is loaded)
_SIG_CACHE = {}


def _header_shapes(path):
    key = (path, os.path.getmtime(path))
    if key in _SIG_CACHE:
        return _SIG_CACHE[key]
    if path.lower().endswith(".gguf"):
        try:
            import gguf  # ships with ComfyUI-GGUF
        except Exception:
            _SIG_CACHE[key] = None
            return None
        r = gguf.GGUFReader(path)
        shapes = {t.name: list(reversed([int(x) for x in t.shape])) for t in r.tensors}
        dtypes = {}
    else:
        with open(path, "rb") as f:
            n = struct.unpack("<Q", f.read(8))[0]
            h = json.loads(f.read(n))
        h.pop("__metadata__", None)
        shapes = {k: v["shape"] for k, v in h.items()}
        dtypes = {k: v["dtype"] for k, v in h.items()}
    _SIG_CACHE[key] = (shapes, dtypes)
    return _SIG_CACHE[key]


def te_signature(path):
    got = _header_shapes(path)
    if not got:
        return None
    shapes = got[0]
    layers = set()
    for k in shapes:
        m = re.search(r"(?:^|\.)(?:layers|blk)\.(\d+)\.", k)
        if m and "visual" not in k and "vision" not in k:
            layers.add(int(m.group(1)))
    emb = next((v for k, v in shapes.items() if re.search(r"embed_tokens\.weight$|token_embd\.weight$", k)), None)
    if not layers or not emb:
        return None
    return (len(layers), emb[-1], any("visual" in k or "vision" in k for k in shapes))


def vae_signature(path):
    got = _header_shapes(path)
    if not got:
        return None
    for k, s in got[0].items():
        if re.search(r"(?:^|\.)decoder\.(conv_in|conv1)(\.conv)?\.weight$", k) and not k.startswith("audio_vae"):
            return (s[1], len(s))
    return None


def model_class(path):
    """ComfyUI's own model detection, run on empty placeholder tensors built from the header."""
    got = _header_shapes(path)
    if not got or path.lower().endswith(".gguf"):
        return None
    import torch
    import comfy.model_detection

    shapes, dtypes = got
    dt = {"F32": torch.float32, "BF16": torch.bfloat16, "F16": torch.float16}
    sd = {k: torch.empty(s, dtype=dt.get(dtypes.get(k), torch.uint8), device="meta") for k, s in shapes.items()}
    try:
        prefix = comfy.model_detection.unet_prefix_from_state_dict(sd)
        cfg = comfy.model_detection.model_config_from_unet(sd, prefix)
        return type(cfg).__name__ if cfg else None
    except Exception:
        return None


def check_files(profile_id, picks):
    """Hints for known mismatches. picks: {role: path or None}. Returns [(icon, text)]."""
    prof = profiles().get(profile_id, {})
    name = prof.get("name", profile_id)
    hints = []
    p = picks.get("model")
    if is_custom(profile_id):
        cls = model_class(p) if p else None
        if cls:
            hints.append(("ℹ️", f"This model file looks like {cls}."))
        return hints
    if p and profile_id in MODEL_CLASSES:
        cls = model_class(p)
        want = MODEL_CLASSES[profile_id]
        if cls and cls != want and not (want == "ZImage" and cls.startswith("ZImage")):
            hints.append(("⚠️", f"This model file looks like {cls}, not {name}. Check the base model setting."))
    p = picks.get("clip")
    if p and checkpoint_only(profile_id) and MODEL_CLASSES.get(profile_id) == "SDXL":
        hints.append(("⚠️", f"{name} needs CLIP-L and CLIP-G together. One text encoder file loads as a single CLIP: expect errors. "
                             "Leave the text encoder blank to use the checkpoint's own."))
    elif p and profile_id in TE_EXPECTS:
        want = TE_EXPECTS[profile_id]
        sig = te_signature(p)
        if sig is None:
            hints.append(("ℹ️", "Could not check this text encoder."))
        elif sig != want[1:]:
            got = TE_NAMES.get(sig, f"{sig[0]} layers, width {sig[1]}{', with vision' if sig[2] else ''}")
            hints.append(("⚠️", f"{name} expects {want[0]}. This text encoder looks like {got}: expect errors or bad results."))
    p = picks.get("vae")
    if p and profile_id in VAE_EXPECTS:
        sig = vae_signature(p)
        want = VAE_EXPECTS[profile_id]
        if sig and sig != want:
            hints.append(("⚠️", f"{name} expects a {VAE_NAMES.get(want, want)} VAE. This one is {VAE_NAMES.get(sig, f'{sig[0]}-channel')}: expect errors or wrong colors."))
    return hints


# ---------------------------------------------------------------- downloads (first run, like LC Vision)
_DL_LOCK = threading.Lock()


def _repo_path(repo, filename):
    """Where the file sits inside the Hugging Face repo (Comfy-Org repos keep them in split_files/...)."""
    try:
        from huggingface_hub import HfApi

        files = HfApi().list_repo_files(repo)
    except Exception:
        import urllib.request

        with urllib.request.urlopen(f"https://huggingface.co/api/models/{repo}/tree/main?recursive=true", timeout=30) as r:
            files = [x["path"] for x in json.load(r) if x.get("type") == "file"]
    for f in files:
        if f.split("/")[-1] == filename:
            return f
    raise FileNotFoundError(f"[LC Optimizer] {filename} is not in https://huggingface.co/{repo}")


def _stream(repo, path_in_repo, dest, label):
    """Download one file in chunks to dest, checking ComfyUI's cancel button between chunks: cancelling stops the
    download and deletes the partial file. Uses the Hugging Face login when there is one (gated repos)."""
    import urllib.request

    import comfy.model_management as mm

    headers = {}
    try:
        from huggingface_hub.utils import build_hf_headers

        headers = build_hf_headers()
    except Exception:
        pass
    url = f"https://huggingface.co/{repo}/resolve/main/{path_in_repo}"
    part = dest + ".part"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as r, open(part, "wb") as out:
            total = int(r.headers.get("Content-Length") or 0)
            done, shown = 0, -1
            while True:
                mm.throw_exception_if_processing_interrupted()
                chunk = r.read(8 << 20)
                if not chunk:
                    break
                out.write(chunk)
                done += len(chunk)
                pct = int(done * 100 / total) if total else -1
                if pct >= 0 and pct // 10 != shown:
                    shown = pct // 10
                    print(f"[LC Optimizer] {label}: {pct}% of {total / 1024 ** 3:.1f} GB (cancel the run to stop)")
        os.replace(part, dest)
    except BaseException as e:
        try:
            os.remove(part)
        except OSError:
            pass
        if isinstance(e, mm.InterruptProcessingException):
            print(f"[LC Optimizer] {label}: download stopped, nothing kept.")
        elif "401" in str(e) or "403" in str(e):
            raise RuntimeError(f"[LC Optimizer] {repo} is gated: accept its license on https://huggingface.co/{repo} and log in "
                               "with `huggingface-cli login`, or pick another file.") from e
        raise


def download(variant):
    """Download a profile file into the root of its ComfyUI model folder. Returns (folder, name)."""
    folder = FOLDER_BY_LOADER.get(variant["loader"], "diffusion_models")
    hit = find_on_disk(variant["file"], [folder])
    if hit:
        return hit
    target = folder_paths.get_folder_paths(folder)[0]
    os.makedirs(target, exist_ok=True)
    dest = os.path.join(target, variant["file"])
    with _DL_LOCK:
        repo = variant["repo"]
        path_in_repo = _repo_path(repo, variant["file"])
        print(f"[LC Optimizer] Downloading {variant['file']} ({variant.get('gb', '?')} GB) from {repo} ...")
        _stream(repo, path_in_repo, dest, variant["file"])
    print(f"[LC Optimizer] Finished downloading {variant['file']}.")
    folder_paths.filename_list_cache.clear() if hasattr(folder_paths, "filename_list_cache") else None
    return folder, os.path.relpath(dest, target)


# ---------------------------------------------------------------- Lonecat's own models (Krealism, Animosity)
# Never a choice in the picker. When a workflow opens with one of these as its model file and the file is missing,
# it downloads from Lonecat's Hugging Face repo into the same folder path the workflow saved, so the value stays valid.
_SHIPPED = None


def shipped(name):
    global _SHIPPED
    if _SHIPPED is None:
        _SHIPPED = {}
        try:
            path = os.path.join(os.path.dirname(__file__), "optimizer_shipped_models.json")
            for m in json.load(open(path, encoding="utf-8")).get("models", []):
                for n in m.get("names", []):
                    _SHIPPED[n.lower()] = m
        except Exception:
            pass
    return _SHIPPED.get(os.path.basename(str(name).replace("\\", "/")).lower())


def shipped_all():
    shipped("")  # loads the list
    return list({id(m): m for m in _SHIPPED.values()}.values())


# Lonecat's model families by name, for files the shipped list does not name (other versions, renamed files)
_OWN = [(re.compile(r"krealism[ _-]?v\d", re.I), "krea2"),
        (re.compile(r"animosity.*krea|krea.*animosity", re.I), "krea2"),
        (re.compile(r"animosity.*illustrious", re.I), "illustrious"),
        (re.compile(r"animosity.*anima", re.I), "anima"),
        (re.compile(r"animoss|animosity.*moss", re.I), "moss_image")]


def own_profile(name):
    """The base model one of Lonecat's own model files (Krealism, Animosity) is for, or None."""
    entry = shipped(name)
    if entry:
        return entry.get("profile")
    base = os.path.basename(str(name).replace("\\", "/"))
    return next((pid for rx, pid in _OWN if rx.search(base)), None)


def download_shipped(entry, value, folder="diffusion_models"):
    """Download one of Lonecat's models to <folder root>/<the path the workflow saved>. Returns (folder, value)."""
    root = folder_paths.get_folder_paths(folder)[0]
    dest = os.path.join(root, value.replace("\\", "/"))
    if os.path.exists(dest):
        return folder, value
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with _DL_LOCK:
        print(f"[LC Optimizer] The workflow uses {entry['family']} ({os.path.basename(dest)}, {entry['gb']} GB): downloading from "
              f"https://huggingface.co/{entry['repo']} ...")
        _stream(entry["repo"], entry["path"], dest, os.path.basename(dest))
    print(f"[LC Optimizer] Finished downloading {os.path.basename(dest)}.")
    return folder, value


# ---------------------------------------------------------------- one-click picks: Lonecat's releases, the author's files
# "★ Krealism V3.1": the newest featured release of a family for this base model, in the quant that suits this machine
# (the same format the report recommends for the base model). "★ Author: <file> | <link>": a file the workflow's
# author named in the Vision Assistant tour; it downloads from a Hugging Face link, other links are shown to the reader.
AUTHOR = "★ Author: "
_FMT_CLASS = {"bf16": 16, "fp16": 16, "fp32": 16, "fp8_scaled": 8, "fp8_e4m3fn": 8, "int8_convrot": 8, "mxfp8": 8, "gguf_q8_0": 8,
              "nvfp4": 4, "w4a8": 4, "mxfp4": 4}


def _fmt_class(fmt):
    fmt = str(fmt or "").lower()
    if fmt in _FMT_CLASS:
        return _FMT_CLASS[fmt]
    m = re.search(r"q(\d)", fmt)
    return int(m.group(1)) if m else 16


def is_pick(value):
    return isinstance(value, str) and value.startswith("★ ") and value != RECOMMENDED


def releases(profile_id):
    """[(label, [entries])] of the featured releases for this base model, one per family (newest featured version)."""
    out = {}
    for m in shipped_all():
        if m.get("profile") == profile_id and m.get("featured"):
            out.setdefault(m["family"], {}).setdefault(m.get("version", ""), []).append(m)
    rel = []
    for fam, versions in out.items():
        ver = sorted(versions, key=lambda v: [int(x) for x in re.findall(r"\d+", v)] or [0])[-1]
        rel.append((f"{fam} {ver}".strip(), versions[ver]))
    return sorted(rel, key=lambda r: r[0])


def release_pick(profile_id, label, goal):
    """The file of a release that suits this machine: the report's format for the base model, on disk first.
    Returns (entry, hit or None) or None."""
    entries = next((es for lb, es in releases(profile_id) if lb == label), None)
    if not entries:
        return None
    prof = profiles().get(profile_id)
    rec = recommended(prof, "model", goal) if prof else None
    fmt = (rec or {}).get("format")
    want = _fmt_class(fmt)
    hits = {m["file"]: find_on_disk(m["file"], ROLE_FOLDERS["model"]) for m in entries}
    exact = [m for m in entries if m.get("format") == fmt]
    same = [m for m in entries if _fmt_class(m.get("format")) == want]
    for group in (exact, same):
        for m in group:
            if hits[m["file"]]:
                return m, hits[m["file"]]
    if exact:
        return exact[0], None
    if same:
        return min(same, key=lambda m: m.get("gb") or 0), None
    # no file of that size class: the closest smaller one, else the smallest
    gb = (rec or {}).get("gb") or 0
    smaller = [m for m in entries if (m.get("gb") or 0) <= gb]
    m = max(smaller, key=lambda m: m.get("gb") or 0) if smaller else min(entries, key=lambda m: m.get("gb") or 0)
    return m, hits[m["file"]]


def parse_author(value):
    """'★ Author: file | link' -> (file, link, (repo, path) for a Hugging Face file link or None)."""
    body = value[len(AUTHOR):]
    file, _, link = body.partition(" | ")
    link = link.strip()
    m = re.match(r"https?://huggingface\.co/([^/]+/[^/]+)/(?:resolve|blob)/[^/]+/(.+?)(?:\?.*)?$", link)
    hf = (m.group(1), m.group(2)) if m else None
    file = file.strip() or (os.path.basename(hf[1]) if hf else "")
    return file, link, hf


def author_target(role, value):
    """(file, link, hf, hit) for an author pick."""
    file, link, hf = parse_author(value)
    hit = find_on_disk(os.path.basename(file), ROLE_FOLDERS[role]) if file else None
    return file, link, hf, hit


def download_author(role, value):
    file, link, hf, hit = author_target(role, value)
    if hit:
        return hit
    if not hf:
        raise FileNotFoundError(f"[LC Optimizer] {file or 'The author file'} is not on disk and only downloads from a Hugging Face "
                                f"link. Get it here: {link or '(no link given)'}")
    folder = ROLE_FOLDERS[role][0]
    target = folder_paths.get_folder_paths(folder)[0]
    os.makedirs(target, exist_ok=True)
    name = os.path.basename(hf[1])
    with _DL_LOCK:
        print(f"[LC Optimizer] The workflow's author picked {name}: downloading from https://huggingface.co/{hf[0]} ...")
        _stream(hf[0], hf[1], os.path.join(target, name), name)
    print(f"[LC Optimizer] Finished downloading {name}.")
    return folder, name


def pick_choices(profile_id, role, goal):
    """The one-click picks under ★ Recommended for the model: each featured release in the quant for this machine."""
    out = []
    if role != "model" or is_custom(profile_id):
        return out
    for label, _ in releases(profile_id):
        got = release_pick(profile_id, label, goal)
        if got:
            m, hit = got
            out.append({"value": "★ " + label, "label": label, "file": m["file"], "format": m.get("format"), "gb": m.get("gb"),
                        "on_disk": bool(hit)})
    return out


# ---------------------------------------------------------------- what's on disk for a base model, grouped
_GROUP_TOKEN = re.compile(r"(?:^|[_\-\s.])(v\d+(?:[._]\d+)*)|(bf16|fp16|fp32|fp8|int8|nvfp4|mxfp8|mxfp4|w4a8|q\d(?:_k)?(?:_[msl0-9])*|gguf|"
                          r"scaled|convrot|turbo|base)(?=$|[_\-\s.])", re.I)


def _family_version(name, entry=None):
    if entry:
        return entry["family"], entry.get("version", "")
    stem = os.path.splitext(os.path.basename(name.replace("\\", "/")))[0]
    m = _GROUP_TOKEN.search(stem)
    cut = m.start() if m else len(stem)
    camel = re.search(r"(?<=[a-z])V\d", stem)  # finepornV5INT8, moodyKrea2MixV8
    if camel and camel.start() < cut:
        cut = camel.start()
    fam = stem[:cut]
    fam = re.sub(r"[_\-\s.]+$", "", fam) or stem
    ver = ""
    vm = re.search(r"(?:^|[_\-\s.])v(\d+(?:[._]\d+)*)", stem, re.I) or re.search(r"(?<=[a-z])V(\d+(?:\.\d+)?)", stem)
    if vm:
        digits = vm.group(1).replace("_", ".")
        ver = "V" + (digits if "." in digits or len(digits) == 1 else f"{digits[0]}.{digits[1:]}")
    return fam, ver


# the format tags a release's files differ by: Animosity_Krea2_V2.0_nvfp4 is the same release as ..._V2.0_bf16
_FORMAT_TAIL = re.compile(r"[_\-\s.]+(bf16|fp16|fp32|fp8(?:[_\-]?(?:scaled|e4m3fn|e5m2|mixed))?|int8(?:[_\-]?convrot)?|nvfp4|mxfp8|mxfp4|"
                          r"w4a8|q\d(?:_k)?(?:_[msl0-9])*|gguf|scaled|convrot)$", re.I)
_SIBLINGS = None


def _release_key(name):
    stem = os.path.splitext(os.path.basename(str(name).replace("\\", "/")))[0].lower()
    while True:
        cut = _FORMAT_TAIL.sub("", stem)
        if cut == stem:
            return stem
        stem = cut


def _sibling(name):
    """The shipped entry of the same release in another format (a file made locally, or not published)."""
    global _SIBLINGS
    if _SIBLINGS is None:
        shipped("")  # loads _SHIPPED
        _SIBLINGS = {}
        for n, m in (_SHIPPED or {}).items():
            _SIBLINGS.setdefault(_release_key(n), m)
    return _SIBLINGS.get(_release_key(name))


# model class per file header, kept on disk (user/LC123) so the first picker after a restart doesn't read every
# header again: path|mtime|size -> class name (None = not a model ComfyUI detects)
_CLASS_CACHE = None
_CLASS_LOCK = threading.Lock()
_CLASS_DIRTY = False


def _class_cache_path():
    return os.path.join(folder_paths.get_user_directory(), "LC123", "optimizer_model_classes.json")


def _class_cache():
    global _CLASS_CACHE
    if _CLASS_CACHE is None:
        try:
            with open(_class_cache_path(), encoding="utf-8") as f:
                _CLASS_CACHE = json.load(f)
        except Exception:
            _CLASS_CACHE = {}
    return _CLASS_CACHE


def _save_class_cache():
    global _CLASS_DIRTY
    if not _CLASS_DIRTY:
        return
    try:
        path = _class_cache_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with _CLASS_LOCK:
            data = dict(_class_cache())
            _CLASS_DIRTY = False
        with open(path + ".tmp", "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(path + ".tmp", path)
    except Exception as e:
        print(f"[LC Optimizer] could not save the model class cache: {e}")


def _class_of(folder, name):
    global _CLASS_DIRTY
    p = full_path(folder, name)
    if not p or p.lower().endswith(".gguf"):
        return None
    try:
        st = os.stat(p)
    except OSError:
        return None
    key = f"{p}|{st.st_mtime}|{st.st_size}"
    cache = _class_cache()
    if key not in cache:
        cls = model_class(p)
        with _CLASS_LOCK:
            cache[key] = cls
            _CLASS_DIRTY = True
    return cache[key]


def warm_class_cache():
    """Read the headers of every diffusion model not in the cache yet (run in the background after startup)."""
    try:
        for folder, name in local_files("model"):
            if folder == "diffusion_models":
                _class_of(folder, name)
        _save_class_cache()
    except Exception as e:
        print(f"[LC Optimizer] model class warm-up: {e}")


def on_disk_groups(profile_id, role):
    """Model files on disk made for this base model, grouped family -> version -> files: Lonecat's releases (by
    name), the profile's own files and any other file whose header ComfyUI detects as this model."""
    prof = profiles().get(profile_id)
    if not prof or role != "model":
        return []
    want = MODEL_CLASSES.get(profile_id)
    official = {n.lower() for v in variants(prof, role) for n in [v["file"]] + list(v.get("also") or [])}
    tree = {}
    for folder, name in local_files(role):
        base = os.path.basename(name.replace("\\", "/"))
        entry = shipped(base) or _sibling(base)
        own = own_profile(base)
        if base.lower() in official:
            fam, ver = prof["name"] + " (official)", ""
        elif own == profile_id or (entry and entry.get("profile") == profile_id):
            fam, ver = _family_version(base, entry)
        elif own or (entry and entry.get("profile")):
            continue  # one of Lonecat's models for another base model
        elif want and (folder == "diffusion_models" or checkpoint_only(profile_id)) and _class_of(folder, name) == want:
            fam, ver = _family_version(base)
        else:
            continue
        tree.setdefault(fam, {}).setdefault(ver, []).append(name)
    _save_class_cache()
    return [{"family": f, "versions": [{"version": v, "files": sorted(fs, key=lambda n: os.path.basename(n).lower())}
                                       for v, fs in sorted(vs.items(), key=lambda x: x[0], reverse=True)]}
            for f, vs in sorted(tree.items(), key=lambda x: (not x[0].endswith(" (official)"), x[0].lower()))]  # the base model's own files first


# ---------------------------------------------------------------- resolve a widget value to a file
def resolve(profile_id, role, value, goal):
    """Widget value -> (folder, name, variant or None). Downloads when needed. None for 'None' / From checkpoint."""
    if value in (NONE, FROM_CKPT, "", None):
        return None
    if is_pick(value):
        if value.startswith(AUTHOR):
            folder, name = download_author(role, value)
            return folder, name, None
        got = release_pick(profile_id, value[2:], goal) if role == "model" else None
        if not got:
            raise FileNotFoundError(f"[LC Optimizer] {value[2:]} is not a release for this base model. Pick another file.")
        entry, hit = got
        if hit:
            return hit[0], hit[1], None
        folder, name = download_shipped(entry, f"{entry['family']}/{entry['file']}", entry.get("folder", "diffusion_models"))
        return folder, name, None
    prof = profiles().get(profile_id)
    vs = variants(prof, role) if prof else []
    if value == RECOMMENDED:
        rec = recommended(prof, role, goal) if prof else None
        if not rec:
            return None
        v = rec
    elif value.startswith(DOWNLOAD):
        if is_custom(profile_id):
            raise FileNotFoundError(f"[LC Optimizer] Custom: downloads are {UNSUPPORTED}. Pick a file you have for the {role}.")
        fname = value[len(DOWNLOAD):]
        v = next((x for x in vs if x["file"] == fname), None)
        if v is None:
            for other in profiles().values():  # the base model changed after picking: still find it
                v = next((x for x in variants(other, role) if x["file"] == fname), None)
                if v:
                    break
        if v is None:
            entry = shipped(fname) if role == "model" else None
            if entry:  # one of Lonecat's models, offered as a featured download
                hit = find_on_disk(entry["file"], ROLE_FOLDERS[role])
                if hit:
                    return hit[0], hit[1], None
                folder, name = download_shipped(entry, f"{entry['family']}/{entry['file']}", entry.get("folder", "diffusion_models"))
                return folder, name, None
            raise FileNotFoundError(f"[LC Optimizer] No download known for {fname}.")
    else:
        for folder in ROLE_FOLDERS[role]:
            if value in _list(folder):
                v = next((x for x in vs if x["file"] == os.path.basename(value.replace("\\", "/"))), None)
                return folder, value, v
        entry = shipped(value) if role == "model" else None
        if entry:
            folder, name = download_shipped(entry, value, entry.get("folder", "diffusion_models"))  # checkpoints (SDXL family) go to checkpoints
            return folder, name, None
        raise FileNotFoundError(f"[LC Optimizer] {value} was not found in the {'/'.join(ROLE_FOLDERS[role])} folders.")
    folder = FOLDER_BY_LOADER.get(v["loader"], ROLE_FOLDERS[role][0])
    hit = find_on_disk(v["file"], [folder]) or download(v)
    return hit[0], hit[1], v


# ---------------------------------------------------------------- what a node actually loads (for LC Save Metadata)
_META_ROLES = {"model_file": ("model", "diffusion_models"), "text_encoder": ("clip", "text_encoders"), "vae": ("vae", "vae"),
               "audio_vae": ("audio_vae", "vae"), "latent_upscaler": ("upscaler", "latent_upscale_models"), "lora": ("lora", "loras")}


def loaded_files(inputs):
    """[(file name relative to its folder, folder)] an LC Model Optimizer node loads with these inputs. Never downloads:
    by the time metadata is written the node has run, so the files are on disk."""
    out = []
    base = inputs.get("base_model")
    base = LEGACY_BASE.get(base, base)
    pid = next((p for p, n in base_names(None) if n == base), None)
    if pid == "custom" and "latent_upscaler" in inputs:  # both Customs are named "Custom": a video node has these widgets
        pid = "custom_video"
    prof = profiles().get(pid) if pid else None
    goal = inputs.get("goal") or "Optimal"
    roles = roles_for(pid) if pid else ["model", "clip", "vae"]
    for widget, (role, folder) in _META_ROLES.items():
        value = inputs.get(widget)
        if role not in roles or not isinstance(value, str) or value in (NONE, FROM_CKPT, ""):
            continue
        try:
            if is_pick(value):
                if value.startswith(AUTHOR):
                    hit = author_target(role, value)[3]
                else:
                    got = release_pick(pid, value[2:], goal) if role == "model" else None
                    hit = got[1] if got else None
                if hit:
                    out.append((hit[1], hit[0]))
            elif value == RECOMMENDED or value.startswith(DOWNLOAD):
                if value == RECOMMENDED:
                    v = recommended(prof, role, goal) if prof else None
                    fname = v["file"] if v else None
                    folder = FOLDER_BY_LOADER.get(v["loader"], folder) if v else folder
                else:
                    fname = value[len(DOWNLOAD):]
                hit = find_on_disk(fname, [folder] + [f for f in ROLE_FOLDERS.get(role, []) if f != folder]) if fname else None
                if hit:
                    out.append((hit[1], hit[0]))
            else:
                hit = next(((value, f) for f in ROLE_FOLDERS.get(role, [folder]) if value in _list(f)), None)
                out.append(hit or (value, folder))
        except Exception:
            continue
    return out


# ---------------------------------------------------------------- loading through ComfyUI's own loaders
def _node(name):
    import nodes

    cls = nodes.NODE_CLASS_MAPPINGS.get(name)
    if cls is None:
        raise RuntimeError(f"[LC Optimizer] The {name} loader is not installed.")
    return cls


def _call(name, **kw):
    cls = _node(name)
    if hasattr(cls, "execute") and hasattr(cls, "define_schema"):  # new-style io.ComfyNode
        out = cls.execute(**kw)
        return tuple(out.result) if hasattr(out, "result") else tuple(out)
    inst = cls()
    return tuple(getattr(inst, cls.FUNCTION)(**kw))


def load_model(folder, name):
    """-> (model, clip or None, vae or None, how)"""
    if folder == "checkpoints":
        m, c, v = _call("CheckpointLoaderSimple", ckpt_name=name)
        return m, c, v, "checkpoint"
    if name.lower().endswith(".gguf"):
        import nodes

        if "UnetLoaderGGUF" in nodes.NODE_CLASS_MAPPINGS:
            try:
                return _call("UnetLoaderGGUF", unet_name=name)[0], None, None, "GGUF"
            except Exception as e:
                if "LoaderGGUF" not in nodes.NODE_CLASS_MAPPINGS:
                    raise
                print(f"[LC Optimizer] ComfyUI-GGUF could not load {name} ({e}); trying the calcuis gguf pack.")
        if "LoaderGGUF" in nodes.NODE_CLASS_MAPPINGS:
            return _call("LoaderGGUF", gguf_name=name)[0], None, None, "GGUF (calcuis)"
        raise RuntimeError("[LC Optimizer] GGUF files need the ComfyUI-GGUF pack (install it from ComfyUI-Manager).")
    if _is_moss(full_path(folder, name)) and not _native_moss():
        # the MOSS-Image plugin reads OpenMOSS's own checkpoints: with these (fused qkv) files it renders noise
        raise RuntimeError("[LC Optimizer] MOSS-Image needs a ComfyUI with native MOSS-Image support (update ComfyUI: "
                           "the dev branch after 0.41.3 has it).")
    return _call("UNETLoader", unet_name=name, weight_dtype="default")[0], None, None, "diffusion model"


def _is_moss(path):
    """A MOSS-Image diffusion model, by its weight names (read from the header only)."""
    if not path or not path.lower().endswith(".safetensors"):
        return False
    try:
        import json
        import struct

        with open(path, "rb") as f:
            n = struct.unpack("<Q", f.read(8))[0]
            if n > 64 * 1024 * 1024:
                return False
            keys = json.loads(f.read(n)).keys()
        return any(k.endswith("shared_block_modulation.weight") for k in keys)
    except Exception:
        return False


def _native_moss():
    """True once ComfyUI loads MOSS-Image itself (its CLIPLoader lists the moss_image type)."""
    try:
        import nodes

        return "moss_image" in nodes.NODE_CLASS_MAPPINGS["CLIPLoader"].INPUT_TYPES()["required"]["type"][0]
    except Exception:
        return False


def load_clip(folder, name, clip_type, ckpt_name=None):
    if clip_type == "moss_image" and not _native_moss():
        raise RuntimeError("[LC Optimizer] MOSS-Image's text encoder needs a ComfyUI with native MOSS-Image support "
                           "(update ComfyUI: the dev branch after 0.41.3 has it).")
    if clip_type == "LTXAVTextEncoderLoader":
        if not ckpt_name:
            raise RuntimeError("[LC Optimizer] LTX 2.3's text encoder also reads the LTX 2.3 checkpoint: pick a checkpoint as the model.")
        return _call("LTXAVTextEncoderLoader", text_encoder=name, ckpt_name=ckpt_name)[0]
    if name.lower().endswith(".gguf"):
        import nodes

        if "CLIPLoaderGGUF" in nodes.NODE_CLASS_MAPPINGS:
            return _call("CLIPLoaderGGUF", clip_name=name, type=clip_type)[0]
        if "ClipLoaderGGUF" in nodes.NODE_CLASS_MAPPINGS:
            return _call("ClipLoaderGGUF", clip_name=name, type=clip_type)[0]
        raise RuntimeError("[LC Optimizer] GGUF text encoders need the ComfyUI-GGUF pack.")
    return _call("CLIPLoader", clip_name=name, type=clip_type)[0]


def load_vae(folder, name, audio=False):
    if audio and folder == "checkpoints":
        return _call("LTXVAudioVAELoader", ckpt_name=name)[0]
    return _call("VAELoader", vae_name=name)[0]


def load_upscaler(name):
    return _call("LatentUpscaleModelLoader", model_name=name)[0]


def apply_lora(model, name, strength=1.0):
    return _call("LoraLoaderModelOnly", model=model, lora_name=name, strength_model=strength)[0]


# ---------------------------------------------------------------- speed-ups
ATTENTION = ["auto", "pytorch", "sage", "sage3", "flash", "xformers", "comfy_kitchen_int8"]
ATTN_LABEL = {"pytorch": "Standard (PyTorch)", "sage": "Sage", "sage3": "Sage 3", "flash": "Flash", "xformers": "xformers",
              "comfy_kitchen_int8": "Comfy Kitchen int8"}


QWEN_CACHE = {"lossless": ("auto", "default"), "int8": ("auto", "int8"), "int4": ("auto", "int4"), "RAM": ("cpu", "default"),
              "RAM + int8": ("cpu", "int8"), "off": ("off", "default")}
QWEN_CACHE_LABEL = {"lossless": "lossless", "int8": "int8", "int4": "int4", "RAM": "in RAM", "RAM + int8": "int8 in RAM", "off": "off"}


def _registered():
    try:
        from comfy.ldm.modules.attention import REGISTERED_ATTENTION_FUNCTIONS

        return set(REGISTERED_ATTENTION_FUNCTIONS)
    except Exception:
        return {"pytorch"}


def _sage_flag():
    """True when ComfyUI was started with --use-sage-attention (Sage forced on for every model)."""
    try:
        from comfy.cli_args import args

        return bool(getattr(args, "use_sage_attention", False))
    except Exception:
        return False


# Spectrum for MiniMax H3 (xmarre's ComfyUI-Spectrum-MiniMax-H3, GPL-3.0, installed separately): forecasts some
# steps instead of running them. 2026-10-21 bench, 3 seeds,
# Optimal goal with Sage: 119 s -> 91 s, sharpness, lip sync and face match unchanged.
SPECTRUM_PROFILES = {"minimax_h3", "minimax_h3_fl2va"}
# auto only where it held up: on Ref2VA (minimax_h3) it smeared the picture and scrambled text in every test
# (2026-10-21, desktop and laptop, with or without the sigma shift), so there it is on by hand only.
# 2026-10-30: FL2VA too. At 1344x768 a busy wide two-shot (cafe, reference pictures) filled with floating blobs on
# 2 of 2 seeds, gone with Spectrum off; close-ups looked fine, which is why the 10-21 bench missed it
SPECTRUM_AUTO = set()
SPECTRUM_NODE = "SpectrumApplyMiniMaxH3"
SPECTRUM_SETTINGS = dict(
    enabled=True, blend_weight=0.5, degree=1, ridge_lambda=0.1, window_size=2.0, flex_window=0.75, warmup_steps=1,
    tail_actual_steps=1, max_history=8, debug=False, history_storage="system_ram", bootstrap_first_forecast=True,
    anchor_residual_feedback=False, selective_rollback_correction=False, offline_smoothing_replay=True, audio_blend_weight=0.0,
    offline_archive_storage="system_ram", model_aware_mode="off", model_aware_risk_threshold=0.65,
    model_aware_trust_shrinkage=False, model_aware_replay_generic_correction=False, generic_correction_mode="coordinate_rls",
    generic_correction_limiter="hard_clip", generic_correction_limit=0.4, generic_correction_attenuation="no_attenuation")


# step- and size-aware: on 8-step turbo runs at about 1 MP nothing changed, but lip sync dropped at 25 steps (5 of 6
# seeds) and at low resolution (0.4 MP clearly, 0.7 MP on 1 of 3 seeds; 2026-10-21), so Spectrum sits out those runs
SPECTRUM_MAX_STEPS = 12
SPECTRUM_MIN_MP = 0.9
H3_LATENT_SCALE = 16  # H3 video latent: one cell per 16 x 16 pixels
SPECTRUM_BINDING = "spectrum_h3_binding"  # Spectrum's own wrappers pass straight through when this is missing


# Veda (learned sparse attention, Veda-on-ComfyUI, installed separately) is the low-resolution partner: on an 8 GB laptop
# at 0.4 MP it was 1.4x faster with nothing lost, while at about 1 MP the face drifted on every seed (2026-10-21). So it
# runs below the size where Spectrum takes over, and goes back to full attention above it.
VEDA_PROFILES = {"minimax_h3", "minimax_h3_fl2va"}
VEDA_NODE = "VedaSparseAttention"
VEDA_PREDICTOR = "minimax_h3_t2va_veda_8nfe_600step_preview_fp8.safetensors"
VEDA_SETTINGS = dict(predictor=VEDA_PREDICTOR, generated_sparsity="32", reference_sparsity="32", full_attention_layers="",
                     full_attention_steps="", verbose=False)
VEDA_MAX_MP = SPECTRUM_MIN_MP
VEDA_KEY = "veda_sparse_attention"  # Veda's own callback key

# Spectrum for image models is our own (lc_spectrum), nothing to install. Every 2nd middle step forecast on Optimal:
# MOSS 1.7x (2.1x on an 8 GB laptop), Krea 2 Turbo 1.36x at 10 steps, Raw 1.6x at 52 steps, no visible change.
# Every 3rd on Fast: MOSS 2.1x with a sign's lettering style changed; on Krea 2 Turbo it left a ghost pattern, so Turbo
# stays at every 2nd on Fast too.
IMAGE_SPECTRUM_PROFILES = {"moss_image", "moss_image_base", "krea2", "krea2_raw"}
IMAGE_SPECTRUM_BY_HAND = {"fibo2_edit_turbo"}  # supported, but auto leaves it off until it is measured
IMAGE_SPECTRUM_INTERVAL = {"Optimal": 2, "Fast": 3, "Quality": 2}
IMAGE_SPECTRUM_EVERY_2ND = {"krea2"}
IMAGE_SPECTRUM_GAIN = {"moss_image": "about 1.7x", "moss_image_base": "about 1.7x", "krea2": "about 1.35x at 10 steps",
                       "krea2_raw": "about 1.6x at 52 steps"}


def _veda_patch(model):
    """Veda's per-model patch object, from the callback it registers (the node only returns the model)."""
    import comfy.patcher_extension as pe

    for fn in (model.callbacks.get(pe.CallbacksMP.ON_PREPARE_STATE, {}).get(VEDA_KEY) or []):
        for cell in (getattr(fn, "__closure__", None) or ()):
            obj = cell.cell_contents
            if hasattr(obj, "settings") and hasattr(obj, "make_override"):
                return obj
    return None


def _h3_speed_guard(executor, noise, latent_image, sampler, sigmas, *args, state=None, **kwargs):
    """Per run: Spectrum only on short runs at about 1 MP, Veda only below that. Each sits out the rest."""
    opts = getattr(executor.class_obj, "model_options", None) or {}
    steps = max(0, len(sigmas) - 1)
    # the latent arrives packed flat here; its real shapes come in latent_shapes (video: B, C, T, H/16, W/16)
    shapes = kwargs.get("latent_shapes") or (args[4] if len(args) > 4 else None) or []
    video = next((tuple(sh) for sh in shapes if len(sh) == 5), None)
    mp = video[-2] * video[-1] * H3_LATENT_SCALE ** 2 / 1e6 if video else SPECTRUM_MIN_MP
    undo, notes = [], []
    if SPECTRUM_BINDING in opts and not (steps <= SPECTRUM_MAX_STEPS and mp >= SPECTRUM_MIN_MP):
        binding = opts.pop(SPECTRUM_BINDING)
        undo.append(lambda: opts.__setitem__(SPECTRUM_BINDING, binding))
        notes.append(f"Spectrum sits out ({steps} steps)" if steps > SPECTRUM_MAX_STEPS else f"Spectrum sits out ({mp:.2f} MP)")
    veda = (state or {}).get("veda")
    if veda is not None and not state.get("veda_force") and mp >= VEDA_MAX_MP:
        import dataclasses

        old = veda.settings
        veda.settings = dataclasses.replace(old, dense_steps=range(1 << 20))  # every step full attention
        undo.append(lambda: setattr(veda, "settings", old))
        notes.append(f"Veda sits out ({mp:.2f} MP)")
    if notes:
        print(f"[LC Optimizer] {', '.join(notes)}: where it cost quality in our tests.")
    try:
        return executor(noise, latent_image, sampler, sigmas, *args, **kwargs)
    finally:
        for u in undo:
            u()


def _veda_installed():
    try:
        import folder_paths
        import nodes

        return VEDA_NODE in nodes.NODE_CLASS_MAPPINGS and VEDA_PREDICTOR in folder_paths.get_filename_list("veda")
    except Exception:
        return False


def _spectrum_installed():
    try:
        import nodes

        return SPECTRUM_NODE in nodes.NODE_CLASS_MAPPINGS
    except Exception:
        return False


def plan_speedups(profile_id, goal, manual=None):
    """What to apply and why. manual: {attention, fp16_accumulation, step_cache, torch_compile, spectrum, veda} or None (Auto).
    Returns [{key, label, state: on/off/na, value, why}]."""
    sysp = report() or {}
    t = sysp.get("tests") or {}
    reg = _registered()
    steps = lc_model_calc.STEPS.get(profile_id, 20)
    manual = manual or {}
    rows = []

    # attention: the fastest one that ran AND matched standard attention in the report
    want = (manual.get("attention") or "auto")
    if want == "auto":
        pick = next((k for k, tk in (("sage", "sageattention"), ("flash", "flash_attn")) if (t.get(tk) or {}).get("ok") and k in reg), None)
        if pick:
            why = f"{(t.get('sageattention' if pick == 'sage' else 'flash_attn') or {}).get('detail', 'tested fine')}"
            rows.append({"key": "attention", "label": f"Attention: {ATTN_LABEL[pick]}", "state": "on", "value": pick, "why": why})
        else:
            why = "Sage not installed or failed its test: see Recommended to install in the report" if sysp else "run the report to pick one"
            rows.append({"key": "attention", "label": "Attention: standard", "state": "off", "value": None, "why": why})
    elif want == "pytorch" or want in reg:
        rows.append({"key": "attention", "label": f"Attention: {ATTN_LABEL.get(want, want)}", "state": "on", "value": want, "why": "set by hand"})
    else:
        rows.append({"key": "attention", "label": f"Attention: {ATTN_LABEL.get(want, want)}", "state": "na", "value": None, "why": "not installed: see Recommended to install in the report"})

    kit = sysp.get("kitchen") or {}
    if kit.get("installed"):
        cuda = ((kit.get("backends") or {}).get("cuda") or {}).get("available")
        rows.append({"key": "kitchen", "label": "Comfy Kitchen (int8 / fp8 / nvfp4 files)", "state": "on" if cuda else "off", "value": None,
                     "why": "ComfyUI uses it by itself for those model files (not an attention setting)" if cuda
                     else "GPU backend not available: slower path"})
    elif sysp:
        rows.append({"key": "kitchen", "label": "Comfy Kitchen", "state": "na", "value": None, "why": "not installed: see Recommended to install in the report"})

    want = (manual.get("fp16_accumulation") or "auto")
    fp16_ok = (t.get("matmul_fp16") or {}).get("ok")
    on = want == "on" or (want == "auto" and goal == "Fast" and fp16_ok)
    rows.append({"key": "fp16_accumulation", "label": "fp16 accumulation", "state": "on" if on else "off", "value": bool(on),
                 "why": "set by hand" if want != "auto" else ("Fast goal" if on else "Fast goal only (small quality cost)")})

    want = (manual.get("step_cache") or "auto")
    on = want == "on" or (want == "auto" and goal == "Fast" and steps >= 20)
    why = "set by hand" if want != "auto" else ("Fast goal, skips near-duplicate steps" if on else
                                                 ("Fast goal only" if steps >= 20 else f"not worth it at {steps} steps"))
    rows.append({"key": "step_cache", "label": "Step cache (EasyCache)", "state": "on" if on else "off", "value": bool(on), "why": why})

    if profile_id in VEDA_PROFILES:
        want = (manual.get("veda") or "auto")
        if not _veda_installed():
            rows.append({"key": "veda", "label": "Veda (sparse attention, low res)", "state": "na", "value": None,
                         "why": f"not installed: Veda-on-ComfyUI + {VEDA_PREDICTOR} in models/veda"})
        else:
            # Auto keeps Sage: on the 2026-10-22 bank Veda was 8% slower than Sage at 960x544 and drifted the framing
            on = want == "on"
            why = ("set by hand: every resolution" if want == "on" else "set by hand") if want != "auto" else (
                "Auto keeps Sage attention. Set to on to try it under the MP limit")
            rows.append({"key": "veda", "label": "Veda (sparse attention, low res)", "state": "on" if on else "off",
                         "value": want == "on", "why": why})

    if profile_id in SPECTRUM_PROFILES:
        want = (manual.get("spectrum") or "auto")
        if not _spectrum_installed():
            rows.append({"key": "spectrum", "label": "Spectrum (step forecast)", "state": "na", "value": None,
                         "why": "not installed: ComfyUI-Spectrum-MiniMax-H3 by xmarre (Manager or GitHub)"})
        else:
            auto_ok = profile_id in SPECTRUM_AUTO
            on = want == "on" or (want == "auto" and goal != "Quality" and auto_ok)
            why = "set by hand" if want != "auto" else (
                f"about 1.3x faster; sits out runs over {SPECTRUM_MAX_STEPS} steps or under {SPECTRUM_MIN_MP} MP" if on else
                ("Auto leaves it off: it put floating blobs in busy wide shots in our tests (set it to on to try)"
                 if not auto_ok else "Optimal and Fast goals only"))
            rows.append({"key": "spectrum", "label": "Spectrum (step forecast)", "state": "on" if on else "off", "value": bool(on), "why": why})

    if profile_id in IMAGE_SPECTRUM_PROFILES or profile_id in IMAGE_SPECTRUM_BY_HAND:
        want = (manual.get("spectrum") or "auto")
        on = want == "on" or (want == "auto" and goal != "Quality" and profile_id in IMAGE_SPECTRUM_PROFILES)
        every = 2 if profile_id in IMAGE_SPECTRUM_EVERY_2ND else IMAGE_SPECTRUM_INTERVAL.get(goal, 2)
        why = "set by hand" if want != "auto" else (
            (f"{IMAGE_SPECTRUM_GAIN.get(profile_id, 'faster')} ({'every 3rd' if every == 3 else 'every 2nd'} step after the "
             f"warm-up forecast); sits out runs under 8 steps") if on else (
            "not on by default for this model yet: set it to on to try" if profile_id in IMAGE_SPECTRUM_BY_HAND
            else "Optimal and Fast goals only"))
        rows.append({"key": "spectrum", "label": "Spectrum (step forecast)", "state": "on" if on else "off",
                     "value": ("img", every) if on else False, "why": why})

    if any(r["key"] == "spectrum" and r["state"] == "on" for r in rows):  # one step skipper at a time
        for r in rows:
            if r["key"] == "step_cache" and r["state"] == "on":
                r["state"], r["value"], r["why"] = "off", False, "Spectrum is on (one step skipper at a time)"

    if profile_id == "qwen_image_21":
        # Qwen Image 2.1 Cache (ComfyUI core): where the KV cache lives and how it is stored. int4 is never picked
        # automatically: its tooltip says it roughly doubles the per-step error.
        want = manual.get("qwen21_cache", "auto")
        vram = ((sysp.get("gpus") or [{}])[0].get("vram_gb") or 0)
        if want == "auto":
            if goal == "Fast" or (goal == "Optimal" and vram and vram < 16):
                want, why = "int8", ("Fast goal" if goal == "Fast" else f"{vram:g} GB card: halves the cache, about bf16 accuracy")
            else:
                want, why = "lossless", "Comfy's default: spare VRAM first, then RAM"
        else:
            why = "set by hand"
        dev, dt = QWEN_CACHE[want]
        # "off" is the one choice that turns the cache off; every other choice is an active cache
        rows.append({"key": "qwen21_cache", "label": f"Qwen 2.1 cache: {QWEN_CACHE_LABEL[want]}",
                     "state": "off" if want == "off" else "on", "value": (dev, dt), "why": why})

    want = manual.get("torch_compile", "off")
    tri = (t.get("triton") or {}).get("ok")
    if want == "on":
        rows.append({"key": "torch_compile", "label": "torch.compile", "state": "on" if tri or not sysp else "na", "value": True,
                     "why": "first run compiles (slow), later runs are faster" if tri or not sysp else "Triton failed the report's test"})
    return rows


def apply_speedups(model, rows):
    m = model.clone()
    applied = []
    if any(r["key"] in ("spectrum", "veda") and r["state"] == "on" and not isinstance(r["value"], tuple) for r in rows):
        import functools
        import comfy.patcher_extension as pe

        # added first so it sits outside Spectrum's and Veda's own hooks; clones share the state dict
        state = {}
        m.add_wrapper_with_key(pe.WrappersMP.OUTER_SAMPLE, "lc_optimizer_h3_guard", functools.partial(_h3_speed_guard, state=state))
    for r in rows:
        if r["state"] != "on" and r["key"] != "qwen21_cache":  # the cache is set even when switched off
            continue
        if r["key"] == "attention" and r["value"]:
            from comfy.ldm.modules.attention import get_attention_function

            m.set_model_optimized_attention(get_attention_function(r["value"]))
            applied.append(r["label"])
        elif r["key"] == "fp16_accumulation":
            import torch
            import comfy.patcher_extension as pe

            def outer(executor, *args, **kwargs):
                old = getattr(torch.backends.cuda.matmul, "allow_fp16_accumulation", False)
                try:
                    torch.backends.cuda.matmul.allow_fp16_accumulation = True
                    return executor(*args, **kwargs)
                finally:
                    torch.backends.cuda.matmul.allow_fp16_accumulation = old

            if hasattr(torch.backends.cuda.matmul, "allow_fp16_accumulation"):
                m.add_wrapper_with_key(pe.WrappersMP.OUTER_SAMPLE, "lc_optimizer_fp16acc", outer)
                applied.append(r["label"])
            else:
                r["state"], r["why"] = "na", "needs PyTorch 2.7 or newer"
        elif r["key"] == "step_cache":
            m = _call("EasyCache", model=m, reuse_threshold=0.2, start_percent=0.15, end_percent=0.95, verbose=False)[0]
            applied.append(r["label"])
        elif r["key"] == "veda":
            m = _call(VEDA_NODE, model=m, **VEDA_SETTINGS)[0]
            state["veda"], state["veda_force"] = _veda_patch(m), bool(r["value"])
            applied.append(r["label"])
        elif r["key"] == "spectrum" and isinstance(r["value"], tuple):  # image models: our own
            from . import lc_spectrum

            m = lc_spectrum.apply(m, r["value"][1])
            applied.append(r["label"])
        elif r["key"] == "spectrum":
            m = _call(SPECTRUM_NODE, model=m, **SPECTRUM_SETTINGS)[0]
            applied.append(r["label"])
        elif r["key"] == "qwen21_cache":
            dev, dt = r["value"]
            m = _call("QwenImage21Cache", model=m, device=dev, dtype=dt)[0]
            if r["state"] == "on":
                applied.append(r["label"])
        elif r["key"] == "torch_compile":
            m = _call("TorchCompileModel", model=m, backend="inductor")[0]
            applied.append(r["label"])
    return m, applied


# ---------------------------------------------------------------- the plan shown on the node before a run
_QUANT_NAME = re.compile(r"int8|fp8|nvfp4|mxfp8|mxfp4|w4a8|convrot|e4m3|e5m2|\.gguf$", re.I)


def plan(profile_id, goal, picks, manual=None):
    """picks: {role: widget value}. Everything the face shows, without loading or downloading anything."""
    prof = profiles().get(profile_id)
    custom = is_custom(profile_id)
    out = {"base": prof["name"] if prof else profile_id, "roles": roles_for(profile_id), "extras": EXTRAS.get(profile_id, []), "files": [], "speedups": plan_speedups(profile_id, goal, manual),
           "hints": [], "report": None, "estimate": UNSUPPORTED if custom else None, "custom": custom, "checkpoint_only": checkpoint_only(profile_id)}
    sysp = report()
    if sysp:
        g = (sysp.get("gpus") or [{}])[0]
        out["report"] = {"when": sysp.get("when"), "gpu": g.get("name"), "vram_gb": g.get("vram_gb")}
        if g.get("vram_gb") and g["vram_gb"] <= 8.5:  # token bench 2026-10-25: every 250 prompt tokens ~ +7% per image on any card
            out["hints"].append(("💡", f"Your {round(g['vram_gb'])} GB card is better suited for prompts of 250 - 500 tokens (a 2B or 4B vision "
                                       "model for captions). Every 250 tokens adds about 7% to each image. Go longer for the images that matter."))
    elif custom:
        out["hints"].append(("💡⚠️", "No report yet: run the System & Model Optimization Report so the speed-ups suit this machine."))
    else:
        out["hints"].append(("💡⚠️", "No report yet: using Comfy's default files. Run the System & Model Optimization Report for picks that suit this machine."))
    if _sage_flag():
        att = next((r for r in out["speedups"] if r["key"] == "attention"), None)
        if att and att.get("value") and att["value"] != "sage":
            out["hints"].append(("⚠️", f"--use-sage-attention is in your .bat, so Sage is ComfyUI's default. This node's choice "
                                       f"({ATTN_LABEL.get(att['value'], att['value'])}) still wins for this model. Remove the flag: some "
                                       "models give black images with Sage, and this node turns it on per model."))
        else:
            out["hints"].append(("⚠️", "--use-sage-attention is in your .bat: it forces Sage on every model, and some models give black "
                                       "images with it. Remove it, this node turns Sage on per model (or set speed_ups to Manual and "
                                       "attention to pytorch)."))
    if custom:
        out["hints"].append(("ℹ️", "Custom: recommended files, downloads, estimates and file checks are unsupported. Pick your own files; the speed-ups still apply."))
    paths = {}
    ckpt = False
    for role, value in picks.items():
        if role not in out["roles"] or value in (NONE, None, ""):
            continue
        if value == FROM_CKPT:
            out["files"].append({"role": role, "label": "from the checkpoint", "state": "ckpt"})
            continue
        row = {"role": role, "value": value}
        if custom and (value == RECOMMENDED or value.startswith(DOWNLOAD)):
            if not (ckpt and role in ("clip", "vae", "audio_vae")):
                out["files"].append(dict(row, label=f"{role}: {UNSUPPORTED}", state=UNSUPPORTED))
            else:
                out["files"].append({"role": role, "label": "from the checkpoint", "state": "ckpt"})
            continue
        try:
            if is_pick(value):
                if value.startswith(AUTHOR):
                    file, link, hf, hit = author_target(role, value)
                    row.update(label=os.path.basename(file) or "the author's file", state="disk" if hit else ("download" if hf else "missing"))
                    if not hit:
                        out["hints"].append(("ℹ️", f"The workflow's author picked {os.path.basename(file) or 'this file'}: "
                                                   + (f"it downloads from huggingface.co/{hf[0]} on the first run." if hf else f"get it at {link or '(no link given)'}.")))
                else:
                    got = release_pick(profile_id, value[2:], goal) if role == "model" else None
                    if not got:
                        row.update(label=value[2:], state="missing")
                        out["hints"].append(("⚠️", f"{value[2:]} is not a release for {out['base']}. Pick another file."))
                        out["files"].append(row)
                        continue
                    entry, hit = got
                    row.update(label=entry["file"], gb=entry.get("gb"), state="disk" if hit else "download")
                    if not hit:
                        out["hints"].append(("ℹ️", f"{entry['family']} downloads from huggingface.co/{entry['repo']} on the first run."))
                if hit:
                    paths[role] = full_path(*hit)
                    ckpt = ckpt or (role == "model" and hit[0] == "checkpoints")
            elif value == RECOMMENDED or value.startswith(DOWNLOAD):
                if value == RECOMMENDED:
                    v = recommended(prof, role, goal) if prof else None
                else:
                    fname = value[len(DOWNLOAD):]
                    v = next((x for x in variants(prof, role) if x["file"] == fname), None) if prof else None
                    entry = shipped(fname) if (role == "model" and not v) else None
                    if entry:  # a featured download of Lonecat's (Krealism V3.1)
                        hit = find_on_disk(entry["file"], ROLE_FOLDERS[role])
                        row.update(label=entry["file"], gb=entry["gb"], state="disk" if hit else "download")
                        if hit:
                            paths[role] = full_path(*hit)
                        else:
                            out["hints"].append(("ℹ️", f"{entry['family']} downloads from huggingface.co/{entry['repo']} on the first run."))
                        out["files"].append(row)
                        continue
                if not v:
                    if ckpt and role in ("clip", "vae", "audio_vae"):
                        out["files"].append({"role": role, "label": "from the checkpoint", "state": "ckpt"})
                    continue
                folder = FOLDER_BY_LOADER.get(v["loader"], ROLE_FOLDERS[role][0])
                hit = find_on_disk(v["file"], [folder])
                row.update(label=v.get("display") or v["file"], gb=v.get("gb"), state="disk" if hit else "download")
                ckpt = ckpt or (role == "model" and folder == "checkpoints")  # also before it is downloaded
                if hit:
                    paths[role] = full_path(*hit)
                if role == "model" and v.get("pick", {}).get("step_s"):
                    pk = v["pick"]
                    out["estimate"] = {"step_s": pk["step_s"], "total_s": pk.get("total_s"), "steps": pk.get("steps"), "fits": pk.get("fits"),
                                       "confidence": pk.get("confidence")}
            else:
                folder = next((f for f in ROLE_FOLDERS[role] if value in _list(f)), None)
                row.update(label=os.path.basename(value.replace("\\", "/")), state="disk" if folder else "missing")
                entry = shipped(value) if (role == "model" and not folder) else None
                if entry:
                    row.update(state="download", gb=entry["gb"])
                    out["hints"].append(("ℹ️", f"This workflow uses {entry['family']}: it downloads from huggingface.co/{entry['repo']} on the first run."))
                    if prof and entry.get("profile") and entry["profile"] != profile_id:
                        out["hints"].append(("⚠️", f"{entry['family']} is a {profiles().get(entry['profile'], {}).get('name', entry['profile'])} model: set the base model to match."))
                if folder:
                    paths[role] = full_path(folder, value)
                    ckpt = ckpt or (role == "model" and folder == "checkpoints")
        except Exception as e:
            row.update(label=str(value), state="missing", error=str(e))
        out["files"].append(row)
    out["checkpoint"] = ckpt
    try:
        out["hints"] += check_files(profile_id, paths)
    except Exception as e:
        out["hints"].append(("ℹ️", f"Could not check the files ({type(e).__name__})."))
    if prof and "Needs BOTH" in " ".join(prof.get("notes", [])):
        out["hints"].append(("ℹ️", "Ideogram 4 samples with two models: LC Optimizer (pipe) loads the unconditional one into model 2."))
    # Comfy Kitchen only speeds up int8 / fp8 / nvfp4 files: for a bf16 / fp16 model it is not in play
    kit_row = next((r for r in out["speedups"] if r["key"] == "kitchen" and r["state"] == "on"), None)
    mrow = next((f for f in out["files"] if f.get("role") == "model"), None)
    name = str((mrow or {}).get("label") or "")
    if kit_row and name and mrow.get("state") not in ("ckpt", UNSUPPORTED) and not _QUANT_NAME.search(name):
        kit_row["state"], kit_row["why"] = "off", "not in play: the model file is bf16 / fp16 (it only speeds up int8 / fp8 / nvfp4 files)"
    return out


def summary_text(pl, applied, loaded):
    lines = [f"LC Optimizer: {pl['base']}"]
    for role, name in loaded:
        lines.append(f"{role}: {name}")
    lines.append("speed-ups: " + (", ".join(applied) if applied else "none"))
    if pl.get("estimate") == UNSUPPORTED:
        lines.append(f"estimate: {UNSUPPORTED}")
    elif pl.get("estimate"):
        e = pl["estimate"]
        lines.append(f"estimate: ~{e['step_s']} s/step" + (f", ~{e['total_s']} s for {e['steps']} steps" if e.get("total_s") else ""))
    for icon, text in pl["hints"]:
        lines.append(f"{icon} {text}")
    return "\n".join(lines)
