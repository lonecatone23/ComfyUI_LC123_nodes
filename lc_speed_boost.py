"""
LC Speed Boost (BETA): starts the render at half size, then grows it to full size partway through, so the early steps
cost about a quarter as much. The layout is decided while the picture is small (like the model's own trained size), the
detail at full size. Roughly 1.5x to 2x faster first passes on Krea 2, Z-Image and Flux.2 Klein, with the same quality,
about 1.4x on SDXL, Pony and Illustrious, about 1.2x on Flux 3 Klein and 1.6x on MOSS Image.

Based on SPEED, "Spectral Progressive Diffusion for Efficient Image and Video Generation" (Xiao, Chao, Yariv and
Wetzstein, 2026), and the MIT licensed ComfyUI-SPEED-SwarmNeo. This is LC's own version: it runs on the GPU, it always
grows to full size before the last steps, and it steps aside where it can't help.

How the grow works (flow models: x = (1 - t) * picture + t * noise): the noise is shrunk by keeping the low part of its
cosine spectrum (still pure noise, same strength). At the grow point the small state is padded back to full size in the
same spectrum and the new fine part is filled with fresh noise. Padding leaves the picture 1/r as strong as the noise
(r = full size / small size, per side), so the state is scaled by k = r / (1 + (r - 1) * t) and sampling carries on at
the matching noise level k * t.
SDXL family (x = picture + sigma * noise): the same padding, then the state is scaled by r and sampling carries on at
r * sigma. Its switch point is set on the same 0..1 scale (t = sigma / (1 + sigma)) and sits a little later (0.6).
"""

from __future__ import annotations

import math

import torch

from comfy.samplers import KSAMPLER

_DCT = {}


def _dct(n, device):
    """Orthonormal DCT-II matrix (n x n): coefficients = D @ signal, signal = D.T @ coefficients."""
    key = (n, str(device))
    if key not in _DCT:
        k = torch.arange(n, dtype=torch.float64).unsqueeze(1)
        i = torch.arange(n, dtype=torch.float64).unsqueeze(0)
        d = torch.cos(math.pi * (2 * i + 1) * k / (2 * n)) * math.sqrt(2.0 / n)
        d[0] /= math.sqrt(2.0)
        _DCT[key] = d.to(device=device, dtype=torch.float32)
    return _DCT[key]


def _spec(x):
    """Cosine spectrum over the last two (height, width) dims."""
    h, w = x.shape[-2:]
    return _dct(h, x.device) @ x.float() @ _dct(w, x.device).T


def _unspec(c):
    h, w = c.shape[-2:]
    return _dct(h, c.device).T @ c @ _dct(w, c.device)


def shrink(x, h, w):
    """Noise at full size -> noise at h x w: keep the low part of its spectrum. White noise stays white, same strength."""
    return _unspec(_spec(x)[..., :h, :w].contiguous()).to(x.dtype)


def grow(y, H, W, t, seed, kind="flow"):
    """Small state at noise level t -> full size state, and its noise level. See the module notes.
    kind "sigma" (SDXL family: x = picture + sigma * noise): padding leaves the picture 1/r as strong, so the state is
    scaled by r and sampling carries on at r * sigma."""
    h, w = y.shape[-2:]
    c = torch.zeros(*y.shape[:-2], H, W, device=y.device, dtype=torch.float32)
    c[..., :h, :w] = _spec(y)
    g = torch.Generator(device="cpu").manual_seed(int(seed) & 0xFFFFFFFF)
    fresh = torch.randn(*y.shape[:-2], H, W, generator=g).to(y.device)
    fresh[..., :h, :w] = 0.0  # fresh noise only where the small picture had nothing (white noise in this basis)
    c += t * fresh
    r = math.sqrt((H * W) / float(h * w))
    k = r if kind == "sigma" else r / (1.0 + (r - 1.0) * t)
    return (_unspec(c) * k).to(y.dtype), k * t


def _patcher(model):
    m = model
    for _ in range(6):
        if hasattr(m, "model_patcher"):
            return m.model_patcher
        m = getattr(m, "inner_model", None)
        if m is None:
            return None
    return None


def _kind(model, sigmas):
    """'flow' (Krea 2, Z-Image, Flux, Qwen-Image, Wan), 'sigma' (SDXL family: eps / v prediction), or None."""
    try:
        import comfy.model_sampling as ms

        p = _patcher(model)
        if p is not None:
            m = p.get_model_object("model_sampling")
            if isinstance(m, ms.CONST):
                return "flow"
            if isinstance(m, (ms.EPS, ms.V_PREDICTION)) and not isinstance(m, getattr(ms, "EDM", ())):
                return "sigma"
            return None
    except Exception:
        pass
    return "flow" if float(sigmas.max()) <= 1.001 else None


def _auto_off(model):
    """Why auto Speed Boost should not run on this model, or None. Qwen-Image 2.1's VAE packs 16 x 16 pixels into one
    latent cell (8 x 8 elsewhere), so half size is very coarse: photos come out fine, but line art, anime, text, logos
    and flat art got doubled lines and blocky color (tested 2026-10). A grow_at_step set by hand still runs."""
    p = _patcher(model)
    name = type(getattr(p, "model", None)).__name__ if p is not None else ""
    if name == "QwenImage21":
        return ("Qwen-Image 2.1 draws line art, text, anime and flat color badly at half size (its latent is very "
                "coarse). Photos are fine: set grow_at_step by hand (about 6 of 25 steps) to use it there")
    return None


def _pixel_model(model):
    """SenseNova U1.5 / U1.6 and HiDream-O1: pixel-space models whose noise is scaled by the picture size (tested
    2026-11-24: a grow at step 4 gave pure colored noise). Speed Boost always sits them out."""
    p = _patcher(model)
    return type(getattr(p, "model", None)).__name__ in ("SenseNovaU15", "HiDreamO1")


# readable names for the warning on the node
_MODEL_NAMES = {"SenseNovaU15": "SenseNova", "HiDreamO1": "HiDream-O1", "MiniMaxH3": "MiniMax H3 video",
                "MiniMaxH3Image": "MiniMax H3 Image", "QwenImage21": "Qwen-Image 2.1", "MOSSImage": "MOSS Image",
                "WAN21": "Wan", "WAN22": "Wan", "LTXAV": "LTX", "LTXV": "LTX", "HunyuanVideo": "Hunyuan Video"}


def _model_class(model):
    p = _patcher(model)
    return type(getattr(p, "model", None)).__name__ if p is not None else ""


def _model_name(model):
    cls = _model_class(model)
    return _MODEL_NAMES.get(cls, cls or "this model")


def _tell(node, text, level):
    """Status line under the node (and a toast for warnings). Never stops the run."""
    if node is None:
        return
    try:
        from server import PromptServer

        PromptServer.instance.send_sync("lc_speed_boost_status", {"node": str(node), "text": text, "level": level})
    except Exception:
        pass


def _flow_t(s, kind):
    """A noise level on the 0..1 flow scale (SDXL's sigma s is the same mix as flow t = s / (1 + s))."""
    return s if kind == "flow" else s / (1.0 + s)


def _is_flow(model, sigmas):
    try:
        import comfy.model_sampling as ms

        p = _patcher(model)
        if p is not None:
            return isinstance(p.get_model_object("model_sampling"), ms.CONST)
    except Exception:
        pass
    return float(sigmas.max()) <= 1.001


MIN_START = 0.9  # below this it's an upscale / image to image pass: nothing to gain
AUTO_NOISE = 0.7  # tested sweet spot on Krea 2, Z-Image and Klein: about 2x faster, same quality
# SDXL family (on the same 0..1 scale, t = sigma / (1 + sigma)): clean down to 0.56, harsh skin at 0.44, broken at 0.31
# (SDXL base, Juggernaut, two Illustrious, Pony; dpmpp_2m, euler, euler_a, dpmpp_2m_sde, dpmpp_sde). 0.6 keeps a step
# of margin: about 45 % of the steps at half size, 1.4 - 1.5x faster on an RTX 5060 Laptop.
AUTO_NOISE_SDXL = 0.6
# Flux 3 Klein's schedule stays noisy much longer (step 5 of 16 is still at 0.938): at 0.7 only 4 steps ran at full
# size and text smeared, small faces went blotchy and hands broke. Clean down to 0.938, sign letters break at 0.92,
# small faces at 0.87 (5 prompts + 2 edits x 3 seeds, 2026-10-17): about 1.2x faster.
AUTO_NOISE_FLUX3 = 0.94
# MOSS Image has shift 5 built in, so its schedule stays noisy long too: at 0.7 a 25-step run had 17 steps at half size
# and only 8 at full size, and faces came out blotchy and smeared (3 seeds). Growing near 0.85 (step 12 of 25) stays
# clean at about 1.5x; the 8-step DMD LoRA is fine either way (2026-10-18).
AUTO_NOISE_MOSS = 0.85


def _auto_target(model, kind, steps=0):
    """The noise level auto grows at for this model."""
    if kind != "flow":
        return AUTO_NOISE_SDXL
    p = _patcher(model)
    name = type(getattr(p, "model", None)).__name__ if p is not None else ""
    if name == "MOSSImage" and 0 < steps <= 10:  # a few-step distill (the 8-step DMD LoRA) stays clean at 0.7: 2.4x
        return AUTO_NOISE
    return {"Flux3": AUTO_NOISE_FLUX3, "MOSSImage": AUTO_NOISE_MOSS}.get(name, AUTO_NOISE)


def plan(sigmas, auto, step, kind="flow", target=None):
    """Step where the picture grows to full size, counted from the start of the run. None = stay at full size.
    The last step always runs at full size, the last two when nothing follows (a single pass)."""
    n = len(sigmas) - 1
    if n < 2 or (not auto and step <= 0):
        return None
    s = [_flow_t(float(v), kind) for v in sigmas]
    keep = 1 if s[-1] > 0 else (2 if n >= 4 else 1)  # a pass that ends above 0 hands over to a low pass at full size
    # auto: the step nearest noise 0.7 (a 9-step Turbo schedule has 0.706 then 0.600: "first under 0.7" lost a full size step)
    if target is None:
        target = AUTO_NOISE if kind == "flow" else AUTO_NOISE_SDXL
    j = min(range(1, n), key=lambda i: (abs(s[i] - target), i)) if auto else int(step)
    return max(1, min(j, n - keep))


def _shrink_start(model, x, s0, h, w, kind="flow"):
    """The starting state at half size. x = (1 - s0) * latent + s0 * noise: the noise shrinks as noise, the latent as a
    picture (its spectrum is r times its half size version's). An empty latent is just noise."""
    lat, nz = getattr(model, "latent_image", None), getattr(model, "noise", None)
    if lat is not None and nz is not None and lat.shape == x.shape:
        if not torch.count_nonzero(lat):
            return shrink(x, h, w)
        r = math.sqrt((x.shape[-2] * x.shape[-1]) / float(h * w))
        lat = lat.to(x.device)
        if kind == "sigma":  # x = picture + scaled noise: the noise part is x - picture
            return (shrink(lat, h, w) / r + shrink(x - lat, h, w)).to(x.dtype)
        return ((1.0 - s0) * shrink(lat, h, w) / r + s0 * shrink(nz.to(x.device), h, w)).to(x.dtype)
    return shrink(x, h, w) if s0 >= 0.99 else None


LAYOUT_NODES = {"LCMOSSLayoutPrompt", "MOSSImageLayoutPrompt"}


def layout_upstream(prompt, node_id):
    """True when a MOSS layout prompt feeds this node (through any input). Its boxes are pixel positions at the full
    size: at Speed Boost's half size they would land twice as far from the centre."""
    if not isinstance(prompt, dict) or node_id is None:
        return False
    seen, todo = set(), [str(node_id)]
    while todo:
        nid = todo.pop()
        if nid in seen or nid not in prompt:
            continue
        seen.add(nid)
        if prompt[nid].get("class_type") in LAYOUT_NODES:
            return True
        for v in (prompt[nid].get("inputs") or {}).values():
            if isinstance(v, list) and len(v) == 2 and isinstance(v[1], int):
                todo.append(str(v[0]))
    return False


def layout_for_sampler_node(prompt, node_id):
    """LC Speed Boost (the SAMPLER node): look upstream of the samplers it feeds."""
    if not isinstance(prompt, dict):
        return False
    users = [k for k, n in prompt.items() for v in (n.get("inputs") or {}).values()
             if isinstance(v, list) and len(v) == 2 and str(v[0]) == str(node_id)]
    return any(layout_upstream(prompt, u) for u in users)


def _half_conds(model, raw, xs):
    """The half-size prompt prepared the way ComfyUI prepares the positive (for the half-size latent)."""
    import comfy.sampler_helpers
    import comfy.samplers

    guider = model.inner_model
    conds = {"positive": comfy.sampler_helpers.convert_cond(raw)}
    return comfy.samplers.process_conds(guider.inner_model, xs, conds, xs.device)["positive"]


def _sampler(model, x, sigmas, extra_args=None, callback=None, disable=None, *, lc_inner, lc_auto, lc_step, lc_layout=False,
             lc_half_positive=None, lc_node=None, **kw):
    extra_args = dict(extra_args or {})
    inner_fn, inner_opts = lc_inner.sampler_function, dict(lc_inner.extra_options)

    def run(xx, ss, offset):
        cb = None
        if callback is not None:
            cb = lambda d: callback({**d, "i": d["i"] + offset})
        return inner_fn(model, xx, ss, extra_args=extra_args, callback=cb, disable=disable, **inner_opts)

    why = None
    model_says_no = False  # the model can't take Speed Boost at all (warn), not this run's settings (just note)
    if extra_args.get("denoise_mask") is not None:
        why = "inpaint mask (it only works on the whole picture)"
    elif lc_layout and lc_half_positive is None:
        why = "MOSS layout boxes (they are placed in full-size pixels)"
    elif _model_class(model) == "MiniMaxH3":
        why = ("MiniMax H3 video packs its video and audio into one flat latent while sampling, so there is no "
               "half size picture to start from")
        model_says_no = True
    elif _pixel_model(model):
        why = ("SenseNova / HiDream-O1 draw in pixels and scale their noise to the picture size, so a half size start "
               "turns the picture into colored noise")
        model_says_no = True
    elif not (x.ndim == 4 or (x.ndim == 5 and x.shape[2] == 1)):  # Krea 2 / Flux 2 style: 5D with one frame is a picture
        why = "video and other multi-frame latents can't start at half size"
        model_says_no = True
    kind = None if why else _kind(model, sigmas)
    if why:
        pass
    elif kind is None:
        why = "this model type isn't supported (flow models and SDXL-family models are)"
        model_says_no = True
    elif lc_auto and _auto_off(model):
        why = _auto_off(model)
        model_says_no = True
    elif _flow_t(float(sigmas[0]), kind) < MIN_START:
        why = f"the run starts at noise {_flow_t(float(sigmas[0]), kind):.2f}, too little to start small (upscale / image to image pass)"
    j = None if why else plan(sigmas, lc_auto, lc_step, kind, _auto_target(model, kind, len(sigmas) - 1))
    if j is None:
        if not why:
            why = "grow_at_step is 0" if not lc_auto and lc_step <= 0 else "too few steps"
        print(f"[LC Speed Boost] Off for this run: {why}. Sampling at full size.")
        if model_says_no:
            _tell(lc_node, f"⚠️ Speed Boost does not work with {_model_name(model)}: no speed-up, it samples at full size "
                           f"({why}).", "warn")
        else:
            _tell(lc_node, f"ℹ️ Speed Boost off for this run: {why}.", "info")
        return run(x, sigmas, 0)

    H, W = x.shape[-2:]
    h, w = max(2, round(H / 2)), max(2, round(W / 2))
    t = float(sigmas[j])
    xs = _shrink_start(model, x, float(sigmas[0]), h, w, kind)
    if xs is None:
        print("[LC Speed Boost] Off for this run: can't separate the starting picture from the noise. Sampling at full size.")
        _tell(lc_node, f"⚠️ Speed Boost does not work with {_model_name(model)} here: it can't separate the starting "
                       "picture from the noise, so it samples at full size.", "warn")
        return run(x, sigmas, 0)
    guider = getattr(model, "inner_model", None)
    swap = None
    if lc_half_positive is not None and guider is not None and isinstance(getattr(guider, "conds", None), dict):
        try:
            swap = guider.conds.get("positive")
            guider.conds["positive"] = _half_conds(model, lc_half_positive, xs)
        except Exception as e:  # never lose the run over it: the half-size steps use the normal prompt
            print(f"[LC Speed Boost] positive_half could not be used ({e}); the half-size steps use the positive.")
            if swap is not None:
                guider.conds["positive"] = swap
            swap = None
    try:
        y = run(xs, sigmas[: j + 1], 0)
    finally:
        if swap is not None:
            guider.conds["positive"] = swap
    X, t2 = grow(y, H, W, t, extra_args.get("seed", 0) + 7, kind)
    rest = torch.cat([torch.tensor([t2], dtype=sigmas.dtype, device=sigmas.device), sigmas[j + 1:]])
    n = len(sigmas) - 1
    print(f"[LC Speed Boost] {j} of {n} steps at half size (latent {w}x{h} of {W}x{H}), grew at noise {t:.3f} "
          f"(carries on at {t2:.3f}), {n - j} at full size.")
    _tell(lc_node, f"🚀 Speed Boost on: {j} of {n} steps at half size ({_model_name(model)}).", "ok")
    _reset_size_cache(model)
    return run(X, rest, j)


def _reset_size_cache(model):
    """Qwen-Image 2.1 caches its text K/V per image size. Two sizes in one run make two cache slots, and ComfyUI's
    slot lookup then crashes (it compares slots holding tensors). Clearing it at the switch keeps one slot: the cache
    still speeds up both the half size and the full size steps."""
    try:
        dm = model.inner_model.model_patcher.model.diffusion_model
    except AttributeError:
        return
    if getattr(dm, "prefix_cache_enabled", False) and hasattr(dm, "reset_prefix_cache"):
        dm.reset_prefix_cache(True)


def _wrap(sampler, auto, step, layout=False, half_positive=None, node=None):
    # The LC Detail Daemon times its window by step. Wrapped inside the size switch, each size part would restart that
    # window, so it goes outside: the Daemon sees the whole schedule, Speed Boost runs inside it.
    opts = getattr(sampler, "extra_options", {}) or {}
    if "lc_wrapped" in opts and "lc_amount" in opts:
        inner = _wrap(opts["lc_wrapped"], auto, step, layout, half_positive, node)
        return KSAMPLER(sampler.sampler_function, extra_options={**opts, "lc_wrapped": inner},
                        inpaint_options=getattr(sampler, "inpaint_options", {}))
    return KSAMPLER(_sampler, extra_options={"lc_inner": sampler, "lc_auto": bool(auto), "lc_step": int(step), "lc_layout": bool(layout),
                                             "lc_half_positive": half_positive, "lc_node": node},
                    inpaint_options=getattr(sampler, "inpaint_options", {}))


class LCSpeedBoost:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "sampler": ("SAMPLER", {"tooltip": "High pass sampler only. From LC Sigmas, KSamplerSelect or LC Detail Daemon."}),
            "auto": ("BOOLEAN", {"default": True, "label_on": "auto", "label_off": "grow_at_step",
                                 "tooltip": "Picks the grow step from the run's own schedule (about 2x faster, same quality)."}),
            "grow_at_step": ("INT", {"default": 4, "min": 0, "max": 200, "step": 1,
                                     "tooltip": "Used when auto is off. The step where the picture grows to full size, counted "
                                                "like step_swap. 0 = every step at full size."}),
        }, "hidden": {"prompt": "PROMPT", "unique_id": "UNIQUE_ID"}}

    RETURN_TYPES = ("SAMPLER",)
    FUNCTION = "go"
    CATEGORY = "LC123/sampling"
    DESCRIPTION = ("BETA. Plug it into the high pass sampler only. It starts the picture at half size and grows it to full "
                   "size partway through: about 2x faster, same quality. The layout follows the model's trained size, so a "
                   "seed frames differently with it on.\n"
                   "Put LC Detail Daemon on the low pass. Detail is made in the last steps.\n"
                   "Speeds up passes that start from noise (denoise 0.9 and up). Upscale and image to image passes run as "
                   "normal: their layout comes from your image.\n"
                   "Works on Krea 2, Z-Image, Flux.2 Klein, Qwen-Image, Wan, and SDXL / Pony / Illustrious (about 1.4x "
                   "there). On Flux 3 Klein auto grows early (about 1.2x) so text and small faces stay clean. On MOSS Image it grows at noise 0.85 (about 1.6x, 2.4x with the 8-step LoRA). It does not work with SenseNova, HiDream-O1 or MiniMax H3 video: the node shows a ⚠️ under it and samples at full size. It switches itself off on inpaint masks and MOSS layout boxes (the console says why). On Qwen-Image 2.1 auto stays "
                   "off: line art, text and flat color break at its half size. Set grow_at_step by hand for photos.\n"
                   "Based on SPEED (Xiao, Chao, Yariv and Wetzstein, 2026).")

    def go(self, sampler, auto, grow_at_step, prompt=None, unique_id=None):
        return (_wrap(sampler, auto, grow_at_step, layout_for_sampler_node(prompt, unique_id), node=unique_id),)


class LCSpeedBoostKSampler:
    """A KSampler with Speed Boost built in. Same inputs, same results with Speed Boost off. start / end / leftover noise
    work like KSampler (Advanced), so it can hand off to a regular or ClownShark sampler."""

    @classmethod
    def INPUT_TYPES(cls):
        import comfy.samplers
        from .lc_sampler_configure import _gap
        from .lc_sigmas import clown_names  # RES4LYF / ClownShark sampler names, empty without RES4LYF
        samplers = list(comfy.samplers.KSampler.SAMPLERS) + [n for n in dict.fromkeys(clown_names().values())
                                                             if n not in comfy.samplers.KSampler.SAMPLERS]
        return {"required": {
            "model": ("MODEL", {"tooltip": "The model used for denoising the input latent."}),
            "positive": ("CONDITIONING", {"tooltip": "What you want in the image."}),
            "negative": ("CONDITIONING", {"tooltip": "What you want out of the image."}),
            "latent_image": ("LATENT", {"tooltip": "The latent to denoise."}),
            "speed_boost": ("BOOLEAN", {"default": True, "label_on": "auto", "label_off": "grow_at_step",
                                        "tooltip": "auto = Speed Boost picks the switch step from the schedule (about 2x "
                                                   "faster, same quality). grow_at_step = set it yourself below."}),
            "grow_at_step": ("INT", {"default": 4, "min": 0, "max": 200, "step": 1,
                                     "tooltip": "Used when speed_boost is on grow_at_step: the step where it switches to "
                                                "full resolution. 0 = a plain KSampler."}),
            "_gap1": _gap(),
            "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff, "control_after_generate": True,
                             "tooltip": "The random seed used for creating the noise."}),
            "steps": ("INT", {"default": 10, "min": 1, "max": 10000, "tooltip": "The number of steps."}),
            "cfg": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 100.0, "step": 0.1, "round": 0.01,
                              "tooltip": "How closely it follows the prompt."}),
            "sampler_name": (samplers, {"tooltip": "The sampling algorithm. ClownShark (RES4LYF) samplers are listed "
                                                   "too when RES4LYF is installed, and a ClownSampler Selector can be wired in."}),
            "scheduler": (comfy.samplers.KSampler.SCHEDULERS, {"tooltip": "How the noise is removed over the steps."}),
            "denoise": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01,
                                  "tooltip": "1 = a new picture. Lower = image to image (Speed Boost steps aside under 0.9)."}),
            "_gap2": _gap(),
            "start_at_step": ("INT", {"default": 0, "min": 0, "max": 10000,
                                      "tooltip": "Start partway through the steps, like KSampler (Advanced). Above 0, Speed "
                                                 "Boost steps aside (the picture is already past the layout steps)."}),
            "end_at_step": ("INT", {"default": 10000, "min": 0, "max": 10000,
                                    "tooltip": "Stop at this step. Hand the rest to another sampler with "
                                               "return_with_leftover_noise on."}),
            "return_with_leftover_noise": ("BOOLEAN", {"default": False, "label_on": "enable", "label_off": "disable",
                                                       "tooltip": "enable = stop at end_at_step with the noise left in, for "
                                                                  "a regular or ClownShark sampler to finish (add_noise off, "
                                                                  "start_at_step = this end_at_step)."}),
        }, "optional": {
            "sampler": ("SAMPLER", {"tooltip": "Optional. A ClownSampler (or any SAMPLER) with its own settings, like eta. "
                                               "Replaces sampler_name."}),
            "positive_half": ("CONDITIONING", {"tooltip": "Optional positive for the half-size steps."}),
        }, "hidden": {"prompt": "PROMPT", "unique_id": "UNIQUE_ID"}}

    RETURN_TYPES = ("LATENT",)
    FUNCTION = "sample"
    CATEGORY = "LC123/sampling"

    @classmethod
    def VALIDATE_INPUTS(cls, input_types):
        # a wired sampler_name / scheduler list (rgthree KSampler Config etc.) passes even when it isn't our exact list
        from .lc_sigmas import linked_inputs_ok
        return linked_inputs_ok(cls, input_types)
    DESCRIPTION = ("BETA. A KSampler with LC Speed Boost built in: about half the processing time, same VRAM, same detail. "
                   "Drop it in where your KSampler was. The layout is worked out at a lower resolution, so a seed frames "
                   "a bit tighter with it on.\n"
                   "start_at_step, end_at_step and return_with_leftover_noise work like KSampler (Advanced): stop early "
                   "with the noise left in and let a regular or ClownShark sampler finish.\n"
                   "ClownShark (RES4LYF) samplers are in the sampler list when RES4LYF is installed. Wire a ClownSampler "
                   "into sampler to use its own settings.\n"
                   "Works on Krea 2, Z-Image, Flux.2 Klein, Qwen-Image, Wan, and SDXL / Pony / Illustrious (about 1.4x "
                   "there). On Flux 3 Klein auto grows early (about 1.2x) so text and small faces stay clean. On MOSS Image it grows at noise 0.85 (about 1.6x, 2.4x with the 8-step LoRA). It does not work with SenseNova, HiDream-O1 or MiniMax H3 video: the node shows a ⚠️ under it and samples at full size. On image to image (denoise under 0.9), inpaint masks and MOSS layout boxes it samples like a plain KSampler. On "
                   "Qwen-Image 2.1 auto stays off: line art, text and flat color break at its half size. Set grow_at_step "
                   "by hand for photos.\n"
                   "Based on SPEED (Xiao, Chao, Yariv and Wetzstein, 2026).")

    def sample(self, model, positive, negative, latent_image, speed_boost=True, grow_at_step=4, seed=0, steps=20, cfg=8.0,
               sampler_name="euler", scheduler="simple", denoise=1.0, start_at_step=0, end_at_step=10000,
               return_with_leftover_noise=False, sampler=None, positive_half=None, prompt=None, unique_id=None, **_gaps):
        import comfy.sample
        import comfy.samplers
        import comfy.utils
        import latent_preview
        from .lc_sigmas import make_sampler  # Comfy names and RES4LYF / ClownShark names

        latent = latent_image["samples"]
        latent = comfy.sample.fix_empty_latent_channels(model, latent, latent_image.get("downscale_ratio_spacial", None),
                                                        latent_image.get("downscale_ratio_temporal", None))
        out = latent_image.copy()
        out.pop("downscale_ratio_spacial", None)
        out.pop("downscale_ratio_temporal", None)
        # the same steps a KSampler would take (denoise included), then start / end like KSampler (Advanced)
        ks = comfy.samplers.KSampler(model, steps=steps, device=model.load_device, sampler="euler",  # sigmas only
                                     scheduler=scheduler, denoise=denoise, model_options=model.model_options)
        sigmas = ks.sigmas
        last = int(end_at_step)
        if last < sigmas.shape[-1] - 1:
            sigmas = sigmas[: last + 1]
            if not return_with_leftover_noise:
                sigmas = sigmas.clone()
                sigmas[-1] = 0
        first = int(start_at_step)
        if first > 0:
            if first >= sigmas.shape[-1] - 1:
                out["samples"] = latent
                return (out,)
            sigmas = sigmas[first:]
        if sigmas.shape[-1] < 2:  # denoise 0: nothing to do, like KSampler
            out["samples"] = latent
            return (out,)
        noise = comfy.sample.prepare_noise(latent, seed, latent_image.get("batch_index", None))
        boosted = _wrap(sampler if sampler is not None else make_sampler(sampler_name), speed_boost, grow_at_step,
                        layout_upstream(prompt, unique_id), positive_half, node=unique_id)
        callback = latent_preview.prepare_callback(model, sigmas.shape[-1] - 1)
        out["samples"] = comfy.sample.sample_custom(model, noise, cfg, boosted, sigmas, positive, negative, latent,
                                                    noise_mask=latent_image.get("noise_mask", None), callback=callback,
                                                    disable_pbar=not comfy.utils.PROGRESS_BAR_ENABLED, seed=seed)
        return (out,)


NODE_CLASS_MAPPINGS = {"LCSpeedBoost": LCSpeedBoost, "LCSpeedBoostKSampler": LCSpeedBoostKSampler}
NODE_DISPLAY_NAME_MAPPINGS = {"LCSpeedBoost": "LC Speed Boost (BETA) 🚀", "LCSpeedBoostKSampler": "LC Speed Boost 🚀 KSampler (BETA)"}
