"""
LC MOSS Layout Prompt 🗺️
------------------------
Turns the boxes from LC Bounding Boxes (or Create Bounding Boxes) into MOSS Image's layout prompt: a summary (caption,
canvas) plus one item per box (object / character / text, caption, text, palette, box).

The format follows OpenMOSS's public layout vocabulary (MOSS-Image skills/moss-image-prompt-enhancer, Apache-2.0):
pixel boxes centred on the canvas, [top, left, bottom, right], left/top floored and right/bottom ceiled. ComfyUI's own
MOSS Image Layout Prompt writes the same boxes; this node adds the labels from the box editor, the canvas and
the canvas size taken from the boxes.
"""
from __future__ import annotations

import json
import math
import re

from .lc_flux3 import palette_list, palette_split

CANVAS = ["single", "multi_panel", "collage"]


def centred_box(bbox, width, height):
    """0-1000 [y0, x0, y1, x1] -> pixel edges enclosing the box, origin at the canvas centre (OpenMOSS's rounding)."""
    y0, x0, y1, x1 = (float(v) for v in bbox)
    return [math.floor(round(y0 * height / 1000, 9)) - height // 2, math.floor(round(x0 * width / 1000, 9)) - width // 2,
            math.ceil(round(y1 * height / 1000, 9)) - height // 2, math.ceil(round(x1 * width / 1000, 9)) - width // 2]


def snap16(v):
    return max(16, int(v) // 16 * 16)


class LCMOSSLayoutPrompt:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt": ("STRING", {"multiline": True, "dynamicPrompts": True, "default": "",
                                      "placeholder": "base prompt (empty = the model picks the setting)",
                                      "tooltip": "Your base prompt: the scene and anyone not in a box (characters in boxes are described in "
                                                 "their boxes only). Wire this node's output into LC Vision Prompt Enhancer's prompt_text: the boxes stay "
                                                 "intact. Bypass this node and the base prompt goes straight through. Empty: the model picks "
                                                 "the setting."}),
                "elements": ("ARRAY", {"tooltip": "The boxes from LC Bounding Boxes (or Create Bounding Boxes). Draw the background first, "
                                                  "the foreground last."}),
                "canvas": (CANVAS, {"default": "single", "tooltip": "single = one picture. multi_panel = comic panels or a split screen. "
                                                                    "collage = a moodboard or sticker sheet."}),
            },
            "optional": {
                "width": ("INT", {"default": 0, "min": 0, "max": 16384, "step": 16,
                                  "tooltip": "0 = the boxes' canvas (the usual). Set it only to override the picture size, e.g. when this "
                                             "sits after an upscale. Must match the latent or the boxes land in the wrong place."}),
                "height": ("INT", {"default": 0, "min": 0, "max": 16384, "step": 16,
                                   "tooltip": "0 = the boxes' canvas. Set it only to override the picture size (after an upscale)."}),
            },
        }

    RETURN_TYPES = ("STRING", "INT", "INT", "STRING")
    RETURN_NAMES = ("prompt", "width", "height", "info")
    OUTPUT_TOOLTIPS = ("The layout prompt: wire it into the positive prompt's text.",
                       "The width the boxes were placed in: use it for the latent.",
                       "The height the boxes were placed in.",
                       "What went in, and anything to fix.")
    FUNCTION = "run"
    CATEGORY = "LC123/MOSS Image"
    DESCRIPTION = ("Builds MOSS Image's layout prompt from boxes: each box becomes an object, a character or a block of text "
                   "with its own caption and palette, in the place you drew it.")

    def run(self, prompt, elements, canvas, width=0, height=0, **_old):  # **_old: meta / palette / character_boxes from 1.53.0
        els = [e for e in (elements if isinstance(elements, list) else []) if isinstance(e, dict) and e.get("bbox")]
        cw, ch = next((e["canvas"] for e in els if isinstance(e.get("canvas"), (list, tuple)) and len(e["canvas"]) == 2), (1024, 1024))
        width, height = snap16(width or cw), snap16(height or ch)
        caption = prompt.strip()
        if not els:
            return (caption, width, height, "No boxes: the prompt goes through unchanged.")
        if not caption:
            caption = "A picture."  # never the box descriptions: repeated in the caption they lock the characters in
        summary = {"canvas": canvas, "caption": caption}
        items, notes, counts = [], [], {"object": 0, "character": 0, "text": 0}
        for i, e in enumerate(els):
            if e.get("type") == "text" and not str(e.get("text") or "").strip():
                notes.append(f"text box {i + 1} has no text to write: left out")  # MOSS would make up words for it
                continue
            if e.get("type") == "text":
                label = "text"
            elif e.get("label") == "character":
                label = "character"
            else:
                label = "object"
            counts[label] += 1
            desc = str(e.get("desc") or "").strip()
            if not desc:
                notes.append(f"box {i + 1} has no description")
                desc = "text" if label == "text" else label
            item = {"label": label, "caption": desc}
            if label == "text":
                item["text"] = str(e.get("text"))
            pal, bad = palette_split(e.get("color_palette") or e.get("palette"))
            bad = list(e.get("palette_left_out") or []) + bad
            if pal:
                item["palette"] = pal
            if bad:
                notes.append(f"box {i + 1} palette: left out {', '.join(repr(b) for b in bad)} (not a colour)")
            item["bbox"] = centred_box(e.get("tgt_bbox") or e["bbox"], width, height)
            items.append(item)
        layout = {"summary": summary, "items": items, "bbox_coord_space": "abs_centralized", "bbox_format": "yxyx"}
        parts = [f"{n} {k}{'s' if n != 1 else ''}" for k, n in counts.items() if n]
        info = f"{width}x{height}, {canvas}: " + ", ".join(parts) + "."
        if (width, height) != (snap16(cw), snap16(ch)):
            info += f" ⚠️ The boxes were drawn on {cw}x{ch}: they are stretched to fit."
        if notes:
            info += " ⚠️ " + "; ".join(notes) + "."
        return (json.dumps(layout, ensure_ascii=False, separators=(",", ":")), width, height, info)


NODE_CLASS_MAPPINGS = {"LCMOSSLayoutPrompt": LCMOSSLayoutPrompt}
NODE_DISPLAY_NAME_MAPPINGS = {"LCMOSSLayoutPrompt": "LC MOSS Layout Prompt 🗺️"}
