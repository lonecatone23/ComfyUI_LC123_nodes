"""Anima Regional Inline Canvas — paint RGB regions; emit separate cond + masks.

Designed to feed Sen-sou AnimaConditioningRegion (or any regional system):
  GLOBAL → background_conditioning
  RED/GREEN/BLUE CONDITIONING + MASK → AnimaConditioningRegion chain
"""

import torch

from .regional_canvas_common import (
    ANIMA_PROMPT_DEFAULTS,
    REGIONS,
    _CANVAS_CONTINUE,
    _build_metadata,
    _encode_text,
    _extract_masks,
    _image_from_canvas,
    _inline_input_types,
    _latent_size,
    _mask_has_paint,
    _mask_output,
    _prompts,
    _register_apply_route,
    _resize_image_tensor,
    _tensor_to_png_b64,
)


def _empty_conditioning(clip):
    return _encode_text(clip, " ")


def _encode_global(clip, prompts):
    text = "\n\n".join(
        s.strip()
        for s in [prompts.get("quality") or "", prompts.get("scene") or ""]
        if s and s.strip()
    )
    return _encode_text(clip, text or " ")


def _encode_region_only(clip, prompts, key):
    """Quality + region subject only (no scene) — attach mask externally."""
    text = "\n\n".join(
        s.strip()
        for s in [prompts.get("quality") or "", prompts.get(key) or ""]
        if s and s.strip()
    )
    if not text.strip():
        return _empty_conditioning(clip)
    return _encode_text(clip, text)


def _zero_mask(h=64, w=64):
    return torch.zeros((1, h, w), dtype=torch.float32)


def _region_pack(clip, prompts, masks, regional_enabled):
    """Return dict: global, negative, red, red_mask, green, green_mask, blue, blue_mask."""
    global_c = _encode_global(clip, prompts)
    negative = _encode_text(clip, prompts.get("negative") or "")

    h = w = 64
    for key, _, _ in REGIONS:
        m = masks.get(key)
        if m is not None:
            h, w = int(m.shape[-2]), int(m.shape[-1])
            break

    outs = {"global": global_c, "negative": negative}
    for key, _, _ in REGIONS:
        m = masks.get(key)
        if m is None:
            mask_t = _zero_mask(h, w)
            has = False
        else:
            mask_t = m.unsqueeze(0).float() if m.ndim == 2 else m.float()
            has = float(mask_t.max()) > 0.01 and bool((prompts.get(key) or "").strip())

        if regional_enabled and has:
            outs[key] = _encode_region_only(clip, prompts, key)
            outs[f"{key}_mask"] = mask_t
        else:
            outs[key] = _empty_conditioning(clip)
            if m is None:
                outs[f"{key}_mask"] = _zero_mask(h, w)
            elif m.ndim == 2:
                outs[f"{key}_mask"] = (m * 0).unsqueeze(0).float()
            else:
                outs[f"{key}_mask"] = (m * 0).float()

    return outs


def _interrupt(reason: str) -> None:
    """Stop the graph so downstream nodes do not run on empty / unconfirmed canvas."""
    try:
        from comfy.model_management import InterruptProcessingException

        raise InterruptProcessingException()
    except ImportError:
        raise RuntimeError(
            f"Anima Regional Canvas stopped: {reason}. "
            "Paint regions if needed, click Apply, then queue again."
        ) from None


class AnimaRegionalCanvasInline:
    """Paint RGB regions → separate GLOBAL / per-color CONDITIONING + MASK.

    Wire into Sen-sou (or similar)::

        GLOBAL     → ApplyAnimaRegionalConditioningPatch.background_conditioning
        RED + RED_MASK → AnimaConditioningRegion
              └→ GREEN + GREEN_MASK → AnimaConditioningRegion
                    └→ BLUE + BLUE_MASK → AnimaConditioningRegion → regions
        MODEL      → ApplyAnimaRegionalConditioningPatch → KSampler
        NEGATIVE   → KSampler negative
        MASK       → optional preview / LLLite
    """

    @classmethod
    def INPUT_TYPES(cls):
        return _inline_input_types(ANIMA_PROMPT_DEFAULTS)

    RETURN_TYPES = (
        "IMAGE",
        "MODEL",
        "CONDITIONING",
        "CONDITIONING",
        "MASK",
        "CONDITIONING",
        "MASK",
        "CONDITIONING",
        "MASK",
        "CONDITIONING",
        "STRING",
        "MASK",
    )
    RETURN_NAMES = (
        "IMAGE",
        "MODEL",
        "GLOBAL",
        "RED",
        "RED_MASK",
        "GREEN",
        "GREEN_MASK",
        "BLUE",
        "BLUE_MASK",
        "NEGATIVE",
        "JSON",
        "MASK",
    )
    FUNCTION = "execute"
    CATEGORY = "Anima/Regional"

    @classmethod
    def IS_CHANGED(cls, unique_id=None, canvas_data="", **kwargs):
        uid = str(unique_id) if unique_id is not None else ""
        if uid and uid in _CANVAS_CONTINUE:
            return float("nan")
        return canvas_data if canvas_data is not None else ""

    def execute(
        self,
        model,
        clip,
        width,
        height,
        batch_size,
        brush_size,
        region_strength,
        canvas_data="",
        keep_mask=True,
        stop_on_empty_mask=True,
        pause_until_apply=True,
        unique_id=None,
        **kwargs,
    ):
        try:
            _register_apply_route()
        except Exception:
            pass

        width, height = _latent_size(width, height)
        batch_size = max(1, int(batch_size))
        uid = str(unique_id) if unique_id is not None else None

        cont = _CANVAS_CONTINUE.pop(uid, None) if uid else None
        if cont and cont.get("canvas_data"):
            canvas_data = cont["canvas_data"]

        base_image = kwargs.get("image")
        if base_image is not None:
            base_image = _resize_image_tensor(base_image, width, height)

        image = _image_from_canvas(canvas_data, width, height, batch_size)
        has_paint = _mask_has_paint(image)

        bg_b64 = _tensor_to_png_b64(base_image) if base_image is not None else None
        ui = {
            "arc_size": [{"width": int(width), "height": int(height)}],
            "arc_background": [{
                "image": bg_b64,
                "width": int(width),
                "height": int(height),
                "clear": bg_b64 is None,
            }],
        }

        waiting_for_apply = bool(pause_until_apply) and cont is None
        empty_mask_hold = bool(stop_on_empty_mask) and not has_paint
        should_pause = waiting_for_apply or empty_mask_hold

        try:
            from server import PromptServer

            PromptServer.instance.send_sync(
                "anima.canvas.update",
                {
                    "node_id": uid,
                    "width": int(width),
                    "height": int(height),
                    "background": bg_b64,
                    "clear_background": bg_b64 is None,
                    "has_paint": has_paint,
                    "paused": should_pause,
                    "reason": (
                        "empty_mask" if empty_mask_hold and not waiting_for_apply
                        else ("waiting_for_apply" if waiting_for_apply else None)
                    ),
                },
            )
        except Exception:
            pass

        # Hard stop: do not let the rest of the graph run on empty / unconfirmed paint
        if should_pause:
            if empty_mask_hold and not waiting_for_apply:
                reason = "empty mask"
            elif empty_mask_hold and waiting_for_apply:
                reason = "empty mask — paint a region, then click Apply"
            else:
                reason = "waiting for Apply"
            _interrupt(reason)

        prompts = _prompts(kwargs)
        regional_enabled = kwargs.get("regional_enabled", True)
        masks = _extract_masks(image)
        pack = _region_pack(clip, prompts, masks, regional_enabled)
        union = _mask_output(masks)

        metadata = _build_metadata(
            "Anima Regional Inline Canvas",
            "inline",
            prompts,
            width,
            height,
            regional_enabled,
            region_strength,
            extra=None,
        )

        result = (
            image,
            model,
            pack["global"],
            pack["red"],
            pack["red_mask"],
            pack["green"],
            pack["green_mask"],
            pack["blue"],
            pack["blue_mask"],
            pack["negative"],
            metadata,
            union,
        )
        return {"ui": ui, "result": result}


NODE_CLASS_MAPPINGS = {
    "AnimaRegionalCanvasInline": AnimaRegionalCanvasInline,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "AnimaRegionalCanvasInline": "Anima Regional Inline Canvas",
}
