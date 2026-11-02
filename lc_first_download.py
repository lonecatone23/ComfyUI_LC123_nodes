"""First-use model download, the same in every LC pack (each pack carries its own copy of this file).

A gentle warning toast in the browser ("Downloading X (size) for first use. This may take several minutes. Press Stop to
cancel."), a progress bar on the node, and Stop cancels it with no half file left behind. The LC Model Optimizer does
NOT use this: its downloads stay on a click, since people rename files and use their own finetunes.
"""

from __future__ import annotations

import os
import urllib.request

CHUNK = 1 << 20


def _mb(n):
    if n >= 1e9:
        return f"{n / 1e9:.1f} GB"
    return f"{n / 1e6:.0f} MB" if n >= 1e6 else f"{max(1, round(n / 1e3))} KB"


def toast(label, size_text=""):
    """The browser toast only (for a download this file doesn't run itself)."""
    try:
        from server import PromptServer

        PromptServer.instance.send_sync("lc.download", {"label": label, "size": size_text})
    except Exception:
        pass  # no browser connected: the console line still says it


def hf_url(repo_id, filename, revision="main"):
    base = (os.environ.get("HF_ENDPOINT") or "https://huggingface.co").rstrip("/")  # a mirror (hf-mirror.com) still works
    return f"{base}/{repo_id}/resolve/{revision}/{filename}"


def download(url, dest, label, size_hint="", cancel=True, announce=True):
    """Download url to dest once. Raises on Stop (cancel=True) or a failed download, and leaves nothing behind.
    cancel=False for downloads started outside a run (a button's own thread): Stop belongs to the queue."""
    import comfy.model_management
    import comfy.utils

    os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
    part = dest + ".part"
    req = urllib.request.Request(url, headers={"User-Agent": "ComfyUI-LC"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r, open(part, "wb") as f:
            total = int(r.headers.get("Content-Length") or 0)
            size_text = _mb(total) if total else size_hint
            print(f"[LC] Downloading {label} ({size_text or 'unknown size'}) for first use -> {dest}")
            if announce:
                toast(label, size_text)
            bar = comfy.utils.ProgressBar(total or 1) if cancel else None  # outside a run there's no node to show it on
            got = 0
            while True:
                if cancel:
                    comfy.model_management.throw_exception_if_processing_interrupted()
                block = r.read(CHUNK)
                if not block:
                    break
                f.write(block)
                got += len(block)
                if total and bar:
                    bar.update_absolute(min(got, total), total)
        if total and got != total:
            raise IOError(f"download cut short ({_mb(got)} of {_mb(total)})")
        os.replace(part, dest)
    except BaseException:
        try:
            if os.path.exists(part):
                os.remove(part)
        except OSError:
            pass
        raise
    print(f"[LC] {label} downloaded.")
    return dest
