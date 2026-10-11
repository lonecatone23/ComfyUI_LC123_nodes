"""
LC Last Image Holder
--------------------
Standalone node that holds and displays the last generated image.

- Shows the held image on the node at all times (once stored)
- Keeps the image even when the input is disconnected or null
- Single temp file per node ID (overwritten, no buildup)
- Clear via API route (no full workflow re-run)
- Guards against double-execution in a single queue so the hold
  survives when a comparer (or any downstream) is connected
- "hold until seed change" keeps the image of the current seed (seed socket)
  and stores a new one when the seed changes
"""

import os
import folder_paths
import torch
import numpy as np
from PIL import Image
from nodes import PreviewImage

# ---------------------------------------------------------------------------
# Per-process guard: only write the store once per prompt per node
# ---------------------------------------------------------------------------
_last_write_prompt = {}


def _current_prompt_id():
    """Id of the prompt being executed, or None if the server does not expose it."""
    try:
        from server import PromptServer
        pid = getattr(PromptServer.instance, "last_prompt_id", None)
        return ("prompt_id", pid) if pid else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Temp file helpers
# ---------------------------------------------------------------------------

def _temp_dir():
    d = os.path.join(folder_paths.get_temp_directory(), "lc_last_image_holder")
    os.makedirs(d, exist_ok=True)
    return d


def _path_for_node(unique_id: str) -> str:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in str(unique_id))
    return os.path.join(_temp_dir(), f"held_{safe}.png")


def _tensor_to_pil(img_tensor):
    t = img_tensor[0] if img_tensor.ndim == 4 else img_tensor
    arr = (t.detach().cpu().numpy() * 255.0).clip(0, 255).astype(np.uint8)
    return Image.fromarray(arr)


def _pil_to_tensor(pil_img):
    arr = np.array(pil_img.convert("RGB")).astype(np.float32) / 255.0
    return torch.from_numpy(arr)[None, ...]


def _load_held(path):
    if not os.path.isfile(path):
        return None
    try:
        return _pil_to_tensor(Image.open(path))
    except Exception:
        return None


def _seed_path(path):
    return path[:-4] + ".seed"


def _read_seed(path):
    try:
        with open(_seed_path(path), encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return None


def _write_seed(path, seed):
    with open(_seed_path(path), "w", encoding="utf-8") as f:
        f.write(str(seed))


def _delete_held(path):
    if os.path.isfile(_seed_path(path)):
        try:
            os.remove(_seed_path(path))
        except OSError:
            pass
    if os.path.isfile(path):
        try:
            os.remove(path)
            return True
        except OSError:
            return False
    return False


# ---------------------------------------------------------------------------
# Custom API route — Clear without re-running the workflow
# ---------------------------------------------------------------------------

try:
    from server import PromptServer
    from aiohttp import web

    @PromptServer.instance.routes.post("/lc123/last_image_holder/clear")
    async def lc_clear_held(request):
        data = await request.json()
        uid = str(data.get("node_id", ""))
        if not uid:
            return web.json_response({"ok": False, "error": "missing node_id"}, status=400)
        path = _path_for_node(uid)
        deleted = _delete_held(path)
        _last_write_prompt.pop(uid, None)
        return web.json_response({"ok": True, "deleted": deleted})

except Exception as e:
    print(f"[LC123] Last Image Holder: API route not registered yet ({e})")


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

class LCLastImageHolder(PreviewImage):
    """Hold and display the previous generation. Works with or without input."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "mode": (
                    ["hold previous generation", "hold until cleared", "hold until seed change"],
                    {
                        "default": "hold previous generation",
                        "tooltip": (
                            "hold previous generation: every generation outputs the previous "
                            "image, then stores the current one.\n"
                            "hold until cleared: stores the first image and freezes "
                            "until you press Clear.\n"
                            "hold until seed change: keeps the image from the current seed "
                            "(wire the seed socket) and stores a new one when the seed changes. "
                            "Tweak settings on one seed and compare against its first image."
                        ),
                    },
                ),
            },
            "optional": {
                "new_image": (
                    "IMAGE",
                    {
                        "tooltip": (
                            "Optional. Current generation to store. "
                            "The node keeps and displays the held image even when this "
                            "input is disconnected or empty."
                        ),
                    },
                ),
                "seed": (
                    "INT",
                    {
                        "forceInput": True,
                        "tooltip": (
                            "For hold until seed change: wire the same seed your sampler uses. "
                            "A new seed replaces the held image."
                        ),
                    },
                ),
            },
            "hidden": {
                "unique_id": "UNIQUE_ID",
                "prompt": "PROMPT",
                "extra_pnginfo": "EXTRA_PNGINFO",
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("held image",)
    FUNCTION = "hold"
    CATEGORY = "LC123/image"
    OUTPUT_NODE = True
    DESCRIPTION = (
        "Hold the last generated image for before/after. Survives disconnect; clear empties memory without re-running."
    )

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")

    def hold(
        self,
        mode="hold previous generation",
        new_image=None,
        seed=None,
        unique_id="0",
        prompt=None,
        extra_pnginfo=None,
    ):
        uid = str(unique_id)
        path = _path_for_node(uid)

        previous = _load_held(path)
        has_stored = previous is not None

        prompt_key = _current_prompt_id()
        if prompt_key is None:
            # fallback: id() of the prompt dict (can repeat once the old dict is freed)
            prompt_key = id(prompt) if prompt is not None else None
        already_wrote_this_prompt = (
            prompt_key is not None and _last_write_prompt.get(uid) == prompt_key
        )

        if new_image is not None and not already_wrote_this_prompt:
            if mode == "hold previous generation":
                _tensor_to_pil(new_image).save(path)
                if prompt_key is not None:
                    _last_write_prompt[uid] = prompt_key

            elif mode == "hold until seed change":
                if seed is None:
                    print("[LC Last Image Holder] hold until seed change: no seed wired, holding until cleared")
                if not has_stored or (seed is not None and _read_seed(path) != str(seed)):
                    _tensor_to_pil(new_image).save(path)
                    _write_seed(path, "" if seed is None else seed)
                    previous = None
                    if prompt_key is not None:
                        _last_write_prompt[uid] = prompt_key

            elif mode == "hold until cleared":
                if not has_stored:
                    _tensor_to_pil(new_image).save(path)
                    previous = None
                    if prompt_key is not None:
                        _last_write_prompt[uid] = prompt_key

        out = previous if previous is not None else new_image

        result = {"ui": {"images": []}, "result": (None,)}

        if out is not None:
            saved = self.save_images(
                out,
                filename_prefix=f"lc.held.{uid}.",
                prompt=prompt,
                extra_pnginfo=extra_pnginfo,
            )
            result["ui"]["images"] = saved["ui"]["images"]
            result["result"] = (out,)
        else:
            blank = torch.zeros(1, 64, 64, 3)
            result["result"] = (blank,)

        return result


NODE_CLASS_MAPPINGS = {
    "LCLastImageHolder": LCLastImageHolder,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LCLastImageHolder": "LC Last Image Holder",
}
