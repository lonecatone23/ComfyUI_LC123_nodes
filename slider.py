"""
LC123 Slider — value on face; min/max/step/decimals via Settings.
Always snaps to step. decimals=0 → INT, else FLOAT.
"""


class AnyType(str):
    def __ne__(self, __value: object) -> bool:
        return False


any_type = AnyType("*")


def _snap(value: float, lo: float, hi: float, step: float) -> float:
    if lo > hi:
        lo, hi = hi, lo
    st = step if step and step > 0 else 1.0
    n = round((value - lo) / st)
    v = lo + n * st
    if v < lo:
        v = lo
    if v > hi:
        v = hi
    return v


class LC123Slider:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "value": (
                    "FLOAT",
                    {
                        "default": 20.0,
                        "min": -1e9,
                        "max": 1e9,
                        "step": 0.01,
                        "display": "slider",
                    },
                ),
                "min": (
                    "FLOAT",
                    {"default": 0.0, "min": -1e9, "max": 1e9, "step": 0.01},
                ),
                "max": (
                    "FLOAT",
                    {"default": 100.0, "min": -1e9, "max": 1e9, "step": 0.01},
                ),
                "step": (
                    "FLOAT",
                    {"default": 1.0, "min": 1e-6, "max": 1e9, "step": 0.01},
                ),
                "decimals": (
                    "INT",
                    {"default": 0, "min": 0, "max": 4, "step": 1},
                ),
            },
        }

    RETURN_TYPES = (any_type,)
    RETURN_NAMES = ("*",)
    FUNCTION = "main"
    CATEGORY = "LC123/utils"
    DESCRIPTION = (
        "Slider: value on the face. min / max / step / decimals via ⚙ Settings. "
        "Always snaps to step. decimals=0 → INT output; 1–4 → FLOAT."
    )

    def main(self, value, min, max, step, decimals):
        # NOTE: params named min/max shadow builtins — never call min()/max() here
        lo = float(min)
        hi = float(max)
        if lo > hi:
            lo, hi = hi, lo
        st = float(step) if float(step) > 0 else 1.0
        v = _snap(float(value), lo, hi, st)
        d = int(decimals)
        if d < 0:
            d = 0
        if d > 4:
            d = 4
        if d <= 0:
            return (int(round(v)),)
        rn = 10 ** d
        return (round(v * rn) / rn,)


NODE_CLASS_MAPPINGS = {
    "LC123Slider": LC123Slider,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LC123Slider": "🎚️ LC123 Slider",
}
