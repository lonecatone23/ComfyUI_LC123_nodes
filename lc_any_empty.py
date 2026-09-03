"""
LC Any Empty Bool / LC Any Empty Int
------------------------------------
Autogrow any_* sockets. Only plugged sockets count.
Mute (mode 2) or bypass (mode 4) on the source node = empty.
"""

from __future__ import annotations

MAX_SLOTS = 20


def _is_empty(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (bytes, bytearray)):
        return len(value) == 0
    if isinstance(value, dict):
        if not value:
            return True
        samples = value.get("samples")
        if samples is not None and _is_empty(samples):
            return True
        return False
    if isinstance(value, (list, tuple, set)):
        return len(value) == 0
    try:
        if hasattr(value, "numel"):
            n = int(value.numel())
            if n == 0:
                return True
            shape = getattr(value, "shape", None)
            if shape is not None and len(shape) > 0 and int(shape[0]) == 0:
                return True
            return False
    except Exception:
        pass
    return False


def _slot_name(i: int) -> str:
    return f"any_{i:02d}"


def _workflow_dead_slots(unique_id, extra_pnginfo) -> set[str]:
    """Slot names whose source node is muted (2) or bypassed (4)."""
    dead = set()
    if unique_id is None or not isinstance(extra_pnginfo, dict):
        return dead
    wf = extra_pnginfo.get("workflow")
    if not isinstance(wf, dict):
        return dead
    try:
        my_id = int(unique_id)
    except (TypeError, ValueError):
        return dead
    nodes = {int(n["id"]): n for n in wf.get("nodes") or [] if isinstance(n, dict) and "id" in n}
    me = nodes.get(my_id)
    if not me:
        return dead
    links_by_id = {}
    for row in wf.get("links") or []:
        if isinstance(row, (list, tuple)) and len(row) >= 5:
            links_by_id[row[0]] = row
    for inp in me.get("inputs") or []:
        if not isinstance(inp, dict):
            continue
        name = str(inp.get("name") or "")
        if not name.startswith("any_"):
            continue
        lid = inp.get("link")
        if lid is None:
            continue
        row = links_by_id.get(lid)
        if not row:
            continue
        src_id = row[1]
        src = nodes.get(int(src_id)) if src_id is not None else None
        if src is not None and src.get("mode") in (2, 4):
            dead.add(name)
    return dead


def _plugged_empty(kwargs, unique_id=None, extra_pnginfo=None) -> bool:
    dead = _workflow_dead_slots(unique_id, extra_pnginfo)
    saw = False
    for i in range(1, MAX_SLOTS + 1):
        key = _slot_name(i)
        if key not in kwargs:
            continue
        saw = True
        if key in dead or _is_empty(kwargs.get(key)):
            return True
    # also accept legacy single "any"
    if "any" in kwargs:
        saw = True
        if _is_empty(kwargs.get("any")):
            return True
    if not saw:
        return True
    return False


def _any_slots():
    return {
        _slot_name(i): ("*", {"tooltip": "Any type. Unplugged slots are ignored."})
        for i in range(1, MAX_SLOTS + 1)
    }


class LCAnyEmptyBool:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {},
            "optional": _any_slots(),
            "hidden": {
                "unique_id": "UNIQUE_ID",
                "extra_pnginfo": "EXTRA_PNGINFO",
            },
        }

    RETURN_TYPES = ("BOOLEAN",)
    RETURN_NAMES = ("empty",)
    FUNCTION = "check"
    CATEGORY = "LC123/utils"
    DESCRIPTION = (
        "Autogrow any_* sockets. Only plugged wires count. "
        "True if any plugged source is empty, muted, or bypassed."
    )

    def check(self, unique_id=None, extra_pnginfo=None, **kwargs):
        return (_plugged_empty(kwargs, unique_id, extra_pnginfo),)


class LCAnyEmptyInt:
    @classmethod
    def INPUT_TYPES(cls):
        optional = _any_slots()
        return {
            "required": {
                "empty": (
                    "INT",
                    {
                        "default": 0,
                        "min": -0x7FFFFFFF,
                        "max": 0x7FFFFFFF,
                        "tooltip": "Returned when any plugged source is empty / muted / bypassed.",
                    },
                ),
                "not_empty": (
                    "INT",
                    {
                        "default": 1,
                        "min": -0x7FFFFFFF,
                        "max": 0x7FFFFFFF,
                        "tooltip": "Returned when every plugged source has a live value.",
                    },
                ),
            },
            "optional": optional,
            "hidden": {
                "unique_id": "UNIQUE_ID",
                "extra_pnginfo": "EXTRA_PNGINFO",
            },
        }

    RETURN_TYPES = ("INT",)
    RETURN_NAMES = ("int",)
    FUNCTION = "check"
    CATEGORY = "LC123/utils"
    DESCRIPTION = (
        "Same multi-socket empty test as Any Empty Bool. "
        "Returns empty / not_empty integers."
    )

    def check(self, empty=0, not_empty=1, unique_id=None, extra_pnginfo=None, **kwargs):
        is_empty = _plugged_empty(kwargs, unique_id, extra_pnginfo)
        return (int(empty) if is_empty else int(not_empty),)



class LCAnyEmptyFloat:
    @classmethod
    def INPUT_TYPES(cls):
        optional = _any_slots()
        return {
            "required": {
                "empty": (
                    "FLOAT",
                    {
                        "default": 0.00,
                        "min": -1e9,
                        "max": 1e9,
                        "step": 0.01,
                        "round": 0.01,
                        "tooltip": "Returned when any plugged source is empty / muted / bypassed.",
                    },
                ),
                "not_empty": (
                    "FLOAT",
                    {
                        "default": 1.00,
                        "min": -1e9,
                        "max": 1e9,
                        "step": 0.01,
                        "round": 0.01,
                        "tooltip": "Returned when every plugged source has a live value.",
                    },
                ),
            },
            "optional": optional,
            "hidden": {
                "unique_id": "UNIQUE_ID",
                "extra_pnginfo": "EXTRA_PNGINFO",
            },
        }

    RETURN_TYPES = ("FLOAT",)
    RETURN_NAMES = ("float",)
    FUNCTION = "check"
    CATEGORY = "LC123/utils"
    DESCRIPTION = (
        "Same multi-socket empty test as Any Empty Int. "
        "Returns empty / not_empty floats (2 decimal places)."
    )

    def check(self, empty=0.0, not_empty=1.0, unique_id=None, extra_pnginfo=None, **kwargs):
        is_empty = _plugged_empty(kwargs, unique_id, extra_pnginfo)
        val = float(empty) if is_empty else float(not_empty)
        return (round(val, 2),)


NODE_CLASS_MAPPINGS = {
    "LCAnyEmptyBool": LCAnyEmptyBool,
    "LCAnyEmptyInt": LCAnyEmptyInt,
    "LCAnyEmptyFloat": LCAnyEmptyFloat,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "LCAnyEmptyBool": "LC Any Empty Bool",
    "LCAnyEmptyInt": "LC Any Empty Int",
    "LCAnyEmptyFloat": "LC Any Empty Float",
}
