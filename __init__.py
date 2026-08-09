"""
ComfyUI_LC123_nodes — custom nodes by lonecatone23

https://github.com/lonecatone23
https://ko-fi.com/lonecatone
"""

NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}
_FAILED = []


def _load(label, import_fn):
    global NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
    try:
        cmap, dmap = import_fn()
        NODE_CLASS_MAPPINGS.update(cmap or {})
        NODE_DISPLAY_NAME_MAPPINGS.update(dmap or {})
    except Exception as e:
        _FAILED.append(f"{label}: {e}")
        print(f"[ComfyUI_LC123_nodes] FAILED to load {label}: {e}")


def _aspect():
    from .aspect_ratio import NODE_CLASS_MAPPINGS as c, NODE_DISPLAY_NAME_MAPPINGS as d
    return c, d


def _anima():
    from .anima_regional_canvas import NODE_CLASS_MAPPINGS as c, NODE_DISPLAY_NAME_MAPPINGS as d
    return c, d


def _krea():
    from .krea2_regional_canvas import NODE_CLASS_MAPPINGS as c, NODE_DISPLAY_NAME_MAPPINGS as d
    return c, d


def _slider():
    from .slider import NODE_CLASS_MAPPINGS as c, NODE_DISPLAY_NAME_MAPPINGS as d
    return c, d


def _save_text():
    try:
        from .lc_save_text import NODE_CLASS_MAPPINGS as c, NODE_DISPLAY_NAME_MAPPINGS as d
        return c, d
    except ImportError:
        from .LC_save_text import NODE_CLASS_MAPPINGS as c, NODE_DISPLAY_NAME_MAPPINGS as d
        return c, d


def _any_switch():
    from .lc_any_switch import NODE_CLASS_MAPPINGS as c, NODE_DISPLAY_NAME_MAPPINGS as d
    return c, d


def _combo():
    from .lc_combo import NODE_CLASS_MAPPINGS as c, NODE_DISPLAY_NAME_MAPPINGS as d
    return c, d


def _invert_bool():
    from .lc_invert_boolean import NODE_CLASS_MAPPINGS as c, NODE_DISPLAY_NAME_MAPPINGS as d
    return c, d


def _dynamic_overlay():
    from .dynamic_overlay import NODE_CLASS_MAPPINGS as c, NODE_DISPLAY_NAME_MAPPINGS as d
    return c, d


_load("aspect_ratio", _aspect)
_load("anima_regional_canvas", _anima)
_load("krea2_regional_canvas", _krea)
_load("slider", _slider)
_load("lc_save_text", _save_text)
_load("lc_any_switch", _any_switch)
_load("lc_combo", _combo)
_load("lc_invert_boolean", _invert_bool)
_load("dynamic_overlay", _dynamic_overlay)

if _FAILED:
    print(
        f"[ComfyUI_LC123_nodes] {len(_FAILED)} module(s) failed; "
        f"still registered: {list(NODE_CLASS_MAPPINGS)}"
    )
    for msg in _FAILED:
        print(f"[ComfyUI_LC123_nodes]   - {msg}")
else:
    print(f"[ComfyUI_LC123_nodes] loaded: {list(NODE_CLASS_MAPPINGS)}")

WEB_DIRECTORY = "./web"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
