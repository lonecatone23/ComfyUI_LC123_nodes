"""
LC Size Pad: a 2D slider for width x height. The frame is pinned bottom-left; drag its top-right corner, pick a model preset and an aspect ratio, and
it hands out a size the model is happy with: snapped to the model's step (H3 and LTX 32, SDXL 64, Krea 2, Klein and
Wan 16) and kept under the model's megapixel limit. The megapixel limit and its tip work like LC Outpaint's frame (LC MaskMaker). The pad itself lives in web/lc_size_pad.js; this file snaps and outputs.
"""

import math

# step: both sides are a multiple of it (the model's own nodes enforce it). mp: the default size in megapixels, the
# size it was made for. max_mp: the drag stops here (the limit for good results / VRAM, not a hard crash point).
PRESETS = {
    "MiniMax H3": {"step": 32, "mp": 1.03, "max_mp": 1.6},   # trained around 1344 x 768
    "Krea 2": {"step": 16, "mp": 1.05, "max_mp": 2.0},
    "SDXL": {"step": 64, "mp": 1.05, "max_mp": 1.5},           # its buckets: 1024 x 1024, 1216 x 832, 1344 x 768...
    "LTX": {"step": 32, "mp": 0.9, "max_mp": 2.1},            # 1280 x 704 up to 1920 x 1088
    "Klein 9B": {"step": 16, "mp": 1.05, "max_mp": 4.0},
    "Wan 2.2": {"step": 16, "mp": 0.92, "max_mp": 0.93},      # 720p (1280 x 720); 0.4 MP is 480p (832 x 480)
    "Custom": {"step": 8, "mp": 1.0, "max_mp": 16.0},
}
ASPECTS = ["free", "1:1", "4:5", "5:4", "2:3", "3:2", "3:4", "4:3", "9:16", "16:9", "9:21", "21:9"]


def snap(v, step):
    return max(step, int(math.floor(float(v) / step + 0.5)) * step)  # halves round up, like the pad


def fit(w, h, preset):
    """Snap to the step and keep under the megapixel limit, keeping the shape."""
    p = PRESETS.get(preset, PRESETS["Custom"])
    w, h = snap(w, p["step"]), snap(h, p["step"])
    limit = p["max_mp"] * 1e6
    if w * h > limit:
        k = math.sqrt(limit / (w * h))
        w = max(p["step"], int(w * k) // p["step"] * p["step"])
        h = max(p["step"], int(h * k) // p["step"] * p["step"])
    return w, h


class LCSizePad:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": (list(PRESETS), {"default": "Krea 2",
                                          "tooltip": "Snaps the size to what this model wants (its step and size) and "
                                                     "stops the drag at its megapixel limit. Custom: steps of 8, no real limit."}),
                "aspect": (ASPECTS, {"default": "free",
                                     "tooltip": "Locks the frame to this shape while you drag. free: any shape."}),
                "megapixels": ("FLOAT", {"default": 1.0, "min": 0.1, "max": 16.0, "step": 0.05,
                                         "tooltip": "The size at the current shape. Changing it resizes the frame; "
                                                    "dragging updates it. It never goes past the model's limit."}),
                "width": ("INT", {"default": 1024, "min": 64, "max": 16384, "step": 8}),
                "height": ("INT", {"default": 1024, "min": 64, "max": 16384, "step": 8}),
            },
        }

    RETURN_TYPES = ("INT", "INT", "STRING", "FLOAT")
    RETURN_NAMES = ("width", "height", "info", "megapixels")
    OUTPUT_TOOLTIPS = ("Width, snapped for the model.", "Height, snapped for the model.", "e.g. 1344 x 768 · 1.03 MP · Krea 2",
                       "The snapped size in megapixels (width x height / 1,000,000), e.g. 1.03.")
    FUNCTION = "run"
    CATEGORY = "LC123/utils"
    DESCRIPTION = ("A 2D slider for width x height: drag the frame's corner, pick a model preset (MiniMax H3, Krea 2, SDXL, LTX, "
                   "Klein 9B, Wan 2.2) and an aspect ratio. The size is snapped to the model's step and kept under its "
                   "megapixel limit.")

    def run(self, model, aspect, megapixels, width, height):
        w, h = fit(width, height, model)
        mp = round(w * h / 1e6, 2)
        return (w, h, f"{w} x {h} · {mp:.2f} MP · {model}", mp)


NODE_CLASS_MAPPINGS = {"LCSizePad": LCSizePad}
NODE_DISPLAY_NAME_MAPPINGS = {"LCSizePad": "LC Size Pad 📐"}
