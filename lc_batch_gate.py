"""
LC Batch Gate 🚦 + LC Preview Gate 🛑
-------------------------------------
A look before the long run. For batches: Smart Prompt Batch prompts, a character dataset, any list or picture batch.

  LC Batch Gate (before the cheap first pass): the preview run lets only the first `preview` items through.
  LC Preview Gate (after the cheap first pass): shows the pictures on the node and stops the run, like LC Stop.
    Click a picture to drop it. ▶ Continue (or Run) carries on with every item except the dropped ones.

The phase and the dropped items never sit in the workflow: the continue run writes them into the queued prompt
(web/lc_batch_gate.js), and LC Continue (web/lc_continue.js) hands back every seed the last run used, so the
first items come out exactly as previewed. The hidden `phase` / `drop` widgets only carry those values.
"""

import time

import nodes
import torch


class AnyType(str):
    def __ne__(self, __value: object) -> bool:
        return False


any_type = AnyType("*")
MAX_SHOWN = 64  # pictures shown on the Preview Gate (a whole dataset at the end of a run)
# what each Preview Gate showed in its last preview (pictures + the `also` values, per list item), so the full run can
# put the kept ones back in front instead of rendering them again. Keyed by the Preview Gate's node id.
STORE: dict = {}


def _first(v, default=None):
    return v[0] if isinstance(v, list) and v else (default if isinstance(v, list) else v)


def _drop_set(text):
    out = set()
    for part in str(text or "").replace(";", ",").split(","):
        part = part.strip()
        if part.isdigit():
            out.add(int(part))
    return out


def _split_batch(item):
    """One picture batch / mask batch / latent batch as its single elements, or None when it is not a batch."""
    if torch.is_tensor(item) and item.ndim >= 3 and item.shape[0] > 1:
        return [item[i:i + 1] for i in range(item.shape[0])], lambda parts: torch.cat(parts, 0)
    if isinstance(item, dict) and torch.is_tensor(item.get("samples")) and item["samples"].shape[0] > 1:
        s = item["samples"]

        def join(parts):
            return {**item, "samples": torch.cat([p["samples"] for p in parts], 0)}
        return [{**item, "samples": s[i:i + 1]} for i in range(s.shape[0])], join
    return None


class LCBatchGate:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "items": (any_type, {"tooltip": "The list (Smart Prompt Batch prompts, dataset rows) or the picture batch, "
                                                "before the cheap first pass."}),
                "preview": ("INT", {"default": 4, "min": 1, "max": 64,
                                    "tooltip": "How many items the preview run lets through. After ▶ on LC Preview Gate, "
                                               "all of them go (minus the ones you dropped)."}),
                "phase": ("STRING", {"default": "preview", "tooltip": "Set by LC Preview Gate's ▶. Leave it."}),
                "drop": ("STRING", {"default": "", "tooltip": "Set by LC Preview Gate's ▶. Leave it."}),
            },
        }

    @classmethod
    def VALIDATE_INPUTS(cls, **kwargs):
        return True

    INPUT_IS_LIST = True
    RETURN_TYPES = (any_type,)
    RETURN_NAMES = ("items",)
    OUTPUT_IS_LIST = (True,)
    FUNCTION = "main"
    CATEGORY = "LC123/utils"
    DESCRIPTION = ("Put it before the cheap first pass of a batch. The preview run lets only the first `preview` items "
                   "through, so LC Preview Gate can show them fast. ▶ on LC Preview Gate then runs them all, minus the "
                   "ones you dropped.")

    def main(self, items, preview, phase, drop):
        n = int(_first(preview, 4))
        ph = str(_first(phase, "preview"))
        full = ph.startswith("all")
        gate = ph.split(":", 1)[1] if ":" in ph else ""
        dropped = _drop_set(_first(drop, ""))
        items = list(items or [])
        split = _split_batch(items[0]) if len(items) == 1 else None
        seq, join = split if split else (items, None)
        stored = STORE.get(gate) if full and gate else None
        if stored and stored["mode"] == "list" and not join and stored["n"] <= len(seq):
            # the previewed items are kept by LC Preview Gate: only the rest renders now
            picked = seq[stored["n"]:]
            print(f"[LC Batch Gate] full run: {len(picked)} new item(s) after the {stored['n']} previewed")
            return (picked,)
        # a picture / latent batch keeps every position in the full run: its noise is drawn by position, so taking one
        # out would shift the rest onto other noise. LC Preview Gate drops those after the cheap pass instead.
        if join:
            dropped = set()
        keep = [i for i in range(len(seq)) if (i not in dropped)] if full else list(range(min(n, len(seq))))
        if not keep:
            raise ValueError("[LC Batch Gate] every item was dropped: keep at least one, or just don't press ▶.")
        picked = [seq[i] for i in keep]
        print(f"[LC Batch Gate] {'full run' if full else 'preview'}: {len(picked)} of {len(seq)} items"
              + (f" ({len(dropped)} dropped)" if full and dropped else ""))
        return ([join(picked)] if join else picked,)


class LCPreviewGate:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE", {"tooltip": "The pictures of the cheap first pass."}),
                "enable": ("BOOLEAN", {"default": True, "label_on": "STOP", "label_off": "bypass",
                                       "tooltip": "ON: show the pictures and stop. OFF: pass through without stopping."}),
                "phase": ("STRING", {"default": "preview", "tooltip": "Set by ▶. Leave it."}),
                "drop": ("STRING", {"default": "", "tooltip": "Set by ▶. Leave it."}),
            },
            "optional": {
                "also": (any_type, {"tooltip": "Anything else per picture that must wait for ▶ too: the caption text of a "
                                               "dataset, so no caption file is written in the preview run."}),
                "also_2": (any_type, {"tooltip": "One more, like also: the save metadata of each picture."}),
                "also_3": (any_type, {"tooltip": "One more, like also."}),
                "note": (any_type, {"tooltip": "A short note per picture, written on its thumbnail: the score from LC "
                                               "Face Match or the note from LC Vision Reviewer. A note with ❌ puts a "
                                               "red ✕ in the corner: a likely drop. Nothing is dropped until you click."}),
                "note_2": (any_type, {"tooltip": "A second note per picture, like note."}),
            },
            "hidden": {"unique_id": "UNIQUE_ID"},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, **kwargs):
        return True

    @classmethod
    def IS_CHANGED(cls, phase=None, enable=None, **kwargs):
        # a preview always runs the gate: from the cache it would neither show nor stop, and the saves below would run
        # (Clear, then Run with nothing changed). A full run or a bypass may come from the cache.
        ph = phase[0] if isinstance(phase, list) and phase else phase
        on = enable[0] if isinstance(enable, list) and enable else enable
        return float("nan") if (on is not False and not str(ph or "preview").startswith("all")) else str(ph)

    INPUT_IS_LIST = True
    RETURN_TYPES = ("IMAGE", any_type, any_type, any_type)
    RETURN_NAMES = ("images", "also", "also_2", "also_3")
    OUTPUT_IS_LIST = (True, True, True, True)
    OUTPUT_NODE = True
    FUNCTION = "main"
    CATEGORY = "LC123/utils"
    DESCRIPTION = ("Shows the cheap first pass and stops the run there, like LC Stop. Click a picture to drop it, then "
                   "▶ Continue (or Run) runs the rest with the same seeds. With LC Batch Gate above, the preview only "
                   "renders its first items and the dropped ones never reach the long stages.")

    def main(self, images, enable, phase, drop, also=None, also_2=None, also_3=None, note=None, note_2=None,
             unique_id=None):
        images = list(images or [])
        extra = [list(a) if a is not None else [None] for a in (also, also_2, also_3)]
        gid = str(_first(unique_id, "") or "")
        on = bool(_first(enable, True))
        ph = str(_first(phase, "preview"))
        full = ph.startswith("all")
        passed = {"ui": {"lc_gate": [{"state": "passed"}]}}
        if not on or full:
            dropped = _drop_set(_first(drop, "")) if full else set()
            stored = STORE.pop(gid, None) if full else None
            if ph == "all:stored" and stored and stored["mode"] == "list":
                # the kept previews go back in front of the new pictures, each with its own also values
                keep = [i for i in range(stored["n"]) if not all(f in dropped for f in stored["frames"][i])]
                out = [stored["images"][i] for i in keep] + images
                ext = []
                for k, a in enumerate(extra):
                    old = stored["also"][k]
                    ext.append([old[i] for i in keep if i < len(old)] + a if old is not None and a != [None] else a)
                print(f"[LC Preview Gate] full run: {len(keep)} kept preview(s) + {len(images)} new")
                return {**passed, "result": (out, *ext)}
            if dropped and len(images) == 1 and images[0].shape[0] > 1 and (ph == "all" or (stored and stored["mode"] == "batch")):
                # one picture batch, rendered whole (its noise is by position): drop the pictures here
                batch = images[0]
                keep = [i for i in range(batch.shape[0]) if i not in dropped]
                if not keep:
                    raise ValueError("[LC Preview Gate] every picture was dropped: keep at least one, or just don't press ▶.")
                return {**passed, "result": ([batch[keep]], *extra)}
            if dropped and ph == "all":
                # no LC Batch Gate above: the whole list was rendered, drop by picture number
                out, k, ext_keep = [], 0, []
                for idx, batch in enumerate(images):
                    keep = [i for i in range(batch.shape[0]) if (k + i) not in dropped]
                    k += batch.shape[0]
                    if keep:
                        out.append(batch[keep])
                        ext_keep.append(idx)
                if not out:
                    raise ValueError("[LC Preview Gate] every picture was dropped: keep at least one, or just don't press ▶.")
                ext = [[a[i] for i in ext_keep if i < len(a)] if a != [None] else a for a in extra]
                return {**passed, "result": (out, *ext)}
            return {**passed, "result": (images, *extra)}

        frames, owner, per_item = [], [], []
        for idx, batch in enumerate(images):
            mine = []
            for f in range(batch.shape[0]):
                mine.append(len(owner))
                owner.append(idx)
                if len(frames) < MAX_SHOWN:
                    frames.append(batch[f:f + 1])
            per_item.append(mine)
        STORE[gid] = {"mode": "batch" if len(images) == 1 and images[0].shape[0] > 1 else "list", "n": len(images),
                      "images": images, "frames": per_item, "also": [None if a == [None] else a for a in extra]}
        shown = _save_frames(frames)
        nodes.interrupt_processing()
        print(f"[LC Preview Gate] stopped with {len(owner)} picture(s): look, drop the bad ones, then ▶ to run the rest")
        # one note per shown picture: the notes of its list item (a single batch: one note per picture)
        notes = []
        for k in range(len(shown)):
            idx = owner[k] if len(images) > 1 else k
            notes.append("\n".join(t for t in (_note_at(note, idx), _note_at(note_2, idx)) if t))
        # a fresh stamp per stop (LC Continue): the next queue is a continue with the same seeds
        return {"ui": {"lc_hold": [time.time()],
                       "lc_gate": [{"state": "stopped", "images": shown, "owner": owner[:len(shown)], "total": len(owner),
                                    "notes": notes}]},
                "result": (images, *extra)}


def _save_frames(frames):
    """The shown thumbnails as temp files. Pictures of different sizes (a list) go one by one."""
    if not frames:
        return []
    if all(f.shape[1:] == frames[0].shape[1:] for f in frames):
        return nodes.PreviewImage().save_images(torch.cat(frames, 0), filename_prefix="LC_gate")["ui"]["images"]
    out = []
    for f in frames:
        out += nodes.PreviewImage().save_images(f, filename_prefix="LC_gate")["ui"]["images"]
    return out


def _note_at(v, i):
    """The note of list item i as one short line ('' when there is none)."""
    if v is None:
        return ""
    v = list(v) if isinstance(v, (list, tuple)) else [v]
    if not v:
        return ""
    x = v[i] if i < len(v) else (v[0] if len(v) == 1 else None)
    if isinstance(x, (list, tuple)):
        x = x[0] if x else None
    if isinstance(x, bool):
        return "✅" if x else "❌"
    if isinstance(x, float):
        return f"{x:.2f}"
    if isinstance(x, (str, int)):
        return str(x).strip()[:160]
    # anything else (a picture passed through when the scorer is bypassed): no note
    return ""


NODE_CLASS_MAPPINGS = {"LCBatchGate": LCBatchGate, "LCPreviewGate": LCPreviewGate}
NODE_DISPLAY_NAME_MAPPINGS = {"LCBatchGate": "LC Batch Gate 🚦", "LCPreviewGate": "LC Preview Gate 🛑"}
