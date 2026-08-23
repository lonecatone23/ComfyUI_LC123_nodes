"""
LC Custom Combo — inputcount option slots + choice dropdown → STRING + INDEX.
"""

from __future__ import annotations


class AnyType(str):
    def __ne__(self, __value: object) -> bool:
        return False


any_type = AnyType("*")


class LCCustomCombo:
    @classmethod
    def INPUT_TYPES(cls):
        options = {
            f"option_{i:02d}": ("STRING", {"default": "", "multiline": False})
            for i in range(1, 21)
        }
        return {
            "required": {
                "inputcount": (
                    "INT",
                    {"default": 2, "min": 2, "max": 20, "step": 1},
                ),
                "choice": (
                    "STRING",
                    {"default": "", "multiline": False},
                ),
            },
            "optional": options,
        }

    RETURN_TYPES = ("STRING", "INT", any_type)
    RETURN_NAMES = ("STRING", "INDEX", "OPT_CONNECTION")
    FUNCTION = "select"
    CATEGORY = "LC123/utils"
    DESCRIPTION = "Option slots + choice → STRING + INDEX. OPT_CONNECTION → panel."

    def select(self, inputcount: int, choice: str, **kwargs):
        n = max(2, min(20, int(inputcount)))
        filled = []
        for i in range(1, n + 1):
            s = str(kwargs.get(f"option_{i:02d}") or "").strip()
            if s:
                filled.append(s)
        if not filled:
            return ("", 0, None)
        c = str(choice or "").strip()
        idx = filled.index(c) if c in filled else 0
        return (filled[idx], int(idx), None)


class LCCustomComboPanel:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {},
            "optional": {"hub": (any_type, {})},
        }

    RETURN_TYPES = ()
    FUNCTION = "noop"
    CATEGORY = "LC123/utils"
    OUTPUT_NODE = True
    DESCRIPTION = "Choice remote for LC Custom Combo."

    def noop(self, hub=None):
        return ()


NODE_CLASS_MAPPINGS = {
    "LCCustomCombo": LCCustomCombo,
    "LCCustomComboPanel": LCCustomComboPanel,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "LCCustomCombo": "LC Custom Combo",
    "LCCustomComboPanel": "LC Custom Combo Panel",
}
