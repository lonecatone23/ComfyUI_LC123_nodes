"""
Load editable prompt-builder lists from assets/prompt_builder/*.json
Falls back to empty/minimal defaults if a file is missing.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

_ASSETS = Path(__file__).resolve().parent / "assets" / "prompt_builder"


def _load_json(name: str, default: Any) -> Any:
    path = _ASSETS / name
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if data is not None else default
    except Exception:
        return default


def _list(name: str, default: List[str]) -> List[str]:
    data = _load_json(name, default)
    if isinstance(data, list) and data:
        return [str(x) for x in data]
    return list(default)


def _dict(name: str, default: Dict[str, str]) -> Dict[str, str]:
    data = _load_json(name, default)
    if isinstance(data, dict) and data:
        return {str(k): str(v) for k, v in data.items()}
    return dict(default)


# Minimal fallbacks if assets missing
_FB_POSE = ["standing", "sitting", "walking"]
_FB_ACTION = ["none", "looking at camera"]
_FB_OUTFIT = ["none", "Female/sundress", "Male/graphic tee and jeans"]

POSES = _list("poses.json", _FB_POSE)
ACTIONS = _list("actions.json", _FB_ACTION)
OUTFITS = _list("outfits.json", _FB_OUTFIT)
POS_H = _list("position_horizontal.json", ["left", "center", "right"])
POS_V = _list("position_vertical.json", ["top", "middle", "bottom"])
POS_D = _list("position_depth.json", ["foreground", "midground", "background"])

CAMERA_ANGLES = _list("camera_angles.json", ["eye level", "slightly high angle"])
DISTANCES = _list("distances.json", ["Medium shot", "Full body"])
F_STOPS = _list("f_stops.json", ["1.4", "2.8", "5.6"])
DEPTH_PRESETS = _list("depth_presets.json", ["Shallow", "Deep"])
CAMERA_ANGLE_DETAIL = _dict("camera_angle_detail.json", {})
CAMERA_DISTANCE_DETAIL = _dict("camera_distance_detail.json", {})

LIGHTING_STYLES = _list("lighting_styles.json", ["soft ambient", "golden hour"])
LIGHTING_DIRECTIONS = _list("lighting_directions.json", ["front", "front-left"])
LIGHTING_DETAIL = _dict("lighting_detail.json", {})
LIGHT_DIR_DETAIL = _dict("light_direction_detail.json", {})

SCENE_PRESETS = _dict("scene_presets.json", {"Studio seamless white": "clean white studio seamless backdrop"})
SCENE_PRESET_NAMES = list(SCENE_PRESETS.keys()) if SCENE_PRESETS else ["Studio seamless white"]

# Optional secondary objects for bbox elements: {preset: [{desc,h,v,d}, ...]}
_raw_so = _load_json("scene_objects.json", {})
SCENE_OBJECTS = {}
if isinstance(_raw_so, dict):
    for k, v in _raw_so.items():
        if isinstance(v, list):
            SCENE_OBJECTS[str(k)] = v


STYLE_CATEGORIES = _list("style_categories.json", ["Photorealistic", "Editorial"])
STYLE_PRESETS = _dict("style_presets.json", {"Ultra-realistic commercial": "ultra-realistic commercial photography"})
STYLE_PRESET_NAMES = list(STYLE_PRESETS.keys()) if STYLE_PRESETS else ["Ultra-realistic commercial"]

QUALITY_LEVELS = _list("quality_levels.json", ["Standard", "Editorial quality"])
QUALITY_DETAIL = _dict("quality_detail.json", {})

PALETTE_PRESETS = _load_json("palette_presets.json", {
    "Vibrant Primary": ["#FF0000", "#00FF00", "#0000FF", "#FFFF00"],
})
if not isinstance(PALETTE_PRESETS, dict) or not PALETTE_PRESETS:
    PALETTE_PRESETS = {"Vibrant Primary": ["#FF0000", "#00FF00", "#0000FF", "#FFFF00"]}

TIME_OF_DAY = _list("time_of_day.json", ["Morning", "Afternoon", "Golden hour", "Night"])
WEATHER = _list("weather.json", ["Clear", "Overcast", "Rainy"])
TIME_DETAIL = _dict("time_detail.json", {})
WEATHER_DETAIL = _dict("weather_detail.json", {})
