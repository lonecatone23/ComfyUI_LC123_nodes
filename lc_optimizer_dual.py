"""
LC Dual Model Optimizer: one family, one or two diffusion models of it, with the same file pickers, downloads and
speed-ups as the LC Model Optimizer nodes (lc_optimizer_engine does the work).

  MiniMax H3 (FL2VA + Ref2VA)  model 1 = FL2VA, model 2 = Ref2VA
  Wan 2.2                      model 1 = high noise, model 2 = low noise (with a pair check: lc_wan_pair)
  any other family             two models of it, e.g. for merging

Each model has its own on/off, model file and text encoder. A model that is off is not loaded: its model and clip
outputs are None. The VAE, audio VAE and latent upscaler are shared. The node face is web/lc_optimizer_dual.js.
"""

from __future__ import annotations

import hashlib
import json
import os
import re

from . import lc_model_calc
from . import lc_optimizer_engine as E
from .lc_optimizer_node import MANUAL, QWEN_TIP, VEDA_TIP, CLIP_TIP

H3_PAIR = "MiniMax H3 (FL2VA + Ref2VA)"
WAN = "wan22"
SLOT_WIDGETS = [("model_1_on", "model_file_1", "text_encoder_1"), ("model_2_on", "model_file_2", "text_encoder_2")]
SHARED = [("vae", "vae"), ("audio_vae", "audio_vae"), ("upscaler", "latent_upscaler")]  # (role, widget)
SPECTRUM_DUAL_TIP = ("MiniMax H3, MOSS Image and Krea 2: Spectrum forecasts some steps instead of running them. "
                     "auto = the same choice as LC Model Optimizer for this family. on = try it. off = opt out "
                     "(works with speed_ups on Auto too). Replaces the step cache when on.")


# ---------------------------------------------------------------- families
def families():
    """{name: {pids, comps, labels}} in dropdown order. Pairs first by name, Custom last."""
    profs = E.profiles()
    out = {}
    for pid, p in profs.items():
        if E.is_custom(pid) or p["name"] in out:
            continue
        out[p["name"]] = {"pids": (pid, pid), "comps": (None, None), "labels": ("Model 1", "Model 2")}
    if WAN in profs:
        out[profs[WAN]["name"]] = {"pids": (WAN, WAN), "comps": ("diffusion_high", "diffusion_low"), "labels": ("High noise", "Low noise")}
    if "minimax_h3_fl2va" in profs and "minimax_h3" in profs:
        out[H3_PAIR] = {"pids": ("minimax_h3_fl2va", "minimax_h3"), "comps": (None, None), "labels": ("FL2VA", "Ref2VA")}
    ordered = dict(sorted(out.items(), key=lambda x: x[0].lower()))
    ordered[E.CUSTOM_NAME] = {"pids": ("custom_video", "custom_video"), "comps": (None, None), "labels": ("Model 1", "Model 2")}
    return ordered


def family(name):
    fam = families().get(name)
    if not fam:
        raise ValueError(f"[LC Dual Optimizer] Unknown base model {name}.")
    return fam


def _anchor(on):
    """The slot the shared parts (VAE, audio VAE, upscaler) follow: the first one that is on."""
    return 0 if on[0] or not on[1] else 1


# ---------------------------------------------------------------- per slot recommendations (Wan: high / low)
def slot_recommended(fam, slot, role, goal):
    """The ★ Recommended file of one slot. For a family split into components (Wan 2.2) only that slot's component."""
    pid, comp = fam["pids"][slot], fam["comps"][slot] if role == "model" else None
    prof = E.profiles().get(pid)
    if not prof:
        return None
    if not comp:
        return E.recommended(prof, role, goal)
    vs = list(prof["components"][comp]["variants"])
    if not vs:
        return None
    sysp = E.report()
    if sysp:
        try:
            rec = lc_model_calc.recommend(prof, sysp, goal)
            files = {p["file"]: p for p in rec["picks"]}
            for v in vs:
                if v["file"] in files:
                    return dict(v, pick=files[v["file"]], source="report")
        except Exception:
            pass
    v = next((v for v in vs if v.get("default")), vs[0])
    return dict(v, source="default")


def _rec_hit(v, role="model"):
    folder = E.FOLDER_BY_LOADER.get(v["loader"], E.ROLE_FOLDERS[role][0])
    return E.find_on_disk(v["file"], [folder])


def resolve(fam, slot, role, value, goal):
    """Widget value -> (folder, name, variant or None) for one slot (downloads a ⬇ pick)."""
    pid = fam["pids"][slot]
    if role == "model" and value == E.RECOMMENDED and fam["comps"][slot]:
        v = slot_recommended(fam, slot, role, goal)
        if not v:
            return None
        folder = E.FOLDER_BY_LOADER.get(v["loader"], "diffusion_models")
        hit = E.locate(v["file"], [folder], v.get("repo"), sha=v.get("sha256"))
        if not hit:
            raise E.ask_download(v["file"], v.get("gb"))
        return hit[0], hit[1], v
    return E.resolve(pid, role, value, goal)


def smart_defaults(name, goal):
    """What a click on the family puts in the pickers: each slot's recommended file, or the family's own file already
    on disk when the recommended one isn't (an official file of the same slot)."""
    fam = family(name)
    out = {}
    for slot, (_, mw, tw) in enumerate(SLOT_WIDGETS):
        pid = fam["pids"][slot]
        prof = E.profiles().get(pid)
        out[mw] = out[tw] = E.RECOMMENDED
        if not prof or E.is_custom(pid):
            continue
        for role, w in (("model", mw), ("clip", tw)):
            rec = slot_recommended(fam, slot, role, goal)
            if not rec or _rec_hit(rec, role):
                continue
            comp = fam["comps"][slot] if role == "model" else None
            vs = prof["components"][comp]["variants"] if comp else E.variants(prof, role)
            want = E._fmt_class(rec.get("format"))
            have = [(v, _rec_hit(v, role)) for v in vs]
            have = [(v, h) for v, h in have if h and (not rec.get("task") or v.get("task") == rec.get("task"))]
            if have:  # the closest size class to the recommended one
                v, h = min(have, key=lambda x: abs(E._fmt_class(x[0].get("format")) - want))
                out[w] = h[1]
            elif role == "clip":  # a renamed or community copy of the same encoder (nsfw_wan_umt5-xxl for umt5_xxl)
                key = re.split(r"[_\-.]", rec["file"].lower())[0]
                same = sorted(n for _, n in E.local_files("clip") if len(key) >= 4 and key in os.path.basename(n).lower())
                if same:
                    out[w] = same[0]
    for _, w in SHARED:
        out[w] = E.RECOMMENDED
    return out


# ---------------------------------------------------------------- checks only this node makes
def _wan_checks(paths):
    """Hints for Wan 2.2 files: the model kind from the header (one model on: the pair check covers two) and the
    text encoder's shape."""
    hints = []
    models = [p for p in paths.get("models", []) if p]
    if len(models) == 1:
        from . import lc_wan_pair

        task, dim, other = lc_wan_pair.header_task(models[0])
        if other or dim not in (None, 5120):
            hints.append(("⚠️", f"This looks like a Wan {other or '5B'} model, not a Wan 2.2 A14B high or low model."))
    for slot, p in enumerate(paths.get("clips", [])):
        if not p or p.lower().endswith(".gguf"):
            continue
        got = E._header_shapes(p)
        if not got:
            continue
        shapes = got[0]
        emb = next((s for k, s in shapes.items() if k.endswith("shared.weight")), None)
        if not (emb and emb[-1] == 4096 and any(".block." in k for k in shapes)):
            hints.append(("⚠️", f"Wan 2.2 expects umt5-xxl. Text encoder {slot + 1} doesn't look like it: expect errors."))
    return hints


def _lightning_hint(task=None):
    prof = E.profiles().get(WAN) or {}
    xs = [x for x in prof.get("extras") or [] if not task or x.get("task") == task]
    if not xs:
        return None
    have = [x for x in xs if E.find_on_disk(x["file"], ["loras"])]
    if have:
        return ("💡", "4 steps: Lightning LoRAs on disk (" + ", ".join(x["file"] for x in have) + "). High LoRA on model 1, low on model 2.")
    return ("💡", "4 steps: the Lightning LoRAs (lightx2v) come from huggingface.co/" + xs[0]["repo"] + ". High LoRA on model 1, low on model 2.")


# ---------------------------------------------------------------- the plan the face shows (nothing loads)
def _slot_picks(fam, slot, model_value, goal):
    """Wan: ★ Recommended becomes the slot's own file for the engine's plan (it knows one model per base model)."""
    if model_value != E.RECOMMENDED or not fam["comps"][slot]:
        return model_value, None
    v = slot_recommended(fam, slot, "model", goal)
    if not v:
        return model_value, None
    hit = _rec_hit(v)
    return (hit[1] if hit else E.DOWNLOAD + v["file"]), v


def dual_plan(name, goal, picks, on, manual=None, check=True, allow_hash=False, allow_net=False):
    """picks: {widget: value}. on: [bool, bool]. Everything the face shows, without loading anything."""
    fam = family(name)
    a = _anchor(on)
    out = {"base": name, "labels": list(fam["labels"]), "on": list(on), "anchor": a, "slots": [], "files": [], "hints": [], "pair": None}
    paths = {"models": [None, None], "clips": [None, None]}
    for slot, (_, mw, tw) in enumerate(SLOT_WIDGETS):
        pid = fam["pids"][slot]
        mval, rec = _slot_picks(fam, slot, picks.get(mw, E.RECOMMENDED), goal)
        sp = {"model": mval, "clip": picks.get(tw, E.RECOMMENDED)}
        if slot == a:
            for role, w in SHARED:
                sp[role] = picks.get(w, E.RECOMMENDED)
        pl = E.plan(pid, goal, sp, manual)
        for row in pl["files"]:
            if row.get("role") == "model" and rec is not None:
                row["value"] = E.RECOMMENDED
                if row.get("state") == "download":
                    row["state"] = "pick"  # ★ Recommended never downloads on its own
        slot_files = [dict(r, slot=slot) for r in pl["files"] if r.get("role") in ("model", "clip")]
        slot_rows = {"pid": pid, "label": fam["labels"][slot], "on": bool(on[slot]), "files": slot_files,
                     "speedups": pl["speedups"], "estimate": pl.get("estimate"), "checkpoint": pl.get("checkpoint")}
        out["slots"].append(slot_rows)
        if slot == a:
            out.update(report=pl.get("report"), custom=pl.get("custom"), checkpoint=pl.get("checkpoint"), speedups=pl["speedups"],
                       estimate=pl.get("estimate"), roles=[r for r in pl["roles"] if r in ("vae", "audio_vae", "upscaler")])
            out["files"] = [r for r in pl["files"] if r.get("role") in ("vae", "audio_vae", "upscaler")]
        if on[slot]:
            for h in pl["hints"]:
                h = list(h)
                if h not in out["hints"]:
                    out["hints"].append(h)
        try:  # the paths for the pair check
            for role, key in (("model", "models"), ("clip", "clips")):
                v = sp[role]
                got = None
                if v == E.RECOMMENDED and role == "model" and rec is not None:
                    got = _rec_hit(rec)
                elif v not in (E.RECOMMENDED, E.NONE, E.FROM_CKPT, None, "") and not str(v).startswith((E.DOWNLOAD, "★ ")):
                    got = next(((f, v) for f in E.ROLE_FOLDERS[role] if v in E._list(f)), None) or E.find_on_disk(os.path.basename(str(v)), E.ROLE_FOLDERS[role])
                elif v == E.RECOMMENDED and role == "clip":
                    r = E.recommended(E.profiles().get(pid) or {}, "clip", goal) if E.profiles().get(pid) else None
                    got = _rec_hit(r, "clip") if r else None
                paths[key][slot] = E.full_path(*got) if got else None
        except Exception:
            pass
    if fam["pids"][0] == WAN:
        try:
            out["hints"] += [list(h) for h in _wan_checks({"models": [p if on[i] else None for i, p in enumerate(paths["models"])],
                                                          "clips": [p if on[i] else None for i, p in enumerate(paths["clips"])]})]
        except Exception as e:
            print(f"[LC Dual Optimizer] Wan checks: {e}")
        if check and on[0] and on[1] and all(paths["models"]):
            from . import lc_wan_pair

            try:
                out["pair"] = lc_wan_pair.check_pair(paths["models"][0], paths["models"][1], allow_hash, allow_net)
            except Exception as e:
                out["pair"] = {"level": "note", "text": f"ℹ️ Unverified pair: the check failed ({type(e).__name__})."}
        task = next((x.get("task") for x in (out["pair"] or {}).get("files", []) if x.get("task")), None)
        lh = _lightning_hint(task)
        if lh:
            out["hints"].append(list(lh))
    if not on[0] and not on[1]:
        out["hints"].insert(0, ["ℹ️", "Both models are off: only the VAE (and audio VAE, upscaler) load."])
    return out


# ---------------------------------------------------------------- the node
DESC_DUAL = (
    "Loads one or two models of one family, each with its own text encoder, plus the shared VAE, audio VAE and latent "
    "upscaler. Same file pickers, downloads and speed-ups as LC Model Optimizer.\n"
    "MiniMax H3 (FL2VA + Ref2VA): model 1 = FL2VA, model 2 = Ref2VA.\n"
    "Wan 2.2: model 1 = high noise, model 2 = low noise. The node checks they are a matching pair in the right slots and "
    "shows a ⚠️ if not (it still runs).\n"
    "Any other family: two models of it, for merging or A/B tests.\n"
    "Click the family to fill both slots with the recommended files. Change either slot after that.\n"
    "The switch next to each model turns it off: it isn't loaded, and its model and clip outputs are None.\n"
    "Missing a file? Pick a ⬇ entry and it downloads on the first run. Nothing else ever downloads on its own."
)
SLOT_TIP = "On: loads this model. Off: skips it, and its model and clip outputs are None."


def _values(role):
    vals = [E.RECOMMENDED, E.FROM_CKPT, E.NONE]
    for prof in E.profiles().values():
        if prof.get("components"):
            vals += [E.DOWNLOAD + v["file"] for v in E.variants(prof, role) if E.DOWNLOAD + v["file"] not in vals]
    vals += [n for _, n in E.local_files(role) if n not in vals]
    return vals


class LCOptimizerDual:
    CATEGORY = "LC123/optimizer"
    FUNCTION = "run"
    RETURN_TYPES = ("MODEL", "MODEL", "CLIP", "CLIP", "VAE", "VAE", "LATENT_UPSCALE_MODEL", "STRING")
    RETURN_NAMES = ("model_1", "model_2", "clip_1", "clip_2", "vae", "audio_vae", "latent_upscaler", "info")
    DESCRIPTION = DESC_DUAL

    @classmethod
    def INPUT_TYPES(cls):
        names = list(families())
        default = H3_PAIR if H3_PAIR in names else names[0]
        req = {
            "base_model": (names, {"default": default, "tooltip": "The model family. Picks the recommended files for both models and the checks."}),
            "goal": (E.GOALS, {"default": "Optimal", "tooltip": "Quality = closest to bf16. Optimal = fast and near identical. Fast = fastest that still looks right."}),
        }
        for on_w, mw, tw in SLOT_WIDGETS:  # hidden: the face draws the switches and pickers
            req[on_w] = ("BOOLEAN", {"default": True, "tooltip": SLOT_TIP})
            req[mw] = (_values("model"), {"default": E.RECOMMENDED})
            req[tw] = (_values("clip"), {"default": E.RECOMMENDED})
        for role, w in SHARED:
            req[w] = (_values(role), {"default": E.RECOMMENDED})
        req["speed_ups"] = (["Auto", "Manual"], {"default": "Auto", "tooltip": "Auto = from the System & Model Optimization Report. Manual = choose each one below."})
        for k, (opts, d, tip) in MANUAL.items():
            req[k] = (opts, {"default": d, "tooltip": tip})
        req["qwen21_cache"] = (["auto"] + list(E.QWEN_CACHE), {"default": "auto", "tooltip": QWEN_TIP})
        req["spectrum"] = (["auto", "on", "off"], {"default": "auto", "tooltip": SPECTRUM_DUAL_TIP})
        req["veda"] = (["auto", "on", "off"], {"default": "auto", "tooltip": VEDA_TIP})
        req["clip_type"] = (E.clip_types("video"), {"default": E.CLIP_AUTO, "tooltip": CLIP_TIP})
        return {"required": req, "hidden": {"unique_id": "UNIQUE_ID"}}

    @classmethod
    def VALIDATE_INPUTS(cls, **kw):
        return True  # file lists change as files download; checked (and downloaded) when the node runs

    @classmethod
    def IS_CHANGED(cls, **kw):
        kw.pop("unique_id", None)
        sysp = E.report() or {}
        return hashlib.sha1((json.dumps(kw, sort_keys=True, default=str) + str(sysp.get("when"))).encode()).hexdigest()

    def run(self, base_model, goal, speed_ups, unique_id=None, **kw):
        fam = family(base_model)
        on = [bool(kw.get("model_1_on", True)), bool(kw.get("model_2_on", True))]
        manual = ({k: kw[k] for k in list(MANUAL) + ["qwen21_cache", "spectrum", "veda"] if kw.get(k) is not None}
                  if speed_ups == "Manual" else None)
        for k in ("spectrum", "veda"):  # their opt-outs work on Auto too
            if kw.get(k) in ("on", "off"):
                manual = {**(manual or {}), k: kw[k]}
        swap, loaded = {}, []
        models, clips, applied_all, slot_ckpt = [None, None], [None, None], [], [None, None]
        clip_cache = {}
        ckpt_vae = None
        a = _anchor(on)

        def res(slot, role, widget):
            value = kw.get(widget, E.RECOMMENDED)
            r = resolve(fam, slot, role, value, goal)
            if r and isinstance(value, str) and value.startswith(E.DOWNLOAD):
                swap[widget] = r[1]
            return r

        for slot, (_, mw, tw) in enumerate(SLOT_WIDGETS):
            label = f"model {slot + 1} ({fam['labels'][slot]})" if fam["labels"][slot] != f"Model {slot + 1}" else f"model {slot + 1}"
            pid = fam["pids"][slot]
            if not on[slot]:
                loaded.append((label, "off"))
                continue
            got = res(slot, "model", mw)
            if not got:
                raise ValueError(f"[LC Dual Optimizer] Custom: ★ Recommended is unsupported. Pick your own file for model {slot + 1}."
                                 if E.is_custom(pid) else f"[LC Dual Optimizer] Pick a file for model {slot + 1}.")
            folder, name, _ = got
            model, clip, vae, how = E.load_model(folder, name)
            loaded.append((label, f"{name} ({how})"))
            ckpt = name if folder == "checkpoints" else None
            slot_ckpt[slot] = ckpt
            if slot == a:
                ckpt_vae = vae
            te = kw.get(tw, E.RECOMMENDED)
            gotc = None if (clip is not None and te == E.RECOMMENDED) else res(slot, "clip", tw)
            if gotc:
                f, n, v = gotc
                prof = E.profiles().get(pid) or {}
                if E.is_custom(pid):
                    ctype = kw.get("clip_type") or E.CLIP_AUTO
                    if ctype == E.CLIP_AUTO:
                        ctype, seen = E.auto_clip_type(E.full_path(f, n))
                        if not ctype:
                            raise ValueError("[LC Dual Optimizer] Custom: could not tell how to load this text encoder"
                                             + (f" (it fits {', '.join(seen)})" if seen else "") + ". Set clip_type on the node.")
                else:
                    ctype = (v or {}).get("clip_type") or next((c.get("clip_type") for c in prof["components"].values() if c["role"] == "text_encoder"), "stable_diffusion")
                key = (f, n, ctype, ckpt if ctype == "LTXAVTextEncoderLoader" else None)
                if key not in clip_cache:  # the same text encoder for both models loads once
                    clip_cache[key] = E.load_clip(f, n, ctype, ckpt)
                    loaded.append((f"clip {slot + 1}", f"{n} ({ctype})" if E.is_custom(pid) else n))
                else:
                    loaded.append((f"clip {slot + 1}", f"{n} (shared with clip 1)"))
                clip = clip_cache[key]
            elif clip is not None:
                loaded.append((f"clip {slot + 1}", "from the checkpoint"))
            # the same speed-ups as LC Model Optimizer, each model with its own family's plan
            model, applied = E.apply_speedups(model, E.plan_speedups(pid, goal, manual))
            applied_all.append((slot, applied))
            models[slot], clips[slot] = model, clip

        # shared parts follow the first model that is on
        pid_a = fam["pids"][a]
        roles_a = E.roles_for(pid_a)
        vae_pick = kw.get("vae", E.RECOMMENDED)
        vae = None
        gv = None if (ckpt_vae is not None and vae_pick == E.RECOMMENDED) else resolve(fam, a, "vae", vae_pick, goal)
        if gv:
            vae = E.load_vae(gv[0], gv[1])
            loaded.append(("vae", gv[1]))
            if vae_pick.startswith(E.DOWNLOAD):
                swap["vae"] = gv[1]
        elif ckpt_vae is not None:
            vae = ckpt_vae
            loaded.append(("vae", "from the checkpoint"))
        audio = None
        if "audio_vae" in roles_a:
            ap = kw.get("audio_vae", E.RECOMMENDED)
            ck = slot_ckpt[a]
            ga = None if (ck and ap == E.RECOMMENDED) else resolve(fam, a, "audio_vae", ap, goal)
            if ga:
                audio = E.load_vae(ga[0], ga[1], audio=True)
                loaded.append(("audio vae", ga[1]))
                if ap.startswith(E.DOWNLOAD):
                    swap["audio_vae"] = ga[1]
            elif ck and ap in (E.RECOMMENDED, E.FROM_CKPT):
                audio = E.load_vae("checkpoints", ck, audio=True)
                loaded.append(("audio vae", "from the checkpoint"))
        upscaler = None
        if "upscaler" in roles_a:
            up = kw.get("latent_upscaler", E.RECOMMENDED)
            gu = resolve(fam, a, "upscaler", up, goal)
            if gu:
                upscaler = E.load_upscaler(gu[1])
                loaded.append(("upscaler", gu[1]))
                if up.startswith(E.DOWNLOAD):
                    swap["latent_upscaler"] = gu[1]

        picks = {w: kw.get(w) for trio in SLOT_WIDGETS for w in trio[1:]}
        picks.update({w: kw.get(w) for _, w in SHARED})
        for slot, w in enumerate(("model_file_1", "model_file_2")):  # after a download the plan reads the real file
            if w in swap:
                picks[w] = swap[w]
        dp = dual_plan(base_model, goal, picks, on, manual, check=True, allow_hash=True, allow_net=True)
        dp["applied"] = sorted({x for _, ap in applied_all for x in ap})
        dp["applied_slots"] = {str(s): ap for s, ap in applied_all}
        text = self._info(base_model, dp, applied_all, loaded)
        if dp.get("pair"):
            self._tell(unique_id, dp["pair"]["text"], {"ok": "ok", "warn": "warn"}.get(dp["pair"]["level"], "info"))
            print(f"[LC Dual Optimizer] {dp['pair']['text']}")
        ui = {"lc_optimizer_dual": [json.dumps(dp, default=str)], "lc_optimizer_dual_swap": [json.dumps(swap)]}
        return {"ui": ui, "result": (models[0], models[1], clips[0], clips[1], vae, audio, upscaler, text)}

    @staticmethod
    def _info(base, dp, applied_all, loaded):
        lines = [f"LC Dual Model Optimizer: {base}"]
        lines += [f"{role}: {name}" for role, name in loaded]
        sets = {tuple(ap) for _, ap in applied_all}
        if len(sets) <= 1:
            lines.append("speed-ups: " + (", ".join(applied_all[0][1]) if applied_all and applied_all[0][1] else "none"))
        else:
            for slot, ap in applied_all:
                lines.append(f"speed-ups {slot + 1}: " + (", ".join(ap) or "none"))
        if dp.get("pair"):
            lines.append(dp["pair"]["text"])
        for icon, t in dp.get("hints", []):
            lines.append(f"{icon} {t}")
        return "\n".join(lines)

    @staticmethod
    def _tell(node, text, level):
        """Status line under the node (and a toast for warnings). Never stops the run."""
        if node is None:
            return
        try:
            from server import PromptServer

            PromptServer.instance.send_sync("lc_dual_optimizer_status", {"node": str(node), "text": text, "level": level})
        except Exception:
            pass


# ---------------------------------------------------------------- what the node loads (for LC Save Metadata)
def loaded_files(inputs):
    """[(file name, folder)] of the files this node loads with these inputs. Never downloads."""
    try:
        fam = family(inputs.get("base_model"))
    except Exception:
        return []
    goal = inputs.get("goal") or "Optimal"
    on = [inputs.get("model_1_on", True) is not False, inputs.get("model_2_on", True) is not False]
    a = _anchor(on)
    out = []
    for slot, (_, mw, tw) in enumerate(SLOT_WIDGETS):
        if not on[slot] and slot != a:
            continue
        pid = fam["pids"][slot]
        prof = E.profiles().get(pid) or {}
        mval = inputs.get(mw)
        if mval == E.RECOMMENDED and fam["comps"][slot]:
            v = slot_recommended(fam, slot, "model", goal)
            hit = _rec_hit(v) if v else None
            mval = hit[1] if hit else None
        sub = {"base_model": E.CUSTOM_NAME if E.is_custom(pid) else prof.get("name"), "goal": goal, "latent_upscaler": E.NONE}
        if on[slot]:
            sub.update(model_file=mval, text_encoder=inputs.get(tw))
        if slot == a:
            sub.update(vae=inputs.get("vae"), audio_vae=inputs.get("audio_vae"), latent_upscaler=inputs.get("latent_upscaler"))
        for item in E.loaded_files(sub):
            if item not in out:
                out.append(item)
    return out


NODE_CLASS_MAPPINGS = {"LCOptimizerDual": LCOptimizerDual}
NODE_DISPLAY_NAME_MAPPINGS = {"LCOptimizerDual": "LC Dual Model Optimizer ⚡⚡"}


# ---------------------------------------------------------------- routes for the node face
try:
    from aiohttp import web
    from server import PromptServer

    def _choices(base, slot, role, goal):
        fam = family(base)
        pid = fam["pids"][slot]
        res = E.choices(pid, role, goal)
        comp = fam["comps"][slot] if role == "model" else None
        if comp:  # Wan 2.2: this slot's half only
            prof = E.profiles()[pid]
            mine = {v["file"] for v in prof["components"][comp]["variants"]}
            res["downloads"] = [d for d in res["downloads"] if d["value"][len(E.DOWNLOAD):] in mine]
            rec = slot_recommended(fam, slot, role, goal)
            if rec:
                res["recommended"] = {"file": rec["file"], "gb": rec.get("gb"), "on_disk": bool(_rec_hit(rec)), "source": rec["source"]}
        return res

    @PromptServer.instance.routes.get("/lc123/optimizer_dual/choices")
    async def _lc_dual_choices(request):
        import asyncio

        q = request.rel_url.query
        try:
            slot = 1 if q.get("slot") == "2" else 0
            res = await asyncio.get_running_loop().run_in_executor(None, _choices, q.get("base"), slot, q.get("role", "model"), q.get("goal", "Optimal"))
        except Exception as e:
            print(f"[LC Dual Optimizer] model picker: {e}")
            return web.json_response({"error": f"Could not list the model files: {e}"})
        return web.json_response(res)

    @PromptServer.instance.routes.get("/lc123/optimizer_dual/defaults")
    async def _lc_dual_defaults(request):
        import asyncio

        q = request.rel_url.query
        try:
            res = await asyncio.get_running_loop().run_in_executor(None, smart_defaults, q.get("base"), q.get("goal", "Optimal"))
        except Exception as e:
            return web.json_response({"error": str(e)})
        return web.json_response(res)

    @PromptServer.instance.routes.post("/lc123/optimizer_dual/plan")
    async def _lc_dual_plan(request):
        import asyncio

        body = await request.json()
        manual = body.get("manual") if body.get("speed_ups") == "Manual" else None
        for k in ("spectrum", "veda"):  # their opt-outs work on Auto too
            val = (body.get("manual") or {}).get(k)
            if val in ("on", "off"):
                manual = {**(manual or {}), k: val}
        on = body.get("on") or [True, True]
        try:
            pl = await asyncio.get_running_loop().run_in_executor(
                None, lambda: dual_plan(body.get("base"), body.get("goal", "Optimal"), body.get("picks") or {}, [bool(on[0]), bool(on[1])], manual))
        except Exception as e:
            return web.json_response({"error": str(e), "hints": [["⚠️", str(e)]]})
        return web.json_response(json.loads(json.dumps(pl, default=str)))

except Exception:
    pass
