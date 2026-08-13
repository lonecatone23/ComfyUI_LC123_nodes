"""
LC Stop
-------
mxStop-style breakpoint with built-in enable/bypass.

  enable ON  (STOP)   → pass data through, then interrupt (same as mxStop)
  enable OFF (bypass) → pass data through, no interrupt

Continue by clicking the play button on the node title bar, or Queue again.
"""

import nodes


class AnyType(str):
    def __ne__(self, __value: object) -> bool:
        return False


any_type = AnyType("*")


class LCStop:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "In": (any_type,),
                "enable": ("BOOLEAN", {
                    "default": True,
                    "label_on": "STOP",
                    "label_off": "bypass",
                    "tooltip": "ON: stop here (mxStop behaviour). OFF: pass through without stopping.",
                }),
            },
        }

    @classmethod
    def VALIDATE_INPUTS(cls, **kwargs):
        return True

    RETURN_TYPES = (any_type,)
    RETURN_NAMES = ("Out",)
    FUNCTION = "main"
    CATEGORY = "LC123/utils"
    DESCRIPTION = (
        "Queue breakpoint with an enable switch. When enabled, stops until you continue from the queue/play control. Bypass/off passes data through without stopping."
    )

    def main(self, In, enable=True):
        out = In
        if enable:
            nodes.interrupt_processing()
        return (out,)


NODE_CLASS_MAPPINGS = {
    "LCStop": LCStop,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LCStop": "LC Stop 🛑",
}
