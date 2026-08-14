"""
LC Notify 🔊
------------
Play a sound when the node executes. Preview via on-node ▶ button (JS).
Files live in this pack's ``assets/sounds/`` folder.
"""

from __future__ import annotations

import os

_ASSETS_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), "assets")
_SOUNDS_DIR = os.path.join(_ASSETS_DIR, "sounds")

# Serve assets/sounds over HTTP for the browser player
try:
    from aiohttp import web
    from server import PromptServer

    @PromptServer.instance.routes.get("/lc123/sounds/{filename}")
    async def _lc123_serve_sound(request):
        name = request.match_info.get("filename", "")
        name = os.path.basename(name)
        path = os.path.join(_SOUNDS_DIR, name)
        if not os.path.isfile(path):
            return web.Response(status=404, text="sound not found")
        return web.FileResponse(path)

except Exception:
    pass


def _list_sounds():
    files = []
    if os.path.isdir(_SOUNDS_DIR):
        for name in sorted(os.listdir(_SOUNDS_DIR)):
            low = name.lower()
            if low.endswith((".mp3", ".wav", ".ogg", ".m4a", ".flac")):
                files.append(name)
    if not files:
        files = ["notify.mp3"]
    return files


class LCNotify:
    @classmethod
    def INPUT_TYPES(cls):
        sounds = _list_sounds()
        return {
            "required": {
                "mode": (
                    ["always", "on empty queue"],
                    {
                        "default": "always",
                        "tooltip": "always = every run. on empty queue = only when the queue is empty afterward.",
                    },
                ),
                "volume": (
                    "FLOAT",
                    {
                        "default": 0.5,
                        "min": 0.0,
                        "max": 1.0,
                        "step": 0.05,
                        "tooltip": "Playback volume (0–1).",
                    },
                ),
                "file": (
                    sounds,
                    {
                        "default": sounds[0],
                        "tooltip": "Sound file from assets/sounds/.",
                    },
                ),
            },
            "optional": {
                "any": (
                    "*",
                    {
                        "tooltip": "Optional pass-through so the node sits in your graph order.",
                    },
                ),
            },
        }

    RETURN_TYPES = ("*",)
    RETURN_NAMES = ("any",)
    FUNCTION = "notify"
    CATEGORY = "LC123/utils"
    OUTPUT_NODE = True
    DESCRIPTION = (
        "Play a sound from assets/sounds when the node runs. "
        "▶ on the node previews the selected file. "
        "Mode: always or on empty queue."
    )

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")

    def notify(self, mode="always", volume=0.5, file="notify.mp3", any=None):
        return {
            "ui": {
                "mode": [mode],
                "volume": [volume],
                "file": [file],
            },
            "result": (any,),
        }


NODE_CLASS_MAPPINGS = {
    "LCNotify": LCNotify,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LCNotify": "LC Notify 🔊",
}
