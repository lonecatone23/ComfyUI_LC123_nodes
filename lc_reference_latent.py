"""
LC Reference Latent
-------------------
Packs up to 8 VAE-encoded reference latents into CONDITIONING meta for
FLUX.2 Klein-style multi-reference workflows.

All latent slots are optional. If none are connected (or none yield a valid
4-D samples tensor), conditioning is passed through unchanged — safe to leave
in the graph with everything bypassed/disconnected.
"""

from __future__ import annotations

from typing import Any, List, Optional

try:
    import torch
except Exception:  # pragma: no cover
    torch = None


def _samples(latent: Any):
    """Return a 4-D latent tensor or None if the slot is empty / invalid."""
    if latent is None:
        return None
    if isinstance(latent, dict):
        latent = latent.get("samples")
    if torch is not None and torch.is_tensor(latent) and getattr(latent, "ndim", 0) == 4:
        return latent
    return None


class LCReferenceLatent:
    @classmethod
    def INPUT_TYPES(cls):
        opt = {
            f"latent_{i}": (
                "LATENT",
                {
                    "tooltip": f"Optional reference latent {i}. Unconnected or invalid slots are ignored.",
                },
            )
            for i in range(1, 9)
        }
        return {
            "required": {
                "conditioning": (
                    "CONDITIONING",
                    {
                        "tooltip": "Text conditioning to attach reference latents to.",
                    },
                ),
            },
            "optional": opt,
        }

    RETURN_TYPES = ("CONDITIONING",)
    RETURN_NAMES = ("conditioning",)
    FUNCTION = "apply"
    CATEGORY = "LC123/conditioning"
    DESCRIPTION = (
        "Attach up to 8 reference latents to conditioning (Klein index method). "
        "All latent inputs optional — if none are valid, passes conditioning through."
    )

    def apply(self, conditioning, **kwargs):
        refs: List = []
        # Stable order latent_1 … latent_8
        for i in range(1, 9):
            z = _samples(kwargs.get(f"latent_{i}"))
            if z is None:
                continue
            for b in range(int(z.shape[0])):
                refs.append(z[b : b + 1].detach())

        if not refs:
            # Nothing attached — pass through unchanged
            return (conditioning,)

        out = []
        for cond, meta in conditioning:
            meta = dict(meta) if isinstance(meta, dict) else {}
            meta["reference_latents"] = list(refs)
            meta["reference_latents_method"] = "index"
            out.append([cond, meta])
        return (out,)


NODE_CLASS_MAPPINGS = {
    "LCReferenceLatent": LCReferenceLatent,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LCReferenceLatent": "LC Reference Latent",
}
