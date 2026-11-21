"""
LC Add Weights
--------------
Puts weights back on a prompt that another node rewrote (LC Vision Smart Prompt Batch): weight the base prompt once
in an LC Weighted Prompt, every variant gets the weights back on the phrases it still has.

weights: the `weights` output of an LC Weighted Prompt (JSON), or typed by hand as (parka:1.3), (fur hood:1.2).

With clip + model wired it applies the weights the way LC Weighted Prompt does, on the final text of each variant:
Krea 2 and MOSS get them inside the model (model out), other models get (phrase:weight) in the prompt. Nothing may
be added to the prompt after this node (Krea 2 places a weight by its distance from the end of the prompt).
Without clip + model: prompt out with (phrase:weight) written in, for an LC Weighted Prompt or encoder after it.
"""

from __future__ import annotations

import json
import re

from .lc_weighted_prompt import LCWeightedPrompt, _is_krea2, _is_moss, _phrases, _spans, weighted_text

NODE_NAME = "LCAddWeights"
_WRITTEN = re.compile(r"\(([^():]+?):\s*(-?\d+(?:\.\d+)?)\)")


def read_weights(weights: str) -> list:
    """(phrase, weight) pairs from JSON rows or from (phrase:weight) text."""
    s = (weights or "").strip()
    if s.startswith("["):
        return _phrases(s)
    out = []
    for m in _WRITTEN.finditer(s):
        t, w = m.group(1).strip(), float(m.group(2))
        if t and abs(w - 1.0) > 1e-6:
            out.append((t, w))
    return out


def unwrite(text: str) -> tuple:
    """The prompt with every (phrase:weight) taken out, plus the (phrase, weight) pairs found."""
    found = []

    def take(m):
        t, w = m.group(1), float(m.group(2))
        if t.strip() and abs(w - 1.0) > 1e-6 and all(t.strip().lower() != p.lower() for p, _ in found):
            found.append((t.strip(), w))
        return t

    return _WRITTEN.sub(take, text or ""), found


class LCAddWeights:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt": ("STRING", {"forceInput": True,
                                      "tooltip": "The prompt to weight, e.g. the prompt output of LC Vision Smart Prompt "
                                                 "Batch (every variant gets the weights)."}),
                "weights": ("STRING", {"forceInput": True,
                                       "tooltip": "The weights output of an LC Weighted Prompt, or text like "
                                                  "(parka:1.3), (fur hood:1.2)."}),
            },
            "optional": {
                "clip": ("CLIP", {"tooltip": "Wire clip + model and the weights are applied here, on each variant's final "
                                             "text (Krea 2 and MOSS inside the model)."}),
                "model": ("MODEL", {"tooltip": "The model to carry the weights (Krea 2, MOSS). Use the model out for "
                                               "sampling."}),
                "strength": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 2.0, "step": 0.05,
                                       "tooltip": "Scales every weight, like strength on LC Weighted Prompt."}),
            },
        }

    RETURN_TYPES = ("MODEL", "STRING", "STRING")
    RETURN_NAMES = ("model", "prompt", "weighted_prompt")
    OUTPUT_TOOLTIPS = ("The model with the weights in it (Krea 2, MOSS). Sample with this one.",
                       "The prompt, clean, for the encoder. With no clip + model wired it has (phrase:weight) written in.",
                       "The prompt with (phrase:weight) written in, for metadata or a CLIP encoder.")
    FUNCTION = "run"
    CATEGORY = "LC123/conditioning"
    DESCRIPTION = ("Puts weights back on a prompt that another node rewrote (LC Vision Smart Prompt Batch): prompt in, "
                   "weights in. With clip + model it applies them like LC Weighted Prompt, on every variant.")

    def run(self, prompt, weights, clip=None, model=None, strength=1.0):
        text, written = unwrite(str(prompt or ""))
        phrases = read_weights(weights)
        have = {p.lower() for p, _ in phrases}
        phrases = [(t, w) for t, w in written if t.lower() not in have] + phrases
        missing = [t for t, _ in phrases if not _spans(text, t)]
        if missing:
            print(f"[LC Add Weights] {len(missing)} weight(s) not in this prompt: {', '.join(missing)}")
        wtext = weighted_text(text, phrases)
        if clip is None or model is None:
            return (model, wtext, wtext)
        if not (_is_krea2(model) or _is_moss(model)):  # CLIP models: the weights travel in the text
            return (model, wtext, wtext)
        rows = json.dumps([{"text": t, "w": w} for t, w in phrases], ensure_ascii=False)
        out = LCWeightedPrompt().encode(clip, text, strength, rows, model=model)
        return (out["result"][0], text, wtext)


NODE_CLASS_MAPPINGS = {NODE_NAME: LCAddWeights}
NODE_DISPLAY_NAME_MAPPINGS = {NODE_NAME: "LC Add Weights ⚖️"}
