"""
LC Batch Image Comparer
-----------------------
A drop-in replacement for rgthree Image Comparer that keeps the image area
position and size constant even with large batches.

Instead of a growing list of clickable numbers at the top, it uses a compact
dropdown (combo) selector.  A fixed-height placeholder is always reserved so
the image never jumps when the batch size changes (including single-image runs).
"""

from nodes import PreviewImage
from folder_paths import get_temp_directory
import folder_paths
import os
import json


class LCBatchImageComparer(PreviewImage):
    """Compare two images (or batch pairs) with a stable layout and dropdown selector."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {},
            "optional": {
                "image_a": ("IMAGE",),
                "image_b": ("IMAGE",),
            },
            "hidden": {
                "prompt": "PROMPT",
                "extra_pnginfo": "EXTRA_PNGINFO",
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("images",)
    FUNCTION = "compare"
    CATEGORY = "LC123/image"
    OUTPUT_NODE = True
    DESCRIPTION = (
        "Stable Image Comparer for large batches. "
        "Uses a compact dropdown instead of an overflowing number list. "
        "Image area position and size stay constant (placeholder always reserved)."
    )

    def compare(self, image_a=None, image_b=None, prompt=None, extra_pnginfo=None):
        # Re-use PreviewImage's save_images helper so the frontend receives
        # the same {filename, subfolder, type} structure that rgthree expects.
        result = {
            "ui": {
                "a_images": [],
                "b_images": [],
            },
            "result": (None,),
        }

        filename_prefix = "lc.compare."

        if image_a is not None and len(image_a) > 0:
            saved = self.save_images(
                image_a,
                filename_prefix=filename_prefix + "a_",
                prompt=prompt,
                extra_pnginfo=extra_pnginfo,
            )
            result["ui"]["a_images"] = saved["ui"]["images"]

        if image_b is not None and len(image_b) > 0:
            saved = self.save_images(
                image_b,
                filename_prefix=filename_prefix + "b_",
                prompt=prompt,
                extra_pnginfo=extra_pnginfo,
            )
            result["ui"]["b_images"] = saved["ui"]["images"]

        # Pass the first image of A through so the node can still be chained
        # if desired (matches rgthree behaviour).
        if image_a is not None and len(image_a) > 0:
            result["result"] = (image_a,)

        return result


NODE_CLASS_MAPPINGS = {
    "LCBatchImageComparer": LCBatchImageComparer,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LCBatchImageComparer": "LC Batch Image Comparer",
}
