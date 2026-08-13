"""
LC Split Sigmas (Advanced)
--------------------------
Inputs (top → bottom): model_1, sigmas_1, model_2 (opt), sigmas_2 (opt)
Widgets: step_swap, denoise
Outputs: sigmas_high, sigmas_low

If sigmas_2 is disconnected → use sigmas_1 for the full schedule (both halves).
If model_2 is disconnected → treated as model_1 (wiring only; not used in sigma math).
Total steps are set on upstream schedulers (e.g. LC Basic Scheduler).
"""

import torch


def _as_1d(sigmas):
    if sigmas is None:
        return None
    if isinstance(sigmas, torch.Tensor):
        return sigmas.detach().cpu().float().flatten()
    try:
        return torch.FloatTensor(list(sigmas)).flatten()
    except Exception:
        return None


def _apply_denoise(sigmas: torch.Tensor, denoise: float) -> torch.Tensor:
    denoise = float(denoise)
    if denoise >= 1.0:
        return sigmas
    if denoise <= 0.0:
        return torch.FloatTensor([])
    n = int(sigmas.shape[0])
    if n <= 1:
        return sigmas
    steps = max(n - 1, 1)
    keep = int(steps * denoise) + 1
    keep = max(1, min(keep, n))
    return sigmas[-(keep):].clone()


class LCSplitSigmasAdvanced:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model_1": (
                    "MODEL",
                    {"tooltip": "1st-pass model (pair with sigmas_1 / high pass)."},
                ),
                "sigmas_1": (
                    "SIGMAS",
                    {
                        "tooltip": "Full 1st-pass schedule (steps set on LC Basic Scheduler).",
                    },
                ),
                "step_swap": (
                    "INT",
                    {
                        "default": 10,
                        "min": 0,
                        "max": 10000,
                        "tooltip": (
                            "Handoff step after denoise. "
                            "If >= total steps on sigmas_1, split is ignored and sigmas_1 runs to completion."
                        ),
                    },
                ),
                "denoise": (
                    "FLOAT",
                    {
                        "default": 1.0,
                        "min": 0.0,
                        "max": 1.0,
                        "step": 0.01,
                        "tooltip": "Denoise applied to curve(s) before the split (1.0 = full).",
                    },
                ),
            },
            "optional": {
                "model_2": (
                    "MODEL",
                    {
                        "tooltip": "2nd-pass model. Optional — falls back to model_1 when empty.",
                    },
                ),
                "sigmas_2": (
                    "SIGMAS",
                    {
                        "tooltip": "2nd-pass schedule. Optional — falls back to sigmas_1 (entire schedule from the first curve).",
                    },
                ),
            },
        }

    RETURN_TYPES = ("SIGMAS", "SIGMAS")
    RETURN_NAMES = ("sigmas_high", "sigmas_low")
    FUNCTION = "split"
    CATEGORY = "LC123/sampling"
    DESCRIPTION = (
        "Split sigma curves at step_swap. "
        "Required: model_1, sigmas_1, step_swap, denoise. "
        "Optional: model_2, sigmas_2 — if sigmas_2 is missing, sigmas_1 is used for the whole schedule. "
        "Outputs: sigmas_high, sigmas_low."
    )

    def split(
        self,
        model_1,
        sigmas_1,
        step_swap,
        denoise=1.0,
        model_2=None,
        sigmas_2=None,
    ):
        # Models are for dual-pass wiring; sigma math uses curves only.
        _ = model_2 if model_2 is not None else model_1

        s1 = _as_1d(sigmas_1)
        if s1 is None or len(s1) == 0:
            raise ValueError("LC Split Sigmas (Advanced): sigmas_1 is empty")

        s2 = _as_1d(sigmas_2) if sigmas_2 is not None else None
        if s2 is None or len(s2) == 0:
            # No second curve → entire schedule from the first
            s2 = s1

        s1 = _apply_denoise(s1, denoise)
        s2 = _apply_denoise(s2, denoise)
        if len(s1) == 0 or len(s2) == 0:
            raise ValueError("LC Split Sigmas (Advanced): denoise left an empty sigma curve")

        n1 = int(s1.shape[0])
        n2 = int(s2.shape[0])
        steps_1 = max(n1 - 1, 0)
        step = int(step_swap)

        if step >= steps_1 or step >= n1:
            return (s1.clone(), s1[-1:].clone())

        step = max(0, min(step, max(n1 - 1, 0), max(n2 - 1, 0)))
        high = s1[: step + 1].clone()
        low = s2[step:].clone()
        return (high, low)


NODE_CLASS_MAPPINGS = {
    "LCSplitSigmasAdvanced": LCSplitSigmasAdvanced,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LCSplitSigmasAdvanced": "LC Split Sigmas (Advanced)",
}
