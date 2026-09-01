"""
LC Batch Image
--------------
Stack IMAGE sockets into one batch. Autogrow slots (chrome).
Missing / muted / empty sockets are skipped — a wired slot with no tensor
does not fail the node.
"""

from __future__ import annotations

import torch
import torch.nn.functional as F


MAX_INPUTS = 20


def _as_nchw_batch(v):
    """None / blocker / empty → None. Else IMAGE [B,H,W,C] float."""
    if v is None:
        return None
    name = type(v).__name__
    if name in ("ExecutionBlocker", "UnexecutedNodeException"):
        return None
    if isinstance(v, (list, tuple)):
        parts = []
        for x in v:
            b = _as_nchw_batch(x)
            if b is not None:
                parts.append(b)
        if not parts:
            return None
        return torch.cat(parts, dim=0)
    if not torch.is_tensor(v):
        return None
    t = v
    if t.ndim == 3:
        t = t.unsqueeze(0)
    if t.ndim != 4 or t.shape[0] == 0 or t.numel() == 0:
        return None
    return t


def _match(t: torch.Tensor, h: int, w: int, c: int) -> torch.Tensor:
    if t.shape[-1] != c:
        if t.shape[-1] == 1 and c == 3:
            t = t.repeat(1, 1, 1, 3)
        elif t.shape[-1] >= 3 and c == 3:
            t = t[..., :3]
        elif t.shape[-1] == 4 and c == 4:
            pass
        elif t.shape[-1] < c:
            pad = c - t.shape[-1]
            t = torch.cat([t, t[..., -1:].repeat(1, 1, 1, pad)], dim=-1)
        else:
            t = t[..., :c]
    if t.shape[1] != h or t.shape[2] != w:
        x = t.permute(0, 3, 1, 2).float()
        x = F.interpolate(x, size=(h, w), mode="bilinear", align_corners=False)
        t = x.permute(0, 2, 3, 1)
    return t


class LCBatchImage:
    @classmethod
    def INPUT_TYPES(cls):
        optional = {
            f"image_{i:02d}": (
                "IMAGE",
                {
                    "tooltip": "Skipped if disconnected, muted, or empty. Different sizes resize to the first live image.",
                },
            )
            for i in range(1, MAX_INPUTS + 1)
        }
        return {"required": {}, "optional": optional}

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "batch"
    CATEGORY = "LC123/image"
    DESCRIPTION = (
        "Batch images from autogrow slots. Wired sockets with no signal "
        "(muted / missing) are ignored. Bypass that still outputs an image is kept. "
        "Later slots are resized to the first live image."
    )

    def batch(self, **kwargs):
        batches = []
        for i in range(1, MAX_INPUTS + 1):
            t = _as_nchw_batch(kwargs.get(f"image_{i:02d}"))
            if t is not None:
                batches.append(t)
        if not batches:
            raise ValueError(
                "LC Batch Image: no images received. "
                "Every slot is empty, muted, or disconnected."
            )
        ref = batches[0]
        _, h, w, c = ref.shape
        device, dtype = ref.device, ref.dtype
        aligned = [_match(b.to(device=device, dtype=dtype), h, w, c) for b in batches]
        return (torch.cat(aligned, dim=0),)


NODE_CLASS_MAPPINGS = {"LCBatchImage": LCBatchImage}
NODE_DISPLAY_NAME_MAPPINGS = {"LCBatchImage": "LC Batch Image 🖼️"}
