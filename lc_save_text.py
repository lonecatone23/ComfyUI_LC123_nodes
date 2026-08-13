"""LC123 Save Text — first file is bare name, then _01, _02, ... (2-digit).

Path segments are sanitized for Windows-illegal characters.
"""

import json
import os
import re

import folder_paths

# Windows-forbidden in file/folder names: < > : " / \ | ? *
# Also strip control chars and trailing dots/spaces (Windows rejects those).
_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_MULTI_UNDERSCORE = re.compile(r"_+")


def _sanitize_segment(name: str, fallback: str = "untitled") -> str:
    """Make a single path segment safe for Windows (and other OSes)."""
    if name is None:
        return fallback
    s = str(name).strip().replace("\r", " ").replace("\n", " ")
    s = _ILLEGAL.sub("_", s)
    # collapse runs of underscores/spaces mixed from replacements
    s = re.sub(r"[_\s]+", "_", s)
    s = s.strip(" ._")
    # Windows reserved device names
    reserved = {
        "CON", "PRN", "AUX", "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }
    if not s or s.upper() in reserved:
        return fallback
    # keep length reasonable
    if len(s) > 120:
        s = s[:120].rstrip(" ._")
    return s or fallback


def _sanitize_prefix(prefix: str) -> tuple[str, str]:
    """
    Split prefix into subfolder + stem, sanitize each segment.
    Returns (subfolder_relative, stem).
    """
    prefix = (prefix or "ComfyUI").replace("\\", "/")
    parts = [p for p in prefix.split("/") if p and p != "."]
    if not parts:
        return "", "ComfyUI"
    safe = [_sanitize_segment(p) for p in parts]
    stem = safe[-1]
    sub = "/".join(safe[:-1]) if len(safe) > 1 else ""
    return sub, stem


class LC123SaveText:
    """Save text with naming: prefix.ext, then prefix_01.ext, prefix_02.ext, ..."""

    FORMAT_EXTENSIONS = {
        "txt": "txt",
        "md": "md",
        "json": "json",
        "csv": "csv",
    }

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": ("STRING", {"forceInput": True}),
                "filename_prefix": (
                    "STRING",
                    {
                        "default": "ComfyUI",
                        "tooltip": "File name (and optional subfolders). Illegal path characters are replaced with _.",
                    },
                ),
                "format": (list(cls.FORMAT_EXTENSIONS.keys()), {"default": "txt"}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    FUNCTION = "save"
    CATEGORY = "LC123/utils"
    DESCRIPTION = (
        "Write a text string to a file under the output folder. Filename is sanitized for Windows-illegal characters."
    )
    OUTPUT_NODE = True

    def _next_path(self, folder, stem, extension):
        """
        First free name:
          stem.ext          (if missing)
          stem_01.ext
          stem_02.ext
          ...
        """
        bare = os.path.join(folder, f"{stem}.{extension}")
        if not os.path.exists(bare):
            return bare, f"{stem}.{extension}"

        pattern = re.compile(
            rf"^{re.escape(stem)}_(\d+)\.{re.escape(extension)}$",
            re.IGNORECASE,
        )
        max_n = 0
        try:
            for name in os.listdir(folder):
                m = pattern.match(name)
                if m:
                    max_n = max(max_n, int(m.group(1)))
        except OSError:
            pass

        n = max(1, max_n + 1)
        while True:
            filename = f"{stem}_{n:02d}.{extension}"
            path = os.path.join(folder, filename)
            if not os.path.exists(path):
                return path, filename
            n += 1

    def save(self, text, filename_prefix="ComfyUI", format="txt"):
        extension = self.FORMAT_EXTENSIONS.get(format)
        if extension is None:
            raise ValueError(f"Unsupported format: {format!r}")

        subfolder, stem = _sanitize_prefix(filename_prefix)

        output_dir = folder_paths.get_output_directory()
        full_folder = os.path.join(output_dir, subfolder) if subfolder else output_dir
        os.makedirs(full_folder, exist_ok=True)

        filepath, filename = self._next_path(full_folder, stem, extension)

        if extension == "json":
            try:
                data = json.loads(text)
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
            except (json.JSONDecodeError, TypeError):
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(text if text is not None else "")
        else:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(text if text is not None else "")

        return {
            "ui": {
                "text": (text if text is not None else "",),
            },
            "result": (text if text is not None else "",),
        }


NODE_CLASS_MAPPINGS = {
    "LC123SaveText": LC123SaveText,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LC123SaveText": "📝 LC Save Text",
}
