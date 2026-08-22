"""
LC Wildcard — pick a list from assets/wildcards/, return one seed-stable random line.
Plain STRING out (prompt boxes, Join Strings, etc.). No __keyword__ syntax.

Uses base_seed + seed_mode only (no seed output socket; no control_after_generate).
"""

from __future__ import annotations

import random
import time
from pathlib import Path
from typing import List

_WILDCARD_ROOT = Path(__file__).resolve().parent / "assets" / "wildcards"


def _scan_wildcards() -> List[str]:
    if not _WILDCARD_ROOT.is_dir():
        return ["(no wildcards found)"]
    keys = []
    for path in sorted(_WILDCARD_ROOT.rglob("*.txt")):
        try:
            rel = path.relative_to(_WILDCARD_ROOT).as_posix()
        except ValueError:
            continue
        if rel:
            keys.append(rel)
    return keys or ["(no wildcards found)"]


def _load_lines(key: str) -> List[str]:
    if not key or key.startswith("("):
        return []
    path = _WILDCARD_ROOT / str(key).replace("\\", "/")
    if not path.is_file():
        return []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []
    lines = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        lines.append(s)
    return lines


def _resolve_seed(seed: int, seed_mode: str) -> int:
    mode = (seed_mode or "fixed").lower().strip()
    s = int(seed) & 0xFFFFFFFFFFFFFFFF
    if mode == "randomize":
        return random.randint(0, 0xFFFFFFFFFFFFFFFF)
    if mode == "increment":
        return (s + 1) & 0xFFFFFFFFFFFFFFFF
    if mode == "decrement":
        return (s - 1) & 0xFFFFFFFFFFFFFFFF
    return s


class LCWildcard:
    @classmethod
    def INPUT_TYPES(cls):
        options = _scan_wildcards()
        return {
            "required": {
                "wildcard": (options, {
                    "default": options[0],
                    "tooltip": "List file under assets/wildcards/. One random line is chosen.",
                }),
                "base_seed": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 0xFFFFFFFFFFFFFFFF,
                    "tooltip": "Base seed. seed_mode decides fixed / randomize / increment / decrement.",
                }),
                "seed_mode": (["fixed", "randomize", "increment", "decrement"], {
                    "default": "randomize",
                    "tooltip": "fixed: reuse base_seed. randomize / increment / decrement: every run "
                               "(full queue or this node only).",
                }),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    FUNCTION = "pick"
    CATEGORY = "LC123/prompt"
    DESCRIPTION = (
        "Random line from assets/wildcards/*.txt. "
        "Wire text into any STRING / prompt / Join Strings."
    )

    @classmethod
    def IS_CHANGED(cls, wildcard, base_seed, seed_mode="fixed"):
        mode = (seed_mode or "fixed").lower().strip()
        if mode == "randomize":
            return time.time()
        return f"{wildcard}:{int(base_seed)}:{mode}"

    def pick(self, wildcard, base_seed, seed_mode="fixed"):
        lines = _load_lines(str(wildcard))
        used = _resolve_seed(base_seed, seed_mode)
        if not lines:
            return ("",)
        rng = random.Random(used)
        # Persist used seed into ui so JS can update base_seed after partial runs
        return {
            "ui": {"seed": [used]},
            "result": (rng.choice(lines),),
        }


NODE_CLASS_MAPPINGS = {
    "LCWildcard": LCWildcard,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LCWildcard": "🎲LC Wildcard",
}
