"""
LC Gate 🚧
----------
Open: passes its input straight through. Closed: everything after it is skipped quietly (ComfyUI's ExecutionBlocker),
no error, and its input isn't even asked for, so a branch that only feeds the gate (a caption, an outpaint) never runs.
Unlike LC Stop, which ends the whole run, a closed gate skips just its own branch.
"""

from __future__ import annotations


class AnyType(str):
    def __ne__(self, __value: object) -> bool:
        return False


any_type = AnyType("*")


class LCGate:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "open": ("BOOLEAN", {"default": True, "label_on": "open", "label_off": "closed",
                                     "tooltip": "Open: the input passes through. Closed: every node after the gate is skipped "
                                                "quietly, and the nodes that only feed the gate don't run either."}),
            },
            "optional": {
                "input": (any_type, {"lazy": True, "tooltip": "Anything: an image, a latent, text, a model."}),
            },
        }

    RETURN_TYPES = (any_type,)
    RETURN_NAMES = ("output",)
    FUNCTION = "gate"
    CATEGORY = "LC123/utils"
    DESCRIPTION = ("Skips a branch: open passes the input through, closed skips everything after the gate quietly (no error) "
                   "and doesn't run what only feeds it. LC Stop ends the whole run; the gate skips just its branch.")

    def check_lazy_status(self, open, **kwargs):
        # closed: don't ask for the input, so its branch doesn't run
        if bool(open) and "input" in kwargs and kwargs["input"] is None:
            return ["input"]
        return []

    def gate(self, open, input=None):
        if bool(open):
            return (input,)
        from comfy_execution.graph import ExecutionBlocker
        return (ExecutionBlocker(None),)  # None message: the nodes after it are skipped without an error


NODE_CLASS_MAPPINGS = {"LCGate": LCGate}
NODE_DISPLAY_NAME_MAPPINGS = {"LCGate": "LC Gate 🚧"}
