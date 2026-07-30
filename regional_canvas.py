import base64
import io
import json
import numpy as np
import torch
from PIL import Image


MAX_RESOLUTION = 16384
REGIONS = (
    ("red", "RED", (1.0, 0.0, 0.0)),
    ("blue", "BLUE", (0.0, 0.0, 1.0)),
    ("yellow", "YELLOW", (1.0, 1.0, 0.0)),
    ("green", "GREEN", (0.0, 1.0, 0.0)),
    ("magenta", "MAGENTA", (1.0, 0.0, 1.0)),
)
STANDARD_PROMPT_DEFAULTS = {
    "quality_prompt": "masterpiece, absurdres, score_7, anime style",
    "scene_prompt": "",
    "red_prompt": "",
    "blue_prompt": "",
    "yellow_prompt": "",
    "green_prompt": "",
    "magenta_prompt": "",
    "negative_prompt": "worst quality, low quality, blurry, bad anatomy",
}

def _text_input(default=""):
    return ("STRING", {"multiline": True, "dynamicPrompts": True, "default": default})


def _canvas_input():
    return ("STRING", {"multiline": True, "default": ""})


def _encode_text(clip, text):
    if clip is None:
        raise RuntimeError("CLIP input is required.")
    tokens = clip.tokenize(text or "")
    if hasattr(clip, "encode_from_tokens_scheduled"):
        return clip.encode_from_tokens_scheduled(tokens)

    if hasattr(clip, "encode_from_tokens"):
        try:
            encoded = clip.encode_from_tokens(tokens, return_pooled=True)
        except TypeError:
            encoded = clip.encode_from_tokens(tokens)
        if isinstance(encoded, tuple):
            cond = encoded[0]
            pooled = encoded[1] if len(encoded) > 1 else None
            meta = {"pooled_output": pooled} if pooled is not None else {}
            return [[cond, meta]]
        return [[encoded, {}]]

    raise RuntimeError("CLIP object does not support token encoding.")


def _intermediate_device():
    try:
        import comfy.model_management as model_management

        return model_management.intermediate_device()
    except Exception:
        return torch.device("cpu")


def _intermediate_dtype():
    try:
        import comfy.model_management as model_management

        return model_management.intermediate_dtype()
    except Exception:
        return torch.float32


def _conditioning_set_values(conditioning, values):
    updated = []
    for item in conditioning:
        entry = [item[0], item[1].copy()]
        for key, value in values.items():
            entry[1][key] = value
        updated.append(entry)
    return updated


def _nearest_resample():
    resampling = getattr(Image, "Resampling", None)
    return getattr(resampling, "NEAREST", Image.NEAREST)


def _set_mask(conditioning, mask, strength, set_area_to_bounds=False):
    if len(mask.shape) < 3:
        mask = mask.unsqueeze(0)
    return _conditioning_set_values(
        conditioning,
        {
            "mask": mask,
            "set_area_to_bounds": set_area_to_bounds,
            "mask_strength": strength,
        },
    )


def _set_default(conditioning):
    return _conditioning_set_values(conditioning, {"default": True})


def _latent(width, height, batch_size):
    width, height = _latent_size(width, height)
    samples = torch.zeros(
        [batch_size, 4, height // 8, width // 8],
        device=_intermediate_device(),
        dtype=_intermediate_dtype(),
    )
    return {"samples": samples, "downscale_ratio_spacial": 8}


def _latent_size(width, height):
    width = min(MAX_RESOLUTION, max(16, int(width))) // 8 * 8
    height = min(MAX_RESOLUTION, max(16, int(height))) // 8 * 8
    return width, height


def _resize_image_tensor(image, width, height):
    width, height = _latent_size(width, height)
    src = image[:, :, :, :3].float()
    if src.shape[1:3] == (height, width):
        return src
    return torch.nn.functional.interpolate(
        src.movedim(-1, 1),
        size=(height, width),
        mode="bilinear",
        align_corners=False,
    ).movedim(1, -1)


def _grow_mask(mask, amount):
    mask = mask.reshape((-1, 1, mask.shape[-2], mask.shape[-1]))
    amount = max(0, int(amount))
    if amount <= 0:
        return mask.round()
    mask = mask.round()
    kernel_size = amount * 2 + 1
    return torch.nn.functional.max_pool2d(mask, kernel_size, stride=1, padding=amount)


def _inpaint_latent(vae, pixels, mask, grow_mask_by):
    downscale_ratio = vae.spacial_compression_encode() if hasattr(vae, "spacial_compression_encode") else 8
    height = (pixels.shape[1] // downscale_ratio) * downscale_ratio
    width = (pixels.shape[2] // downscale_ratio) * downscale_ratio
    mask = torch.nn.functional.interpolate(
        mask.reshape((-1, 1, mask.shape[-2], mask.shape[-1])),
        size=(pixels.shape[1], pixels.shape[2]),
        mode="bilinear",
    )
    pixels = pixels.clone()
    if pixels.shape[1] != height or pixels.shape[2] != width:
        y_offset = (pixels.shape[1] % downscale_ratio) // 2
        x_offset = (pixels.shape[2] % downscale_ratio) // 2
        pixels = pixels[:, y_offset:height + y_offset, x_offset:width + x_offset, :]
        mask = mask[:, :, y_offset:height + y_offset, x_offset:width + x_offset]

    noise_mask = _grow_mask(mask, grow_mask_by)[:, :, :height, :width].round()
    keep = (1.0 - mask.round()).squeeze(1)
    for channel in range(3):
        pixels[:, :, :, channel] -= 0.5
        pixels[:, :, :, channel] *= keep
        pixels[:, :, :, channel] += 0.5

    return {"samples": vae.encode(pixels), "noise_mask": noise_mask}


def _image_from_canvas(canvas_data, width, height, batch_size):
    width, height = _latent_size(width, height)
    image = None
    if canvas_data:
        try:
            payload = json.loads(canvas_data)
            data_url = payload.get("data_url", "")
            if "," in data_url:
                data_url = data_url.split(",", 1)[1]
            raw = base64.b64decode(data_url)
            image = Image.open(io.BytesIO(raw)).convert("RGB")
        except Exception:
            image = None

    if image is None:
        image = Image.new("RGB", (width, height), (255, 255, 255))
    elif image.size != (width, height):
        image = image.resize((width, height), _nearest_resample())

    arr = np.asarray(image, dtype=np.float32) / 255.0
    tensor = torch.from_numpy(arr).unsqueeze(0).to(
        device=_intermediate_device(),
        dtype=_intermediate_dtype(),
    )
    if batch_size > 1:
        tensor = tensor.repeat(batch_size, 1, 1, 1)
    return tensor


def _mask_preview_image(mask_image, base_image=None, alpha=0.45):
    mask = mask_image[:, :, :, :3].float()
    if base_image is None:
        base = torch.ones_like(mask)
    else:
        base = base_image[:, :, :, :3].float()
        if base.shape[1:3] != mask.shape[1:3]:
            base = torch.nn.functional.interpolate(
                base.movedim(-1, 1),
                size=mask.shape[1:3],
                mode="bilinear",
                align_corners=False,
            ).movedim(1, -1)
        if base.shape[0] != mask.shape[0]:
            base = base[:1].repeat(mask.shape[0], 1, 1, 1)
    painted = (mask < 0.98).any(dim=-1, keepdim=True).float()
    return torch.clamp(base * (1.0 - painted * alpha) + mask * (painted * alpha), 0.0, 1.0)


def _extract_masks(image, threshold=0.15):
    src = image[0].detach()
    r, g, b = src[..., 0], src[..., 1], src[..., 2]
    masks = {
        "red": ((r >= 1 - threshold) & (g < threshold) & (b < threshold)).float(),
        "blue": ((r < threshold) & (g < threshold) & (b >= 1 - threshold)).float(),
        "yellow": ((r >= 1 - threshold) & (g >= 1 - threshold) & (b < threshold)).float(),
        "green": ((r < threshold) & (g >= 1 - threshold) & (b < threshold)).float(),
        "magenta": ((r >= 1 - threshold) & (g < threshold) & (b >= 1 - threshold)).float(),
        "white": ((r >= 1 - threshold) & (g >= 1 - threshold) & (b >= 1 - threshold)).float(),
    }
    union = torch.zeros_like(masks["white"])
    for key, _, _ in REGIONS:
        union = torch.maximum(union, masks[key])
    masks["base"] = torch.clamp(1.0 - union, 0.0, 1.0)
    return masks


def _prompts(kwargs):
    legacy_base = kwargs.get("base_prompt_in") or kwargs.get("base_prompt") or ""
    result = {
        "quality": kwargs.get("quality_prompt_in") or kwargs.get("quality_prompt") or legacy_base,
        "scene": kwargs.get("scene_prompt_in") or kwargs.get("scene_prompt") or "",
        "negative": kwargs.get("negative_prompt_in") or kwargs.get("negative_prompt") or "",
    }
    for key, label, _ in REGIONS:
        result[key] = kwargs.get(f"{key}_prompt_in") or kwargs.get(f"{key}_prompt") or ""
    return result


def _positive_prompt_text(prompts):
    return "\n\n".join(
        text.strip()
        for text in [prompts["quality"], prompts["scene"], *(prompts[key] for key, _, _ in REGIONS)]
        if text and text.strip()
    )


def _global_prompt_text(prompts):
    return "\n\n".join(
        text.strip()
        for text in [prompts["quality"], prompts["scene"]]
        if text and text.strip()
    )


def _region_prompt_text(prompts, key):
    return "\n\n".join(
        text.strip()
        for text in [prompts["quality"], prompts["scene"], prompts[key]]
        if text and text.strip()
    )


def _conditioning(clip, prompts, masks, strength, enabled=True):
    global_text = _global_prompt_text(prompts) or _positive_prompt_text(prompts)

    if not enabled:
        positive = _encode_text(clip, _positive_prompt_text(prompts) or global_text)
        negative = _encode_text(clip, prompts["negative"])
        return positive, negative

    positive = _set_default(_encode_text(clip, global_text))
    active_regions = 0
    for key, _, _ in REGIONS:
        text = prompts[key].strip()
        if not text:
            continue
        mask = masks.get(key)
        if mask is None or torch.max(mask).item() <= 0:
            continue
        positive.extend(_set_mask(_encode_text(clip, _region_prompt_text(prompts, key)), mask, strength, False))
        active_regions += 1

    if active_regions == 0:
        positive = _encode_text(clip, global_text)

    negative = _encode_text(clip, prompts["negative"])
    return positive, negative


def _metadata(prompts, width, height, mode, regional_enabled, region_strength):
    return json.dumps(
        {
            "node": "Anima Regional Canvas",
            "mode": mode,
            "width": width,
            "height": height,
            "regional_enabled": bool(regional_enabled),
            "region_strength": float(region_strength),
            "regions": {label: prompts[key] for key, label, _ in REGIONS},
            "prompt": _positive_prompt_text(prompts),
            "quality": prompts["quality"],
            "scene": prompts["scene"],
            "base": _global_prompt_text(prompts),
            "negative": prompts["negative"],
        },
        ensure_ascii=False,
    )



def _mask_has_paint(image, threshold=0.15):
    if image is None or image.numel() == 0:
        return False
    src = image[0].detach()
    r, g, b = src[..., 0], src[..., 1], src[..., 2]
    white = (r >= 1.0 - threshold) & (g >= 1.0 - threshold) & (b >= 1.0 - threshold)
    return bool((~white).any().item())


def _tensor_to_png_b64(image):
    if image is None:
        return None
    try:
        arr = image[0].detach().float().cpu().numpy()
        arr = (arr * 255.0).clip(0, 255).astype(np.uint8)
        if arr.shape[-1] > 3:
            arr = arr[..., :3]
        img = Image.fromarray(arr, mode="RGB")
        buf = io.BytesIO()
        img.save(buf, format="PNG", compress_level=3)
        return base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception:
        return None



_ANIMA_CONTINUE = {}


def _register_apply_route():
    try:
        from server import PromptServer
        from aiohttp import web
    except Exception:
        return
    if getattr(PromptServer.instance, "_irc_canvas_routes", False):
        return

    @PromptServer.instance.routes.post("/anima/canvas/apply")
    async def irc_canvas_apply(request):
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"ok": False, "error": "invalid json"}, status=400)
        node_id = str(data.get("node_id", "")).strip()
        if not node_id:
            return web.json_response({"ok": False, "error": "missing node_id"}, status=400)
        _ANIMA_CONTINUE[node_id] = {
            "canvas_data": data.get("canvas_data"),
            "ts": data.get("ts"),
        }
        return web.json_response({"ok": True, "node_id": node_id})

    PromptServer.instance._irc_canvas_routes = True


try:
    _register_apply_route()
except Exception:
    pass


def _interrupt_like_mxstop():
    try:
        import nodes as comfy_nodes
        if hasattr(comfy_nodes, "interrupt_processing"):
            comfy_nodes.interrupt_processing()
            return True
    except Exception:
        pass
    try:
        import comfy.model_management as mm
        if hasattr(mm, "interrupt_processing"):
            mm.interrupt_processing()
            return True
    except Exception:
        pass
    return False


def _build_metadata(node_name, mode, prompts, width, height, regional_enabled, region_strength, extra=None):
    payload = {
        "node": node_name,
        "mode": mode,
        "width": width,
        "height": height,
        "regional_enabled": bool(regional_enabled),
        "region_strength": float(region_strength),
        "regions": {label: prompts[key] for key, label, _ in REGIONS},
        "prompt": _positive_prompt_text(prompts),
        "quality": prompts["quality"],
        "scene": prompts["scene"],
        "base": _global_prompt_text(prompts),
        "negative": prompts["negative"],
    }
    if extra:
        payload.update(extra)
    return json.dumps(payload, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Shared execute core
# ---------------------------------------------------------------------------


def _pack_inline_result(
    image, positive, negative, metadata, preview,
    *, model=None, latent=None, pass_model=True, pass_latent=True,
):
    """Build return tuple: IMAGE, [MODEL], POSITIVE, NEGATIVE, [LATENT], JSON, MASK_PREVIEW."""
    out = [image]
    if pass_model:
        out.append(model)
    out.extend([positive, negative])
    if pass_latent:
        out.append(latent)
    out.extend([metadata, preview])
    return tuple(out)


def _run_inline_canvas(
    *,
    node_name,
    clip,
    width,
    height,
    batch_size,
    region_strength,
    canvas_data,
    stop_on_empty_mask,
    pause_until_apply,
    unique_id,
    kwargs,
    model=None,
    pass_model=True,
    pass_latent=True,
    prompt_defaults=None,
):
    try:
        _register_apply_route()
    except Exception:
        pass

    width, height = _latent_size(width, height)
    batch_size = max(1, int(batch_size))
    uid = str(unique_id) if unique_id is not None else None

    cont = _ANIMA_CONTINUE.pop(uid, None) if uid else None
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

    prompts = _prompts(kwargs)
    regional_enabled = kwargs.get("regional_enabled", True)

    if should_pause:
        masks = _extract_masks(image)
        try:
            positive, negative = _conditioning(clip, prompts, masks, region_strength, regional_enabled)
        except Exception:
            positive = negative = None
        latent = _latent(width, height, batch_size)
        metadata = _build_metadata(
            node_name, "paused", prompts, width, height, regional_enabled, region_strength,
            extra={"has_paint": has_paint, "has_image": base_image is not None,
                   "reason": "empty_mask" if empty_mask_hold else "waiting_for_apply"},
        )
        if base_image is not None:
            if base_image.shape[0] != batch_size:
                base_image = base_image[:1].repeat(batch_size, 1, 1, 1)
            preview = _mask_preview_image(image, base_image=base_image)
        else:
            preview = image
        result = _pack_inline_result(
            image, positive, negative, metadata, preview,
            model=model, latent=latent, pass_model=pass_model, pass_latent=pass_latent,
        )
        _interrupt_like_mxstop()
        return {"ui": ui, "result": result}

    masks = _extract_masks(image)
    positive, negative = _conditioning(clip, prompts, masks, region_strength, regional_enabled)
    latent = _latent(width, height, batch_size)
    metadata = _build_metadata(
        node_name, "inline", prompts, width, height, regional_enabled, region_strength,
    )

    if base_image is not None:
        if base_image.shape[0] != batch_size:
            base_image = base_image[:1].repeat(batch_size, 1, 1, 1)
        preview = _mask_preview_image(image, base_image=base_image)
    else:
        preview = image

    result = _pack_inline_result(
        image, positive, negative, metadata, preview,
        model=model, latent=latent, pass_model=pass_model, pass_latent=pass_latent,
    )
    return {"ui": ui, "result": result}


def _inline_input_types(prompt_defaults, include_model=True):
    required = {}
    if include_model:
        required["model"] = ("MODEL",)
    required.update({
        "clip": ("CLIP",),
        "width": ("INT", {"default": 1024, "min": 16, "max": MAX_RESOLUTION, "step": 8, "forceInput": True}),
        "height": ("INT", {"default": 1024, "min": 16, "max": MAX_RESOLUTION, "step": 8, "forceInput": True}),
        "batch_size": ("INT", {"default": 1, "min": 1, "max": 4096}),
        "brush_size": ("INT", {"default": 92, "min": 1, "max": 512, "step": 1}),
        "region_strength": ("FLOAT", {"default": 0.95, "min": 0.0, "max": 10.0, "step": 0.01}),
        "quality_prompt": _text_input(prompt_defaults["quality_prompt"]),
        "scene_prompt": _text_input(prompt_defaults["scene_prompt"]),
        "red_prompt": _text_input(prompt_defaults["red_prompt"]),
        "blue_prompt": _text_input(prompt_defaults["blue_prompt"]),
        "yellow_prompt": _text_input(prompt_defaults["yellow_prompt"]),
        "green_prompt": _text_input(prompt_defaults["green_prompt"]),
        "magenta_prompt": _text_input(prompt_defaults["magenta_prompt"]),
        "negative_prompt": _text_input(prompt_defaults["negative_prompt"]),
        "canvas_data": _canvas_input(),
        "regional_enabled": ("BOOLEAN", {"default": True}),
        "keep_mask": ("BOOLEAN", {"default": True}),
        "stop_on_empty_mask": ("BOOLEAN", {"default": True}),
        "pause_until_apply": ("BOOLEAN", {"default": True}),
    })
    optional = {
        "image": ("IMAGE",),
        "quality_prompt_in": ("STRING", {"forceInput": True}),
        "scene_prompt_in": ("STRING", {"forceInput": True}),
        "negative_prompt_in": ("STRING", {"forceInput": True}),
    }
    return {
        "required": required,
        "optional": optional,
        "hidden": {"unique_id": "UNIQUE_ID"},
    }


ANIMA_PROMPT_DEFAULTS = {
    "quality_prompt": "masterpiece, absurdres, score_7, anime style",
    "scene_prompt": "",
    "red_prompt": "",
    "blue_prompt": "",
    "yellow_prompt": "",
    "green_prompt": "",
    "magenta_prompt": "",
    "negative_prompt": "worst quality, low quality, blurry, bad anatomy",
}

KREA2_PROMPT_DEFAULTS = {
    "quality_prompt": "high quality photograph, sharp detail, natural lighting",
    "scene_prompt": "",
    "red_prompt": "",
    "blue_prompt": "",
    "yellow_prompt": "",
    "green_prompt": "",
    "magenta_prompt": "",
    "negative_prompt": "blurry, low quality, distorted, watermark, text, logo",
}


class AnimaRegionalCanvasInline:
    """Anima Regional Inline Canvas — paint regions, pause, Apply to continue."""

    @classmethod
    def INPUT_TYPES(cls):
        return _inline_input_types(ANIMA_PROMPT_DEFAULTS)

    RETURN_TYPES = ("IMAGE", "MODEL", "CONDITIONING", "CONDITIONING", "LATENT", "STRING", "IMAGE")
    RETURN_NAMES = ("IMAGE", "MODEL", "POSITIVE", "NEGATIVE", "LATENT", "JSON", "MASK_PREVIEW")
    FUNCTION = "execute"
    CATEGORY = "Anima/Regional"

    @classmethod
    def IS_CHANGED(cls, unique_id=None, canvas_data="", **kwargs):
        uid = str(unique_id) if unique_id is not None else ""
        if uid and uid in _ANIMA_CONTINUE:
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
        return _run_inline_canvas(
            node_name="Anima Regional Inline Canvas",
            model=model,
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

    RETURN_TYPES = ("IMAGE", "CONDITIONING", "CONDITIONING", "STRING", "IMAGE")
    RETURN_NAMES = ("IMAGE", "POSITIVE", "NEGATIVE", "JSON", "MASK_PREVIEW")
    FUNCTION = "execute"
    CATEGORY = "Krea2/Regional"

    @classmethod
    def IS_CHANGED(cls, unique_id=None, canvas_data="", **kwargs):
        uid = str(unique_id) if unique_id is not None else ""
        if uid and uid in _ANIMA_CONTINUE:
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
    "AnimaRegionalCanvasInline": AnimaRegionalCanvasInline,
    "Krea2RegionalCanvasInline": Krea2RegionalCanvasInline,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "AnimaRegionalCanvasInline": "Anima Regional Inline Canvas",
    "Krea2RegionalCanvasInline": "Krea2 Regional Inline Canvas",
}
