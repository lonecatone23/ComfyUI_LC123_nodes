"""
LC Sampler Configure
--------------------
Central config nodes for dual-pass / split-sigma and simple single-CFG workflows.

- LC Sampler Configure — full dual-pass widgets
- LC Sampler Configure (pipe) — same + optional pipe in (left) + pipe out (top)
- LC Sampler Configure Pipe Out — unpack pipe → sockets
- LC Sampler Configure Simple — no step_swap / cfg_2
- LC Sampler Configure Simple (pipe) — simple + optional pipe in + pipe out
"""

from __future__ import annotations

import comfy.samplers

PIPE_TYPE = "LC_PIPE"


def _gap():
    return (
        "STRING",
        {
            "default": "",
            "multiline": False,
            "tooltip": "Layout spacer",
        },
    )


def _full_widgets():
    return {
        "required": {
            "total_steps": (
                "INT",
                {
                    "default": 40,
                    "min": 1,
                    "max": 10000,
                    "tooltip": "Total sampling steps for the full schedule.",
                },
            ),
            "step_swap": (
                "INT",
                {
                    "default": 30,
                    "min": 0,
                    "max": 10000,
                    "tooltip": "Step index where the first pass hands off to the second (SplitSigmas step).",
                },
            ),
            "detailer_steps": (
                "INT",
                {
                    "default": 0,
                    "min": 0,
                    "max": 10000,
                    "tooltip": "Steps reserved for a detailer / refiner stage (0 = unused).",
                },
            ),
            "denoise": (
                "FLOAT",
                {
                    "default": 1.0,
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.01,
                    "round": 0.01,
                    "tooltip": "Denoise strength used when building the sigma schedule (1.0 = full).",
                },
            ),
            "_gap1": _gap(),
            "cfg_1": (
                "FLOAT",
                {
                    "default": 8.0,
                    "min": 0.0,
                    "max": 100.0,
                    "step": 0.1,
                    "tooltip": "CFG for the first (high-sigma) pass.",
                },
            ),
            "cfg_2": (
                "FLOAT",
                {
                    "default": 1.0,
                    "min": 0.0,
                    "max": 100.0,
                    "step": 0.1,
                    "tooltip": "CFG for the second (low-sigma) pass.",
                },
            ),
            "_gap2": _gap(),
            "sampler_name": (
                comfy.samplers.KSampler.SAMPLERS,
                {
                    "default": "euler",
                    "tooltip": "Sampler algorithm.",
                },
            ),
            "scheduler": (
                comfy.samplers.KSampler.SCHEDULERS,
                {
                    "default": "normal",
                    "tooltip": "Noise schedule.",
                },
            ),
        },
    }


def _simple_widgets():
    return {
        "required": {
            "total_steps": (
                "INT",
                {
                    "default": 40,
                    "min": 1,
                    "max": 10000,
                    "tooltip": "Total sampling steps.",
                },
            ),
            "detailer_steps": (
                "INT",
                {
                    "default": 0,
                    "min": 0,
                    "max": 10000,
                    "tooltip": "Steps reserved for a detailer / refiner stage (0 = unused).",
                },
            ),
            "denoise": (
                "FLOAT",
                {
                    "default": 1.0,
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.01,
                    "round": 0.01,
                    "tooltip": "Denoise strength (1.0 = full).",
                },
            ),
            "_gap1": _gap(),
            "cfg": (
                "FLOAT",
                {
                    "default": 8.0,
                    "min": 0.0,
                    "max": 100.0,
                    "step": 0.1,
                    "tooltip": "Classifier-free guidance scale.",
                },
            ),
            "_gap2": _gap(),
            "sampler_name": (
                comfy.samplers.KSampler.SAMPLERS,
                {
                    "default": "euler",
                    "tooltip": "Sampler algorithm.",
                },
            ),
            "scheduler": (
                comfy.samplers.KSampler.SCHEDULERS,
                {
                    "default": "normal",
                    "tooltip": "Noise schedule.",
                },
            ),
        },
    }


def _vals_from_full(total_steps, sampler_name, scheduler, **kwargs):
    return (
        int(total_steps),
        float(kwargs.get("cfg_1", 8.0)),
        float(kwargs.get("denoise", 1.0)),
        int(kwargs.get("step_swap", 0)),
        float(kwargs.get("cfg_2", 1.0)),
        sampler_name,
        scheduler,
        int(kwargs.get("detailer_steps", 0)),
    )


def _vals_from_simple(total_steps, sampler_name, scheduler, **kwargs):
    cfg = float(kwargs.get("cfg", 8.0))
    return (
        int(total_steps),
        cfg,
        float(kwargs.get("denoise", 1.0)),
        sampler_name,
        scheduler,
        int(kwargs.get("detailer_steps", 0)),
    )


def _pipe_from_full_vals(vals, base=None):
    """vals order: total_steps, cfg_1, denoise, step_swap, cfg_2, sampler, scheduler, detailer_steps"""
    pipe = dict(base) if isinstance(base, dict) else {}
    pipe["_type"] = PIPE_TYPE
    pipe.update(
        {
            "total_steps": vals[0],
            "cfg_1": vals[1],
            "denoise": vals[2],
            "step_swap": vals[3],
            "cfg_2": vals[4],
            "sampler_name": vals[5],
            "scheduler": vals[6],
            "detailer_steps": vals[7],
        }
    )
    return pipe


def _pipe_from_simple_vals(vals, base=None):
    """vals: total_steps, cfg, denoise, sampler, scheduler, detailer_steps
    Pack into full LC_PIPE with safe dual-pass defaults (step_swap=0, cfg_2=cfg).
    """
    pipe = dict(base) if isinstance(base, dict) else {}
    pipe["_type"] = PIPE_TYPE
    cfg = vals[1]
    pipe.update(
        {
            "total_steps": vals[0],
            "cfg_1": cfg,
            "denoise": vals[2],
            "step_swap": 0,
            "cfg_2": cfg,
            "sampler_name": vals[3],
            "scheduler": vals[4],
            "detailer_steps": vals[5],
        }
    )
    return pipe


class LCSamplerConfigure:
    @classmethod
    def INPUT_TYPES(cls):
        return _full_widgets()

    # Historical socket order for existing graphs
    RETURN_TYPES = (
        "INT",
        "FLOAT",
        "FLOAT",
        "INT",
        "FLOAT",
        comfy.samplers.KSampler.SAMPLERS,
        comfy.samplers.KSampler.SCHEDULERS,
        "INT",
    )
    RETURN_NAMES = (
        "total_steps",
        "cfg_1",
        "denoise",
        "step_swap",
        "cfg_2",
        "sampler_name",
        "scheduler",
        "detailer_steps",
    )
    FUNCTION = "configure"
    CATEGORY = "LC123/sampling"
    DESCRIPTION = (
        "Central dual-pass sampler settings: steps, swap, detailer steps, denoise, "
        "CFGs, sampler, and scheduler."
    )

    def configure(self, total_steps, sampler_name, scheduler, **kwargs):
        return _vals_from_full(total_steps, sampler_name, scheduler, **kwargs)


class LCSamplerConfigurePipeOut:
    """Full dual-pass configure + optional pipe in (left) + pipe out (top)."""

    @classmethod
    def INPUT_TYPES(cls):
        d = _full_widgets()
        d["optional"] = {
            "pipe": (
                PIPE_TYPE,
                {
                    "tooltip": "Optional LC_PIPE in. Sampler keys from this node overwrite matching keys; other pipe fields pass through.",
                },
            ),
        }
        return d

    RETURN_TYPES = (
        PIPE_TYPE,
        "INT",
        "FLOAT",
        "FLOAT",
        "INT",
        "FLOAT",
        comfy.samplers.KSampler.SAMPLERS,
        comfy.samplers.KSampler.SCHEDULERS,
        "INT",
    )
    RETURN_NAMES = (
        "pipe",
        "total_steps",
        "cfg_1",
        "denoise",
        "step_swap",
        "cfg_2",
        "sampler_name",
        "scheduler",
        "detailer_steps",
    )
    FUNCTION = "configure"
    CATEGORY = "LC123/sampling"
    DESCRIPTION = (
        "Dual-pass sampler configure with optional pipe in (left) and pipe out (top). "
        "Widget values write into the pipe; other keys from pipe in are kept."
    )

    def configure(self, total_steps, sampler_name, scheduler, pipe=None, **kwargs):
        vals = _vals_from_full(total_steps, sampler_name, scheduler, **kwargs)
        out_pipe = _pipe_from_full_vals(vals, base=pipe)
        return (out_pipe,) + vals


class LCSamplerConfigurePipe:
    """Unpack-only: pipe in → individual sockets (+ pipe pass-through)."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "pipe": (
                    PIPE_TYPE,
                    {
                        "tooltip": "Pipe from LC Sampler Configure (pipe) or LC Pipe (in/edit).",
                    },
                ),
            },
        }

    RETURN_TYPES = (
        PIPE_TYPE,
        "INT",
        "FLOAT",
        "FLOAT",
        "INT",
        "FLOAT",
        comfy.samplers.KSampler.SAMPLERS,
        comfy.samplers.KSampler.SCHEDULERS,
        "INT",
    )
    RETURN_NAMES = (
        "pipe",
        "total_steps",
        "cfg_1",
        "denoise",
        "step_swap",
        "cfg_2",
        "sampler_name",
        "scheduler",
        "detailer_steps",
    )
    FUNCTION = "unpack"
    CATEGORY = "LC123/sampling"
    DESCRIPTION = (
        "Unpacks an LC_PIPE into sampler configure sockets. "
        "Pipe is passed through for further Get/Set chaining."
    )

    def unpack(self, pipe):
        if not isinstance(pipe, dict):
            pipe = {"_type": PIPE_TYPE}
        return (
            pipe,
            int(pipe.get("total_steps") or 0),
            float(pipe.get("cfg_1") or 0.0),
            float(pipe.get("denoise") if pipe.get("denoise") is not None else 1.0),
            int(pipe.get("step_swap") or 0),
            float(pipe.get("cfg_2") or 0.0),
            pipe.get("sampler_name"),
            pipe.get("scheduler"),
            int(pipe.get("detailer_steps") or 0),
        )


class LCSamplerConfigureSimple:
    """Single-CFG configure — no step_swap / cfg_2."""

    @classmethod
    def INPUT_TYPES(cls):
        return _simple_widgets()

    RETURN_TYPES = (
        "INT",
        "FLOAT",
        "FLOAT",
        comfy.samplers.KSampler.SAMPLERS,
        comfy.samplers.KSampler.SCHEDULERS,
        "INT",
    )
    RETURN_NAMES = (
        "total_steps",
        "cfg",
        "denoise",
        "sampler_name",
        "scheduler",
        "detailer_steps",
    )
    FUNCTION = "configure"
    CATEGORY = "LC123/sampling"
    DESCRIPTION = (
        "Simple sampler settings: steps, detailer steps, denoise, one CFG, sampler, scheduler. "
        "No step_swap / cfg_2 (single-pass friendly)."
    )

    def configure(self, total_steps, sampler_name, scheduler, **kwargs):
        return _vals_from_simple(total_steps, sampler_name, scheduler, **kwargs)


class LCSamplerConfigureSimplePipeOut:
    """Simple configure + optional pipe in + pipe out."""

    @classmethod
    def INPUT_TYPES(cls):
        d = _simple_widgets()
        d["optional"] = {
            "pipe": (
                PIPE_TYPE,
                {
                    "tooltip": "Optional LC_PIPE in. Sampler keys from this node overwrite; other keys pass through.",
                },
            ),
        }
        return d

    RETURN_TYPES = (
        PIPE_TYPE,
        "INT",
        "FLOAT",
        "FLOAT",
        comfy.samplers.KSampler.SAMPLERS,
        comfy.samplers.KSampler.SCHEDULERS,
        "INT",
    )
    RETURN_NAMES = (
        "pipe",
        "total_steps",
        "cfg",
        "denoise",
        "sampler_name",
        "scheduler",
        "detailer_steps",
    )
    FUNCTION = "configure"
    CATEGORY = "LC123/sampling"
    DESCRIPTION = (
        "Simple sampler configure with optional pipe in (left) and pipe out (top). "
        "Packs into LC_PIPE with step_swap=0 and cfg_2=cfg for dual-pass consumers."
    )

    def configure(self, total_steps, sampler_name, scheduler, pipe=None, **kwargs):
        vals = _vals_from_simple(total_steps, sampler_name, scheduler, **kwargs)
        out_pipe = _pipe_from_simple_vals(vals, base=pipe)
        return (out_pipe,) + vals


NODE_CLASS_MAPPINGS = {
    "LCSamplerConfigure": LCSamplerConfigure,
    "LCSamplerConfigurePipeOut": LCSamplerConfigurePipeOut,
    "LCSamplerConfigurePipe": LCSamplerConfigurePipe,
    "LCSamplerConfigureSimple": LCSamplerConfigureSimple,
    "LCSamplerConfigureSimplePipeOut": LCSamplerConfigureSimplePipeOut,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LCSamplerConfigure": "LC Sampler Configure",
    "LCSamplerConfigurePipeOut": "LC Sampler Configure (pipe)",
    "LCSamplerConfigurePipe": "LC Sampler Configure Pipe Out",
    "LCSamplerConfigureSimple": "LC Sampler Configure Simple",
    "LCSamplerConfigureSimplePipeOut": "LC Sampler Configure Simple (pipe)",
}
