"""
Copy sample LUTs from pack assets/luts → ComfyUI/models/luts.
- Creates models/luts if missing
- Never overwrites an existing file with the same name
- Runs on every pack import (update-safe: new files appear, user files kept)
"""

from __future__ import annotations

import os
import shutil


def install_sample_luts() -> None:
    try:
        import folder_paths
    except Exception as e:
        print(f"[LC123] LUT install: folder_paths unavailable ({e})")
        return

    pack_dir = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.join(pack_dir, "assets", "luts")
    if not os.path.isdir(src_dir):
        return

    try:
        dst_dir = os.path.join(folder_paths.models_dir, "luts")
    except Exception:
        # fallback relative to Comfy root if needed
        dst_dir = os.path.join(os.path.dirname(folder_paths.models_dir), "models", "luts")

    try:
        os.makedirs(dst_dir, exist_ok=True)
    except Exception as e:
        print(f"[LC123] LUT install: could not create {dst_dir}: {e}")
        return

    copied = 0
    skipped = 0
    for name in os.listdir(src_dir):
        if name.startswith("."):
            continue
        low = name.lower()
        if not (low.endswith(".cube") or low.endswith(".3dl")):
            continue
        src = os.path.join(src_dir, name)
        if not os.path.isfile(src):
            continue
        dst = os.path.join(dst_dir, name)
        if os.path.exists(dst):
            skipped += 1
            continue
        try:
            shutil.copy2(src, dst)
            copied += 1
        except Exception as e:
            print(f"[LC123] LUT install: failed {name}: {e}")

    if copied or skipped:
        print(
            f"[LC123] LUTs → {dst_dir}: "
            f"{copied} new file(s) copied, {skipped} existing skipped (no overwrite)"
        )


# run on import
try:
    install_sample_luts()
except Exception as e:
    print(f"[LC123] LUT install error: {e}")
