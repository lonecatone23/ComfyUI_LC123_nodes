"""Shared helpers for Anima / Krea2 regional inline canvas nodes."""
import base64
import io
import json

import numpy as np
import torch
from PIL import Image


MAX_RESOLUTION = 16384
REGIONS = (
    # RGB only — exclusive region colors for paint + conditioning
    ("red", "RED", (1.0, 0.0, 0.0)),
    ("green", "GREEN", (0.0, 1.0, 0.0)),
    ("blue", "BLUE", (0.0, 0.0, 1.0)),
)

ANIMA_PROMPT_DEFAULTS = {
    "quality_prompt": "masterpiece, absurdres, score_7, anime style",
    "scene_prompt": "",
    "red_prompt": "",
    "green_prompt": "",
    "blue_prompt": "",
    "negative_prompt": "worst quality, low quality, blurry, bad anatomy",
}

KREA2_PROMPT_DEFAULTS = {
    "quality_prompt": "high quality photograph, sharp detail, natural lighting",
    "scene_prompt": "",
    "red_prompt": "",
    "green_prompt": "",
    "blue_prompt": "",
    "negative_prompt": "blurry, low quality, distorted, watermark, text, logo",
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


def _dilate(mask, px=12):
    if px <= 0:
        return mask
    m = mask.reshape(1, 1, mask.shape[-2], mask.shape[-1])
    k = px * 2 + 1
    out = torch.nn.functional.max_pool2d(m, kernel_size=k, stride=1, padding=px)
    return out.reshape(mask.shape[-2], mask.shape[-1]).clamp(0.0, 1.0)


def _mask_bbox(mask, min_size=8, expand=0.12, img_h=None, img_w=None):
    """Pixel bbox expanded slightly so area does not hard-crop into a cutout panel."""
    m = mask.detach()
    if m.ndim == 3:
        m = m[0]
    h_img, w_img = int(m.shape[0]), int(m.shape[1])
    ys = torch.where(m.max(dim=1).values > 0.05)[0]
    xs = torch.where(m.max(dim=0).values > 0.05)[0]
    if ys.numel() == 0 or xs.numel() == 0:
        return None
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    x0, x1 = int(xs.min()), int(xs.max()) + 1
    bh, bw = max(min_size, y1 - y0), max(min_size, x1 - x0)
    pad_y, pad_x = int(bh * expand), int(bw * expand)
    y0 = max(0, y0 - pad_y)
    x0 = max(0, x0 - pad_x)
    y1 = min(h_img, y1 + pad_y)
    x1 = min(w_img, x1 + pad_x)
    return x0, y0, max(min_size, x1 - x0), max(min_size, y1 - y0)


def _set_area(conditioning, x, y, w, h, strength):
    """Comfy area tuple is (h/8, w/8, y/8, x/8) in latent cells."""
    return _conditioning_set_values(
        conditioning,
        {
            "area": (max(1, h // 8), max(1, w // 8), max(0, y // 8), max(0, x // 8)),
            "strength": float(strength),
            "set_area_to_bounds": False,
        },
    )


def _set_region(conditioning, mask, strength, feather=True):
    """Soft mask + slightly expanded area — avoids white cutout panels."""
    if len(mask.shape) < 3:
        mask = mask.unsqueeze(0)
    soft = mask.float()
    if feather:
        soft = _dilate(soft[0] if soft.ndim == 3 else soft, px=10)
        if soft.ndim == 2:
            soft = soft.unsqueeze(0)
    hard = (soft > 0.12).float() * soft.clamp(0.0, 1.0)
    if float(hard.max()) <= 0:
        hard = soft
    out = _set_mask(conditioning, hard, float(strength), set_area_to_bounds=False)
    bbox = _mask_bbox(hard, expand=0.18)
    if bbox is not None:
        x, y, w, h = bbox
        out = _set_area(out, x, y, w, h, float(strength) * 0.65)
    return out


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


def _extract_masks(image, max_dist=0.45):
    """Exact exclusive RGB masks with soft strength from color purity."""
    src = image[0].detach().float().clamp(0.0, 1.0)
    h, w, _ = src.shape
    device = src.device

    keys = [key for key, _, _ in REGIONS]
    targets = torch.tensor([rgb for _, _, rgb in REGIONS], device=device, dtype=src.dtype)

    pix = src.reshape(-1, 3)
    dist = torch.cdist(pix, targets, p=2)
    nearest = torch.argmin(dist, dim=1)
    nearest_dist = dist[torch.arange(dist.shape[0], device=device), nearest]

    soft = (1.0 - (nearest_dist / float(max_dist)).clamp(0.0, 1.0)).clamp(0.0, 1.0)
    assigned = nearest_dist <= float(max_dist)

    masks = {}
    for i, key in enumerate(keys):
        m = torch.zeros(h * w, device=device, dtype=src.dtype)
        sel = (nearest == i) & assigned
        m[sel] = soft[sel]
        masks[key] = m.reshape(h, w)

    union = torch.zeros((h, w), device=device, dtype=src.dtype)
    for key in keys:
        union = torch.maximum(union, masks[key])
    masks["base"] = torch.clamp(1.0 - union, 0.0, 1.0)
    masks["white"] = masks["base"]
    masks["union"] = union
    return masks


def _mask_output(masks):
    """Comfy MASK tensor [1,H,W] — painted regions only (no background)."""
    union = masks.get("union")
    if union is None:
        union = torch.zeros((64, 64))
        for key, _, _ in REGIONS:
            m = masks.get(key)
            if m is not None:
                union = torch.maximum(union, m)
    return union.unsqueeze(0).float()


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
    # Scene is global only — including it per-region makes each strip invent its own bar.
    return "\n\n".join(
        text.strip()
        for text in [prompts["quality"], prompts[key]]
        if text and text.strip()
    )


def _conditioning(clip, prompts, masks, strength, enabled=True):
    """Regional subjects + one shared scene background (Comfy mask/area path)."""
    global_text = _global_prompt_text(prompts) or _positive_prompt_text(prompts)
    scene_only = "\n\n".join(
        s.strip()
        for s in [prompts.get("scene") or "", prompts.get("quality") or ""]
        if s and s.strip()
    ) or global_text

    if not enabled:
        positive = _encode_text(clip, _positive_prompt_text(prompts) or global_text)
        negative = _encode_text(clip, prompts["negative"])
        return positive, negative

    positive = _set_default(_encode_text(clip, scene_only or " "))

    pending = []
    for key, _, _ in REGIONS:
        text = (prompts.get(key) or "").strip()
        if not text:
            continue
        mask = masks.get(key)
        if mask is None or float(mask.max()) <= 0:
            continue
        painted = mask[mask > 0.15]
        if painted.numel() == 0:
            continue
        area = float(painted.numel())
        pending.append((area, key, mask))

    pending.sort(key=lambda x: x[0])
    eff = float(strength) * 0.72
    for _area, key, mask in pending:
        positive.extend(
            _set_region(
                _encode_text(clip, _region_prompt_text(prompts, key)),
                mask,
                eff,
            )
        )

    base = masks.get("base")
    if base is not None and float(base.max()) > 0.05 and scene_only:
        positive.extend(_set_region(_encode_text(clip, scene_only), base, 1.0))

    if not pending:
        positive = _encode_text(clip, global_text)

    negative = _encode_text(clip, prompts["negative"])
    return positive, negative


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


_CANVAS_CONTINUE = {}


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
        _CANVAS_CONTINUE[node_id] = {
            "canvas_data": data.get("canvas_data"),
            "ts": data.get("ts"),
        }
        return web.json_response({"ok": True, "node_id": node_id})

    PromptServer.instance._irc_canvas_routes = True


try:
    _register_apply_route()
except Exception:
    pass


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


def _pack_inline_result(
    image, positive, negative, metadata, preview,
    *, model=None, latent=None, pass_model=True, pass_latent=True,
):
    """Build return tuple: IMAGE, [MODEL], POSITIVE, NEGATIVE, [LATENT], JSON, MASK."""
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

    prompts = _prompts(kwargs)
    regional_enabled = kwargs.get("regional_enabled", True)

    if should_pause:
        # Hard stop so downstream nodes do not run on empty / unconfirmed canvas
        try:
            from comfy.model_management import InterruptProcessingException
            raise InterruptProcessingException()
        except ImportError:
            reason = "empty mask" if empty_mask_hold else "waiting for Apply"
            raise RuntimeError(
                f"{node_name} stopped: {reason}. "
                "Paint if needed, click Apply, then queue again."
            ) from None

    masks = _extract_masks(image)
    positive, negative = _conditioning(clip, prompts, masks, region_strength, regional_enabled)
    mask_out = _mask_output(masks)
    metadata = _build_metadata(
        node_name, "inline", prompts, width, height, regional_enabled, region_strength,
    )
    latent = _latent(width, height, batch_size) if pass_latent else None
    result = _pack_inline_result(
        image, positive, negative, metadata, mask_out,
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
        "green_prompt": _text_input(prompt_defaults["green_prompt"]),
        "blue_prompt": _text_input(prompt_defaults["blue_prompt"]),
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
