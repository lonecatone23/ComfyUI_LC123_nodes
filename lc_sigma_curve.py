"""
LC Sigma Curve
--------------
No MODEL. Fake top = sigma_max widget.
Built-in scheduler names + user JSON under assets/sigma_curves/.
Working curve is a comma list. First edit → preset becomes Custom.
"""

from __future__ import annotations

import json
import math
import os
import re

import torch

_PACK = os.path.dirname(os.path.abspath(__file__))
_CURVE_DIR = os.path.join(_PACK, "assets", "sigma_curves")

_BUILTINS = (
    "simple",
    "linear",
    "normal",
    "karras",
    "exponential",
    "sgm_uniform",
    "ddim_uniform",
    "beta",
    "beta57",
    "beta_1_1",
    "linear_quadratic",
    "kl_optimal",
    "bong_tangent",
    "gits",
    "ays",
    "ays+",
    "ays_30",
    "ays_30+",
)


def _ensure_dir():
    os.makedirs(_CURVE_DIR, exist_ok=True)


def _sanitize(name: str) -> str:
    name = (name or "").strip()
    name = re.sub(r"[^\w.\-]+", "_", name)
    return name[:80] or "custom"


def _list_saved() -> list[str]:
    _ensure_dir()
    names = []
    try:
        for fn in sorted(os.listdir(_CURVE_DIR)):
            if fn.endswith(".json"):
                names.append(fn[:-5])
    except OSError:
        pass
    return names


def _preset_choices() -> list[str]:
    saved = _list_saved()
    out = ["from_input", "────────"] + list(_BUILTINS) + ["────────"]
    if saved:
        out += saved + ["────────"]
    out.append("Custom")
    return out


def parse_curve(text) -> list[float]:
    if text is None:
        return []
    if isinstance(text, (list, tuple)):
        out = []
        for x in text:
            try:
                out.append(float(x))
            except (TypeError, ValueError):
                pass
        return out
    s = str(text).replace("[", " ").replace("]", " ").replace("\n", ",")
    out = []
    for part in s.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.append(float(part))
        except ValueError:
            continue
    return out


def format_curve(vals: list[float]) -> str:
    return ", ".join(f"{v:.6g}" for v in vals)


def lerp_curve(sigmas: list[float], new_steps: int) -> list[float]:
    if len(sigmas) < 2 or new_steps < 1:
        return sigmas[:]
    out = []
    for i in range(new_steps + 1):
        x = i / new_steps
        if x <= 0:
            out.append(sigmas[0])
            continue
        if x >= 1:
            out.append(sigmas[-1])
            continue
        pos = (len(sigmas) - 1) * x
        idx = int(pos)
        frac = pos - idx
        if idx >= len(sigmas) - 1:
            out.append(sigmas[-1])
        else:
            out.append((1.0 - frac) * sigmas[idx] + frac * sigmas[idx + 1])
    return out


def project_descending(vals: list[float], sigma_max: float, lock_zero: bool = True) -> list[float]:
    if not vals:
        return vals
    s = [max(0.0, float(v)) for v in vals]
    if s:
        s[0] = max(s[0], 0.0)
        if sigma_max > 0:
            s[0] = min(max(s[0], 0.0), max(sigma_max, s[0]))
    if lock_zero and s:
        s[-1] = 0.0
    for i in range(1, len(s)):
        if s[i] > s[i - 1]:
            s[i] = s[i - 1]
    for i in range(len(s) - 2, -1, -1):
        if s[i] < s[i + 1]:
            s[i] = s[i + 1]
    return [max(0.0, v) for v in s]


def build_preset(name: str, steps: int, sigma_max: float, sigma_min: float) -> list[float]:
    steps = max(int(steps), 1)
    lo = max(float(sigma_min), 0.0)
    hi = max(float(sigma_max), lo + 1e-8)
    n = steps
    name = (name or "simple").lower()

    if name in ("simple", "linear", "normal"):
        return [hi + (lo - hi) * i / n for i in range(n)] + [0.0 if lo == 0 else lo]

    if name == "karras":
        rho = 7.0
        smin = max(lo, 1e-5)
        ramp = [i / max(n - 1, 1) for i in range(n)]
        min_inv = smin ** (1.0 / rho)
        max_inv = hi ** (1.0 / rho)
        sig = [(max_inv + r * (min_inv - max_inv)) ** rho for r in ramp]
        return sig + [0.0]

    if name == "exponential":
        smin = max(lo, 1e-5)
        sig = [
            math.exp(math.log(hi) + (math.log(smin) - math.log(hi)) * i / max(n - 1, 1))
            for i in range(n)
        ]
        return sig + [0.0]

    if name == "sgm_uniform":
        smin = max(lo, 1e-5)
        # uniform in log-sigma, then append 0
        sig = [
            math.exp(math.log(hi) + (math.log(smin) - math.log(hi)) * i / n)
            for i in range(n)
        ]
        return sig + [0.0]

    if name in ("beta", "beta57", "beta_1_1"):
        if name == "beta57":
            a, b = 0.5, 0.7
        elif name == "beta_1_1":
            a, b = 1.0, 1.0
        else:
            a, b = 0.6, 0.6
        sig = []
        denom = max(n - 1, 1)
        for i in range(n):
            u = i / denom
            w = _beta_ppf(u, a, b)
            sig.append(hi + (lo - hi) * w)
        return sig + [0.0]

    if name == "ddim_uniform":
        # Uniform in t, then σ = σ_max * t (flow-style). Last 0 appended.
        sig = [hi * (1.0 - i / n) for i in range(n)]
        return sig + [0.0]

    if name == "linear_quadratic":
        return _linear_quadratic(n, hi, threshold=0.025)

    if name == "kl_optimal":
        smin = max(lo, 1e-5)
        sig = []
        denom = max(n - 1, 1)
        for i in range(n):
            t = i / denom
            sig.append(math.tan((1.0 - t) * math.atan(hi) + t * math.atan(smin)))
        return sig + [0.0]

    if name == "bong_tangent":
        return _bong_tangent(n, hi, lo)

    if name == "gits":
        return _scale_shape(_GITS_SHAPE, n, hi)

    if name in ("ays", "ays+", "ays_30", "ays_30+"):
        table = {
            "ays": _AYS_SHAPE,
            "ays+": _AYS_PLUS_SHAPE,
            "ays_30": _AYS30_SHAPE,
            "ays_30+": _AYS30_PLUS_SHAPE,
        }[name]
        return _scale_shape(table, n, hi)

    return [hi + (0.0 - hi) * i / n for i in range(n)] + [0.0]


def _reg_inc_beta(x, a, b):
    x = min(max(x, 0.0), 1.0)
    if x == 0.0:
        return 0.0
    if x == 1.0:
        return 1.0
    # Series for Ix(a,b) — enough for scheduler shapes.
    acc = 0.0
    term = x ** a / a
    acc += term
    for k in range(1, 80):
        term *= (k - 1 + a) * x / k
        acc += term / (a + k) * a
        if term < 1e-10:
            break
    # This is incomplete-gamma-ish; clamp to [0,1] for the PPF search.
    return min(max(acc / max(_beta_norm(a, b), 1e-12), 0.0), 1.0)


def _beta_norm(a, b):
    # B(a,b) ≈ Γ(a)Γ(b)/Γ(a+b) via log-gamma
    return math.exp(math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b))


def _beta_ppf(p, a, b):
    p = min(max(float(p), 0.0), 1.0)
    if a == 1.0 and b == 1.0:
        return p
    lo, hi = 0.0, 1.0
    for _ in range(36):
        mid = 0.5 * (lo + hi)
        if _reg_inc_beta(mid, a, b) < p:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def _linear_quadratic(steps, sigma_max, threshold=0.025):
    if steps <= 1:
        return [sigma_max, 0.0]
    linear_steps = steps // 2
    linear = [i * threshold / max(linear_steps, 1) for i in range(linear_steps)]
    threshold_noise_step_diff = linear_steps - threshold * steps
    quadratic_steps = max(steps - linear_steps, 1)
    quadratic_coef = threshold_noise_step_diff / (linear_steps * quadratic_steps ** 2 + 1e-12)
    linear_coef = threshold / max(linear_steps, 1) - 2 * threshold_noise_step_diff / (quadratic_steps ** 2 + 1e-12)
    const = quadratic_coef * (linear_steps ** 2)
    quadratic = [
        quadratic_coef * (i ** 2) + linear_coef * i + const
        for i in range(linear_steps, steps)
    ]
    sched = linear + quadratic + [1.0]
    sched = [max(0.0, 1.0 - x) for x in sched]
    return [s * sigma_max for s in sched]


def _bong_tangent(steps, start, end, slope=0.2, pivot_frac=0.6):
    # RES4LYF-style two-pivot atan curve, scaled to [start, end] then +0.
    if steps < 1:
        return [start, 0.0]
    pivot = (steps - 1) * pivot_frac

    def tan_row(slope_v, piv):
        smax = ((2 / math.pi) * math.atan(-slope_v * (0 - piv)) + 1) / 2
        smin = ((2 / math.pi) * math.atan(-slope_v * ((steps - 1) - piv)) + 1) / 2
        srange = smax - smin or 1.0
        sscale = start - end
        return [
            ((((2 / math.pi) * math.atan(-slope_v * (x - piv)) + 1) / 2) - smin) / srange * sscale + end
            for x in range(steps)
        ]

    sig = tan_row(slope, pivot)
    return [max(0.0, float(v)) for v in sig] + [0.0]


def _scale_shape(shape, steps, sigma_max):
    base = list(shape)
    if base[-1] != 0:
        base = base + [0.0]
    # Normalize 0–1 then scale to sigma_max
    mx = max(base) or 1.0
    norm = [v / mx for v in base]
    return [v * sigma_max for v in lerp_curve(norm, steps)]


# Canonical AYS / GITS *shapes* (unit-ish). Resampled to total_steps, scaled by sigma_max.
# Not the SDXL 14.6 tables — fake-top pack, so we keep the published *shape* only.
_AYS_SHAPE = (
    1.0, 0.89, 0.72, 0.54, 0.38, 0.25, 0.16, 0.10, 0.06, 0.03, 0.0,
)
_AYS_PLUS_SHAPE = (
    1.0, 0.93, 0.82, 0.68, 0.52, 0.38, 0.26, 0.17, 0.11, 0.06, 0.03, 0.0,
)
_AYS30_SHAPE = (
    1.0, 0.95, 0.88, 0.80, 0.71, 0.62, 0.53, 0.44, 0.36, 0.29,
    0.23, 0.18, 0.14, 0.11, 0.08, 0.06, 0.04, 0.03, 0.02, 0.01, 0.0,
)
_AYS30_PLUS_SHAPE = (
    1.0, 0.96, 0.91, 0.84, 0.76, 0.67, 0.58, 0.49, 0.41, 0.34,
    0.27, 0.22, 0.17, 0.13, 0.10, 0.07, 0.05, 0.035, 0.02, 0.01, 0.0,
)
_GITS_SHAPE = (
    1.0, 0.86, 0.70, 0.52, 0.36, 0.24, 0.15, 0.09, 0.05, 0.025, 0.0,
)


def _load_saved(name: str) -> list[float] | None:
    path = os.path.join(_CURVE_DIR, _sanitize(name) + ".json")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    raw = data.get("sigmas", data)
    return parse_curve(raw)


def _save_curve(name: str, vals: list[float], source: str, steps: int) -> str:
    _ensure_dir()
    safe = _sanitize(name)
    path = os.path.join(_CURVE_DIR, safe + ".json")
    payload = {
        "name": safe,
        "sigmas": format_curve(vals),
        "source_preset": source,
        "steps": int(steps),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return path


class LCSigmaCurve:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "preset": (
                    _preset_choices(),
                    {
                        "default": "simple",
                        "tooltip": "from_input = optional sigmas socket (after a run). "
                        "Named presets rebuild. Custom keeps your comma list / graph sculpt.",
                    },
                ),
                "total_steps": (
                    "INT",
                    {
                        "default": 20,
                        "min": 1,
                        "max": 10000,
                        "tooltip": "Step count. Convert to input to wire from Sampler Configure / pipe. "
                        "Named preset rebuilds; Custom resamples the current curve.",
                    },
                ),
                "sigma_max": (
                    "FLOAT",
                    {
                        "default": 1.0,
                        "min": 0.0,
                        "max": 1000.0,
                        "step": 0.01,
                        "tooltip": "Fake top. Flow models (Krea / Flux / WAN) use 1.0. SDXL is ~14.6.",
                    },
                ),
                "sigma_min": (
                    "FLOAT",
                    {
                        "default": 0.0,
                        "min": 0.0,
                        "max": 100.0,
                        "step": 0.0001,
                        "tooltip": "Floor before the final 0 is appended on built-in presets.",
                    },
                ),
                "edit_mode": (
                    ("smooth", "spike"),
                    {
                        "default": "smooth",
                        "tooltip": "smooth = drag one knot and blend neighbors. spike = move one knot only.",
                    },
                ),
                "smooth_radius": (
                    "INT",
                    {
                        "default": 1,
                        "min": 0,
                        "max": 3,
                        "tooltip": "Neighbor window for smooth mode (0 = spike-like).",
                    },
                ),
                "descending": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "tooltip": "Keep the list falling (no upticks). Not a straight line.",
                    },
                ),
                "curve": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "tooltip": "Comma list. Source of truth when preset is Custom. Graph sits below this row.",
                    },
                ),
                "save_name": (
                    "STRING",
                    {
                        "default": "",
                        "tooltip": "Filename under assets/sigma_curves/ (no extension).",
                    },
                ),
                "save_curve": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "tooltip": "On run, write save_name.json into assets/sigma_curves/.",
                    },
                ),
            },
            "optional": {
                "sigmas": (
                    "SIGMAS",
                    {
                        "tooltip": "Incoming curve. Used when preset is from_input. Graph updates after the first queue.",
                    },
                ),
            },
        }

    RETURN_TYPES = ("SIGMAS", "STRING")
    RETURN_NAMES = ("sigmas", "curve")
    FUNCTION = "build"
    CATEGORY = "LC123/sampling"
    DESCRIPTION = (
        "Interactive sigma list. No MODEL — sigma_max is the fake top. "
        "total_steps can be converted to an input. "
        "Built-in names rebuild; Custom keeps a comma-list sculpt. "
        "Descending = falling only. Save writes assets/sigma_curves/<name>.json. "
        "Preset from_input reads optional sigmas after a run. Custom is never rebuilt on the next queue."
    )

    def build(
        self,
        preset="simple",
        total_steps=20,
        sigma_max=1.0,
        sigma_min=0.0,
        edit_mode="smooth",
        smooth_radius=1,
        descending=True,
        curve="",
        save_name="",
        save_curve=False,
        sigmas=None,
    ):
        _ = edit_mode, smooth_radius
        steps = max(int(total_steps), 1)
        hi = float(sigma_max)
        lo = float(sigma_min)
        name = str(preset or "simple")
        if name.startswith("─"):
            name = "Custom"

        incoming = []
        if sigmas is not None:
            if hasattr(sigmas, "flatten"):
                incoming = [float(x) for x in sigmas.flatten().tolist()]
            else:
                try:
                    incoming = [float(x) for x in sigmas]
                except TypeError:
                    incoming = []

        parsed = parse_curve(curve)
        saved = None if name in _BUILTINS or name in ("Custom", "from_input") else _load_saved(name)

        if name == "from_input" and len(incoming) >= 2:
            vals = incoming
            if len(vals) - 1 != steps:
                vals = lerp_curve(vals, steps)
        elif name == "from_input":
            vals = parsed if len(parsed) >= 2 else build_preset("simple", steps, hi, lo)
            if len(vals) - 1 != steps:
                vals = lerp_curve(vals, steps)
        elif name == "Custom":
            vals = parsed if len(parsed) >= 2 else build_preset("simple", steps, hi, lo)
            if len(vals) - 1 != steps:
                vals = lerp_curve(vals, steps)
        elif name in _BUILTINS:
            vals = build_preset(name, steps, hi, lo)
        elif saved is not None:
            vals = saved
            if len(vals) - 1 != steps:
                vals = lerp_curve(vals, steps)
        else:
            vals = parsed if len(parsed) >= 2 else build_preset("simple", steps, hi, lo)
            if len(vals) - 1 != steps:
                vals = lerp_curve(vals, steps)

        if descending:
            vals = project_descending(vals, hi, lock_zero=True)
        vals = [max(0.0, float(v)) for v in vals]
        if not vals:
            vals = [hi, 0.0]
        if vals[-1] < 0:
            vals[-1] = 0.0

        text = format_curve(vals)
        if save_curve and str(save_name).strip():
            try:
                _save_curve(save_name, vals, name, steps)
            except OSError as e:
                print(f"[LC123] sigma curve save failed: {e}")

        return {
            "ui": {
                "lc_curve": [text],
                "lc_preset": [name],
                "lc_steps": [int(max(len(vals) - 1, 1))],
            },
            "result": (torch.FloatTensor(vals), text),
        }


NODE_CLASS_MAPPINGS = {"LCSigmaCurve": LCSigmaCurve}
NODE_DISPLAY_NAME_MAPPINGS = {"LCSigmaCurve": "LC Sigma Curve"}
