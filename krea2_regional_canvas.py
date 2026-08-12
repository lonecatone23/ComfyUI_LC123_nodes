"""Krea2 Regional Inline Canvas — paint RGB regions; CLIP type krea2."""

from .regional_canvas_common import (
    KREA2_PROMPT_DEFAULTS,
    _CANVAS_CONTINUE,
    _inline_input_types,
    _run_inline_canvas,
)


class Krea2RegionalCanvasInline:
    """Krea2 Regional Inline Canvas — same UI; encodes with krea2 CLIP + regional masks.

    Use CLIPLoader with type **krea2**. Spatial masks attach via Comfy conditioning
    area/strength (works at sampler level for Krea2).

    No MODEL or LATENT pass-through — wire UNET and empty latent straight to the sampler.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return _inline_input_types(KREA2_PROMPT_DEFAULTS, include_model=False)

    RETURN_TYPES = ("IMAGE", "CONDITIONING", "CONDITIONING", "STRING", "MASK")
    RETURN_NAMES = ("IMAGE", "POSITIVE", "NEGATIVE", "JSON", "MASK")
    FUNCTION = "execute"
    CATEGORY = "Krea2/Regional"

    @classmethod
    def IS_CHANGED(cls, unique_id=None, canvas_data="", **kwargs):
        uid = str(unique_id) if unique_id is not None else ""
        if uid and uid in _CANVAS_CONTINUE:
            return float("nan")
        return canvas_data if canvas_data is not None else ""

    def execute(
        self,
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
        return _run_inline_canvas(
            node_name="Krea2 Regional Inline Canvas",
            clip=clip,
            width=width,
            height=height,
            batch_size=batch_size,
            region_strength=region_strength,
            canvas_data=canvas_data,
            stop_on_empty_mask=stop_on_empty_mask,
            pause_until_apply=pause_until_apply,
            unique_id=unique_id,
            kwargs=kwargs,
            model=None,
            pass_model=False,
            pass_latent=False,
        )


NODE_CLASS_MAPPINGS = {
    "Krea2RegionalCanvasInline": Krea2RegionalCanvasInline,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "Krea2RegionalCanvasInline": "Krea2 Regional Inline Canvas",
}
