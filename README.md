# ComfyUI LC123 Nodes

> **BETA** — These nodes are under active development. Expect breaking changes, rough edges, and incomplete multi-region behavior. Not recommended for production workflows yet. Feedback welcome.

Custom nodes for [ComfyUI](https://github.com/comfyanonymous/ComfyUI) by **lonecatone23**.

- **GitHub:** [https://github.com/lonecatone23](https://github.com/lonecatone23)
- **Support:** [Buy me a ☕](https://ko-fi.com/lonecatone)

Compatible with **ComfyUI Nodes 1.0** (LiteGraph) and **Nodes 2.0** (Vue).

---

## Install

### ComfyUI Manager

Search for `ComfyUI_LC123_nodes` (once published), or install via git URL:

```text
https://github.com/lonecatone23/ComfyUI_LC123_nodes
```

### Manual

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/lonecatone23/ComfyUI_LC123_nodes.git
```

Restart ComfyUI, then hard-refresh the browser (`Ctrl+F5` / `Cmd+Shift+R`).

**No extra Python dependencies.**

---

## Nodes

| Node | Category | ID |
|------|----------|-----|
| **📐 Aspect Ratio Simplifier** | `image/resize` | `AspectRatioSimplifier` |
| **Anima Regional Inline Canvas** | `Anima/Regional` | `AnimaRegionalCanvasInline` |
| **Krea2 Regional Inline Canvas** | `Krea2/Regional` | `Krea2RegionalCanvasInline` |
| **🎚️ LC123 Slider** | `LC123/utils` | `LC123Slider` |

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

## Regional Inline Canvas

Interactive paint canvas for regional prompts. Two variants share the same UI:

| Variant | CLIP | MODEL / LATENT |
|---------|------|----------------|
| **Anima** | Standard CLIP | Pass-through MODEL + empty LATENT |
| **Krea2** | `CLIPLoader` type **krea2** | No MODEL or LATENT — wire those to the sampler yourself |

### Widgets

| Widget | Description |
|--------|-------------|
| **brush_size** | Paint brush diameter |
| **region_strength** | Strength of each painted region’s prompt |
| **quality_prompt** | Global quality / style text |
| **scene_prompt** | Global scene / setting text |
| **red / blue / yellow / green / magenta_prompt** | Per-color region prompts |
| **negative_prompt** | Negative conditioning |
| **regional_enabled** | On = use regions · Off = global prompts only |
| **keep_mask** | Keep painted regions across runs |
| **stop_on_empty_mask** | Pause if nothing is painted (no hard error) |
| **pause_until_apply** | Hold the graph until **Apply** is clicked |

**Optional inputs:** `image` (background), `quality_prompt_in` / `scene_prompt_in` / `negative_prompt_in`.

**Required (Anima):** `model`, `clip`, `width`, `height`  
**Required (Krea2):** `clip`, `width`, `height`

**Anima outputs:** `IMAGE`, `MODEL`, `POSITIVE`, `NEGATIVE`, `LATENT`, `JSON`, `MASK_PREVIEW`  
**Krea2 outputs:** `IMAGE`, `POSITIVE`, `NEGATIVE`, `JSON`, `MASK_PREVIEW`

### How to use

1. Wire **clip**, **width**, **height** (Anima: also **model**). Optional **image** for a background.
2. Queue Prompt — the node **pauses**.
3. Paint color regions; edit prompts.
4. Click the green **Apply** button — the workflow continues.
5. Toolbar: **Undo**, **Clear Canvas**, **Reset 🖌️**, **Apply**.

### Tips

- Canvas size comes only from **width** / **height** connections.
- Muted or disconnected image → white background.
- Linked prompt inputs lock the matching text fields.
- Empty mask with **stop_on_empty_mask** pauses without throwing.

### Region colors

| Color | Widget |
|-------|--------|
| Red | `red_prompt` |
| Blue | `blue_prompt` |
| Yellow | `yellow_prompt` |
| Green | `green_prompt` |
| Magenta | `magenta_prompt` |

---

## 🎚️ LC123 Slider

mxToolkit-style slider rebuilt for **Nodes 2.0** (DOM UI, not canvas paint).

Works in Nodes 1.0 and 2.0. Output type is `*` (any) so it connects to INT or FLOAT inputs.

### Face

- Drag the track to change the value  
- Click the number to type a value  
- **⚙ Settings** → min, max, step, decimals  

### Settings

| Setting | Description |
|---------|-------------|
| **min / max** | Slider range |
| **step** | Snap increment (always snaps) |
| **decimals** | `0` → integer value · `1–4` → float precision |

### Output

`*` — integer when decimals = 0, float otherwise.

---

## Layout

```text
ComfyUI_LC123_nodes/
├── __init__.py
├── aspect_ratio.py          # 📐 Aspect Ratio Simplifier
├── regional_canvas.py       # Anima + Krea2 Regional Inline Canvas
├── slider.py                # 🎚️ LC123 Slider
├── web/
│   ├── inline_regional_canvas.js
│   └── lc123_slider.js
├── README.md
├── LICENSE
├── .gitignore
└── .comfyignore
```

---

---

## Troubleshooting

### Nodes do not appear after install

1. Confirm the folder name is exactly `ComfyUI_LC123_nodes` under `ComfyUI/custom_nodes/`.
2. Restart **ComfyUI fully** (close the terminal / stop the service, start again). A browser refresh alone is not enough for new Python nodes.
3. Hard-refresh the UI: `Ctrl+F5` (Windows/Linux) or `Cmd+Shift+R` (macOS).
4. Open the ComfyUI terminal log and look for:
   - `ImportError` / `ModuleNotFoundError` under `ComfyUI_LC123_nodes`
   - `Traceback` while loading custom nodes  
   Fix any reported error, then restart again.
5. In the node search box, try the class IDs: `AspectRatioSimplifier`, `AnimaRegionalCanvasInline`, `Krea2RegionalCanvasInline`, `LC123Slider`.

### Slider looks blank or settings do nothing (Nodes 2.0)

- Hard-refresh after updating `web/lc123_slider.js`.
- **Delete** the old slider node and **add a new** 🎚️ LC123 Slider (widget layout changed between versions).
- Confirm `ComfyUI_LC123_nodes/web/lc123_slider.js` exists (not only `slider.py`).
- Disable conflicting old mxToolkit slider experiments if they override the same extension name.

### Regional canvas does not show / Apply does not resume

- Hard-refresh so `web/inline_regional_canvas.js` loads.
- Ensure **width** and **height** are connected (force-input).
- With **pause_until_apply** on, the graph **stops** until you click the green **Apply** button on the node.
- Empty paint + **stop_on_empty_mask** also pauses by design; paint a region or turn that toggle off.
- Krea2: load CLIP with type **krea2**. This variant has **no MODEL or LATENT** outputs — wire those around the node.

### Aspect Ratio Simplifier errors

- Connect at least an **image** or a **mask** (or both).
- If a workflow was saved with an older widget order, **re-add** the node so widgets realign (especially after `max_resolution` / `resolution_source` changes).
- `"aspect_ratio is not available"` usually means stale `widgets_values` — replace the node on the canvas.

### General update checklist

After pulling a new version:

```bash
cd ComfyUI/custom_nodes/ComfyUI_LC123_nodes
git pull
```

Then:

1. Restart ComfyUI  
2. Hard-refresh the browser  
3. Re-add nodes that changed inputs/outputs (slider, Krea2 canvas, aspect ratio)  

Old graphs may keep outdated widget lists until the node instance is replaced.

### Still stuck?

- Note ComfyUI version, Nodes 1.0 vs 2.0, and the exact log traceback.
- Open an issue on [GitHub](https://github.com/lonecatone23/ComfyUI_LC123_nodes) with that info (no API keys or private workflows).

## License

MIT — see [LICENSE](LICENSE).

Use and modify freely with your ComfyUI setup.

If this pack helps your workflows: [Buy me a ☕](https://ko-fi.com/lonecatone)
