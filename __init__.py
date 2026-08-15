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


# Core
_load("aspect_ratio")
_load("slider")
_load("anima_regional_canvas")
_load("krea2_regional_canvas")
_load("dynamic_overlay")

# Utils
_load("lc_any_switch")
_load("lc_combo")
_load("lc_invert_boolean")
_load("lc_boolean")
_load("lc_join_strings")
_load("lc_show_text")
_load("lc_text_replace")
_load("lc_text_remove")
_load("lc_compare")
_load("lc_seed_jump")
_load("lc_notify")
_load("lc_civitai_strip")

# Save text (prefer lowercase module name; fall back to LC_*)
try:
    _load("lc_save_text")
except Exception:
    pass
if "LC123SaveText" not in NODE_CLASS_MAPPINGS:
    _load("LC_save_text")

# Image tools
_load("lc_batch_image_comparer")
_load("lc_last_image_holder")

# Sampling helpers
_load("lc_sampler_configure")
_load("lc_pipe_io")
_load("lc_get_image")
_load("lc_dimension_resize")
_load("lc_image_crop")
_load("lc_image_tools")
_load("lc_apply_lut")
_load("lc_text_overlay")
_load("lc_watermark")
_load("lc_prompt_to_conditioning")
_load("lc_split_sigma_scheduler")
_load("lc_basic_scheduler")
_load("lc_split_sigmas_advanced")
_load("lc_prompt_box")
_load("lc_vram_cache_clear")
_load("lc_stop")
_load("lc_advanced_folder")
_load("lc_easy_folder")

WEB_DIRECTORY = "./web"

print(f"[LC123] total {len(NODE_CLASS_MAPPINGS)} nodes: {sorted(NODE_CLASS_MAPPINGS.keys())}")

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
