"""
LC Weighted Prompt
------------------
A text encoder with a weight per word. The prompt is typed in the node's box, or comes in on the `prompt` socket
and lands in the box; the JS face (web/lc_weighted_prompt.js) shows it as words: click a word (shift-click for a
phrase), move the slider. Above 1 the word gets more weight, below 1 less, below 0 it is taken out.

Block (with the prompt socket wired): on change = the box takes the incoming prompt when it changes, and your edit
in the box holds until then; always = the box holds, and a new incoming prompt stops the run here so you can look
and edit, then Run carries on with the same seeds (web/lc_continue.js); never = the incoming prompt always comes
through. The prompt output is the one used, so an encoder wired from it encodes your edit.

Krea 2: its Qwen3-VL encoder ignores ComfyUI's (word:1.2), so the weight is applied inside the model's attention
through the block attn1_patch: a weight above 1 adds a bias to that word's attention logits (more of the picture
reads it), below 1 scales the word's attention value (less of it; a negative value takes it out). A word is placed
by its distance from the END of the text tokens, measured at run time: every Krea 2 encoder (plain, image reference
edit, identity edit) ends with the prompt and the same template ending, so the node works before any of them. The log-odds
emphasis follows capitan01R's Krea2T-Enhancer (MIT); emphasis on the logits and removal on the value is the split
Kijai's Krea2 Prompt Weight uses. Only the positive (cond) rows are touched, so a negative prompt is unaffected.

SDXL / Illustrious / Pony and other CLIP models: the same weights written as ComfyUI's own (phrase:weight).

The weights live in the hidden `weights` STRING widget as JSON: [{"text": "fur-lined hood", "w": 1.5}, ...],
matched to the prompt by words (any case), so a new prompt keeps the weights of every phrase still in it.
"""

from __future__ import annotations

import json
import math
import re
import time

import nodes
import torch

NODE_NAME = "LCWeightedPrompt"
EMPHASIS = 2.0  # attention logit bias per unit of log weight: (w = 2) -> +1.39 on every block
BLOCK_MODES = ["on change", "always", "never"]


def _phrases(weights: str) -> list:
    try:
        rows = json.loads(weights or "[]")
    except (TypeError, ValueError):
        return []
    out = []
    for r in rows if isinstance(rows, list) else []:
        try:
            text, w = str(r.get("text") or "").strip(), float(r.get("w", 1.0))
        except (AttributeError, TypeError, ValueError):
            continue
        if text and abs(w - 1.0) > 1e-6:
            out.append((text, w))
    return out


def _spans(text: str, phrase: str) -> list:
    """(start, end) of every whole-word, any-case match of `phrase` in `text`, spaces matched loosely."""
    words = [re.escape(w) for w in phrase.split()]
    if not words:
        return []
    pat = re.compile(r"(?<![\w-])" + r"\s+".join(words) + r"(?![\w-])", re.I)
    return [m.span() for m in pat.finditer(text)]


def weighted_text(text: str, phrases: list) -> str:
    """The prompt with ComfyUI's (phrase:weight) around every weighted phrase (longest phrase first, no overlaps)."""
    marks = []
    for phrase, w in sorted(phrases, key=lambda p: -len(p[0])):
        for s, e in _spans(text, phrase):
            if all(e <= a or s >= b for a, b, _ in marks):
                marks.append((s, e, w))
    out, pos = [], 0
    for s, e, w in sorted(marks):
        out.append(text[pos:s] + f"({text[s:e]}:{w:g})")
        pos = e
    return "".join(out) + text[pos:]


def _is_krea2(model) -> bool:
    try:
        dm = model.get_model_object("diffusion_model")
    except Exception:
        return False
    return all(hasattr(dm, a) for a in ("txtfusion", "blocks", "txtmlp"))


def _is_moss(model) -> bool:
    try:
        dm = model.get_model_object("diffusion_model")
    except Exception:
        return False
    return all(hasattr(dm, a) for a in ("text_embedder", "layers", "shared_block_modulation"))


def _ids(clip, text: str) -> list:
    tok = clip.tokenize(text)
    return [t[0] for t in tok[next(iter(tok))][0]]


def _core(ids: list, empty: list) -> tuple:
    """The prompt's own tokens inside the chat template: (start, end) after stripping what an empty prompt has too."""
    a = 0
    while a < min(len(ids), len(empty)) and ids[a] == empty[a]:
        a += 1
    b = 0
    while b < min(len(ids), len(empty)) - a and ids[-1 - b] == empty[-1 - b]:
        b += 1
    return a, len(ids) - b


def _krea2_positions(clip, text: str, phrases: list, cond_len: int, ids: list) -> list:
    """[(conditioning position, weight)] for every token of every weighted phrase. A phrase's tokens are found by
    counting the tokens of the text before it and through it (robust to how the tokenizer merges in context)."""
    empty = _ids(clip, "")
    start, _ = _core(ids, empty)
    visible = len(ids) - cond_len  # the encoder drops the template's lead-in from the conditioning
    out = {}
    for phrase, w in phrases:
        for s, e in _spans(text, phrase):
            # the space before a word belongs to the word's own token (" umbrella"): count the text before without it
            before = text[:s].rstrip()
            a = _core(_ids(clip, before), empty) if before else (0, 0)
            b = _core(_ids(clip, text[:e]), empty)
            n_before, n_through = a[1] - a[0], b[1] - b[0]
            for k in range(start + n_before, start + n_through):
                cp = k - visible
                if 0 <= cp < cond_len:
                    out[cp] = w  # a later (shorter, inner) phrase wins for its own tokens
    return sorted(out.items())


def _attn_patch(offsets: list, strength: float, min_len: int, state: dict):
    """Krea 2 block attn1_patch: logit bias on emphasised text keys, value scale on de-emphasised ones (cond rows only).
    offsets = [(tokens from the end of the text, weight)]; the text length comes from Krea 2's img_slice, or from
    the txtmlp wrapper when another pack's forward does not set it."""
    bias_off = [(d, EMPHASIS * strength * math.log(w)) for d, w in offsets if w > 1.0]
    val_off = [(d, 1.0 + strength * (w - 1.0)) for d, w in offsets if w < 1.0]

    def patch(q, k, v, pe=None, attn_mask=None, extra_options=None):
        opts = extra_options or {}
        if not opts.get("lc_weighted_prompt"):  # only inside the main blocks our wrapper marks (not the text fusion layers)
            return {}
        sl = opts.get("img_slice")
        txt = int(sl[0]) if isinstance(sl, (list, tuple)) and sl else int(state.get("txtlen") or 0)
        if txt < min_len:  # not this prompt: a shorter one (a detailer's) on the same model
            return {}
        if not state.get("told"):
            state["told"] = True
            print(f"[LC Weighted Prompt] weights acting in the sampler (text length {txt})")
        batch = q.shape[0]
        cu = opts.get("cond_or_uncond") or [0]
        per = max(1, batch // max(1, len(cu)))
        rows = torch.tensor([cu[i // per] == 0 if i // per < len(cu) else True for i in range(batch)], device=q.device)
        if not bool(rows.any()):
            return {}
        out = {}
        if val_off:
            v = v.clone()
            for d, f in val_off:
                if 0 <= txt - d < v.shape[2]:
                    v[rows, :, txt - d] = v[rows, :, txt - d] * f
            out["v"] = v
        if bias_off:
            bias = torch.zeros(batch, 1, 1, k.shape[2], device=q.device, dtype=q.dtype)
            for d, b in bias_off:
                if 0 <= txt - d < k.shape[2]:
                    bias[rows, 0, 0, txt - d] = b
            if attn_mask is not None:
                bias = bias + attn_mask
            out["attn_mask"] = bias
        return out

    return patch


def _txt_probe(orig, state: dict):
    """txtmlp runs on the text tokens right before they are joined to the picture's: remember their count."""
    def forward(x, *args, **kwargs):
        y = orig(x, *args, **kwargs)
        try:
            state["txtlen"] = int(y.shape[1])
        except Exception:
            pass
        return y
    return forward


def _block_forward(orig, index: int, patch):
    """A main block's attention forward that runs Krea 2's own forward with our patch and its block number in the
    options. Attached per block on our copy of the model, so it works even when another pack replaces Krea 2's
    forward pass with one that never sets block_index (ComfyUI-Krea2Moodboard does, for the whole server), which
    silently switches every attn1_patch off."""
    def forward(x, freqs=None, mask=None, transformer_options={}):
        to = dict(transformer_options)
        to.setdefault("block_index", index)
        patches = dict(to.get("patches") or {})
        patches["attn1_patch"] = list(patches.get("attn1_patch", [])) + [patch]
        to["patches"] = patches
        to["lc_weighted_prompt"] = True
        return orig(x, freqs, mask, transformer_options=to)
    return forward


def _shown(clip, tok, cond_len: int, positions: list) -> str:
    """'word':weight for the log, read back from the tokens."""
    ids = [t[0] for t in tok[next(iter(tok))][0]]
    vis = len(ids) - cond_len
    try:
        words = [clip.tokenizer.untokenize([(ids[p + vis], 1.0)]) for p, _ in positions]
        return ", ".join(f"{str(w[0][1]) if w else '?'!r}:{wt:g}" for w, (_, wt) in zip(words, positions))
    except Exception:
        return ", ".join(f"{p}:{w:g}" for p, w in positions)


# ---------------------------------------------------------------- MOSS Image
# One stream of 42 layers over [picture tokens | text tokens | (references)]. There is no attention patch hook, so
# the weights ride ComfyUI's per-model attention override: a DIFFUSION_MODEL wrapper notes where the text sits for
# this call, the override reweights the text keys / values in the main layers (not the two text-only layers).
MOSS_KEY = "lc_weighted_prompt_moss"


def _moss_wrapper(executor, x, timestep, context, transformer_options, *args, **kwargs):
    to = dict(transformer_options)
    to[MOSS_KEY] = (int(x.shape[-2]) * int(x.shape[-1]), int(context.shape[1]))  # (picture tokens, text tokens)
    return executor(x, timestep, context, to, *args, **kwargs)


def _moss_override(current, positions: list, strength: float, cond_len: int, state: dict):
    """positions = [(conditioning position, weight)]. A weight above 1 adds a logit bias on that token's key (more of
    the picture reads it), below 1 scales its value (less of it; below 0 it is taken out). Cond rows only."""
    bias_at = [(p, EMPHASIS * strength * math.log(w)) for p, w in positions if w > 1.0]
    val_at = [(p, 1.0 + strength * (w - 1.0)) for p, w in positions if w < 1.0]

    def override(func, q, k, v, heads, *args, **kwargs):
        call = (lambda *a, **kw: current(func, *a, **kw)) if current is not None else func
        to = kwargs.get("transformer_options") or {}
        info = to.get(MOSS_KEY)
        if not info or to.get("block_type") != "single" or "block_index" not in to or kwargs.get("skip_reshape"):
            return call(q, k, v, heads, *args, **kwargs)
        pic, txt = info
        # this prompt only (a detailer's shorter prompt on the same model is left alone); a batch that pads the
        # conditioning by repeating it carries the prompt several times: weight every copy
        if txt < cond_len or txt % cond_len or q.shape[1] < pic + txt:
            return call(q, k, v, heads, *args, **kwargs)
        batch = q.shape[0]
        cu = to.get("cond_or_uncond") or [0]
        per = max(1, batch // max(1, len(cu)))
        rows = torch.tensor([cu[i // per] == 0 if i // per < len(cu) else True for i in range(batch)], device=q.device)
        if not bool(rows.any()):
            return call(q, k, v, heads, *args, **kwargs)
        if not state.get("told"):
            state["told"] = True
            print(f"[LC Weighted Prompt] MOSS: weights acting in the sampler (text length {txt})")
        starts = [pic + c * cond_len for c in range(txt // cond_len)]
        if val_at:
            v = v.clone()
            for p, f in val_at:
                for s in starts:
                    v[rows, s + p] = v[rows, s + p] * f
        if bias_at:
            bias = torch.zeros(batch, 1, 1, k.shape[1], device=q.device, dtype=q.dtype)
            for p, b in bias_at:
                for s in starts:
                    bias[rows, 0, 0, s + p] = b
            old = kwargs.get("mask")
            kwargs["mask"] = bias if old is None else bias + old
        return call(q, k, v, heads, *args, **kwargs)

    # no container_function: ComfyUI's hook hands this override plain tensors
    return override


def _moss_patch(model, positions: list, strength: float, cond_len: int):
    import comfy.patcher_extension

    model = model.clone()
    to = dict(model.model_options.get("transformer_options") or {})
    to["optimized_attention_override"] = _moss_override(to.get("optimized_attention_override"), positions, strength, cond_len, {})
    model.model_options["transformer_options"] = to
    model.add_wrapper_with_key(comfy.patcher_extension.WrappersMP.DIFFUSION_MODEL, MOSS_KEY, _moss_wrapper)
    return model


class LCWeightedPrompt:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "clip": ("CLIP", {"tooltip": "The text encoder (Krea 2, MOSS Image, SDXL, Illustrious, Pony ...)."}),
                "text": ("STRING", {"multiline": True, "default": "", "tooltip": "The prompt. Its words show below, ready to weight."}),
                "strength": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 3.0, "step": 0.05,
                                       "tooltip": "How strongly every weight acts. Lower it if a weighted word starts to break the picture up."}),
                "weights": ("STRING", {"default": "[]", "tooltip": "The word weights (set on the node)."}),
            },
            "optional": {
                "model": ("MODEL", {"tooltip": "Krea 2 and MOSS Image need the model: their weights work inside the model. Other models don't."}),
                "edit_conditioning": ("CONDITIONING", {"tooltip": "Not needed: the weights find their words in any Krea 2 encoding "
                                                                  "(wire this node's prompt into the edit encoder instead). "
                                                                  "Wired, this conditioning comes out as the node's own."}),
                "block": (BLOCK_MODES, {"default": "on change",
                                        "tooltip": "With the prompt socket wired. on change: the box takes the incoming prompt "
                                                   "when it changes, your edit holds until then. always: the box holds, and "
                                                   "a new incoming prompt stops the run here: edit, then Run carries on "
                                                   "with the same seeds. never: the incoming prompt always comes through."}),
                "last_in": ("STRING", {"default": "", "tooltip": "The incoming prompt of the last run (set on the node)."}),
                "prompt": ("STRING", {"forceInput": True, "tooltip": "Optional: a prompt from another node. It lands in the "
                                                                    "box, where you can edit and weight it (see block)."}),
            },
        }

    RETURN_TYPES = ("MODEL", "CONDITIONING", "STRING", "STRING")
    RETURN_NAMES = ("model", "conditioning", "prompt", "weighted_prompt")
    OUTPUT_TOOLTIPS = ("The model, with the word weights built in on Krea 2 and MOSS Image (wire it to the sampler).",
                       "The encoded prompt.", "The prompt used (your edit, or the linked one), without weights: wire it into an "
                       "edit encoder or metadata.",
                       "The prompt with (word:weight) written in, for metadata or another encoder.")
    FUNCTION = "encode"
    CATEGORY = "LC123/conditioning"
    DESCRIPTION = ("A text encoder with a weight per word: click a word, move its slider. Green = more, red = less, "
                   "below 0 = taken out. Works on Krea 2 and MOSS Image (inside the model) and on CLIP models (SDXL, Illustrious, Pony).")

    def encode(self, clip, text, strength, weights, model=None, edit_conditioning=None, block="on change", last_in="",
               prompt=None):
        box = text or ""
        hold = False
        if prompt is None:  # nothing wired: the box
            src, take = box, False
        else:
            incoming = str(prompt)
            changed = incoming != (last_in or "")
            # the incoming prompt, unless Block keeps the box (an empty box always takes it)
            take = block == "never" or not box.strip() or (block == "on change" and changed)
            src = incoming if take else box
            # always: a new incoming prompt (not the first one this node sees) stops the run here
            hold = block == "always" and not take and changed and bool(last_in)
        use_edit = prompt is not None and not take
        phrases = _phrases(weights)
        wtext = weighted_text(src, phrases)
        ui = {"lc_prompt": [src]}
        if prompt is not None:  # the face puts the incoming prompt in the box and remembers it for on change
            ui.update({"lc_in": [str(prompt)], "lc_take": [take]})
        if hold:
            # the face remembers the new prompt as seen, so the Continue run (same seeds, web/lc_continue.js) passes
            nodes.interrupt_processing()
            ui["lc_hold"] = [time.time()]
            print("[LC Weighted Prompt] Block always: a new prompt came in, stopped here. Edit if you like, then Run.")
            return {"ui": ui, "result": (model, None, src, wtext)}
        if model is not None and _is_krea2(model):
            tok = clip.tokenize(src)
            cond = clip.encode_from_tokens_scheduled(tok)
            positions = _krea2_positions(clip, src, phrases, cond[0][0].shape[1], [t[0] for t in tok[next(iter(tok))][0]]) \
                if phrases and strength > 0 else []
            if positions:
                ids = [t[0] for t in tok[next(iter(tok))][0]]
                vis = len(ids) - cond[0][0].shape[1]
                try:
                    words = [clip.tokenizer.untokenize([(ids[p + vis], 1.0)]) for p, _ in positions]
                    shown = ", ".join(f"{str(w[0][1]) if w else '?'!r}:{wt:g}" for w, (_, wt) in zip(words, positions))
                except Exception:
                    shown = ", ".join(f"{p}:{w:g}" for p, w in positions)
                # an edit encoder puts the source pictures' tokens before the prompt; the prompt still ends the user
                # turn, followed by the same template ending, so a word sits as far from the END as in the plain encode
                plain_len = cond[0][0].shape[1]
                offsets = [(plain_len - p, w) for p, w in positions]
                state = {}
                model = model.clone()
                dm = model.get_model_object("diffusion_model")
                patch = _attn_patch(offsets, strength, plain_len, state)
                for i, blk in enumerate(dm.blocks):
                    model.add_object_patch(f"diffusion_model.blocks.{i}.attn.forward", _block_forward(blk.attn.forward, i, patch))
                model.add_object_patch("diffusion_model.txtmlp.forward", _txt_probe(dm.txtmlp.forward, state))
                print(f"[LC Weighted Prompt] Krea 2: {len(positions)} token(s) weighted: {shown} "
                      f"(placed from the end of the prompt, any encoder{', your edit' if use_edit else ''})")
            if edit_conditioning is not None:
                cond = edit_conditioning
            return {"ui": ui, "result": (model, cond, src, wtext)}
        if model is not None and _is_moss(model):
            tok = clip.tokenize(src)
            cond = clip.encode_from_tokens_scheduled(tok)
            cond_len = cond[0][0].shape[1]
            positions = _krea2_positions(clip, src, phrases, cond_len, [t[0] for t in tok[next(iter(tok))][0]]) \
                if phrases and strength > 0 else []
            if positions:
                model = _moss_patch(model, positions, strength, cond_len)
                print(f"[LC Weighted Prompt] MOSS: {len(positions)} token(s) weighted: {_shown(clip, tok, cond_len, positions)}")
            return {"ui": ui, "result": (model, cond, src, wtext)}
        enc = weighted_text(src, [(p, 1.0 + strength * (w - 1.0)) for p, w in phrases]) if phrases else src
        cond = clip.encode_from_tokens_scheduled(clip.tokenize(enc))
        return {"ui": ui, "result": (model, cond, src, wtext)}


NODE_CLASS_MAPPINGS = {NODE_NAME: LCWeightedPrompt}
NODE_DISPLAY_NAME_MAPPINGS = {NODE_NAME: "LC Weighted Prompt ⚖️"}
