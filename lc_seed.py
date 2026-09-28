"""
🌱LC Seed — standalone INT seed, rgthree Seed-style. One widget, no seed_mode: type a number for a fixed
seed, or -1 for a fresh random number every run. Widget is base_seed (not "seed") so ComfyUI does not
inject its own control_after_generate UI on top of this.

-1 is a sentinel, not a real seed -- the actual value used is resolved here and reported back to the
node's face (web/lc_seed.js) via the `ui` message, same as before.

Capped to JS_SAFE_MAX (2**53 - 1, JavaScript's Number.MAX_SAFE_INTEGER) rather than the full 64-bit range:
any integer bigger than that is not exactly representable as an IEEE-754 double, and a resolved seed has
to cross into JS twice -- once over JSON in the `ui` message the browser uses to build the seed history,
and once if it's ever typed into or displayed by the widget itself. Past 2**53 both of those silently round
to the nearest representable double instead of erroring, so the number the history shows (and the number a
user could type back in) is not necessarily the number that was actually used. A generation seed only needs
enough entropy to avoid collisions -- 2**53 possible values is still astronomically more than that needs --
so there's no reason to keep the full 64-bit range and its silent corruption risk.
"""

from __future__ import annotations

import random
import time

RANDOMIZE = -1
JS_SAFE_MAX = (1 << 53) - 1  # Number.MAX_SAFE_INTEGER -- see module docstring


def _resolve_seed(base_seed: int) -> int:
    if int(base_seed) == RANDOMIZE:
        return random.randint(0, JS_SAFE_MAX)
    return max(0, min(int(base_seed), JS_SAFE_MAX))


class LCSeed:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "base_seed": ("INT", {
                    "default": 0,
                    "min": RANDOMIZE,
                    "max": JS_SAFE_MAX,
                    "tooltip": "A number = that exact fixed seed, reused every run. -1 = a fresh random "
                               "number every run. Use the node's own buttons rather than typing -1 by "
                               "hand: 'Randomize Each Time' sets this to -1, 'New Fixed Random' rolls one "
                               "number now and writes it here as a real fixed seed. Capped below 2**64 on "
                               "purpose -- see the module docstring.",
                }),
            },
            "hidden": {
                "prompt": "PROMPT",
                "extra_pnginfo": "EXTRA_PNGINFO",
                "unique_id": "UNIQUE_ID",
            },
        }

    RETURN_TYPES = ("INT",)
    RETURN_NAMES = ("seed",)
    FUNCTION = "emit"
    CATEGORY = "LC123/utils"
    DESCRIPTION = (
        "Utility seed. Type a fixed number, or use the node's face: 'Randomize Each Time', 'New Fixed "
        "Random', manual entry, or pick one of the last 10 seeds this node actually ran with."
    )

    @classmethod
    def IS_CHANGED(cls, base_seed, prompt=None, extra_pnginfo=None, unique_id=None):
        if int(base_seed) == RANDOMIZE:
            return time.time()
        return int(base_seed)

    def emit(self, base_seed, prompt=None, extra_pnginfo=None, unique_id=None):
        used = _resolve_seed(base_seed)
        # Update the queued metadata, not the live widget's randomize sentinel.
        if unique_id is not None:
            node_id = str(unique_id)
            if prompt is not None and node_id in prompt:
                prompt[node_id]["inputs"]["base_seed"] = used
            if extra_pnginfo is not None:
                for node in extra_pnginfo.get("workflow", {}).get("nodes", []):
                    if str(node.get("id")) != node_id or node.get("type") != "LCSeed":
                        continue
                    if node.get("widgets_values"):
                        node["widgets_values"][0] = used
                    if "widgets_values_named" in node:
                        node["widgets_values_named"]["base_seed"] = used
                    break
        return {
            "ui": {"seed": [used]},
            "result": (used,),
        }


NODE_CLASS_MAPPINGS = {
    "LCSeed": LCSeed,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LCSeed": "🌱LC Seed",
}
