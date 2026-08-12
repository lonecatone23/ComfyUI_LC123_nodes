"""
LC Pipe In / Out / Edit
----------------------
General workflow pipe. Get/Set friendly (KJ Set/Get).

Slots (top → bottom):
  Model 1, Clip 1, VAE 1,
  Model 2, Clip 2, VAE 2,
  Width, Height, Latent, Batch,
  Positive prompt, Positive conditioning,
  Negative prompt, Negative conditioning,
  Seed,
  total_steps, cfg_1, denoise, step_swap, cfg_2, sampler_name, scheduler
"""

import comfy.samplers

PIPE_TYPE = "LC_PIPE"

SLOT_ORDER = [
    ("model_1", "MODEL"),
    ("clip_1", "CLIP"),
    ("vae_1", "VAE"),
    ("model_2", "MODEL"),
    ("clip_2", "CLIP"),
    ("vae_2", "VAE"),
    ("width", "INT"),
    ("height", "INT"),
    ("latent", "LATENT"),
    ("batch", "INT"),
    ("positive_prompt", "STRING"),
    ("positive", "CONDITIONING"),
    ("negative_prompt", "STRING"),
    ("negative", "CONDITIONING"),
    ("seed", "INT"),
    ("total_steps", "INT"),
    ("cfg_1", "FLOAT"),
    ("denoise", "FLOAT"),
    ("step_swap", "INT"),
    ("cfg_2", "FLOAT"),
    ("sampler_name", "SAMPLER_NAME"),
    ("scheduler", "SCHEDULER_NAME"),
]

DISPLAY = {
    "model_1": "Model 1",
    "clip_1": "Clip 1",
    "vae_1": "VAE 1",
    "model_2": "Model 2",
    "clip_2": "Clip 2",
    "vae_2": "VAE 2",
    "width": "Width",
    "height": "Height",
    "latent": "Latent",
    "batch": "Batch",
    "positive_prompt": "Positive prompt",
    "positive": "Positive conditioning",
    "negative_prompt": "Negative prompt",
    "negative": "Negative conditioning",
    "seed": "Seed",
    "total_steps": "total_steps",
    "cfg_1": "cfg_1",
    "denoise": "denoise",
    "step_swap": "step_swap",
    "cfg_2": "cfg_2",
    "sampler_name": "sampler_name",
    "scheduler": "scheduler",
}


def _rtype(kind):
    if kind == "SAMPLER_NAME":
        return comfy.samplers.KSampler.SAMPLERS
    if kind == "SCHEDULER_NAME":
        return comfy.samplers.KSampler.SCHEDULERS
    return kind


def _empty():
    return {"_type": PIPE_TYPE}


def _slot_input(key, kind):
    """Optional input — forceInput so unconnected slots stay unset."""
    label = DISPLAY.get(key, key)
    if kind == "SAMPLER_NAME":
        return (comfy.samplers.KSampler.SAMPLERS, {
            "tooltip": label,
            "forceInput": True,
        })
    if kind == "SCHEDULER_NAME":
        return (comfy.samplers.KSampler.SCHEDULERS, {
            "tooltip": label,
            "forceInput": True,
        })
    if kind == "STRING":
        return ("STRING", {
            "default": "",
            "multiline": True,
            "tooltip": label,
            "forceInput": True,
        })
    if kind == "INT":
        return ("INT", {
            "default": 0,
            "min": -1,
            "max": 0xFFFFFFFFFFFFFFFF,
            "tooltip": label,
            "forceInput": True,
        })
    if kind == "FLOAT":
        return ("FLOAT", {
            "default": 0.0,
            "min": 0.0,
            "max": 100.0,
            "step": 0.05,
            "tooltip": label,
            "forceInput": True,
        })
    return (kind, {"tooltip": label})


def _is_provided(val):
    if val is None:
        return False
    if isinstance(val, str) and val == "":
        return False
    return True


class LCPipeIn:
    @classmethod
    def INPUT_TYPES(cls):
        optional = {key: _slot_input(key, kind) for key, kind in SLOT_ORDER}
        return {"required": {}, "optional": optional}

    RETURN_TYPES = (PIPE_TYPE,)
    RETURN_NAMES = ("pipe",)
    FUNCTION = "pack"
    CATEGORY = "LC123/pipe"
    DESCRIPTION = (
        "Packs workflow values into an LC_PIPE. "
        "Connect any subset. Works with KJ Set/Get (and any type-agnostic Get/Set)."
    )

    def pack(self, **kwargs):
        pipe = _empty()
        for key, _kind in SLOT_ORDER:
            val = kwargs.get(key)
            if _is_provided(val):
                pipe[key] = val
        return (pipe,)


class LCPipeOut:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "pipe": (PIPE_TYPE, {
                    "tooltip": "LC_PIPE from Pipe In, Pipe Edit, or KJ Get.",
                }),
            },
        }

    RETURN_TYPES = (PIPE_TYPE,) + tuple(_rtype(kind) for _, kind in SLOT_ORDER)
    RETURN_NAMES = ("pipe",) + tuple(DISPLAY[k] for k, _ in SLOT_ORDER)
    FUNCTION = "unpack"
    CATEGORY = "LC123/pipe"
    DESCRIPTION = (
        "Expands an LC_PIPE into individual sockets (top → bottom). "
        "Pipe is passed through for Get/Set chaining."
    )

    def unpack(self, pipe):
        if not isinstance(pipe, dict):
            pipe = _empty()
        values = tuple(pipe.get(key) for key, _ in SLOT_ORDER)
        return (pipe,) + values


class LCPipeEdit:
    @classmethod
    def INPUT_TYPES(cls):
        optional = {
            "pipe": (PIPE_TYPE, {
                "tooltip": "Existing pipe to modify (optional).",
            }),
        }
        optional.update({key: _slot_input(key, kind) for key, kind in SLOT_ORDER})
        return {"required": {}, "optional": optional}

    RETURN_TYPES = (PIPE_TYPE,)
    RETURN_NAMES = ("pipe",)
    FUNCTION = "edit"
    CATEGORY = "LC123/pipe"
    DESCRIPTION = (
        "Merges overrides into an LC_PIPE. Only provided values replace "
        "existing entries. Works with KJ Set/Get (and any type-agnostic Get/Set)."
    )

    def edit(self, pipe=None, **kwargs):
        base = dict(pipe) if isinstance(pipe, dict) else _empty()
        base["_type"] = PIPE_TYPE
        for key, _kind in SLOT_ORDER:
            val = kwargs.get(key)
            if _is_provided(val):
                base[key] = val
        return (base,)


NODE_CLASS_MAPPINGS = {
    "LCPipeIn": LCPipeIn,
    "LCPipeOut": LCPipeOut,
    "LCPipeEdit": LCPipeEdit,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LCPipeIn": "LC Pipe In",
    "LCPipeOut": "LC Pipe Out",
    "LCPipeEdit": "LC Pipe Edit",
}
