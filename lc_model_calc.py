"""
LC model calculator: which file of a model suits a machine, from its model profile (optimizer_profiles/<id>.json) and a
system profile (lc_system_probe). Everything here is arithmetic on known numbers, and each answer says how sure it is:

  exact     file sizes, VRAM / RAM, whether a format runs natively on the card (tested live or a hardware rule)
  estimate  offload time per step and load time, from measured link and disk speeds
  unknown   what needs benchmark data per model (peak VRAM while sampling, quality loss); shown as such until measured

Also runs on its own:  python lc_model_calc.py <system_profile.json> [model_id ...]
"""

from __future__ import annotations

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PROFILE_DIR = os.path.join(HERE, "optimizer_profiles")
SPARE_GB = 1.0  # the desktop / display and CUDA's own context on the card


def load_profiles(ids=None):
    out = {}
    if not os.path.isdir(PROFILE_DIR):
        return out
    for fn in sorted(os.listdir(PROFILE_DIR)):
        if fn.endswith(".json"):
            try:
                with open(os.path.join(PROFILE_DIR, fn), encoding="utf-8") as f:
                    p = json.load(f)
            except Exception:
                continue
            if not isinstance(p, dict) or "id" not in p or "components" not in p:  # not a model profile
                continue
            if not ids or p["id"] in ids:
                out[p["id"]] = p
    return out


def _cap(sysp):
    g = (sysp.get("gpus") or [{}])[0]
    try:
        a, b = str(g.get("capability", "0.0")).split(".")
        return int(a), int(b), g
    except Exception:
        return 0, 0, g


def format_support(fmt, sysp):
    """How a weight format runs on this card: ('native' | 'cast' | 'slow' | 'no', why). Rules follow ComfyUI's own checks;
    live test results win where there is one."""
    major, minor, g = _cap(sysp)
    t = sysp.get("tests") or {}
    c = sysp.get("comfy") or {}
    packs = sysp.get("packs") or {}
    nv = g.get("vendor") == "NVIDIA"
    cap = (major, minor)
    if not g:
        return "no", "no usable GPU"
    # the format has to exist in this ComfyUI first (read live from comfy.quant_ops); older builds cannot open newer files
    algos = c.get("quant_algos")
    need = {"mxfp8": "mxfp8", "nvfp4": "nvfp4", "int8": "int8_tensorwise", "int8_convrot": "int8_tensorwise",
            "w4a8": "asym_w4a8_int8", "int4_convrot": "convrot_w4a4"}.get(fmt)
    ver = f" {c['version']}" if c.get("version") else ""
    if algos is not None and need and need not in algos:
        return "no", f"your ComfyUI{ver} cannot load {fmt} files yet: update ComfyUI"
    if fmt == "int8_convrot" and c.get("int8_convrot") is False:
        return "no", f"your ComfyUI{ver} loads int8 but not int8_convrot files yet: update ComfyUI"
    if fmt in ("bf16",):
        return ("native", "fast bf16 on this card") if cap >= (8, 0) or not nv else ("slow", "no fast bf16 before RTX 30: ComfyUI runs it in fp16 / fp32")
    if fmt in ("fp16", "fp32"):
        return "native", ""
    if fmt.startswith("fp8"):
        fast = c.get("supports_fp8_compute")
        if fast is None:
            fast = bool((t.get("matmul_fp8") or {}).get("ok"))
        return ("native", "fast fp8 on this card") if fast else ("cast", "stored as fp8 (half the VRAM of bf16), computed in bf16 / fp16: no speed gain before RTX 40")
    if fmt == "mxfp8":
        if c.get("supports_mxfp8_compute") or (nv and cap >= (10, 0)):
            return "native", "fast mxfp8 on RTX 50 / Blackwell"
        return "cast", "stored as 8-bit (half the VRAM of bf16), computed in bf16: no speed gain before RTX 50"
    if fmt in ("w4a8", "int4_convrot"):
        ok = (t.get("matmul_int8") or {}).get("ok")
        if not ok:
            return "no", "needs int8 math, which failed on this card"
        if nv and cap < (8, 0):  # Comfy Kitchen's fast W4A8 kernel needs sm 8.0
            return "cast", "4-bit weights unpacked per layer before RTX 30: saves VRAM, no speed gain"
        return "native", "4-bit weights, int8 math"
    if fmt == "nvfp4":
        if c.get("supports_nvfp4_compute") or (nv and cap >= (10, 0)):
            return "native", "fast nvfp4 on RTX 50 / Blackwell"
        return "cast", "stored as 4-bit, unpacked to bf16 per layer on this card: saves VRAM, costs speed (unconfirmed per model)"
    if fmt in ("int8", "int8_convrot"):
        ok = (t.get("matmul_int8") or {}).get("ok")
        be = ((sysp.get("kitchen") or {}).get("backends") or {})
        kitchen = any(b.get("available") and not b.get("disabled") for n, b in be.items() if n in ("cuda", "hip"))
        if ok and kitchen:
            return "native", "int8 tensor cores through Comfy Kitchen"
        if ok:
            return "cast", "int8 math works, but Comfy Kitchen's GPU backend is not available: slower path"
        return "no", "int8 math failed on this card"
    if fmt.startswith("gguf"):
        if packs.get("GGUF") is False:
            return "no", "needs the ComfyUI-GGUF pack"
        return "cast", "GGUF: unpacked per layer while it runs (a little slower than the same size in fp8 / int8)"
    return "native", ""


def expected_quality(variant):
    """From the bit width only: an expectation until the benchmark measures each file against bf16."""
    b = variant.get("bits")
    if b is None:
        return None
    return "full" if b >= 16 else "near full" if b >= 8 else "high" if b >= 5 else "good" if b >= 4 else "fair" if b >= 3 else "low"


def assess(variant, sysp, role, others_gb=0.0):
    """One file on one machine. role: 'diffusion' (runs every step) or 'text_encoder' (runs once per prompt)."""
    _, _, g = _cap(sysp)
    m = sysp.get("machine") or {}
    t = sysp.get("tests") or {}
    size = variant["gb"]
    vram = g.get("vram_gb") or 0
    ram = m.get("ram_total_gb") or 0
    swap_ok = m.get("swap_managed") or (m.get("swap_total_gb") or 0) > 0
    link = (t.get("transfer") or {}).get("to_gpu_gbs") or 0
    disks = sysp.get("disks") or []
    disk = max((d.get("read_mb_s") or 0) for d in disks) / 1000 if disks else 0
    support, why = format_support(variant["format"], sysp)
    r = {"file": variant["file"], "format": variant["format"], "gb": size, "support": support, "support_why": why, "notes": [],
         "expected_quality": expected_quality(variant)}
    for k in ("repo", "loader", "default", "pruned", "community", "unconfirmed", "note", "display"):
        if variant.get(k) is not None:
            r[k] = variant[k]
    if variant.get("unconfirmed"):
        r["notes"].append("ComfyUI loading not confirmed: " + variant["unconfirmed"])
    budget = max(vram - SPARE_GB, 0.0)  # no GPU (vram 0): nothing fits, but offload doesn't count a negative budget
    if role == "diffusion":
        act = variant.get("activation_gb")  # measured per model; None until the benchmark fills it in
        need = size + (act or 0)
        r["fits"] = "vram" if need <= budget else "offload"
        if act is None:
            r["notes"].append("room for the working memory while sampling is not measured yet")
        if r["fits"] == "offload":
            stream = max(0.0, size - max(0.0, budget - (act or 0)))
            r["stream_gb_per_step"] = round(stream, 1)  # dynamic VRAM overlaps this with compute: it barely shows in step time
    else:  # text encoder: runs once per prompt, then leaves the card
        r["fits"] = "vram" if size <= budget else "offload"
        if r["fits"] == "offload" and link:
            r["offload_s_per_prompt"] = round((size - budget) / link, 1)
    # system RAM has to hold what does not sit on the card (dynamic VRAM keeps the model in RAM and streams it)
    ram_need = size + others_gb
    r["ram"] = "ok" if ram_need <= ram * 0.85 else ("pagefile" if swap_ok else "no")
    if disk:
        r["load_s"] = round(size / disk)
    return r


def _speed(format_, machine):
    """The yardstick that fits the file, as a speed (bigger = faster): fp8-family files by fp8 matmul TFLOPS,
    everything else by 1 / (one standard attention call in ms). None if the machine lacks that test."""
    # plain fp8 files (e4m3fn / e5m2, not "scaled") are converted back up for the math: they scale like bf16
    plain_fp8 = format_ in ("fp8_e4m3fn", "fp8_e5m2")
    if format_.startswith(("fp8", "mxfp8")) and not plain_fp8 and machine.get("fp8_tflops"):
        return machine["fp8_tflops"]
    ms = machine.get("attention_sdpa_ms")
    return 1.0 / ms if ms else None


def _machine_of(sysp):
    t = sysp.get("tests") or {}
    return {"attention_sdpa_ms": (t.get("attention_sdpa") or {}).get("ms"), "fp8_tflops": (t.get("matmul_fp8") or {}).get("tflops")}


def _references(model):
    b = model.get("benchmarks") or {}
    if b.get("references"):
        return b["references"]
    return [{"machine": b.get("ref_machine") or {}, "runs": b.get("runs", [])}] if b.get("runs") else []


def step_times(model, variant, sysp):
    """Seconds per step for this file on this card, from the measured machines.
    Two measured machines: time follows a power curve through both points (t ~ speed^-a), so a card between them is
    interpolated and one outside them is extended from the nearer one. One measured machine: plain scaling (a = 1).
    Why not always a = 1: a small model does not keep a fast card busy, so the fast card's time understates how much
    slower a weak card is (Anima: 9x apart where the yardstick says 7x); two points measure that."""
    me = _machine_of(sysp)
    s = _speed(variant.get("format", ""), me)
    if not s:
        return None
    pts = {}
    for ref in _references(model):
        rs = _speed(variant.get("format", ""), ref.get("machine") or {})
        for r in ref.get("runs", []):
            if r["file"] == variant["file"] and rs and r.get("step_s"):
                pts.setdefault(str(r["megapixels"]), []).append((rs, r["step_s"]))
    out = {}
    for mp, p in pts.items():
        p = sorted(p, reverse=True)  # fastest machine first
        if len(p) >= 2 and p[0][0] > p[-1][0] * 1.05:
            (s1, t1), (s2, t2) = p[0], p[-1]
            import math
            a = math.log(t2 / t1) / math.log(s1 / s2)
            a = min(max(a, 0.3), 2.0)  # keep a single odd pair of runs from bending the curve absurdly
            near = min(p, key=lambda q: abs(math.log(q[0] / s)))
            out[mp] = round(near[1] * (near[0] / s) ** a, 2)
        else:
            # one measured machine: small models do not keep a fast card busy, so slow cards fall further behind.
            # Learned on Anima (2B), checked on Z-Image Turbo (6B): a = 1.15 under ~10B parameters (within 1-9 %,
            # plain scaling was 20-39 % too fast); 13B and up scale evenly (a = 1.0: Krea2, H3).
            s1, t1 = p[0]
            a = 1.15 if (model.get("params_b") or 99) < 10 else 1.0
            out[mp] = round(t1 * (s1 / s) ** a, 2)
    return out or None


def estimate_confidence(model, variant):
    """'good' when the curve between the two machines holds its shape across resolutions (held-out test: median 7 %
    error), 'rough' when it bends (GGUF K-quants, LTX 2.5: a fixed per-step cost that does not scale with the card:
    25 to 100 % off), 'scaled' with a single measured machine."""
    import math
    rows = {}
    for r in _references(model):
        sp = _speed(variant.get("format", ""), r.get("machine") or {})
        for x in r.get("runs", []):
            if x["file"] == variant["file"] and sp and x.get("step_s"):
                rows.setdefault(str(x["megapixels"]), []).append((sp, x["step_s"]))
    exps = []
    for p in rows.values():
        p = sorted(p, reverse=True)
        if len(p) >= 2 and p[0][0] > p[-1][0] * 1.05:
            exps.append(math.log(p[-1][1] / p[0][1]) / math.log(p[0][0] / p[-1][0]))
    if not exps:
        return "scaled" if rows else None
    return "good" if max(exps) - min(exps) <= 0.12 else "rough"


def calc(model, sysp):
    """All components of one model profile against one machine."""
    out = {"id": model["id"], "name": model["name"], "components": {}}
    comps = model["components"]
    # the other parts sit in RAM at the same time: measured on the laptop, RAM grew by video model + text encoder + VAEs
    # (dynamic VRAM stages every loaded model in RAM). Counted with Comfy's default file for each other part.
    def default_gb(c):
        vs = c.get("variants") or []
        picked = [v for v in vs if v.get("default") or v.get("always")]
        return sum(v["gb"] for v in picked) if picked else (min(v["gb"] for v in vs) if vs else 0)
    parts = {k: default_gb(c) for k, c in comps.items()}
    for key, comp in comps.items():
        others = sum(v for k, v in parts.items() if k != key)
        rows = [assess(v, sysp, comp.get("role", "diffusion"), others) for v in comp.get("variants", [])]
        for row, v in zip(rows, comp["variants"]):
            row["on_disk"] = v.get("on_disk")
            mq = ((model.get("quality") or {}).get("files") or {}).get(v["file"])
            if mq:
                row["measured_lpips"] = mq["lpips_avg"]  # distance from bf16 for one step, averaged over early / middle / late
                row["expected_quality"] = "measured"
            st = step_times(model, v, sysp) if comp.get("role", "diffusion") == "diffusion" else None
            if st:
                row["est_step_s"] = st  # {megapixels: seconds per step}
                row["est_confidence"] = estimate_confidence(model, v)
        out["components"][key] = {"label": comp["label"], "rows": rows}
    return out


# ---------------------------------------------------------------- recommendations (the System & Model Optimization Report's model section)
# distance from bf16 for one step (LPIPS) when a file is not measured: what the measured files of that bit width
# landed at across 9 models (8-bit ~0.02, 6 ~0.03, 5 ~0.04, 4 ~0.07, 3 ~0.18, 2 ~0.35)
BITS_TO_LPIPS = {32: 0.0, 16: 0.0, 8: 0.02, 6: 0.03, 5: 0.04, 4: 0.07, 3: 0.18, 2: 0.35}
GOALS = {"Quality": None, "Optimal": 0.05, "Fast": 0.10}  # the most distance from bf16 each goal accepts (frame sheets: under ~0.05 looks the same)
STEPS = {"minimax_h3": 8, "minimax_h3_fl2va": 8, "krea2": 8, "ltx25": 11, "anima": 30, "z_image_turbo": 8, "qwen_image_21": 25, "flux2_klein_9b": 20, "flux2_klein_9b_distilled": 4, "flux3_klein": 16, "fibo2_edit_turbo": 8, "flux3_klein_base": 50, "ideogram4": 20, "ltx23": 11,
         "krea2_raw": 52, "sdxl": 30, "illustrious": 28, "pony": 25}
LOADER_NEEDS = {"UnetLoaderGGUF": "needs a current ComfyUI-GGUF pack (update it if a newer model such as Flux 3 Klein will not load)",
                "CLIPLoaderGGUF": "needs a current ComfyUI-GGUF pack"}


def _class(fmt):
    return "gguf" if fmt.startswith("gguf") else "full" if fmt in ("bf16", "fp16", "fp32", "fp8_e4m3fn", "fp8_e5m2") else "fast"


def _on_disk(names):
    """Which of these file names already sit in ComfyUI's model folders (only when running inside ComfyUI)."""
    try:
        import folder_paths
    except Exception:
        return set()
    have = set()
    for kind in ("diffusion_models", "unet", "checkpoints", "text_encoders", "clip", "vae", "loras", "latent_upscale_models"):
        try:
            for f in folder_paths.get_filename_list(kind):
                have.add(os.path.basename(f).lower())
        except Exception:
            pass
    return {n for n in names if n.lower() in have or n.lower().replace(" ", "") in have}


def recommend(model, sysp, goal="Optimal", megapixels=None):
    """Pick one file per component for this machine and goal. Returns picks with the reasons and warnings to show."""
    res = calc(model, sysp)
    comps = model["components"]
    out = {"id": model["id"], "name": model["name"], "goal": goal, "notes": model.get("notes", []), "picks": [], "warnings": []}
    steps = STEPS.get(model["id"])
    names = [v["file"] for c in comps.values() for v in c.get("variants", [])]
    have = _on_disk(names)
    chosen_gb = {}
    for key, comp in res["components"].items():
        role = comps[key].get("role", "diffusion")
        rows = [r for r in comp["rows"] if r["support"] != "no" and r["ram"] != "no" and not r.get("unconfirmed")]
        if not rows:
            out["warnings"].append(f"{comp['label']}: no file runs on this machine")
            continue
        if role == "fixed":
            picks = [r for r in rows if (r.get("default") or r.get("note") == "always") or any(v["file"] == r["file"] and (v.get("always") or v.get("default")) for v in comps[key]["variants"])]
            for r in picks or rows[:1]:
                out["picks"].append({"component": comp["label"], "file": r["file"], "display": r.get("display"), "gb": r["gb"], "repo": r.get("repo"), "on_disk": r["file"] in have, "role": role})
                chosen_gb[key] = chosen_gb.get(key, 0) + r["gb"]
            continue
        by_fmt = {}
        for r in rows:
            if r.get("measured_lpips") is not None:
                by_fmt.setdefault(r["format"], []).append(r["measured_lpips"])
        for r in rows:
            m = r.get("measured_lpips")
            v = next(x for x in comps[key]["variants"] if x["file"] == r["file"])
            ref_file = (model.get("quality") or {}).get("reference")
            if r["file"] == ref_file:
                r["_q"], r["_q_measured"] = 0.0, "reference"
                continue
            if m is None and by_fmt.get(r["format"]):
                m_same = sorted(by_fmt[r["format"]])[len(by_fmt[r["format"]]) // 2]
                r["_q"], r["_q_measured"] = m_same, "same format"
            else:
                r["_q"] = m if m is not None else BITS_TO_LPIPS.get(v.get("bits") or 16, 0.1)
                r["_q_measured"] = m is not None or (v.get("bits") or 16) >= 16  # a 16-bit file is bf16 itself
                if m is None and (v.get("bits") or 16) < 16:
                    same_class = [x.get("measured_lpips") for x in rows if x.get("measured_lpips") is not None and _class(x["format"]) == _class(r["format"])]
                    if same_class:
                        r["_q"] = max(r["_q"], sorted(same_class)[len(same_class) // 2])
        if role == "text_encoder":
            # runs once per prompt: follow the goal on quality, but never a file that pushes RAM into the page file
            ok = [r for r in rows if r["ram"] == "ok"] or rows
            if goal == "Quality":
                r = min(ok, key=lambda r: (r["_q"], -r["gb"]))
            elif goal == "Fast":
                within = [x for x in ok if x["_q"] <= GOALS["Fast"]] or ok
                r = min(within, key=lambda r: r["gb"])
            else:
                r = next((r for r in ok if r.get("default")), min(ok, key=lambda r: (r["_q"] > 0.03, r["gb"])))
        else:
            mp = megapixels
            for r in rows:
                est = r.get("est_step_s") or {}
                if est:
                    k = min(est, key=lambda x: abs(float(x) - (mp or float(x))))
                    r["_t"], r["_mp"] = est[k], float(k)
            # files without a timing: borrow the median time of measured files of the same class for this model
            by_class = {}
            for r in rows:
                if r.get("_t"):
                    by_class.setdefault(_class(r["format"]), []).append(r["_t"])
            for r in rows:
                if not r.get("_t") and by_class.get(_class(r["format"])):
                    ts = sorted(by_class[_class(r["format"])])
                    r["_t"], r["_t_borrowed"] = ts[len(ts) // 2], True
            limit = GOALS.get(goal)
            pool = [r for r in rows if r["ram"] == "ok"] or rows
            if limit is None:
                r = min(pool, key=lambda r: (round(r["_q"], 3), not r["_q_measured"], r.get("_t") or 1e9, r["gb"]))
            else:
                good = [r for r in pool if r["_q"] <= limit] or [min(pool, key=lambda r: (round(r["_q"], 3), not r["_q_measured"], r["gb"]))]
                # files without a measured step time tie on speed: one that fits in VRAM goes before the closest to bf16
                # (MOSS bf16 on an 8 GB laptop streamed from RAM and ran 2.5x slower than int8, 2026-10-22)
                r = min(good, key=lambda r: (round(r.get("_t") or 1e9, 2), r.get("fits") != "vram", round(r["_q"], 3),
                                             not r["_q_measured"], r["gb"]))
            # Fast on a small GPU: the file tested as the fast pick there (H3 pruned Q4 on an 8 GB laptop: 1.6x faster,
            # visibly softer, so never the Optimal default)
            vram = ((sysp.get("gpus") or [{}])[0].get("vram_gb") or 0)
            if goal == "Fast" and vram:
                small = [x for x in rows if vram <= (next(v for v in comps[key]["variants"] if v["file"] == x["file"]).get("prefer_up_to_vram_gb") or 0)]
                if small:
                    r = small[0]
        v = next(x for x in comps[key]["variants"] if x["file"] == r["file"])
        info = [v["note"]] if v.get("note") not in (None, "pair", "gated") else []
        warn = [w for w in (LOADER_NEEDS.get(r.get("loader", "")), "gated on Hugging Face: accept the license there first" if v.get("note") == "gated" else None,
                            "community file" if r.get("community") else None,
                            "RAM will spill into the page file: slower first run" if r["ram"] == "pagefile" else None) if w]
        pick = {"component": comp["label"], "file": r["file"], "display": r.get("display"), "format": r["format"], "gb": r["gb"], "repo": r.get("repo"), "on_disk": r["file"] in have,
                "role": role, "support": r["support"], "support_why": r.get("support_why"), "fits": r["fits"], "ram": r["ram"],
                "lpips": round(r["_q"], 4), "lpips_measured": r["_q_measured"], "warnings": warn, "info": info, "load_s": r.get("load_s")}
        if role == "diffusion" and r.get("_t"):
            pick.update(step_s=r["_t"], at_mp=r.get("_mp"), borrowed=bool(r.get("_t_borrowed")), confidence=r.get("est_confidence") or "scaled")
            if steps:
                tot = r["_t"] * steps
                pick["total_s"] = round(tot, 1) if tot < 10 else round(tot)
                pick["steps"] = steps
        out["picks"].append(pick)
        chosen_gb[key] = r["gb"]
    ram = (sysp.get("machine") or {}).get("ram_total_gb") or 0
    total = round(sum(chosen_gb.values()), 1)
    out["ram_need_gb"], out["ram_gb"] = total, ram
    if ram and total > ram * 0.85:
        out["warnings"].append(f"These files add up to {total} GB against {ram:g} GB of RAM: expect the page file to be used (slower loading).")
    return out


# ---------------------------------------------------------------- shopping guide (for custom models, any model)
# Ranges measured across 9 models (H3, Krea2, LTX 2.5 / 2.3, Anima, Z-Image Turbo, Qwen-Image 2.1, Flux.2 Klein 9B,
# Ideogram 4) on an RTX 5090 and an RTX 5060 Laptop 8 GB. "vs bf16" = LPIPS after one step, 0 = identical.
def shopping_guide(sysp):
    """What to look for in a model file on this machine, a size guide, and what to avoid. Model independent."""
    major, minor, g = _cap(sysp)
    m = sysp.get("machine") or {}
    vram = g.get("vram_gb") or 0
    ram = m.get("ram_total_gb") or 0
    nv = g.get("vendor") == "NVIDIA"
    fp8 = format_support("fp8_scaled", sysp)[0] == "native"
    nvfp4 = format_support("nvfp4", sysp)[0] == "native"
    int8 = format_support("int8_convrot", sysp)[0] == "native"
    mxfp8 = format_support("mxfp8", sysp)[0] == "native"
    w4a8 = format_support("w4a8", sysp)[0] == "native"
    gguf_pack = (sysp.get("packs") or {}).get("GGUF") is not False
    look, avoid = [], []

    fit = max(0.0, round(vram - 1.5, 1))
    stream = round(max(0.0, ram * 0.5), 0)
    size = {"fits_on_card_gb": fit, "streams_well_up_to_gb": stream, "page_file_after_gb": round(ram * 0.85, 0),
            "text": [f"Up to about {fit:g} GB: the model sits on the card (fastest).",
                     f"Up to about {stream:g} GB: it streams from RAM each step; on these tests that cost little speed.",
                     f"Model + text encoder + VAE over about {ram * 0.85:.0f} GB: RAM spills into the page file (slow loading, GGUF files suffer most)."]}

    big_card = vram >= 20
    if big_card:
        look.append({"what": "bf16 (full precision)", "why": f"Your card holds image models up to ~{fit:g} GB whole: best quality, no guesswork. For big video models pick int8 or fp8 instead."})
    if int8:
        look.append({"what": "int8_convrot", "why": "Fast on this card (int8 math through Comfy Kitchen): 1.3 to 2.2x the speed of bf16 and usually near identical (0.002 to 0.04 vs bf16). Best default in most tests."})
    if fp8:
        look.append({"what": "fp8_scaled / fp8mixed", "why": "Fast fp8 math on this card: 1.2 to 1.75x the speed of bf16, near identical (0.014 to 0.037)."})
    if mxfp8:
        look.append({"what": "mxfp8", "why": "Native on RTX 50: 8-bit with a scale for every 32 values, so it stays close even without the per-layer settings a plain fp8 file needs (Krealism V3.1: 0.019). About int8 speed."})
    if nv and not fp8:
        look.append({"what": "fp8 files (to save VRAM only)", "why": "Half the size of bf16, but this card has no fast fp8 math: no speed gain."})
    if w4a8:
        look.append({"what": "w4a8 (small and close)", "why": "4-bit weights, int8 math: nvfp4 size, but closer to bf16 (Krealism V3.1: 0.031 vs 0.059 for nvfp4). As fast as int8 on an RTX 5090 and an RTX 5060 laptop."})
    if nvfp4:
        look.append({"what": "nvfp4 (for speed)", "why": "Native on this card: the fastest files and a quarter the size of bf16, with small but visible differences (0.05 to 0.15)."})
    if gguf_pack:
        look.append({"what": "GGUF Q8_0 (when fidelity matters)", "why": "Closest to bf16 of all quants (0.0014 to 0.02), but slower than bf16 on most cards and it sits fully in RAM."})
    if not big_card:
        look.append({"what": "Pruned / distilled / turbo versions", "why": "Same output for less size (pruned H3: 60 % of the size, identical output) or fewer steps."})
    look.append({"what": "The model's recommended text encoder in fp8 / int8 / nvfp4", "why": "Runs once per prompt, so a smaller format costs little quality; a smaller text-encoder MODEL usually does not work at all."})

    avoid.append({"what": "GGUF Q3 and Q2", "why": "Falls apart: 0.18 vs bf16 on Anima Q3 (soft, washed out)."})
    avoid.append({"what": "Plain fp8 (e4m3fn / e5m2, not \"scaled\")", "why": "Converted back up for the math: no faster than bf16 (Z-Image test), only smaller."})
    avoid.append({"what": "Q4 / Q5 K-quant GGUFs as a speed fix", "why": "Smaller but 2 to 3x slower than bf16 on a fast card (unpacking cost); pick them only when nothing else fits."})
    if not nvfp4:
        avoid.append({"what": "nvfp4 files", "why": "Not native on this card: unpacked while running, so slower than the 8-bit files."})
    if not fp8 and nv:
        avoid.append({"what": "Expecting fp8 to be faster", "why": "fp8 math needs an RTX 40 or newer."})
    if ram and ram < 48:
        avoid.append({"what": "Big GGUFs with little RAM", "why": f"A GGUF sits fully in RAM; with {ram:g} GB it spills into the page file first (32 GB test: loading twice as slow)."})
    avoid.append({"what": "Files your loader cannot open", "why": "Community GGUFs without an architecture tag (Ideogram 4, most Qwen-Image 2.1) are rejected by ComfyUI-GGUF; some community fp8 / bf16 files are not recognised at all. Check the model page for 'ComfyUI' and the loader."})
    avoid.append({"what": "Community int8 / fp8 conversions of finetunes without a comparison", "why": "Conversions vary, and a file name can be wrong (one finetune's \"int8\" file was really fp8). Official files are measured; a community one is only as good as its converter."})
    avoid.append({"what": "LoRA-heavy workflows on 8-bit quants (video)", "why": "LTX 2.3 with its LoRA drifted 0.07 to 0.09 on fp8 / int8 vs 0.015 for Q8; test before trusting."})
    # the short answer per goal: what to pick on THIS machine, best first
    q, o, f = [], [], []
    if big_card:
        q.append(("bf16", f"when the file is under ~{fit:g} GB"))
    else:
        q.append(("bf16", f"streams fine up to ~{stream:g} GB, just slower"))
    if gguf_pack:
        q.append(("GGUF Q8_0", "nearly identical to bf16, smaller"))
    if int8:
        o.append(("int8_convrot", "fast here, near identical"))
    if mxfp8:
        o.append(("mxfp8", "fast here, very close"))
    if fp8:
        o.append(("fp8_scaled", "fast here, near identical"))
    if not o and gguf_pack:
        o.append(("GGUF Q8_0", "no fast 8-bit math on this card"))
    if nvfp4:
        f.append(("nvfp4", "fastest, small visible changes"))
    if w4a8:
        f.append(("w4a8", "nvfp4 size, closer to bf16"))
    if int8:
        f.append(("int8_convrot", "fast, near identical"))
    elif fp8:
        f.append(("fp8_scaled", "fast, near identical"))
    if gguf_pack:
        f.append(("GGUF Q4_K_M", "only when nothing bigger fits"))
    by_goal = {"Quality": [{"what": a, "why": b} for a, b in q], "Optimal": [{"what": a, "why": b} for a, b in o], "Fast": [{"what": a, "why": b} for a, b in f]}
    tip = "Text encoder: use the model's own one in fp8 / int8 / nvfp4. It runs once per prompt, so the smaller format costs little; a smaller text-encoder MODEL usually does not work at all."
    head = f"{g.get('name', 'This card')}, {vram:g} GB VRAM, {ram:g} GB RAM"
    return {"machine": head, "by_goal": by_goal, "tip": tip, "look_for": look, "avoid": avoid, "size": size}


if __name__ == "__main__":
    import sys

    sysp = json.load(open(sys.argv[1], encoding="utf-8"))
    for mid, model in load_profiles(sys.argv[2:] or None).items():
        res = calc(model, sysp)
        print(f"\n== {res['name']}  on  {(sysp.get('gpus') or [{}])[0].get('name')}")
        for key, comp in res["components"].items():
            print(f"  -- {comp['label']}")
            for r in comp["rows"]:
                extra = []
                if r.get("measured_lpips") is not None:
                    extra.append(f"LPIPS vs bf16 {r['measured_lpips']}")
                if r.get("est_step_s"):
                    extra.append("est. " + ", ".join(f"{s_} s/step @{mp} MP" for mp, s_ in r["est_step_s"].items()) + f" ({r.get('est_confidence')})")
                elif r.get("stream_gb_per_step") is not None:
                    extra.append(f"streams {r['stream_gb_per_step']} GB/step")
                if r.get("offload_s_per_prompt") is not None:
                    extra.append(f"~{r['offload_s_per_prompt']} s extra per prompt")
                if r.get("load_s") is not None:
                    extra.append(f"loads in ~{r['load_s']} s")
                tag = ("*" if r.get("default") else " ") + ("?" if r.get("unconfirmed") else " ")
                print(f"   {tag}{r['file'][:50]:<50} {r['gb']:>6.1f} GB {r['format']:<13} {str(r['expected_quality']):<9} {r['support']:<6} fits:{r['fits']:<7} RAM:{r['ram']:<8} {'; '.join(extra)}")
