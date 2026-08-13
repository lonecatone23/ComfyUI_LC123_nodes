"""
LC Positive / LC Negative
-------------------------
Simple multiline prompt boxes.
Default node colors are applied by web/lc_prompt_box.js
"""


class LCPositive:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "positive": ("STRING", {
                    "multiline": True,
                    "default": "",
                }),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("positive",)
    FUNCTION = "get"
    CATEGORY = "LC123/conditioning"
    DESCRIPTION = "Positive prompt text box."

    def get(self, positive):
        return (positive,)


class LCNegative:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "negative": ("STRING", {
                    "multiline": True,
                    "default": "",
                }),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("negative",)
    FUNCTION = "get"
    CATEGORY = "LC123/conditioning"
    DESCRIPTION = "Negative prompt text box."

    def get(self, negative):
        return (negative,)


NODE_CLASS_MAPPINGS = {
    "LCPositive": LCPositive,
    "LCNegative": LCNegative,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LCPositive": "Positive",
    "LCNegative": "Negative",
}
