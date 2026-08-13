"""
LC Get Image
------------
Read width, height, resolution (longer side), megapixels, batch, and aspect ratio from an IMAGE.
"""


def _aspect_label(w: int, h: int) -> str:
    """Return W:H with one decimal place each, normalized to shorter side = 1.0 scale."""
    if w <= 0 or h <= 0:
        return "0.0:0.0"
    m = float(min(w, h))
    aw = round(w / m, 1)
    ah = round(h / m, 1)
    return f"{aw:.1f}:{ah:.1f}"


class LCGetImage:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE", {
                    "tooltip": "Source image.",
                }),
            },
        }

    RETURN_TYPES = ("FLOAT", "INT", "INT", "INT", "INT", "STRING")
    RETURN_NAMES = ("megapixels", "width", "height", "resolution", "batch", "aspect ratio")
    FUNCTION = "get"
    CATEGORY = "LC123/image"
    OUTPUT_NODE = True
    DESCRIPTION = (
        "Reads resolution and batch size from an image. "
        "Outputs megapixels, width, height, resolution (longer side in pixels), "
        "batch, and aspect ratio (e.g. 1.0:1.2)."
    )

    def get(self, image):
        batch = int(image.shape[0])
        height = int(image.shape[1])
        width = int(image.shape[2])
        resolution = max(width, height)
        megapixels = round((width * height) / 1_000_000.0, 2)
        aspect = _aspect_label(width, height)
        text = (
            f"{megapixels:.2f} MP  |  {width} × {height}  |  res {resolution}  |  "
            f"{aspect}  |  batch {batch}"
        )
        return {
            "ui": {
                "text": [text],
                "lc_mp": [f"{megapixels:.2f}"],
                "lc_w": [str(width)],
                "lc_h": [str(height)],
                "lc_res": [str(resolution)],
                "lc_batch": [str(batch)],
                "lc_aspect": [aspect],
            },
            "result": (
                float(megapixels),
                width,
                height,
                resolution,
                batch,
                aspect,
            ),
        }


NODE_CLASS_MAPPINGS = {
    "LCGetImage": LCGetImage,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LCGetImage": "LC Get Image 📐",
}
