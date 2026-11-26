"""
Wan 2.2 pair check for LC Dual Model Optimizer: are model 1 and model 2 the high noise and low noise halves of one
release, in the right slots? A hint, never a block: a mismatch gets a ⚠️, an unknown file an "unverified pair" note.

Each file is looked up locally first, strongest source first:
  1. its sha256 against the official Wan 2.2 files (optimizer_profiles/wan22.json, from the Hugging Face metadata)
  2. the fingerprint library (models/fingerprints/index.json): its sketch against the library's official high / low
     experts (a finetune sits about 10x closer to its own expert), and the CivitAI model it was matched to
  3. a CivitAI info file next to it (<name>.metadata.json or <name>.civitai.info): same modelId = same release
  4. the high / low words in its file name (high_noise, HighNoise, High, a trailing H / L)
Only when none of those can tell high from low is CivitAI asked by hash (no key); the answer is cached per file.
The sha256 comes from a sidecar (.sha256, or the sha256 in .metadata.json with the same size) or is read once and
cached in user/LC123.
"""

from __future__ import annotations

import json
import os
import re
import threading

import folder_paths

from . import lc_optimizer_engine as E

HIGH, LOW = "high", "low"
_LOCK = threading.Lock()


# ---------------------------------------------------------------- small json caches in user/LC123
def _cache_path(name):
    return os.path.join(folder_paths.get_user_directory(), "LC123", name)


def _load(name):
    try:
        with open(_cache_path(name), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(name, data):
    try:
        p = _cache_path(name)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p + ".tmp", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=1)
        os.replace(p + ".tmp", p)
    except Exception as e:
        print(f"[LC Dual Optimizer] could not save {name}: {e}")


HASHES = "dual_optimizer_hashes.json"
CIVITAI = "dual_optimizer_civitai.json"


# ---------------------------------------------------------------- what is known
def _profile():
    return E.profiles().get("wan22") or {}


def known_hashes():
    """sha256 -> {noise, task, release, file} for the official Wan 2.2 A14B files (and their QuantStack GGUFs)."""
    prof = _profile()
    out = {}
    for comp in (prof.get("components") or {}).values():
        for v in comp.get("variants") or []:
            if v.get("sha256") and v.get("noise"):
                task = (v.get("task") or "").upper()
                out[v["sha256"].lower()] = {"noise": v["noise"], "task": v.get("task"), "file": v["file"],
                                            "release": f"Wan 2.2 {task} (official)"}
    for k in prof.get("pair_known") or []:
        out[k["sha256"].lower()] = {"noise": k["noise"], "task": None, "file": k["file"], "release": k["release"] + " (official)"}
    return out


def _sidecar(path):
    """sha256 from a file next to the model, or None. A .sha256 file counts when it is newer than the model; the
    sha256 in a .metadata.json counts when its size matches."""
    stem = os.path.splitext(path)[0]
    try:
        st = os.stat(path)
    except OSError:
        return None
    for p in (stem + ".sha256", path + ".sha256"):
        try:
            if os.path.getmtime(p) + 1 < st.st_mtime:
                continue
            with open(p, encoding="utf-8") as f:
                sha = (f.read().strip().split() or [""])[0].lower()
            if re.fullmatch(r"[0-9a-f]{64}", sha):
                return sha
        except OSError:
            continue
    meta = _meta(path)
    sha = str(meta.get("sha256") or "").lower()
    if re.fullmatch(r"[0-9a-f]{64}", sha) and meta.get("size") in (None, st.st_size):
        return sha
    return None


def file_sha(path, allow_hash=True):
    """sha256 of a model file: cached, then a sidecar, then read (only with allow_hash). None when not known."""
    try:
        st = os.stat(path)
    except OSError:
        return None
    key = f"{os.path.normcase(os.path.abspath(path))}|{st.st_mtime}|{st.st_size}"
    with _LOCK:
        cache = _load(HASHES)
    if key in cache:
        return cache[key]
    sha = _sidecar(path)
    if not sha and allow_hash:
        print(f"[LC Dual Optimizer] Reading {os.path.basename(path)} once for the pair check ({st.st_size / 1e9:.1f} GB)...")
        sha = E._sha256(path)
    if sha:
        with _LOCK:
            cache = _load(HASHES)
            cache[key] = sha
            _save(HASHES, cache)
    return sha


def _meta(path):
    """The CivitAI info next to a model: LoRA Manager's <name>.metadata.json or the <name>.civitai.info format."""
    stem = os.path.splitext(path)[0]
    for p in (stem + ".metadata.json", stem + ".civitai.info"):
        try:
            with open(p, encoding="utf-8") as f:
                d = json.load(f)
            if isinstance(d, dict):
                return d
        except Exception:
            continue
    return {}


# ---------------------------------------------------------------- reading a name
_TOKEN = re.compile(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|\d+")
_FMT_TOKENS = {"fp", "bf", "q", "k", "m", "s", "gguf", "scaled", "e", "fn", "int", "convrot", "nvfp", "mxfp", "mixed", "safetensors"}


def name_noise(name):
    """'high', 'low' or None from a file (or version) name."""
    stem = os.path.splitext(os.path.basename(str(name).replace("\\", "/")))[0]
    toks = [t.lower() for t in _TOKEN.findall(stem)]
    found = set()
    for i, t in enumerate(toks):
        if t in ("high", "highnoise"):
            found.add(HIGH)
        elif t in ("low", "lownoise"):
            found.add(LOW)
        elif t in ("h", "l") and all(x.isdigit() or x in _FMT_TOKENS for x in toks[i + 1:]):
            found.add(HIGH if t == "h" else LOW)  # Q8H, FP8_L: a lone letter at the end
    return found.pop() if len(found) == 1 else None


def name_release(name):
    """The file name without its high / low words and format tags: the two halves of one release share it."""
    stem = os.path.splitext(os.path.basename(str(name).replace("\\", "/")))[0]
    stem = re.sub(r"(?i)[_\-\s.]?(?:high|low)[_\-\s]?noise", "", stem)
    stem = re.sub(r"(?<=[0-9a-z_\-\s.])(?:High|Low|HIGH|LOW|high|low)(?=$|[_\-\s.A-Z0-9])", "", stem)
    stem = re.sub(r"(?<=[0-9_\-\s.a-z])[HL]$", "", stem)
    stem = re.sub(r"[_\-\s.][HL](?=[_\-\s.])", "", stem)
    return E._release_key(stem)


def name_task(name):
    low = str(name).lower()
    i, t = "i2v" in low, "t2v" in low
    return "i2v" if i and not t else "t2v" if t and not i else None


# ---------------------------------------------------------------- the header: I2V or T2V, and is it an A14B expert
_OTHER_WAN = (("audio_injector", "S2V"), ("casual_audio_encoder", "S2V"), ("vace_blocks", "VACE"), ("face_adapter", "Animate"),
              ("motion_encoder", "Animate"), ("control_adapter", "Fun Camera"))


def header_task(path):
    """('i2v' | 't2v' | None, dim or None, other Wan kind or None) from the header (safetensors or GGUF): the patch
    embedding's input width tells I2V (36) from T2V (16); S2V / VACE / Animate files have their own extra layers."""
    got = E._header_shapes(path)
    if not got:
        return None, None, None
    shapes = got[0]
    other = next((kind for word, kind in _OTHER_WAN if any(word in k for k in shapes)), None)
    for k, s in shapes.items():
        if k.endswith("patch_embedding.weight") and len(s) >= 2:
            return {36: "i2v", 16: "t2v"}.get(s[1]), s[0], other
    return None, None, other


# ---------------------------------------------------------------- the fingerprint library
_FP = {"stamp": None, "index": {}, "sketches": {}}


def _fp_lib():
    return os.path.join(folder_paths.models_dir, "fingerprints")


def _fp_index():
    p = os.path.join(_fp_lib(), "index.json")
    try:
        stamp = os.path.getmtime(p)
    except OSError:
        return {}
    if _FP["stamp"] != stamp:
        try:
            with open(p, encoding="utf-8") as f:
                ix = json.load(f)
        except Exception:
            ix = {}
        _FP.update(stamp=stamp, index={os.path.normcase(os.path.abspath(k)): v for k, v in ix.items()}, sketches={})
    return _FP["index"]


def _fp_sketch(entry):
    rel = entry.get("file")
    if not rel:
        return None
    if rel not in _FP["sketches"]:
        try:
            from safetensors.torch import load_file

            _FP["sketches"][rel] = load_file(os.path.join(_fp_lib(), rel))
        except Exception:
            _FP["sketches"][rel] = None
    return _FP["sketches"][rel]


def _med_rel(a, b):
    """Median relative layer distance between two sketches (0 = the same weights)."""
    shared = [k for k in a if k in b and a[k].shape == b[k].shape]
    if len(shared) < 40:
        return None
    rels = sorted(float((a[k] - b[k]).norm()) / max(float(b[k].norm()), 1e-12) for k in shared)
    return rels[len(rels) // 2]


def fingerprint_info(path):
    """{noise, task, release, label} from the fingerprint library, or None when it doesn't know this file."""
    ix = _fp_index()
    e = ix.get(os.path.normcase(os.path.abspath(path)))
    if not e or e.get("kind") != "model":
        return None
    try:
        st = os.stat(path)
        if e.get("stamp") and e["stamp"] != f"{st.st_size}:{int(st.st_mtime)}":
            return None  # the file changed since it was fingerprinted
    except OSError:
        return None
    out = {}
    civ = e.get("civitai") or {}
    m = re.search(r"/models/(\d+)", str(civ.get("url") or ""))
    if m:
        out["release"], out["label"] = f"civitai:{m.group(1)}", civ.get("model")
    official = {v["file"].lower(): v for v in known_hashes().values() if v.get("task")}
    refs = [(official[os.path.basename(k).lower()], ent) for k, ent in ix.items()
            if os.path.basename(k).lower() in official and ent.get("kind") == "model"]
    sk = _fp_sketch(e) if refs else None
    if sk:
        best = {}
        for v, ent in refs:
            rs = _fp_sketch(ent)
            d = _med_rel(sk, rs) if rs else None
            if d is not None and d < best.get(v["noise"], (9, None))[0]:
                best[v["noise"]] = (d, v.get("task"))
        if HIGH in best and LOW in best:
            (dh, th), (dl, tl) = best[HIGH], best[LOW]
            near, far = (HIGH, LOW) if dh < dl else (LOW, HIGH)
            dn, df = best[near][0], best[far][0]
            if dn < 0.25 and df > 2 * dn:  # measured: 0.05 to its own expert, 0.40 to the other one
                out["noise"] = near
                if dn < 0.12:
                    out["task"] = best[near][1]
    return out or None


# ---------------------------------------------------------------- CivitAI
def _civ_from(d, sha=None):
    """{noise, task, release, label} from a CivitAI model-version record (API or info file)."""
    if not isinstance(d, dict):
        return None
    civ = d.get("civitai") if isinstance(d.get("civitai"), dict) and d.get("civitai") else d
    mid = civ.get("modelId") or (civ.get("model") or {}).get("id")
    out = {}
    if mid:
        out["release"] = f"civitai:{mid}"
        out["label"] = (civ.get("model") or {}).get("name") or d.get("model_name")
    names = [civ.get("name") or ""]
    files = civ.get("files") or []
    if sha:
        files = [f for f in files if str((f.get("hashes") or {}).get("SHA256", "")).lower() == sha] or files
    names += [f.get("name") or "" for f in files if isinstance(f, dict)]
    noises = {n for n in (name_noise(x) for x in names) if n}
    if len(noises) == 1:
        out["noise"] = noises.pop()
    base = str(civ.get("baseModel") or "")
    out["task"] = "i2v" if "I2V" in base else "t2v" if "T2V" in base else None
    return {k: v for k, v in out.items() if v} or None


def civitai_by_hash(sha):
    """CivitAI's record for this file (by sha256, no key), cached per file. None when unknown or offline."""
    with _LOCK:
        cache = _load(CIVITAI)
    if sha in cache:
        return cache[sha] or None
    import urllib.error
    import urllib.request

    req = urllib.request.Request(f"https://civitai.com/api/v1/model-versions/by-hash/{sha}", headers={"User-Agent": "LC123-optimizer"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            d = json.load(r)
        rec = {"modelId": d.get("modelId"), "model": {"name": (d.get("model") or {}).get("name"), "id": d.get("modelId")},
               "name": d.get("name"), "baseModel": d.get("baseModel"),
               "files": [{"name": f.get("name"), "hashes": {"SHA256": (f.get("hashes") or {}).get("SHA256")}} for f in d.get("files") or []]}
    except urllib.error.HTTPError as e:
        if e.code != 404:
            print(f"[LC Dual Optimizer] CivitAI lookup failed ({e.code}): the pair stays unverified.")
            return None
        rec = {}
    except Exception as e:
        print(f"[LC Dual Optimizer] CivitAI lookup failed ({type(e).__name__}): the pair stays unverified.")
        return None
    with _LOCK:
        cache = _load(CIVITAI)
        cache[sha] = rec
        _save(CIVITAI, cache)
    return rec or None


# ---------------------------------------------------------------- one file, then the pair
def file_info(path, allow_hash=True, allow_net=True):
    """What is known about one model file: noise (high / low), task (i2v / t2v), release, and where each came from."""
    info = {"file": os.path.basename(path), "noise": None, "noise_src": None, "task": None, "task_src": None,
            "release": None, "release_src": None, "label": None, "name_key": name_release(path), "a14b": None}

    def put(d, src):
        if not d:
            return
        if d.get("noise") and not info["noise"]:
            info["noise"], info["noise_src"] = d["noise"], src
        if d.get("task") and not info["task"]:
            info["task"], info["task_src"] = d["task"], src
        if d.get("release") and not info["release"]:
            info["release"], info["release_src"], info["label"] = d["release"], src, d.get("label") or d["release"]

    task, dim, other = header_task(path)
    info["a14b"] = None if dim is None else dim == 5120
    info["other"] = other
    if not other:
        put({"task": task}, "header")
    sha = file_sha(path, allow_hash)
    k = known_hashes().get(sha) if sha else None
    if k:
        put({"noise": k["noise"], "task": k["task"], "release": "official:" + k["release"], "label": k["release"]}, "official hash")
    try:
        put(fingerprint_info(path), "fingerprint library")
    except Exception as e:
        print(f"[LC Dual Optimizer] fingerprint library: {e}")
    put(_civ_from(_meta(path), sha), "CivitAI info file")
    put({"noise": name_noise(path), "task": name_task(path)}, "file name")
    if not info["noise"] and sha and allow_net:  # nothing local could tell: ask CivitAI
        put(_civ_from(civitai_by_hash(sha), sha), "CivitAI")
    info["sha256"] = sha
    return info


def _kind(release):
    return str(release).split(":", 1)[0] if release else None


def check_pair(path1, path2, allow_hash=True, allow_net=True):
    """{level: ok | warn | note, text, files: [info1, info2]}. Slot 1 should hold the high noise model."""
    a, b = file_info(path1, allow_hash, allow_net), file_info(path2, allow_hash, allow_net)
    problems, unsure = [], []
    if a["noise"] and b["noise"]:
        if a["noise"] == b["noise"]:
            problems.append(f"both models are {a['noise']} noise")
        elif a["noise"] == LOW:
            problems.append("high and low are swapped: put the high noise model in model 1")
    else:
        miss = [x["file"] for x in (a, b) if not x["noise"]]
        unsure.append(f"could not tell high from low for {' and '.join(miss)}")
    if a["task"] and b["task"] and a["task"] != b["task"]:
        problems.append(f"model 1 is {a['task'].upper()}, model 2 is {b['task'].upper()}")
    for x in (a, b):
        if x.get("other"):
            problems.append(f"{x['file']} is a Wan {x['other']} model, not a high or low noise model")
        elif x["a14b"] is False:
            problems.append(f"{x['file']} is not a Wan 2.2 A14B high or low model")
    same = None
    if a["release"] and b["release"] and _kind(a["release"]) == _kind(b["release"]):
        same = a["release"] == b["release"]
        if not same:
            problems.append(f"different releases: {a['label']} and {b['label']}")
        how = "official hash" if _kind(a["release"]) == "official" else "CivitAI"
    elif a["name_key"] and b["name_key"]:
        same = a["name_key"] == b["name_key"]
        if not same:
            problems.append(f"the names look like different releases ({a['file']} and {b['file']})")
        how = "file names"
    if same is None:
        unsure.append("the release could not be confirmed")
    srcs = sorted({s for x in (a, b) for s in (x["noise_src"], x["release_src"]) if s})
    if problems:
        return {"level": "warn", "files": [a, b],
                "text": "⚠️ Wan 2.2 pair: " + "; ".join(problems) + ". It still runs."}
    if unsure:
        return {"level": "note", "files": [a, b],
                "text": "ℹ️ Unverified pair: " + "; ".join(unsure) + (f" (checked: {', '.join(srcs)})." if srcs else ".")}
    label = a["label"] if a["release"] and a["release"] == b["release"] else None
    return {"level": "ok", "files": [a, b],
            "text": f"✅ Wan 2.2 pair: high + low{f' of {label}' if label else ''}, in the right slots (by {', '.join(srcs) or how})."}
