"""
LC Sampler Configure
--------------------
Central config node for dual-pass / split-sigma workflows.

LC Sampler Configure (pipe) — same widgets, adds a pipe output at the top.
LC Sampler Configure Pipe — unpack-only (pipe in → individual sockets).
"""

import comfy.samplers

PIPE_TYPE = "LC_SAMPLER_PIPE"


class LCSamplerConfigure:
    @classmethod
    def INPUT_TYPES(cls):
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
                "1st_pass_cfg": (
                    "FLOAT",
                    {
                        "default": 8.0,
                        "min": 0.0,
                        "max": 100.0,
                        "step": 0.1,
                        "tooltip": "CFG for the first (high-sigma) pass.",
                    },
                ),
                "base_denoise": (
                    "FLOAT",
                    {
                        "default": 1.0,
                        "min": 0.0,
                        "max": 1.0,
                        "step": 0.05,
                        "tooltip": "Denoise strength used when building the sigma schedule (1.0 = full).",
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
                "2nd_pass_cfg": (
                    "FLOAT",
                    {
                        "default": 1.0,
                        "min": 0.0,
                        "max": 100.0,
                        "step": 0.1,
                        "tooltip": "CFG for the second (low-sigma) pass.",
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
                        "default": "simple",
                        "tooltip": "Noise schedule.",
                    },
                ),
            },
        }

    RETURN_TYPES = (
        "INT",
        "FLOAT",
        "FLOAT",
        "INT",
        "FLOAT",
        comfy.samplers.KSampler.SAMPLERS,
        comfy.samplers.KSampler.SCHEDULERS,
    )
    RETURN_NAMES = (
        "total_steps",
        "1st_pass_cfg",
        "base_denoise",
        "step_swap",
        "2nd_pass_cfg",
        "sampler_name",
        "scheduler",
    )
    FUNCTION = "configure"
    CATEGORY = "LC123/sampling"
    DESCRIPTION = (
        "Central dual-pass sampler settings: steps, CFGs, denoise, swap point, "
        "sampler and scheduler."
    )

    def configure(self, total_steps, sampler_name, scheduler, **kwargs):
        first_cfg = float(kwargs["1st_pass_cfg"])
        base_denoise = float(kwargs["base_denoise"])
        step_swap = int(kwargs["step_swap"])
        second_cfg = float(kwargs["2nd_pass_cfg"])
        return (
            int(total_steps),
            first_cfg,
            base_denoise,
            step_swap,
            second_cfg,
            sampler_name,
            scheduler,
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
    )
    RETURN_NAMES = (
        "pipe",
        "total_steps",
        "1st_pass_cfg",
        "base_denoise",
        "step_swap",
        "2nd_pass_cfg",
        "sampler_name",
        "scheduler",
    )
    FUNCTION = "configure"
    CATEGORY = "LC123/sampling"
    DESCRIPTION = (
        "Same as LC Sampler Configure, with a pipe output at the top "
        "for Get/Set and LC Sampler Configure Pipe unpack."
    )

    def configure(self, total_steps, sampler_name, scheduler, **kwargs):
        vals = LCSamplerConfigure().configure(
            total_steps, sampler_name, scheduler, **kwargs
        )
        pipe = {
            "_type": PIPE_TYPE,
            "total_steps": vals[0],
            "1st_pass_cfg": vals[1],
            "base_denoise": vals[2],
            "step_swap": vals[3],
            "2nd_pass_cfg": vals[4],
            "sampler_name": vals[5],
            "scheduler": vals[6],
        }
        return (pipe,) + vals


class LCSamplerConfigurePipe:
    """Unpack-only: pipe in → individual sockets (+ pipe pass-through)."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "pipe": (PIPE_TYPE, {
                    "tooltip": "Pipe from LC Sampler Configure (pipe) or LC Pipe Get.",
                }),
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
    )
    RETURN_NAMES = (
        "pipe",
        "total_steps",
        "1st_pass_cfg",
        "base_denoise",
        "step_swap",
        "2nd_pass_cfg",
        "sampler_name",
        "scheduler",
    )
    FUNCTION = "unpack"
    CATEGORY = "LC123/sampling"
    DESCRIPTION = (
        "Unpacks an LC_SAMPLER_PIPE into individual sockets. "
        "Pipe is passed through for further Get/Set chaining."
    )

    def unpack(self, pipe):
        if not isinstance(pipe, dict):
            raise ValueError("Expected an LC_SAMPLER_PIPE dict")
        return (
            pipe,
            int(pipe["total_steps"]),
            float(pipe["1st_pass_cfg"]),
            float(pipe["base_denoise"]),
            int(pipe["step_swap"]),
            float(pipe["2nd_pass_cfg"]),
            pipe["sampler_name"],
            pipe["scheduler"],
        )


NODE_CLASS_MAPPINGS = {
    "LCSamplerConfigure": LCSamplerConfigure,
    "LCSamplerConfigurePipeOut": LCSamplerConfigurePipeOut,
    "LCSamplerConfigurePipe": LCSamplerConfigurePipe,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LCSamplerConfigure": "LC Sampler Configure",
    "LCSamplerConfigurePipeOut": "LC Sampler Configure (pipe)",
    "LCSamplerConfigurePipe": "LC Sampler Configure Pipe",
}
