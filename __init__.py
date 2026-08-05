"""
ComfyUI_LC123_nodes — custom nodes by lonecatone23

https://github.com/lonecatone23
https://ko-fi.com/lonecatone
"""

NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}


def _load(module_name: str) -> None:
    """Import a submodule and merge its mappings. Log and skip on failure."""
    import importlib
    import traceback

    try:
        mod = importlib.import_module(f".{module_name}", __name__)
        maps = getattr(mod, "NODE_CLASS_MAPPINGS", None) or {}
        disp = getattr(mod, "NODE_DISPLAY_NAME_MAPPINGS", None) or {}
        NODE_CLASS_MAPPINGS.update(maps)
        NODE_DISPLAY_NAME_MAPPINGS.update(disp)
        print(f"[LC123] + {module_name}: {list(maps.keys())}")
    except Exception as e:
        print(f"[LC123] ! failed to load {module_name}: {e}")
        traceback.print_exc()


_load("aspect_ratio")
_load("slider")
_load("anima_regional_canvas")
_load("krea2_regional_canvas")
_load("dynamic_overlay")
_load("lc_any_switch")
_load("lc_combo")
_load("lc_invert_boolean")

WEB_DIRECTORY = "./web"

print(f"[LC123] total {len(NODE_CLASS_MAPPINGS)} nodes: {sorted(NODE_CLASS_MAPPINGS.keys())}")

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
