"""
LC MiniMax H3 Pipe
------------------
Pack / unpack MiniMax H3 reference media.

Matches MiniMaxH3ReferenceToVideo (Comfy-Org / comfy-core):
  ref_image_0..8, ref_video_0..2, ref_video_audio_0..2, ref_audio_0..2
Prompt tags are 1-based: ref_image_0 = <Picture 1>.
In and Out use the same fixed socket list (no autogrow).

Pipe in accepts LC_H3_PIPE (full merge) or LC_PIPE from Aspect Ratio Simplifier
(width + height only — nothing else is copied).
"""

from __future__ import annotations

PIPE_TYPE = "LC_H3_PIPE"
LC_PIPE = "LC_PIPE"

IMAGE_MAX = 9
VIDEO_MAX = 3
AUDIO_MAX = 3

# Only these keys are taken from an Aspect Ratio / LC_PIPE. Never models, image, mask, latent.
ARS_TAKE = ("width", "height")


def _optional_slot(key, kind, label):
    if kind == "INT":
        specs = {
            "width": dict(default=1344, min=16, max=16384, step=8, tooltip="Video width. ARS pipe on pipe fills this."),
            "height": dict(default=768, min=16, max=16384, step=8, tooltip="Video height."),
            "length": dict(default=124, min=5, max=3600, step=1, tooltip="Frame count. H3 is 24 fps; 124 ≈ 5s, 244 ≈ 10s."),
            "frame_rate": dict(default=24, min=1, max=120, step=1, tooltip="Frame rate. MiniMax H3 is trained at 24."),
        }
        opt = dict(specs.get(key, dict(default=0, min=0, max=0xFFFFFFFF)))
        opt["forceInput"] = True
        return (kind, opt)
    tooltips = {
        "fl2va_model": "First-last-frame to video UNET.",
        "fl2va_clip": "CLIP for FL2VA (MiniMaxH3ImageToVideo).",
        "ref2va_model": "Reference-to-video UNET.",
        "ref2va_clip": "CLIP for REF2VA (MiniMaxH3ReferenceToVideo).",
        "video_vae": "Video VAE (MiniMax vae).",
        "audio_vae": "Audio VAE (MiniMax audio_vae).",
    }
    return (kind, {"tooltip": tooltips.get(key, label)})


class H3PipeAccept(str):
    """Connect LC_H3_PIPE or LC_PIPE (Aspect Ratio Simplifier / LC Pipe)."""

    def __ne__(self, other):
        o = str(other) if other is not None else ""
        return o not in {PIPE_TYPE, LC_PIPE, "*"}


h3_pipe_in = H3PipeAccept(PIPE_TYPE)


def _empty():
    return {"_type": PIPE_TYPE}


def _is_provided(val):
    return val is not None


def _collect(kwargs, prefix, count):
    out = {}
    for i in range(count):
        key = f"{prefix}{i}"
        val = kwargs.get(key)
        if _is_provided(val):
            out[key] = val
    return out


HEAD_SLOTS = [
    ("fl2va_model", "MODEL", "fl2va_model"),
    ("fl2va_clip", "CLIP", "fl2va_clip"),
    ("ref2va_model", "MODEL", "ref2va_model"),
    ("ref2va_clip", "CLIP", "ref2va_clip"),
    ("video_vae", "VAE", "video_vae"),
    ("audio_vae", "VAE", "audio_vae"),
]

SIZE_SLOTS = [
    ("width", "INT", "width"),
    ("height", "INT", "height"),
    ("length", "INT", "length"),
    ("frame_rate", "INT", "frame_rate"),
]


def _slot_keys():
    keys = list(HEAD_SLOTS) + list(SIZE_SLOTS)
    for i in range(IMAGE_MAX):
        keys.append((f"ref_image_{i}", "IMAGE", f"ref_image_{i}"))
    for i in range(VIDEO_MAX):
        keys.append((f"ref_video_{i}", "IMAGE", f"ref_video_{i}"))
    for i in range(VIDEO_MAX):
        keys.append((f"ref_video_audio_{i}", "AUDIO", f"ref_video_audio_{i}"))
    for i in range(AUDIO_MAX):
        keys.append((f"ref_audio_{i}", "AUDIO", f"ref_audio_{i}"))
    return keys


def _merge_incoming(pipe):
    """H3 pipe → copy H3 fields. LC_PIPE (ARS) → width/height only."""
    base = _empty()
    if not isinstance(pipe, dict):
        return base
    t = pipe.get("_type")
    if t == PIPE_TYPE:
        for key, _kind, _label in _slot_keys():
            if key in pipe and pipe[key] is not None:
                base[key] = pipe[key]
        for group in ("ref_images", "ref_videos", "ref_video_audios", "ref_audios"):
            if isinstance(pipe.get(group), dict):
                base[group] = dict(pipe[group])
        # old single clip → both, if the new sockets were empty
        old = pipe.get("clip")
        if old is not None:
            base.setdefault("fl2va_clip", old)
            base.setdefault("ref2va_clip", old)
        return base
    for k in ARS_TAKE:
        if pipe.get(k) is not None:
            base[k] = pipe[k]
    return base


class LCMiniMaxH3Pipe:
    @classmethod
    def INPUT_TYPES(cls):
        optional = {
            "pipe": (h3_pipe_in, {
                "tooltip": "H3 pipe to merge, or Aspect Ratio Simplifier / LC Pipe (copies width + height only).",
            }),
        }
        for key, kind, label in _slot_keys():
            optional[key] = _optional_slot(key, kind, label)
        return {"required": {}, "optional": optional}

    RETURN_TYPES = (PIPE_TYPE,)
    RETURN_NAMES = ("pipe",)
    FUNCTION = "pack"
    CATEGORY = "LC123/pipe"
    DESCRIPTION = (
        "MiniMax H3 pipe in / edit. Same sockets as Pipe Out (all slots always shown, no autogrow). "
        "Pipe accepts an H3 pipe (full merge) or Aspect Ratio Simplifier / LC Pipe (width + height only)."
    )

    def pack(self, pipe=None, **kwargs):
        base = _merge_incoming(pipe)
        for key, _kind, _label in HEAD_SLOTS + SIZE_SLOTS:
            val = kwargs.get(key)
            if _is_provided(val):
                base[key] = val
        images = _collect(kwargs, "ref_image_", IMAGE_MAX)
        videos = _collect(kwargs, "ref_video_", VIDEO_MAX)
        video_audios = _collect(kwargs, "ref_video_audio_", VIDEO_MAX)
        audios = _collect(kwargs, "ref_audio_", AUDIO_MAX)
        if images:
            base["ref_images"] = {**base.get("ref_images", {}), **images}
            for k, v in images.items():
                base[k] = v
        if videos:
            base["ref_videos"] = {**base.get("ref_videos", {}), **videos}
            for k, v in videos.items():
                base[k] = v
        if video_audios:
            base["ref_video_audios"] = {**base.get("ref_video_audios", {}), **video_audios}
            for k, v in video_audios.items():
                base[k] = v
        if audios:
            base["ref_audios"] = {**base.get("ref_audios", {}), **audios}
            for k, v in audios.items():
                base[k] = v
        return (base,)


class LCMiniMaxH3PipeOut:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "pipe": (PIPE_TYPE, {
                    "tooltip": "LC MiniMax H3 Pipe.",
                }),
            },
        }

    RETURN_TYPES = (PIPE_TYPE,) + tuple(kind for _k, kind, _l in _slot_keys())
    RETURN_NAMES = ("pipe",) + tuple(label for _k, _kind, label in _slot_keys())
    FUNCTION = "unpack"
    CATEGORY = "LC123/pipe"
    DESCRIPTION = (
        "Unpacks an LC MiniMax H3 pipe. ref_image_0 = <Picture 1>. "
        "width / height come from the H3 pipe or from an Aspect Ratio Simplifier pipe merged upstream."
    )

    def unpack(self, pipe):
        if not isinstance(pipe, dict):
            pipe = _empty()
        values = tuple(pipe.get(key) for key, _kind, _label in _slot_keys())
        return (pipe,) + values


NODE_CLASS_MAPPINGS = {
    "LCMiniMaxH3Pipe": LCMiniMaxH3Pipe,
    "LCMiniMaxH3PipeOut": LCMiniMaxH3PipeOut,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LCMiniMaxH3Pipe": "LC MiniMax H3 Pipe",
    "LCMiniMaxH3PipeOut": "LC MiniMax H3 Pipe Out",
}
