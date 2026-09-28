"""
ComfyUI_LC123_nodes — custom nodes by lonecatone23

https://github.com/lonecatone23
https://ko-fi.com/lonecatone
"""

import os as _os

_PACK_DIR = _os.path.dirname(_os.path.abspath(__file__))
print(f"[LC123] loading from {_PACK_DIR}")
_nested = _os.path.join(_PACK_DIR, "ComfyUI_LC123_nodes", "__init__.py")
if _os.path.isfile(_nested):
    print(
        "[LC123] WARNING: nested pack folder detected. "
        f"{_nested} will be ignored. Unzip so __init__.py sits in {_PACK_DIR}"
    )

# Sample LUTs: assets/luts → models/luts (no overwrite)
try:
    from . import lc_lut_install  # noqa: F401
except Exception as _lut_e:
    print(f"[LC123] LUT install skip: {_lut_e}")

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
        print(f"[LC123] + {module_name} ({len(maps)})")
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
_load("lc_index_switch")
_load("lc_custom_combo")
_load("lc_combo")
_load("lc_invert_boolean")
_load("lc_is_bypassed_or_muted")
_load("lc_boolean")
_load("lc_boolean_switch")
_load("lc_prompt_builder")
_load("lc_join_strings")
_load("lc_show_text")
_load("lc_widget_to_string")
_load("lc_text_replace")
_load("lc_text_remove")
_load("lc_compare")
_load("lc_seed_jump")
_load("lc_node_snapshot")
_load("lc_notify")
_load("lc_civitai_strip")

_load("lc_save_text")

# Image tools
_load("lc_batch_image")
_load("lc_batch_image_comparer")
_load("lc_image_split")
_load("lc_last_image_holder")
_load("lc_image_label")

# Sampling helpers
_load("lc_sampler_configure")
_load("lc_pipe_io")
_load("lc_minimax_h3_pipe")
_load("lc_get_image")
_load("lc_dimension_resize")
_load("lc_image_mask_resize")
_load("lc_image_total_megapixels")
_load("lc_lighting_v2")
_load("lc_preview_nodes")
_load("lc_label")
_load("lc_lora_loader")
_load("lc_group_lora_loader")
_load("lc_group_lora_stack")
_load("lc_lora_stack")
_load("lc_image_crop")
_load("lc_image_grid")
_load("lc_image_tools")
_load("lc_skin_beauty")
_load("lc_skin_upscale")
_load("lc_phone_look")
_load("lc_apply_lut")
_load("lc_text_overlay")
_load("lc_watermark")
_load("lc_prompt_to_conditioning")
_load("lc_split_sigma_scheduler")
_load("lc_basic_scheduler")
_load("lc_split_sigmas_advanced")
_load("lc_prompt_box")
_load("lc_optimizer")
_load("lc_link_card")
_load("lc_vram_cache_clear")
_load("lc_stop")
_load("lc_advanced_folder")
_load("lc_easy_folder")
_load("lc_save_image")
_load("lc_any_empty")
_load("lc_int_split")
_load("lc_change_step_count")
_load("lc_sigma_curve")
_load("lc_pass")
_load("lc_bypass_relay")
_load("lc_directional_blur")
_load("lc_depth_fx")
_load("lc_phone_filters")
_load("lc_image_ref_pipe")
_load("lc_image_batch_folder")
_load("lc_show_any")

WEB_DIRECTORY = "./web"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]

# Loaded after WEB_DIRECTORY, same order as before; _load prints a traceback on failure
_load("lc_wildcard")  # LC Wildcard
_load("lc_seed")  # LC Seed (utility)
_load("lc_reference_latent")  # LC Reference Latent
_load("lc_denoise")  # LC Denoise
_load("lc_relight")  # LC Relight

print(f"[LC123] total {len(NODE_CLASS_MAPPINGS)} nodes: {sorted(NODE_CLASS_MAPPINGS.keys())}")
