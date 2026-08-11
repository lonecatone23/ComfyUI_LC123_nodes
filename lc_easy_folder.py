"""
LC Easy Folder
--------------
Builds a single filename_prefix string for native SaveImage.

Pattern (default):
  Folder/prefix_suffix_timestamp

Always appends the chosen path separator after Folder.
"""

import os
import re
from datetime import datetime


class AnyType(str):
    def __ne__(self, __value: object) -> bool:
        return False


any_type = AnyType("*")

TIMESTAMP_OPTIONS = [
    "none",
    "%Y-%m-%d",
    "%Y-%m-%d-%H%M%S",
    "%Y%m%d",
    "%Y%m%d_%H%M%S",
    "%Y-%m-%d_%H-%M-%S",
    "%H%M%S",
]

SEP_OPTIONS = [
    "auto",
    "backslash (Windows)",
    "slash (Linux/Mac)",
]


def _pick_sep(choice: str) -> str:
    if choice.startswith("backslash"):
        return "\\"
    if choice.startswith("slash"):
        return "/"
    # auto
    return "\\" if os.name == "nt" else "/"


def _sanitize(text: str, is_path_segment: bool = True) -> str:
    if text is None:
        return ""
    text = str(text).strip()
    # Strip existing trailing separators so we control them
    text = text.rstrip("\\/")
    # Illegal on Windows + common Unix trouble
    illegal = r'[<>:"|?*\x00-\x1f]'
    text = re.sub(illegal, "_", text)
    # Collapse runs of spaces/underscores from cleanup
    text = re.sub(r"[ _]{2,}", "_", text)
    return text


def _stamp(fmt: str) -> str:
    if not fmt or fmt == "none":
        return ""
    try:
        return datetime.now().strftime(fmt)
    except Exception:
        return datetime.now().strftime("%Y-%m-%d")


class LCEasyFolder:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "folder": ("STRING", {
                    "default": "Drafts",
                    "tooltip": "Base folder under the Comfy output directory. Separator is appended automatically.",
                }),
                "prefix": ("STRING", {
                    "default": "Test",
                    "tooltip": "Filename prefix.",
                }),
                "suffix": ("STRING", {
                    "default": "",
                    "tooltip": "Filename suffix (optional).",
                }),
                "timestamp": (TIMESTAMP_OPTIONS, {
                    "default": "%Y-%m-%d",
                    "tooltip": "Timestamp format appended to the name. Choose none to omit.",
                }),
                "path_separator": (SEP_OPTIONS, {
                    "default": "auto",
                    "tooltip": "Path separator style. auto uses the OS default.",
                }),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("filename_prefix",)
    FUNCTION = "build"
    CATEGORY = "LC123/io"
    DESCRIPTION = (
        "Builds a single filename_prefix for the native SaveImage node. "
        "Pattern: Folder/prefix_suffix_timestamp (separator auto). "
        "Creates the folder on disk if missing. Illegal characters are sanitized."
    )

    def build(self, folder, prefix, suffix, timestamp, path_separator):
        sep = _pick_sep(path_separator)
        folder = _sanitize(folder)
        prefix = _sanitize(prefix)
        suffix = _sanitize(suffix)
        ts = _stamp(timestamp)

        parts = [p for p in (prefix, suffix, ts) if p]
        name = "_".join(parts) if parts else "image"

        if folder:
            # Ensure folder exists under Comfy output dir
            try:
                import folder_paths
                out_root = folder_paths.get_output_directory()
                full = os.path.join(out_root, folder.replace("/", os.sep).replace("\\", os.sep))
                os.makedirs(full, exist_ok=True)
            except Exception:
                pass
            result = f"{folder}{sep}{name}"
        else:
            result = name

        return (result,)


NODE_CLASS_MAPPINGS = {
    "LCEasyFolder": LCEasyFolder,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LCEasyFolder": "LC Easy Folder 📂",
}
