"""LC Seed Jump — one seed in, six seeds out stepped by a fixed jump."""


class LCSeedJump:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "seed": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 0xFFFFFFFFFFFFFFFF,
                        "forceInput": True,
                        "tooltip": "Base seed (a). Outputs are a, a+jump, a+2·jump, …",
                    },
                ),
                "jump": (
                    "INT",
                    {
                        "default": 1,
                        "min": 1,
                        "max": 20,
                        "step": 1,
                        "tooltip": "Step size (b). Each output adds this to the previous.",
                    },
                ),
            },
        }

    RETURN_TYPES = ("INT", "INT", "INT", "INT", "INT", "INT")
    RETURN_NAMES = ("seed_1", "seed_2", "seed_3", "seed_4", "seed_5", "seed_6")
    FUNCTION = "jump_seeds"
    CATEGORY = "LC123/utils"
    DESCRIPTION = (
        "Seed jump: input seed a and jump b (1–20). "
        "Outputs: a, a+b, a+2b, a+3b, a+4b, a+5b."
    )

    def jump_seeds(self, seed, jump=1):
        a = int(seed)
        b = max(1, min(20, int(jump)))
        out = tuple(a + i * b for i in range(6))
        return out


NODE_CLASS_MAPPINGS = {
    "LCSeedJump": LCSeedJump,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LCSeedJump": "LC Seed Jump 🌱",
}
