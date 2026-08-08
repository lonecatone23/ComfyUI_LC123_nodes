# ComfyUI LC123 Nodes

> **BETA** — Active development. Expect breaking changes (especially Regional Canvas I/O). Feedback welcome.

Custom nodes for [ComfyUI](https://github.com/comfyanonymous/ComfyUI) by **lonecatone23**.

- **Repo:** [https://github.com/lonecatone23/ComfyUI_LC123_nodes](https://github.com/lonecatone23/ComfyUI_LC123_nodes)
- **Author:** [https://github.com/lonecatone23](https://github.com/lonecatone23)
- **Support:** [Buy me a ☕](https://ko-fi.com/lonecatone)

Compatible with **ComfyUI Nodes 1.0** (LiteGraph) and **Nodes 2.0** (Vue).

---

## Install

### ComfyUI Manager / Registry

Search for `ComfyUI_LC123_nodes`, or install via git URL:

```text
https://github.com/lonecatone23/ComfyUI_LC123_nodes
```

### Manual

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/lonecatone23/ComfyUI_LC123_nodes.git
```

Restart ComfyUI, then hard-refresh the browser (`Ctrl+F5` / `Cmd+Shift+R`).

**No extra Python dependencies** for this pack.

For **Anima** regional attention (recommended path), also install:

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/Sen-sou/Comfyui-Anima-Regional-Conditioning.git
```

---

## Nodes

| Node | Category | ID |
|------|----------|-----|
| **📐 Aspect Ratio Simplifier** | `image/resize` | `AspectRatioSimplifier` |
| **Anima Regional Inline Canvas** | `Anima/Regional` | `AnimaRegionalCanvasInline` |
| **Krea2 Regional Inline Canvas** | `Krea2/Regional` | `Krea2RegionalCanvasInline` |
| **🎚️ LC123 Slider** | `LC123/utils` | `LC123Slider` |
| **📝 LC Save Text** | `LC123/utils` | `LC123SaveText` |

---

## 📐 Aspect Ratio Simplifier

Resolve output size from an **image** and/or **mask**, or from a CR-style aspect preset, then resize both with the same geometry.

**Inputs:** `image` (optional), `mask` (optional) — at least one required. Image is preferred for resolution; mask is the fallback.

**Outputs:** `image`, `mask`, `width`, `height`, `latent`, `batch`

### Widgets

| Widget | Description |
|--------|-------------|
| **max_resolution** | Cap the longer side (`0` = no limit) |
| **resolution_source** | **image/mask** = use input size · **custom / preset** = use aspect ratio or custom W/H |
| **aspect_ratio** | CR Social Media–style presets + common ratios, or `custom` |
| **custom_width / custom_height** | Used when aspect ratio is `custom` |
| **swap_dimensions** | Swap W/H of the chosen size |
| **upscale_method** | nearest-exact, bicubic, bilinear, lanczos, area, nvidia_rtx_vsr |
| **proportion** | crop, stretch, resize, pad, total_pixels |
| **crop_location** | center, top, bottom, left, right |
| **pad_color** | RGB fill for pad mode |
| **divisible_by** | Round size to a multiple (e.g. 8) |
| **batch_size** | Empty latent batch count |

Mask is resized with the same crop/pad/resize geometry (nearest-exact edges).

---

## Anima Regional Inline Canvas

Interactive RGB paint canvas. Emits **separate** global / per-color conditionings and masks for [Sen-sou Anima Regional Conditioning](https://github.com/Sen-sou/Comfyui-Anima-Regional-Conditioning) or any other regional system.

### Widgets

| Widget | What it does |
|--------|----------------|
| **brush_size** | Paint brush diameter on the canvas. |
| **region_strength** | Stored in metadata; region **weight** is set on each `AnimaConditioningRegion`. |
| **quality_prompt** | Style / quality tags (folded into **GLOBAL** and each color conditioning). |
| **scene_prompt** | Shared environment text → **GLOBAL** only. |
| **red / green / blue_prompt** | Subject prompt for that paint color only. |
| **negative_prompt** | Negative conditioning → **NEGATIVE**. |
| **canvas_data** | Hidden/serialized paint data (managed by the UI). |
| **regional_enabled** | On = emit per-color cond + masks · Off = empty region slots. |
| **keep_mask** | Keep painted regions across runs. |
| **stop_on_empty_mask** | Pause if nothing is painted (no hard error). |
| **pause_until_apply** | Stop the graph until you click **Apply**. |

**Optional inputs:** `image` (canvas background), `quality_prompt_in` / `scene_prompt_in` / `negative_prompt_in`.

**Required inputs:** `model`, `clip`, `width`, `height`.

### Outputs

| Socket | Type | Typical use |
|--------|------|-------------|
| **IMAGE** | IMAGE | Paint canvas / preview |
| **MODEL** | MODEL | Pass-through (or wire UNET/LoRA straight to the patch) |
| **GLOBAL** | CONDITIONING | quality + scene → `background_conditioning` / KSampler positive |
| **RED** | CONDITIONING | quality + red prompt → `AnimaConditioningRegion` |
| **RED_MASK** | MASK | Red paint only |
| **GREEN** | CONDITIONING | quality + green prompt |
| **GREEN_MASK** | MASK | Green paint only |
| **BLUE** | CONDITIONING | quality + blue prompt |
| **BLUE_MASK** | MASK | Blue paint only |
| **NEGATIVE** | CONDITIONING | KSampler negative |
| **JSON** | STRING | Debug metadata |
| **MASK** | MASK | Union of painted regions |

Conditionings are **plain** (no embedded mask/area metadata).

### How to use (Sen-sou)

1. Wire **model**, **clip**, **width**, **height** (optional **image**).
2. Queue Prompt — node **pauses**; paint **R / G / B**; edit prompts.
3. Click green **Apply**.
4. Chain: **RED**+**RED_MASK** → Region → **GREEN**+**GREEN_MASK** → Region → **BLUE**+**BLUE_MASK** → Region → Apply **`regions`**.
5. **GLOBAL** → Apply **`background_conditioning`** and (usually) KSampler **positive**.
6. **NEGATIVE** → KSampler negative; Apply **`patched_model`** → KSampler model.

Toolbar: **Undo**, **Clear Canvas**, **Reset 🖌️**, **Apply**.

### Working Apply patch settings (tested)

Credit: [Sen-sou/Comfyui-Anima-Regional-Conditioning](https://github.com/Sen-sou/Comfyui-Anima-Regional-Conditioning)

| Parameter | Value |
|-----------|------:|
| **base_mode** | `disabled` |
| **base_strength** | `0.20` |
| **start_percent** | `0.00` |
| **end_percent** | `0.35` |
| **cross_mask_strength** | `1.00` |
| **self_mask_strength** | `0.10` |
| **base_ratio** | `0.30` |
| **cross_inject_every_n_blocks** | `1` |
| **self_inject_every_n_blocks** | `1` |
| Region **weight** | `1.0` |

### Tips

- Size comes only from **width** / **height** connections.
- Region prompts = **subject only**; room/lighting only in **scene** → **GLOBAL**.
- Muted/disconnected image → white canvas.
- Background coherence is tuned mainly on the **Apply** patch, not this node.
- After I/O changes, **delete and re-add** the Anima node on old workflows.

---

## Krea2 Regional Inline Canvas

Same paint UI; CLIP type **krea2**. Uses Comfy mask/area conditioning (combined positive).

**Required:** `clip`, `width`, `height` — **no** MODEL or LATENT pass-through.

**Outputs:** `IMAGE`, `POSITIVE`, `NEGATIVE`, `JSON`, `MASK`

Wire UNET and empty latent around the node to the sampler.

---

## 🎚️ LC123 Slider

mxToolkit-style slider for **Nodes 2.0** (DOM UI). Works in 1.0 and 2.0.

| Setting | Description |
|---------|-------------|
| **min / max** | Range |
| **step** | Snap increment |
| **decimals** | `0` = int · `1–4` = float precision |

Output type `*` (INT or FLOAT depending on decimals).

---

## 📝 LC Save Text

Drop-in alternative to core **SaveText** with different numbering:

| Save | Filename |
|------|----------|
| 1st | `prefix.ext` |
| 2nd | `prefix_01.ext` |
| 3rd | `prefix_02.ext` |
| … | `prefix_99.ext`, `prefix_100.ext`, … |

**Inputs:** `text` (required), `filename_prefix` (default `ComfyUI`), `format` (`txt` / `md` / `json` / `csv`)

**Output:** `text` (passthrough)

- Subfolders in the prefix work (`tags/myfile` → `output/tags/myfile.txt`).
- JSON is pretty-printed when the content is valid JSON.
- Class ID: `LC123SaveText`.

---

## Layout

```text
ComfyUI_LC123_nodes/
├── __init__.py
├── aspect_ratio.py
├── anima_regional_canvas.py
├── krea2_regional_canvas.py
├── regional_canvas_common.py
├── regional_canvas.py            # compatibility shim
├── slider.py
├── LC_save_text.py                  # 📝 LC Save Text
├── web/
│   ├── inline_regional_canvas.js
│   └── lc123_slider.js
├── README.md
├── LICENSE
├── pyproject.toml
├── .gitignore
└── .comfyignore
```

---

## Troubleshooting

### Nodes do not appear after install

1. Folder name must be `ComfyUI_LC123_nodes` under `ComfyUI/custom_nodes/`.
2. Restart ComfyUI fully (not only browser refresh).
3. Hard-refresh UI: `Ctrl+F5` / `Cmd+Shift+R`.
4. Check the terminal for `ImportError` under this pack.
5. Search class IDs: `AspectRatioSimplifier`, `AnimaRegionalCanvasInline`, `Krea2RegionalCanvasInline`, `LC123Slider`, `LC123SaveText`.

### Anima outputs changed / graph broken after update

- **Re-add** the Anima Regional Inline Canvas node (RETURN_TYPES changed to split GLOBAL / RGB / masks).
- Re-wire to Sen-sou `AnimaConditioningRegion` + `ApplyAnimaRegionalConditioningPatch`.

### Regional canvas does not show / Apply does not resume

- Hard-refresh so `web/inline_regional_canvas.js` loads.
- **width** and **height** must be connected.
- With **pause_until_apply**, click the green **Apply** button after painting.
- Empty paint + **stop_on_empty_mask** pauses by design.

### Background unstable with Sen-sou patch

Expected with regional DiT attention. Raise **base_ratio**, lower **self_mask_strength**, keep **base_mode = disabled**. See table above.

### Slider blank (Nodes 2.0)

Hard-refresh; delete and re-add the slider node; confirm `web/lc123_slider.js` exists.

### Aspect Ratio Simplifier errors

Connect at least **image** or **mask**. Stale widgets → re-add the node.

### Update checklist

```bash
cd ComfyUI/custom_nodes/ComfyUI_LC123_nodes
git pull
```

1. Restart ComfyUI  
2. Hard-refresh browser  
3. Re-add nodes whose inputs/outputs changed  

---

## License

MIT — see [LICENSE](LICENSE).

Anima attention routing depends on [Sen-sou/Comfyui-Anima-Regional-Conditioning](https://github.com/Sen-sou/Comfyui-Anima-Regional-Conditioning) (install separately; follow that project’s license).

If this pack helps: [Buy me a ☕](https://ko-fi.com/lonecatone)
