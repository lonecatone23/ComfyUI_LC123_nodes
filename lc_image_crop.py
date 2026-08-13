"""
LC Image Crop
-------------
Interactive crop (Windows-style box + handles) with optional aspect lock.
Widgets store the crop as percentages of the source (0–100).
"""

from nodes import PreviewImage

ASPECT_OPTIONS = [
    "free",
    "original",
    "1:1",
    "4:3",
    "3:2",
    "16:9",
    "3:4",
    "2:3",
    "9:16",
]


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


class LCImageCrop(PreviewImage):
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE", {
                    "tooltip": "Source image to crop.",
                }),
                "x": ("FLOAT", {
                    "default": 0.0,
                    "min": 0.0,
                    "max": 100.0,
                    "step": 0.1,
                    "tooltip": "Crop left edge as % of image width (0–100).",
                }),
                "y": ("FLOAT", {
                    "default": 0.0,
                    "min": 0.0,
                    "max": 100.0,
                    "step": 0.1,
                    "tooltip": "Crop top edge as % of image height (0–100).",
                }),
                "width": ("FLOAT", {
                    "default": 100.0,
                    "min": 0.5,
                    "max": 100.0,
                    "step": 0.1,
                    "tooltip": "Crop width as % of image width (0.5–100).",
                }),
                "height": ("FLOAT", {
                    "default": 100.0,
                    "min": 0.5,
                    "max": 100.0,
                    "step": 0.1,
                    "tooltip": "Crop height as % of image height (0.5–100).",
                }),
                "aspect": (ASPECT_OPTIONS, {
                    "default": "free",
                    "tooltip": "Lock crop aspect ratio. 'original' matches the source image.",
                }),
            },
            "hidden": {
                "unique_id": "UNIQUE_ID",
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "crop"
    CATEGORY = "LC123/image"
    DESCRIPTION = (
        "Interactive image crop with aspect-ratio lock and on-node preview."
    )
    OUTPUT_NODE = True
    DESCRIPTION = (
        "Windows-style interactive crop: drag the box and handles on the node. "
        "Optional aspect lock (free / original / common ratios). "
        "x,y,width,height are percentages of the source."
    )

    def crop(self, image, x, y, width, height, aspect="free", unique_id=None):
        _b, h, w, _c = image.shape

        x = _clamp(float(x), 0.0, 100.0)
        y = _clamp(float(y), 0.0, 100.0)
        width = _clamp(float(width), 0.5, 100.0)
        height = _clamp(float(height), 0.5, 100.0)

        if x + width > 100.0:
            width = 100.0 - x
        if y + height > 100.0:
            height = 100.0 - y

        x1 = int(round(w * (x / 100.0)))
        y1 = int(round(h * (y / 100.0)))
        x2 = int(round(w * ((x + width) / 100.0)))
        y2 = int(round(h * ((y + height) / 100.0)))

        x1 = _clamp(x1, 0, max(0, w - 1))
        y1 = _clamp(y1, 0, max(0, h - 1))
        x2 = _clamp(x2, x1 + 1, w)
        y2 = _clamp(y2, y1 + 1, h)

        cropped = image[:, y1:y2, x1:x2, :].contiguous()

        result = {"ui": {}, "result": (cropped,)}
        try:
            saved = self.save_images(image, filename_prefix="lc_crop_src")
            result["ui"]["lc_preview"] = saved["ui"]["images"]
            result["ui"]["src_size"] = [{"width": int(w), "height": int(h)}]
        except Exception:
            pass
        return result


NODE_CLASS_MAPPINGS = {
    "LCImageCrop": LCImageCrop,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LCImageCrop": "LC Image Crop 🖼️🔪",
}
