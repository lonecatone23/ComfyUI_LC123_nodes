"""
LC Anima Box Prompt
-------------------
Regional prompting for Anima from LC Bounding Boxes: each box gets its own prompt, with no position words needed.
Two tools from the same boxes (the pair won the 2026-11-01 bench; either one alone fails):

- Regional LLLite (Sen-sou/Anima-LLLite-Regional-Controlnet, anima-lllite-regional-exp-v3) through ComfyUI's core
  Anima LLLite apply: a colour mask (white background, one solid colour per box) holds WHERE things go.
- Sen-sou's Anima Regional Conditioning (Comfyui-Anima-Regional-Conditioning, MIT): one mask + prompt per box, the
  scene prompt as background, routes WHAT goes in each box.

Both are called through ComfyUI's node registry, so their own code runs unchanged. The patch downloads on first use.
"""

from __future__ import annotations

import os

import torch

import folder_paths
import nodes

from . import lc_first_download

PATCH_REPO = "Sen-sou/Anima-LLLite-Regional-Controlnet"
PATCH_FILE = "anima-lllite-regional-exp-v3.safetensors"
REGIONAL_PACK = "https://github.com/Sen-sou/Comfyui-Anima-Regional-Conditioning"
COLORS = [(230, 30, 30), (30, 90, 230), (30, 180, 60), (240, 200, 20), (200, 40, 200), (20, 200, 210), (250, 130, 20),
          (120, 60, 200)]


def _patch_name():
    """The regional patch as a model_patches name, downloaded into model_patches/Anima on first use."""
    for name in folder_paths.get_filename_list("model_patches"):
        if os.path.basename(name.replace("\\", "/")) == PATCH_FILE:
            return name
    root = folder_paths.get_folder_paths("model_patches")[0]
    lc_first_download.download(lc_first_download.hf_url(PATCH_REPO, PATCH_FILE), os.path.join(root, "Anima", PATCH_FILE),
                               "Anima Regional LLLite", "51 MB")
    folder_paths.filename_list_cache.pop("model_patches", None)
    return next(n for n in folder_paths.get_filename_list("model_patches")
                if os.path.basename(n.replace("\\", "/")) == PATCH_FILE)


def _boxes(elements):
    """(prompt, (y0, x0, y1, x1) in 0-1) per usable box, and the canvas size."""
    out, canvas = [], (1024, 1024)
    for e in elements if isinstance(elements, list) else []:
        if not isinstance(e, dict) or not e.get("bbox") or e.get("kind") == "remove":
            continue
        text = str(e.get("desc") or "").strip() or str(e.get("id") or "").rsplit("_", 1)[0].replace("_", " ")
        if not text:
            continue
        y0, x0, y1, x1 = (max(0.0, min(1.0, float(v) / 1000.0)) for v in e["bbox"])
        if x1 - x0 <= 0 or y1 - y0 <= 0:
            continue
        out.append((text, (y0, x0, y1, x1)))
        if isinstance(e.get("canvas"), (list, tuple)) and len(e["canvas"]) == 2:
            canvas = (int(e["canvas"][0]), int(e["canvas"][1]))
    return out, canvas


def _maps(boxes, width, height):
    """The colour mask (1, H, W, 3) on white, and one 0/1 mask (1, H, W) per box."""
    color = torch.ones((1, height, width, 3))
    masks = []
    for k, (_, (y0, x0, y1, x1)) in enumerate(boxes):
        ya, yb = int(round(y0 * height)), max(int(round(y0 * height)) + 1, int(round(y1 * height)))
        xa, xb = int(round(x0 * width)), max(int(round(x0 * width)) + 1, int(round(x1 * width)))
        color[0, ya:yb, xa:xb] = torch.tensor(COLORS[k % len(COLORS)]) / 255.0
        m = torch.zeros((1, height, width))
        m[0, ya:yb, xa:xb] = 1.0
        masks.append(m)
    return color, masks


class LCAnimaBoxPrompt:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("MODEL", {"tooltip": "The Anima model. Wire the output to the sampler."}),
                "clip": ("CLIP", {"tooltip": "Anima's text encoder: each box prompt is encoded with it."}),
                "elements": ("ARRAY", {"tooltip": "The boxes from LC Bounding Boxes. Each box's description is its prompt."}),
                "placement": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 2.0, "step": 0.05,
                                        "tooltip": "How hard the boxes hold their place (Regional LLLite). 1.0 tested best. "
                                                   "Lower it if subjects turn into close-ups that fill the whole box."}),
                "isolation": ("FLOAT", {"default": 0.2, "min": 0.0, "max": 1.0, "step": 0.01,
                                        "tooltip": "How much each box keeps to itself. 0.2 tested best. Higher gives flat "
                                                   "colour panels behind subjects, lower lets the box prompts drift."}),
                "box_prefix": ("STRING", {"default": "",
                                          "tooltip": "Added in front of every box prompt (a style, for example). Leave out "
                                                     "quality tags like masterpiece, best quality: on Anima they pull the "
                                                     "picture toward NSFW."}),
            },
            "optional": {
                "scene": ("CONDITIONING", {"tooltip": "Your main prompt's conditioning: the scene around the boxes. "
                                                      "Unwired, the sampler's own prompt is used."}),
            },
        }

    RETURN_TYPES = ("MODEL", "IMAGE")
    RETURN_NAMES = ("model", "color_map")
    OUTPUT_TOOLTIPS = ("The model with the boxes built in (wire it to the sampler). With no boxes drawn it passes through.",
                       "The colour mask the boxes made, to check them.")
    FUNCTION = "apply"
    CATEGORY = "LC123/conditioning"
    DESCRIPTION = ("Regional prompting for Anima: draw boxes in LC Bounding Boxes, describe what goes in each, and this "
                   "puts it there. Write each box like a normal prompt (a full sentence works best). Your main prompt "
                   "describes the scene. Needs Sen-sou's Anima Regional Conditioning "
                   "pack; the Regional LLLite patch downloads on first use.")

    def apply(self, model, clip, elements, placement, isolation, box_prefix="", scene=None):
        boxes, (width, height) = _boxes(elements)
        if not boxes:
            return (model, torch.ones((1, 64, 64, 3)))
        width, height = max(64, width), max(64, height)
        color, masks = _maps(boxes, width, height)
        reg_cls = nodes.NODE_CLASS_MAPPINGS.get("AnimaConditioningRegion")
        patch_cls = nodes.NODE_CLASS_MAPPINGS.get("ApplyAnimaRegionalConditioningPatch")
        if reg_cls is None or patch_cls is None:
            raise RuntimeError(f"[LC Anima Box Prompt] Install Sen-sou's Anima Regional Conditioning ({REGIONAL_PACK}) "
                               "and restart ComfyUI.")
        if placement > 0:
            patch = nodes.NODE_CLASS_MAPPINGS["ModelPatchLoader"]().load_model_patch(_patch_name())[0]
            model = nodes.NODE_CLASS_MAPPINGS["AnimaLLLiteApply"]().apply_patch(model, patch, color, placement, 0.0, 1.0)[0]
        regions = None
        for (text, _), mask in zip(boxes, masks):
            cond = nodes.CLIPTextEncode().encode(clip, (box_prefix or "") + text)[0]
            regions = reg_cls().create(mask, cond, 1.0, regions)[0]
        model = patch_cls().apply(model, regions, "disabled", 0.2, 0.35, 1.0, float(isolation), 0.1, 1, 1,
                                  start_percent=0.0, background_conditioning=scene)[0]
        print(f"[LC Anima Box Prompt] {len(boxes)} box(es): " + " | ".join(t for t, _ in boxes))
        return (model, color)


NODE_CLASS_MAPPINGS = {"LCAnimaBoxPrompt": LCAnimaBoxPrompt}
NODE_DISPLAY_NAME_MAPPINGS = {"LCAnimaBoxPrompt": "LC Anima Box Prompt 🔲"}
