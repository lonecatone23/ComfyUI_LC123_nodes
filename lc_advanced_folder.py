"""
LC Advanced Folder
------------------
Builds separate path + filename for Image Saver Simple (and similar).

Typical tree:
  path:     metadata\\prefix_timestamp\\
  filename: prefix_suffix_timestamp
"""

import os
import re
from datetime import datetime


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
    return "\\" if os.name == "nt" else "/"


def _sanitize(text: str) -> str:
    if text is None:
        return ""
    text = str(text).strip()
    text = text.rstrip("\\/")
    illegal = r'[<>:"|?*\x00-\x1f]'
    text = re.sub(illegal, "_", text)
    text = re.sub(r"[ _]{2,}", "_", text)
    return text


def _stamp(fmt: str) -> str:
    if not fmt or fmt == "none":
        return ""
    try:
        return datetime.now().strftime(fmt)
    except Exception:
        return datetime.now().strftime("%Y-%m-%d")


class LCAdvancedFolder:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "folder": ("STRING", {
                    "default": "MetaData",
                    "tooltip": "Root folder / subfolder under the saver output path.",
                }),
                "prefix": ("STRING", {
                    "default": "Test",
                    "tooltip": "Used in both the path segment and the filename.",
                }),
                "suffix": ("STRING", {
                    "default": "",
                    "tooltip": "Filename suffix (optional).",
                }),
                "timestamp": (TIMESTAMP_OPTIONS, {
                    "default": "%Y-%m-%d",
                    "tooltip": "Timestamp format. Choose none to omit.",
                }),
                "path_separator": (SEP_OPTIONS, {
                    "default": "auto",
                    "tooltip": "Path separator style. auto uses the OS default.",
                }),
                "include_prefix_in_path": ("BOOLEAN", {
                    "default": True,
                    "label_on": "prefix in path",
                    "label_off": "folder only",
                    "tooltip": "ON: path = folder\\prefix_timestamp\\. OFF: path = folder\\",
                }),
            },
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("filename", "path")
    FUNCTION = "build"
    CATEGORY = "LC123/io"
    DESCRIPTION = (
        "Split filename + path outputs for Image Saver Simple style nodes. Optional prefix-in-path and timestamp format."
    )

    def build(self, folder, prefix, suffix, timestamp, path_separator, include_prefix_in_path=True):
        sep = _pick_sep(path_separator)
        folder = _sanitize(folder)
        prefix = _sanitize(prefix)
        suffix = _sanitize(suffix)
        ts = _stamp(timestamp)

        # filename: prefix_suffix_timestamp
        name_parts = [p for p in (prefix, suffix, ts) if p]
        filename = "_".join(name_parts) if name_parts else "image"

        # path: folder/  or  folder/prefix_timestamp/
        path_parts = []
        if folder:
            path_parts.append(folder)
        if include_prefix_in_path:
            seg = "_".join(p for p in (prefix, ts) if p)
            if seg:
                path_parts.append(seg)

        if path_parts:
            path = sep.join(path_parts) + sep
        else:
            path = ""

        # Create on disk under Comfy output (best-effort)
        if path:
            try:
                import folder_paths
                out_root = folder_paths.get_output_directory()
                full = os.path.join(out_root, path.replace("/", os.sep).replace("\\", os.sep))
                os.makedirs(full, exist_ok=True)
            except Exception:
                pass

        return (filename, path)


NODE_CLASS_MAPPINGS = {
    "LCAdvancedFolder": LCAdvancedFolder,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LCAdvancedFolder": "LC Advanced Folder 📂",
}
