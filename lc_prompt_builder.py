"""
LC Prompt Builder — detailed preset text; camera/lighting split;
JSON without elements; palette single on-face preview (WebP).
"""

from __future__ import annotations

import json
import re
from typing import List, Optional

import numpy as np
import torch

from .lc_prompt_builder_lists import (
    POSES, ACTIONS, OUTFITS, POS_H, POS_V, POS_D,
    CAMERA_ANGLES, DISTANCES, F_STOPS, DEPTH_PRESETS,
    CAMERA_DISTANCE_DETAIL, CAMERA_ANGLE_DETAIL,
    LIGHTING_STYLES, LIGHTING_DETAIL, LIGHTING_DIRECTIONS, LIGHT_DIR_DETAIL,
    SCENE_PRESETS, SCENE_PRESET_NAMES, SCENE_OBJECTS,
    STYLE_CATEGORIES, STYLE_PRESETS, STYLE_PRESET_NAMES,
    QUALITY_LEVELS, QUALITY_DETAIL,
    PALETTE_PRESETS, TIME_OF_DAY, WEATHER, TIME_DETAIL, WEATHER_DETAIL,
)


def _nz(s: Optional[str]) -> str:
    if s is None:
        return ""
    return str(s).strip()


def _join_parts(parts: List[str], sep: str = ", ") -> str:
    return sep.join(p for p in parts if _nz(p))


def _noneish(s: str) -> bool:
    return _nz(s).lower() in ("", "none", "custom")


def _outfit_label(outfit: str) -> str:
    o = _nz(outfit)
    return o.split("/", 1)[-1].strip() if "/" in o else o

def _strip_time_weather_clashes(text: str, time_of_day: str = "", weather: str = "") -> str:
    """Remove baked-in time/weather phrases when user widgets supply their own."""
    t = text or ""
    if time_of_day:
        patterns = [
            r"\bat night\b", r"\bnighttime\b", r"\bnighttime\b", r"\bin daylight\b",
            r"\bdaytime\b", r"\bmidday\b", r"\bgolden hour\b", r"\bat dawn\b",
            r"\bin the morning\b", r"\bin the evening\b", r"\bblue hour\b",
            r"\blate-afternoon\b", r"\blate afternoon\b",
        ]
        for p in patterns:
            t = re.sub(p, "", t, flags=re.IGNORECASE)
    if weather:
        for p in [
            r"\brainy\b", r"\bovercast\b", r"\bfoggy\b", r"\bsnowy\b",
            r"\bclear sky\b", r"\bpartly cloudy\b",
        ]:
            t = re.sub(p, "", t, flags=re.IGNORECASE)
    t = re.sub(r"\s{2,}", " ", t)
    t = re.sub(r"\s+,", ",", t)
    return t.strip(" ,")





# --- placement → Ideogram/Krea2 bbox (yx: ymin,xmin,ymax,xmax on 0–1000) ---
_POS_MARKER = "|||LC_POS:"

_H_RANGE = {
    "left": (0.00, 0.48),
    "center": (0.18, 0.82),
    "right": (0.52, 1.00),
}
_V_RANGE = {
    "top": (0.00, 0.48),
    "middle": (0.18, 0.82),
    "bottom": (0.52, 1.00),
}
_D_SCALE = {
    "foreground": 1.00,
    "midground": 0.88,
    "background": 0.58,
}


def _norm_pos(val, allowed, default):
    s = (val or "").strip().lower()
    for a in allowed:
        if a.lower() == s:
            return a.lower()
    # partial match e.g. "front-left" style not used here
    return default


def _placement_to_bbox(h, v, d, margin=0.05):
    """Return [ymin, xmin, ymax, xmax] ints 0–1000 with margin inset + depth scale."""
    try:
        m = float(margin)
    except (TypeError, ValueError):
        m = 0.05
    m = max(0.0, min(0.25, m))

    h = _norm_pos(h, _H_RANGE.keys(), "center")
    v = _norm_pos(v, _V_RANGE.keys(), "middle")
    d = _norm_pos(d, _D_SCALE.keys(), "midground")

    x0, x1 = _H_RANGE[h]
    y0, y1 = _V_RANGE[v]
    # margin inset on full frame, then clamp slot
    x0 = max(x0, m)
    y0 = max(y0, m)
    x1 = min(x1, 1.0 - m)
    y1 = min(y1, 1.0 - m)
    if x1 <= x0:
        x0, x1 = m, 1.0 - m
    if y1 <= y0:
        y0, y1 = m, 1.0 - m

    # depth: shrink toward slot center
    scale = _D_SCALE.get(d, 0.88)
    cx, cy = (x0 + x1) * 0.5, (y0 + y1) * 0.5
    hw, hh = (x1 - x0) * 0.5 * scale, (y1 - y0) * 0.5 * scale
    x0, x1 = cx - hw, cx + hw
    y0, y1 = cy - hh, cy + hh
    x0, x1 = max(m, x0), min(1.0 - m, x1)
    y0, y1 = max(m, y0), min(1.0 - m, y1)

    ymin = int(round(y0 * 1000))
    xmin = int(round(x0 * 1000))
    ymax = int(round(y1 * 1000))
    xmax = int(round(x1 * 1000))
    ymin, ymax = max(0, min(ymin, ymax)), min(1000, max(ymin, ymax))
    xmin, xmax = max(0, min(xmin, xmax)), min(1000, max(xmin, xmax))
    if ymax - ymin < 40:
        ymax = min(1000, ymin + 40)
    if xmax - xmin < 40:
        xmax = min(1000, xmin + 40)
    return [ymin, xmin, ymax, xmax]


def _encode_pos_trailer(h, v, d):
    return f"{_POS_MARKER}{h}|{v}|{d}|||"


def _split_pos_trailer(text):
    """Return (clean_text, h, v, d). Defaults if no trailer."""
    s = text or ""
    h, v, d = "center", "middle", "midground"
    if _POS_MARKER not in s:
        # legacy: "position: left, top, foreground"
        m = re.search(
            r"position:\s*([^,;]+)\s*,\s*([^,;]+)\s*,\s*([^,;|]+)",
            s, flags=re.I,
        )
        if m:
            h, v, d = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
        return s.strip(), h, v, d
    before, _, rest = s.partition(_POS_MARKER)
    trailer, _, after = rest.partition("|||")
    parts = [p.strip() for p in trailer.split("|") if p.strip()]
    if len(parts) >= 3:
        h, v, d = parts[0], parts[1], parts[2]
    clean = (before + " " + after).strip(" ,;")
    clean = re.sub(r"\s{2,}", " ", clean)
    return clean, h, v, d



def _parse_scene_objects(scene_str):
    """Pull |||LC_OBJ:desc|h|v|d||| markers; return (clean_scene, [(desc,h,v,d), ...])."""
    s = scene_str or ""
    objs = []
    marker = "|||LC_OBJ:"
    while marker in s:
        before, _, rest = s.partition(marker)
        body, _, after = rest.partition("|||")
        s = before + after
        bits = body.split("|")
        if len(bits) >= 4:
            desc = bits[0].strip()
            if desc:
                objs.append((desc, bits[1].strip(), bits[2].strip(), bits[3].strip()))
    s = re.sub(r"\s{2,}", " ", s).strip(" ,;")
    return s, objs

def _parse_subject_chunks(subjects_str):
    """Split multi-subject string on '; ' and yield (clean_desc, h, v, d)."""
    raw = (subjects_str or "").strip()
    if not raw:
        return []
    # Prefer explicit separators from Subject Array
    chunks = [c.strip() for c in re.split(r"\s*;\s*", raw) if c.strip()]
    out = []
    for ch in chunks:
        clean, h, v, d = _split_pos_trailer(ch)
        # also strip human "position: ..." line for element desc
        clean = re.sub(
            r",?\s*position:\s*[^,;]+,\s*[^,;]+,\s*[^,;|]+",
            "", clean, flags=re.I,
        ).strip(" ,;")
        if clean:
            out.append((clean, h, v, d))
    return out



class LCSubject:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "description": ("STRING", {"default": "", "multiline": True,
                    "tooltip": "Who or what the subject is (look, age, vibe). Freeform text."}),
                "pose": (POSES, {"default": "standing",
                    "tooltip": "Body pose. Choose none to rely on the description only."}),
                "action": (ACTIONS, {"default": "none",
                    "tooltip": "What they are doing. none skips this line."}),
                "outfit": (OUTFITS, {"default": "none",
                    "tooltip": "Clothing preset (Female/… or Male/…). none = describe outfit in text."}),
                "position_horizontal": (POS_H, {"default": "center",
                    "tooltip": "Left / center / right placement in the frame."}),
                "position_vertical": (POS_V, {"default": "middle",
                    "tooltip": "Top / middle / bottom placement in the frame."}),
                "position_depth": (POS_D, {"default": "midground",
                    "tooltip": "Foreground / midground / background depth."}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("prompt",)
    FUNCTION = "build"
    CATEGORY = "LC123/prompt"

    def build(self, description, pose, action, outfit, position_horizontal, position_vertical, position_depth):
        parts = [_nz(description)]
        if not _noneish(pose):
            parts.append(f"pose: {pose}")
        if not _noneish(action):
            parts.append(f"action: {action}")
        if not _noneish(outfit):
            parts.append(f"wearing {_outfit_label(outfit)}")
        parts.append(f"position: {position_horizontal}, {position_vertical}, {position_depth}")
        human = _join_parts(parts)
        # Machine trailer for assembler bbox (stripped from final caption text)
        human = human + _encode_pos_trailer(position_horizontal, position_vertical, position_depth)
        return (human,)


class LCSubjectArray:
    DEFAULT_SEP = "; "

    @classmethod
    def INPUT_TYPES(cls):
        opt = {
            f"subject_{i:02d}": ("STRING", {
                "forceInput": True,
                "tooltip": f"Subject prompt slot {i}. Leave unconnected to skip.",
            })
            for i in range(1, 9)
        }
        return {"required": {}, "optional": opt}

    RETURN_TYPES = ("STRING", "INT")
    RETURN_NAMES = ("prompt", "count")
    FUNCTION = "gather"
    CATEGORY = "LC123/prompt"
    DESCRIPTION = "Combine several subject outputs into one line."

    def gather(self, **kwargs):
        parts = []
        for i in range(1, 9):
            v = kwargs.get(f"subject_{i:02d}")
            if v is None:
                continue
            s = _nz(v if not isinstance(v, (list, tuple)) else (v[0] if v else ""))
            if s:
                parts.append(s)
        return (self.DEFAULT_SEP.join(parts), len(parts))


class LCCamera:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt": ("STRING", {"default": "", "multiline": True,
                    "tooltip": "Extra camera notes. Framing presets include natural lens language."}),
                "angle": (CAMERA_ANGLES, {"default": "eye level",
                    "tooltip": "Camera height and tilt relative to the subject."}),
                "distance": (DISTANCES, {"default": "Medium shot",
                    "tooltip": "How much of the subject is in frame (close-up → full body). Includes lens character."}),
                "depth_of_field": (DEPTH_PRESETS, {"default": "Shallow",
                    "tooltip": "Background blur vs sharp throughout (simple stand-in for aperture)."}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("prompt",)
    FUNCTION = "build"
    CATEGORY = "LC123/prompt"
    DESCRIPTION = "Camera framing and DOF. Distance presets include lens character; no raw mm/f-stop."

    def build(self, prompt, angle, distance, depth_of_field):
        parts = [
            _nz(prompt),
            CAMERA_ANGLE_DETAIL.get(angle, f"camera angle: {angle}"),
            CAMERA_DISTANCE_DETAIL.get(distance, f"framing: {distance}"),
        ]
        dof = _nz(depth_of_field)
        if dof and dof.lower() != "none":
            parts.append(f"depth of field: {dof}")
        return (_join_parts(parts),)


class LCLighting:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt": ("STRING", {"default": "", "multiline": True,
                    "tooltip": "Extra lighting notes beyond the presets."}),
                "lighting": (LIGHTING_STYLES, {"default": "soft ambient",
                    "tooltip": "Overall light quality and mood (soft, hard, golden hour, neon, etc.)."}),
                "light_direction": (LIGHTING_DIRECTIONS, {"default": "front-left",
                    "tooltip": "Where the key light sits relative to the subject."}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("prompt",)
    FUNCTION = "build"
    CATEGORY = "LC123/prompt"

    def build(self, prompt, lighting, light_direction):
        parts = [
            _nz(prompt),
            LIGHTING_DETAIL.get(lighting, f"lighting: {lighting}"),
            LIGHT_DIR_DETAIL.get(light_direction, f"light direction: {light_direction}"),
        ]
        return (_join_parts(parts),)


class LCStyleSelector:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt": ("STRING", {"default": "", "multiline": True,
                    "tooltip": "Extra style notes (film stock, art direction, etc.)."}),
                "style_category": (STYLE_CATEGORIES, {"default": "Photorealistic",
                    "tooltip": "Broad style family (photo, editorial, anime, etc.)."}),
                "style_preset": (STYLE_PRESET_NAMES, {"default": STYLE_PRESET_NAMES[0],
                    "tooltip": "Detailed style wording for this family."}),
                "quality_level": (QUALITY_LEVELS, {"default": "Editorial quality",
                    "tooltip": "How polished the finish should read (standard → editorial/hero)."}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("prompt",)
    FUNCTION = "build"
    CATEGORY = "LC123/prompt"

    def build(self, prompt, style_category, style_preset, quality_level):
        detail = STYLE_PRESETS.get(style_preset, style_preset)
        q = QUALITY_DETAIL.get(quality_level, quality_level)
        return (_join_parts([_nz(prompt), _nz(style_category), detail, q]),)


class LCSceneBuilder:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "scene_preset": (SCENE_PRESET_NAMES, {
                    "default": SCENE_PRESET_NAMES[0],
                    "tooltip": "Detailed environment preset (fills the scene description).",
                }),
                "description": ("STRING", {"default": "", "multiline": True,
                    "tooltip": "Override or extend the preset. Empty = use preset text only."}),
                "time_of_day": (TIME_OF_DAY, {"default": "Afternoon",
                    "tooltip": "When it is. none = leave time out."}),
                "weather": (WEATHER, {"default": "Clear",
                    "tooltip": "Sky / weather. none = leave weather out."}),
                "environment_details": ("STRING", {"default": "", "multiline": True,
                    "tooltip": "Props, architecture, atmosphere not covered by the preset."}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("prompt",)
    FUNCTION = "build"
    CATEGORY = "LC123/prompt"

    def build(self, scene_preset, description, time_of_day, weather, environment_details):
        base = SCENE_PRESETS.get(scene_preset, scene_preset)
        tod = _nz(time_of_day)
        wth = _nz(weather)
        if tod.lower() == "none":
            tod = ""
        if wth.lower() == "none":
            wth = ""
        base = _strip_time_weather_clashes(base, tod, wth)
        user = _nz(description)
        scene_body = f"{base}. {user}" if user else base
        parts = [scene_body]
        if tod:
            parts.append(TIME_DETAIL.get(tod) or f"time: {tod}")
        if wth:
            parts.append(WEATHER_DETAIL.get(wth) or f"weather: {wth}")
        parts.append(_nz(environment_details))
        scene_text = _join_parts(parts)
        # Minimal scene objects for bbox elements (optional assets/scene_objects.json)
        objs = SCENE_OBJECTS.get(scene_preset) or []
        for ob in objs:
            if not isinstance(ob, dict):
                continue
            od = _nz(ob.get("desc"))
            if not od:
                continue
            oh = ob.get("h") or ob.get("horizontal") or "center"
            ov = ob.get("v") or ob.get("vertical") or "middle"
            odpth = ob.get("d") or ob.get("depth") or "background"
            scene_text = scene_text + f"|||LC_OBJ:{od}|{oh}|{ov}|{odpth}|||"
        return (scene_text,)


def _palette_from_image(image: torch.Tensor, num_colors: int = 4) -> List[str]:
    if image is None:
        return []
    t = image[0] if isinstance(image, (list, tuple)) else image
    arr = t.detach().cpu().numpy()
    if arr.ndim == 4:
        arr = arr[0]
    if arr.shape[-1] > 4:
        arr = arr[..., :3]
    pixels = arr.reshape(-1, arr.shape[-1]).astype(np.float32)
    n = pixels.shape[0]
    if n > 4000:
        idx = np.linspace(0, n - 1, 4000).astype(np.int64)
        pixels = pixels[idx]
    buckets = np.clip((pixels * 15.99).astype(np.int32), 0, 15)
    keys = buckets[:, 0] * 256 + buckets[:, 1] * 16 + buckets[:, 2]
    uniq, counts = np.unique(keys, return_counts=True)
    order = np.argsort(-counts)
    colors = []
    for u in uniq[order]:
        r = (int(u) // 256) / 15.0
        g = ((int(u) // 16) % 16) / 15.0
        b = (int(u) % 16) / 15.0
        hexv = f"#{int(round(r * 255)):02X}{int(round(g * 255)):02X}{int(round(b * 255)):02X}"
        if hexv not in colors:
            colors.append(hexv)
        if len(colors) >= max(1, int(num_colors)):
            break
    return colors


def _swatch_image(hexes: List[str], height: int = 96) -> torch.Tensor:
    if not hexes:
        hexes = ["#808080"]
    w_each = 80
    W = w_each * len(hexes)
    H = height
    img = np.zeros((H, W, 3), dtype=np.float32)
    for i, hx in enumerate(hexes):
        hx = hx.lstrip("#")
        if len(hx) != 6:
            continue
        r, g, b = int(hx[0:2], 16) / 255.0, int(hx[2:4], 16) / 255.0, int(hx[4:6], 16) / 255.0
        img[:, i * w_each : (i + 1) * w_each, :] = (r, g, b)
    return torch.from_numpy(img).unsqueeze(0)


class LCColorPalette:
    """Single face preview via ui.images only — no second JS strip."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "mode": (["preset", "from_image"], {"default": "preset",
                    "tooltip": "preset = built-in palette. from_image = sample from the input image."}),
                "preset": (list(PALETTE_PRESETS.keys()), {"default": "Vibrant Primary",
                    "tooltip": "Named palette when mode is preset."}),
                "num_colors": ("INT", {"default": 4, "min": 4, "max": 6, "step": 1,
                    "tooltip": "How many colors to use or sample (4–6)."}),
            },
            "optional": {"image": ("IMAGE", {
                "tooltip": "Source image when mode is from_image.",
            })},
        }

    RETURN_TYPES = ("STRING", "IMAGE")
    RETURN_NAMES = ("prompt", "preview")
    FUNCTION = "build"
    CATEGORY = "LC123/prompt"
    OUTPUT_NODE = True

    def build(self, mode, preset, num_colors, image=None):
        n = max(4, min(6, int(num_colors)))
        if mode == "from_image" and image is not None:
            colors = _palette_from_image(image, n)
        else:
            base = list(PALETTE_PRESETS.get(preset) or PALETTE_PRESETS["Vibrant Primary"])
            colors = (base[:n] if len(base) >= n else list(base))
            while len(colors) < n:
                colors.append(colors[-1] if colors else "#808080")
        if not colors:
            colors = ["#808080"] * n
        text = ", ".join(colors)
        preview = _swatch_image(colors)
        ui_images = []
        try:
            import folder_paths
            from PIL import Image
            import os

            arr = (preview[0].cpu().numpy() * 255).clip(0, 255).astype("uint8")
            pil = Image.fromarray(arr)
            folder = folder_paths.get_temp_directory()
            name = f"lc_palette_{abs(hash(text)) % 10_000_000}.webp"
            path = os.path.join(folder, name)
            try:
                pil.save(path, "WEBP", quality=90, method=4)
            except Exception:
                name = name.replace(".webp", ".png")
                path = os.path.join(folder, name)
                pil.save(path)
            ui_images = [{"filename": name, "subfolder": "", "type": "temp"}]
        except Exception:
            ui_images = []
        # ui.images only → one Comfy face strip; preview socket still has tensor
        return {"ui": {"images": ui_images}, "result": (text, preview)}


class LCPromptAssembler:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "pretty_print": ("BOOLEAN", {"default": True,
                    "tooltip": "JSON with indents when on; compact when off."}),
                "remove_empty": ("BOOLEAN", {"default": True,
                    "tooltip": "Skip blank sections so empty sockets do not leave empty lines."}),
                "include_scene_bboxes": ("BOOLEAN", {"default": False,
                    "tooltip": "When on, JSON also includes scene furniture/landmark boxes. "
                               "When off (default), only subject bboxes — the main regional use."}),
            },
            "optional": {
                "subjects": ("STRING", {"forceInput": True,
                    "tooltip": "From 🗒️LC Subject or Subject Array."}),
                "scene": ("STRING", {"forceInput": True,
                    "tooltip": "From 🗒️LC Scene Builder."}),
                "camera": ("STRING", {"forceInput": True,
                    "tooltip": "From 🗒️LC Camera."}),
                "lighting": ("STRING", {"forceInput": True,
                    "tooltip": "From 🗒️LC Lighting."}),
                "style": ("STRING", {"forceInput": True,
                    "tooltip": "From 🗒️LC Style Selector."}),
                "palette": ("STRING", {"forceInput": True,
                    "tooltip": "From 🎨LC Color Palette (text output)."}),
                "mood": ("STRING", {"default": "",
                    "tooltip": "Optional mood line (free text)."}),
                "background": ("STRING", {"default": "",
                    "tooltip": "Optional extra background notes."}),
                "composition": ("STRING", {"default": "",
                    "tooltip": "Optional composition notes (rule of thirds, etc.)."}),
                "extra": ("STRING", {"default": "", "multiline": True,
                    "tooltip": "Anything else to append at the end."}),
                "margin": ("FLOAT", {"default": 0.05, "min": 0.0, "max": 0.25, "step": 0.01,
                    "tooltip": "Inset all bboxes from frame edges (0–0.25). Default 0.05 = 5%."}),
            },
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("prompt", "json")
    FUNCTION = "assemble"
    CATEGORY = "LC123/prompt"

    def assemble(
        self, pretty_print, remove_empty, include_scene_bboxes=False,
        subjects=None, scene=None, camera=None, lighting=None, style=None, palette=None,
        mood="", background="", composition="", extra="", margin=0.05,
    ):
        """Ideogram / Krea2 caption JSON with placement-driven bboxes.

        Subjects carry |||LC_POS:h|v|d||| trailers (from LC Subject) — always in elements.
        Scene objects (|||LC_OBJ:…|||) only when include_scene_bboxes is True.
        margin (0–0.25) insets all boxes from the frame edge (default 5%).
        """
        sub_raw = _nz(subjects)
        scn_raw = _nz(scene)
        cam = _nz(camera)
        lit = _nz(lighting)
        sty = _nz(style)
        pal = _nz(palette)
        mood_s = _nz(mood)
        bg_extra = _nz(background)
        comp = _nz(composition)
        extra_s = _nz(extra)

        scn_clean, scene_objs = _parse_scene_objects(scn_raw)
        subject_chunks = _parse_subject_chunks(sub_raw)

        background_text = _join_parts([x for x in (scn_clean, bg_extra) if x])
        # high-level: subjects without trailers
        sub_descs = [c[0] for c in subject_chunks]
        hld_parts = [x for x in (_join_parts(sub_descs), mood_s, extra_s) if x]
        high_level = _join_parts(hld_parts) if hld_parts else background_text
        if comp:
            high_level = _join_parts([high_level, comp])

        aesthetics = sty
        lighting_text = _join_parts([x for x in (lit, cam) if x])
        medium = "photograph"
        if sty and any(k in sty.lower() for k in ("anime", "illustration", "painting", "3d", "render")):
            medium = "digital art"

        palette_hexes = []
        if pal:
            for tok in re.findall(r"#[0-9A-Fa-f]{6}", pal):
                if tok.upper() not in [h.upper() for h in palette_hexes]:
                    palette_hexes.append(tok.upper())
            if not palette_hexes and pal:
                aesthetics = _join_parts([aesthetics, f"color palette: {pal}"])

        elements = []
        for desc, h, v, d in subject_chunks:
            elements.append({
                "type": "obj",
                "bbox": _placement_to_bbox(h, v, d, margin),
                "desc": desc,
            })
        if include_scene_bboxes:
            for desc, h, v, d in scene_objs:
                elements.append({
                    "type": "obj",
                    "bbox": _placement_to_bbox(h, v, d, margin),
                    "desc": desc,
                })
        # Fallback single full-ish subject box if we have high_level but no elements
        if not elements and high_level and high_level != background_text:
            elements.append({
                "type": "obj",
                "bbox": _placement_to_bbox("center", "middle", "midground", margin),
                "desc": high_level,
            })

        text_sections = []
        for label, val in (
            ("Subject", _join_parts(sub_descs)),
            ("Scene", scn_clean),
            ("Camera", cam),
            ("Lighting", lit),
            ("Style", sty),
            ("Palette", pal),
            ("Mood", mood_s),
            ("Background", bg_extra),
            ("Composition", comp),
            ("Extra", extra_s),
        ):
            if val:
                text_sections.append(f"{label}: {val}" if pretty_print else val)
        plain = "\n".join(text_sections) if pretty_print else _join_parts(
            [x for x in (_join_parts(sub_descs), scn_clean, cam, lit, sty, pal, mood_s, bg_extra, comp, extra_s) if x]
        )

        style_block = {
            "aesthetics": aesthetics,
            "lighting": lighting_text,
            "medium": medium,
        }
        if palette_hexes:
            style_block["color_palette"] = palette_hexes[:6]

        payload = {
            "aspect_ratio": "1:1",
            "bbox_order": "yx",
            "high_level_description": high_level,
            "style_description": style_block,
            "compositional_deconstruction": {
                "background": background_text,
                "elements": elements,
            },
        }
        if pretty_print:
            j = json.dumps(payload, ensure_ascii=False, indent=2)
        else:
            j = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        return (plain, j)



NODE_CLASS_MAPPINGS = {
    "LCSubject": LCSubject,
    "LCSubjectArray": LCSubjectArray,
    "LCCamera": LCCamera,
    "LCLighting": LCLighting,
    "LCStyleSelector": LCStyleSelector,
    "LCSceneBuilder": LCSceneBuilder,
    "LCColorPalette": LCColorPalette,
    "LCPromptAssembler": LCPromptAssembler,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LCSubject": "🗒️LC Subject",
    "LCSubjectArray": "🗒️LC Subject Array",
    "LCCamera": "🗒️LC Camera",
    "LCLighting": "🗒️LC Lighting",
    "LCStyleSelector": "🗒️LC Style Selector",
    "LCSceneBuilder": "🗒️LC Scene Builder",
    "LCColorPalette": "🎨LC Color Palette",
    "LCPromptAssembler": "🧩LC Prompt Assembler",
}
