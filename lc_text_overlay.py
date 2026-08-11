"""
LC Text Overlay
---------------
Draw text on an image. x/y percent = top-center of the text block.
Curated fonts (real file paths + browser-friendly family names).
"""

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from nodes import PreviewImage

from .lc_image_helpers import tensor_to_np, np_to_tensor


def _preview(self, result_tensor, source_tensor=None):
    out = {"ui": {}, "result": (result_tensor,)}
    try:
        after = self.save_images(result_tensor, filename_prefix="lc_after")
        out["ui"]["lc_preview"] = after["ui"]["images"]
        if source_tensor is not None:
            before = self.save_images(source_tensor, filename_prefix="lc_before")
            out["ui"]["lc_before"] = before["ui"]["images"]
    except Exception:
        pass
    return out


# (display name, CSS family fallback, possible relative filenames)
_FONT_CANDIDATES = [
    ("Arial", "Arial, Helvetica, sans-serif", ["arial.ttf", "Arial.ttf", "arial.ttc", "DejaVuSans.ttf"]),
    ("Arial Bold", "Arial, Helvetica, sans-serif", ["arialbd.ttf", "Arial Bold.ttf", "Arial-Bold.ttf", "DejaVuSans-Bold.ttf"]),
    ("Arial Italic", "Arial, Helvetica, sans-serif", ["ariali.ttf", "Arial Italic.ttf", "DejaVuSans-Oblique.ttf"]),
    ("Times New Roman", "Times New Roman, Times, serif", ["times.ttf", "times.ttc", "Times New Roman.ttf", "DejaVuSerif.ttf", "LiberationSerif-Regular.ttf"]),
    ("Times New Roman Bold", "Times New Roman, Times, serif", ["timesbd.ttf", "Times New Roman Bold.ttf", "DejaVuSerif-Bold.ttf"]),
    ("Georgia", "Georgia, serif", ["georgia.ttf", "Georgia.ttf"]),
    ("Georgia Bold", "Georgia, serif", ["georgiab.ttf", "Georgia Bold.ttf"]),
    ("Verdana", "Verdana, Geneva, sans-serif", ["verdana.ttf", "Verdana.ttf", "DejaVuSans.ttf"]),
    ("Verdana Bold", "Verdana, Geneva, sans-serif", ["verdanab.ttf", "Verdana Bold.ttf"]),
    ("Tahoma", "Tahoma, sans-serif", ["tahoma.ttf", "Tahoma.ttf", "DejaVuSans.ttf"]),
    ("Trebuchet MS", "Trebuchet MS, sans-serif", ["trebuc.ttf", "Trebuchet MS.ttf"]),
    ("Comic Sans MS", "Comic Sans MS, cursive", ["comic.ttf", "Comic Sans MS.ttf", "comicbd.ttf"]),
    ("Impact", "Impact, Haettenschweiler, sans-serif", ["impact.ttf", "Impact.ttf"]),
    ("Courier New", "Courier New, Courier, monospace", ["cour.ttf", "courbd.ttf", "Courier New.ttf", "DejaVuSansMono.ttf"]),
    ("Consolas", "Consolas, monospace", ["consola.ttf", "Consolas.ttf", "DejaVuSansMono.ttf"]),
    ("Segoe UI", "Segoe UI, sans-serif", ["segoeui.ttf", "SegoeUI.ttf", "segoeuib.ttf"]),
    ("Segoe UI Bold", "Segoe UI, sans-serif", ["segoeuib.ttf", "Segoe UI Bold.ttf"]),
    ("Calibri", "Calibri, sans-serif", ["calibri.ttf", "Calibri.ttf", "calibril.ttf"]),
    ("Calibri Bold", "Calibri, sans-serif", ["calibrib.ttf", "Calibri Bold.ttf"]),
    ("DejaVu Sans", "DejaVu Sans, sans-serif", ["DejaVuSans.ttf"]),
    ("DejaVu Serif", "DejaVu Serif, serif", ["DejaVuSerif.ttf"]),
    ("DejaVu Sans Mono", "DejaVu Sans Mono, monospace", ["DejaVuSansMono.ttf"]),
    ("Liberation Sans", "Liberation Sans, Arial, sans-serif", ["LiberationSans-Regular.ttf"]),
    ("Liberation Serif", "Liberation Serif, Times, serif", ["LiberationSerif-Regular.ttf"]),
]

_FONT_DIRS = [
    Path("C:/Windows/Fonts"),
    Path("/usr/share/fonts"),
    Path("/usr/share/fonts/truetype"),
    Path("/usr/local/share/fonts"),
    Path.home() / ".fonts",
    Path("/System/Library/Fonts"),
    Path("/Library/Fonts"),
    Path.home() / "Library/Fonts",
]


def _resolve_fonts():
    """Build {display_name: {"path": str|None, "css": str}} for fonts that exist."""
    found = {}
    # index all font files once
    index = {}
    for d in _FONT_DIRS:
        if not d.exists():
            continue
        try:
            for p in d.rglob("*"):
                if p.suffix.lower() in (".ttf", ".otf", ".ttc"):
                    index[p.name.lower()] = p
                    index[p.stem.lower()] = p
        except Exception:
            pass

    for display, css, candidates in _FONT_CANDIDATES:
        path = None
        for name in candidates:
            hit = index.get(name.lower()) or index.get(Path(name).stem.lower())
            if hit is not None:
                path = str(hit)
                break
        # Always list curated fonts; path may be None → PIL default
        found[display] = {"path": path, "css": css}
    return found


_FONT_MAP = _resolve_fonts()
_FONT_NAMES = list(_FONT_MAP.keys())
MARGIN_PX = 6


def _text_bbox(draw, s, font):
    try:
        return draw.textbbox((0, 0), s or " ", font=font)
    except Exception:
        return (0, 0, len(s or " ") * 10, 12)


def _text_width(draw, s, font):
    l, t, r, b = _text_bbox(draw, s, font)
    return max(0, r - l)


def _wrap_line(draw, line, font, max_w):
    line = line.rstrip("\r")
    if not line:
        return [""]
    if _text_width(draw, line, font) <= max_w:
        return [line]
    words = line.split(" ")
    rows, cur = [], ""
    for w in words:
        trial = w if not cur else (cur + " " + w)
        if _text_width(draw, trial, font) <= max_w:
            cur = trial
        else:
            if cur:
                rows.append(cur)
            if _text_width(draw, w, font) > max_w:
                chunk = ""
                for ch in w:
                    t2 = chunk + ch
                    if _text_width(draw, t2, font) <= max_w:
                        chunk = t2
                    else:
                        if chunk:
                            rows.append(chunk)
                        chunk = ch
                cur = chunk
            else:
                cur = w
    if cur:
        rows.append(cur)
    return rows or [""]


class LCTextOverlay(PreviewImage):
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "text": ("STRING", {
                    "default": "Hello",
                    "multiline": True,
                    "tooltip": "Text to draw (wraps at edges with a small margin)",
                }),
                "font": (_FONT_NAMES, {
                    "default": _FONT_NAMES[0],
                    "tooltip": "Font family (curated list — changes apply on queue; live preview uses matching CSS name)",
                }),
                "font_size": ("INT", {
                    "default": 64, "min": 1, "max": 512, "step": 1,
                    "tooltip": "Font size in pixels",
                }),
                "color_r": ("INT", {
                    "default": 255, "min": 0, "max": 255, "step": 1,
                    "tooltip": "Red",
                }),
                "color_g": ("INT", {
                    "default": 255, "min": 0, "max": 255, "step": 1,
                    "tooltip": "Green",
                }),
                "color_b": ("INT", {
                    "default": 255, "min": 0, "max": 255, "step": 1,
                    "tooltip": "Blue",
                }),
                "x_percent": ("FLOAT", {
                    "default": 50.0, "min": 0.0, "max": 100.0, "step": 0.1,
                    "tooltip": "X of text top-center (% from left). Drag on preview.",
                }),
                "y_percent": ("FLOAT", {
                    "default": 90.0, "min": 0.0, "max": 100.0, "step": 0.1,
                    "tooltip": "Y of text top-center (% from top). Drag on preview.",
                }),
                "anchor": ([
                    "left-top", "center-top", "right-top",
                    "left-center", "center-center", "right-center",
                    "left-bottom", "center-bottom", "right-bottom",
                ], {
                    "default": "center-top",
                    "tooltip": "Horizontal align per line + vertical block align around x/y",
                }),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "run"
    CATEGORY = "LC123/image"
    OUTPUT_NODE = True
    DESCRIPTION = "Text overlay with curated fonts, wrap, margins, clamped placement."

    def _font(self, name, size):
        info = _FONT_MAP.get(name) or {}
        path = info.get("path")
        try:
            if path:
                return ImageFont.truetype(path, size)
        except Exception as e:
            print(f"[LCTextOverlay] font load failed '{name}' path={path}: {e}")
        try:
            return ImageFont.load_default(size=size)
        except TypeError:
            return ImageFont.load_default()

    def run(self, image, text, font, font_size, color_r, color_g, color_b,
            x_percent, y_percent, anchor):
        if not text:
            return _preview(self, image, image)

        color = (int(color_r), int(color_g), int(color_b), 255)
        font_obj = self._font(font, int(font_size))
        ah, av = (anchor.split("-") + ["top"])[:2]

        arrays = tensor_to_np(image)
        out = []
        for img in arrays:
            pil = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).convert("RGBA")
            draw = ImageDraw.Draw(pil)
            w, h = pil.size
            max_w = max(8, w - 2 * MARGIN_PX)

            lines = []
            for para in str(text).split("\n"):
                lines.extend(_wrap_line(draw, para, font_obj, max_w))
            if not lines:
                lines = [""]

            metrics = []
            for ln in lines:
                l, t, r, b = _text_bbox(draw, ln, font_obj)
                metrics.append((l, t, r, b, max(1, b - t)))

            gap = max(2, int(font_size * 0.15))
            first_ascent = -metrics[0][1] if metrics[0][1] < 0 else 0
            block_h = first_ascent
            for i, m in enumerate(metrics):
                block_h += m[4]
                if i < len(metrics) - 1:
                    block_h += gap

            cx = int(w * (float(x_percent) / 100.0))
            cy = int(h * (float(y_percent) / 100.0))

            if av == "bottom":
                top_y = cy - block_h
            elif av == "center":
                top_y = cy - block_h // 2
            else:
                top_y = cy

            top_y = int(max(MARGIN_PX, min(h - MARGIN_PX - block_h, top_y)))
            if block_h > h - 2 * MARGIN_PX:
                top_y = MARGIN_PX

            y = top_y + first_ascent
            for (ln, (l, t, r, b, lh)) in zip(lines, metrics):
                tw = max(0, r - l)
                if ah == "left":
                    x = cx - l
                elif ah == "right":
                    x = cx - tw - l
                else:
                    x = cx - tw // 2 - l
                x = int(max(MARGIN_PX - l, min(w - MARGIN_PX - tw - l, x)))
                draw_y = y - t if t < 0 else y
                draw.text((x, draw_y), ln, font=font_obj, fill=color)
                y = draw_y + lh + gap

            rgb = np.array(pil.convert("RGB")).astype(np.float32) / 255.0
            out.append(rgb)

        return _preview(self, np_to_tensor(out), image)


NODE_CLASS_MAPPINGS = {
    "LCTextOverlay": LCTextOverlay,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "LCTextOverlay": "LC Text Overlay",
}
