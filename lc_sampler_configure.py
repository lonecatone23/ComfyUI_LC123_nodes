"""
LC Sampler Configure
--------------------
Central config node for dual-pass / split-sigma workflows.

LC Sampler Configure (pipe) — same widgets, adds a pipe output at the top.
LC Sampler Configure Pipe — unpack-only (pipe in → individual sockets).
"""

import comfy.samplers

PIPE_TYPE = "LC_PIPE"


def _sampler_input_types():
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
            # Visual gap markers — rendered as ~5px spacers by web/lc_sampler_configure.js
            "_gap1": (
                "STRING",
                {
                    "default": "",
                    "multiline": False,
                    "tooltip": "Layout spacer",
                },
            ),
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
            "_gap2": (
                "STRING",
                {
                    "default": "",
                    "multiline": False,
                    "tooltip": "Layout spacer",
                },
            ),
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


class LCSamplerConfigure:
    @classmethod
    def INPUT_TYPES(cls):
        return _sampler_input_types()

    # Keep historical socket order for existing graphs; detailer_steps appended last.
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
        step_swap = int(kwargs.get("step_swap", 0))
        detailer_steps = int(kwargs.get("detailer_steps", 0))
        denoise = float(kwargs.get("denoise", 1.0))
        cfg_1 = float(kwargs.get("cfg_1", 8.0))
        cfg_2 = float(kwargs.get("cfg_2", 1.0))
        # gaps ignored
        return (
            int(total_steps),
            cfg_1,
            denoise,
            step_swap,
            cfg_2,
            sampler_name,
            scheduler,
            detailer_steps,
        )


class LCSamplerConfigurePipeOut:
    """Same as LC Sampler Configure, plus pipe as the top output."""

    @classmethod
    def INPUT_TYPES(cls):
        return LCSamplerConfigure.INPUT_TYPES()

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
        "Same as LC Sampler Configure, with a pipe output at the top "
        "for Get/Set and LC Sampler Configure Pipe Out unpack."
    )

    def configure(self, total_steps, sampler_name, scheduler, **kwargs):
        vals = LCSamplerConfigure().configure(
            total_steps, sampler_name, scheduler, **kwargs
        )
        pipe = {
            "_type": PIPE_TYPE,
            "total_steps": vals[0],
            "cfg_1": vals[1],
            "denoise": vals[2],
            "step_swap": vals[3],
            "cfg_2": vals[4],
            "sampler_name": vals[5],
            "scheduler": vals[6],
            "detailer_steps": vals[7],
        }
        return (pipe,) + vals


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


NODE_CLASS_MAPPINGS = {
    "LCSamplerConfigure": LCSamplerConfigure,
    "LCSamplerConfigurePipeOut": LCSamplerConfigurePipeOut,
    "LCSamplerConfigurePipe": LCSamplerConfigurePipe,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LCSamplerConfigure": "LC Sampler Configure",
    "LCSamplerConfigurePipeOut": "LC Sampler Configure (pipe)",
    "LCSamplerConfigurePipe": "LC Sampler Configure Pipe Out",
}
