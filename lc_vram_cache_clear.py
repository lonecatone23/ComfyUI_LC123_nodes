"""
LC VRAM Cache Clear
-------------------
Passthrough *any → *any that clears GPU VRAM and ComfyUI model/cache
state when it executes. Drop it on a latent/image line after a heavy
pass to free memory before the next stage.
"""

import gc
import torch


class LCVRAMCacheClear:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "any": ("*", {
                    "tooltip": "Any input — passed through unchanged after cache clear.",
                }),
            },
        }

    RETURN_TYPES = ("*",)
    RETURN_NAMES = ("any",)
    FUNCTION = "clear"
    CATEGORY = "LC123/utils"
    DESCRIPTION = (
        "Pass-through *any* node that clears GPU/model cache when it runs. Place between heavy stages."
    )

    def clear(self, any):
        # Soft cache clears used by common "clean GPU / clear cache" nodes
        try:
            import comfy.model_management as mm
            mm.cleanup_models()
            mm.soft_empty_cache()
        except Exception:
            pass

        try:
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.ipc_collect()
        except Exception:
            pass

        return (any,)


NODE_CLASS_MAPPINGS = {
    "LCVRAMCacheClear": LCVRAMCacheClear,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LCVRAMCacheClear": "LC VRAM Cache Clear",
}
