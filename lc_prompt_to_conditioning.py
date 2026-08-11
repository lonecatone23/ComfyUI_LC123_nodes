"""
LC Prompt to Conditioning
-------------------------
CLIP text encode. Text is socket-only (no on-node text box).
Input socket is named "string".

LC Prompt to Conditioning + Zero
--------------------------------
Same encode, plus a zeroed conditioning output (ConditioningZeroOut style).
"""

import torch


def _encode(clip, string):
    tokens = clip.tokenize(string if string is not None else "")
    if hasattr(clip, "encode_from_tokens_scheduled"):
        cond = clip.encode_from_tokens_scheduled(tokens)
    else:
        cond, pooled = clip.encode_from_tokens(tokens, return_pooled=True)
        if not isinstance(cond, list):
            # older path may return tensor + pooled
            d = {}
            if pooled is not None:
                d["pooled_output"] = pooled
            cond = [[cond, d]]
    return cond


def _zero_out(conditioning):
    """Mirror ComfyUI ConditioningZeroOut."""
    c = []
    for t in conditioning:
        d = t[1].copy()
        if "pooled_output" in d and d["pooled_output"] is not None:
            d["pooled_output"] = torch.zeros_like(d["pooled_output"])
        n = [torch.zeros_like(t[0]), d]
        c.append(n)
    return c


class LCPromptToConditioning:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "clip": ("CLIP", {
                    "tooltip": "CLIP model from a checkpoint / CLIP loader.",
                }),
                "string": ("STRING", {
                    "forceInput": True,
                    "tooltip": "Prompt text — wire from a Positive/Negative or other STRING node.",
                }),
            },
        }

    RETURN_TYPES = ("CONDITIONING",)
    RETURN_NAMES = ("conditioning",)
    FUNCTION = "encode"
    CATEGORY = "LC123/conditioning"
    DESCRIPTION = "Encode a text prompt into CLIP conditioning. String is socket-only."

    def encode(self, clip, string):
        return (_encode(clip, string),)


class LCPromptToConditioningZero:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "clip": ("CLIP", {
                    "tooltip": "CLIP model from a checkpoint / CLIP loader.",
                }),
                "string": ("STRING", {
                    "forceInput": True,
                    "tooltip": "Prompt text — wire from a Positive/Negative or other STRING node.",
                }),
            },
        }

    RETURN_TYPES = ("CONDITIONING", "CONDITIONING")
    RETURN_NAMES = ("conditioning", "zero out")
    FUNCTION = "encode"
    CATEGORY = "LC123/conditioning"
    DESCRIPTION = (
        "Encode a text prompt into CLIP conditioning, and also output a "
        "zeroed copy (same as ConditioningZeroOut) on the second socket."
    )

    def encode(self, clip, string):
        cond = _encode(clip, string)
        return (cond, _zero_out(cond))


NODE_CLASS_MAPPINGS = {
    "LCPromptToConditioning": LCPromptToConditioning,
    "LCPromptToConditioningZero": LCPromptToConditioningZero,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LCPromptToConditioning": "Prompt to Conditioning",
    "LCPromptToConditioningZero": "LC Prompt to Conditioning + Zero",
}
