# ComfyUI LC123 Nodes

> **v1.2.0 (BETA)** — Active development. Expect breaking changes (especially Regional Canvas I/O). Feedback welcome.

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
| **📐 Aspect Ratio Simplifier** | `LC123` | `AspectRatioSimplifier` |
| **Anima Regional Inline Canvas** | `Anima/Regional` | `AnimaRegionalCanvasInline` |
| **Krea2 Regional Inline Canvas** | `Krea2/Regional` | `Krea2RegionalCanvasInline` |
| **LC Slider** | `LC123/utils` | `LCSlider` |
| **LC Dynamic Overlay** | `LC123/image` | `LCDynamicOverlay` |
| **LC Combo Selector** | `LC123/utils` | `LCComboSelector` |
| **LC AnySwitch** | `LC123/utils` | `LCAnySwitch` |
| **LC Bypasser** | `LC123/utils` | `LC Bypasser` |
| **LC Groups Bypasser** | `LC123/utils` | `LC Groups Bypasser` |

`LC Bypasser` and `LC Groups Bypasser` are **frontend virtual nodes** (JavaScript only). Mute/bypass is applied in the UI before the graph is queued.

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

Interactive RGB paint canvas. Emits **separate** global / per-color conditionings and masks so you can plug into [Sen-sou Anima Regional Conditioning](https://github.com/Sen-sou/Comfyui-Anima-Regional-Conditioning) or any other regional system.

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
- After this I/O change, **delete and re-add** the Anima node on old workflows.

---

## Krea2 Regional Inline Canvas

Same paint UI; CLIP type **krea2**. Still uses Comfy mask/area conditioning (combined positive).

**Required:** `clip`, `width`, `height` — **no** MODEL or LATENT pass-through.

**Outputs:** `IMAGE`, `POSITIVE`, `NEGATIVE`, `JSON`, `MASK`

Wire UNET and empty latent around the node to the sampler.

---

## LC Slider

Value slider with on-node face UI (DOM). Works in Nodes 1.0 and 2.0.

**Display name:** LC Slider · **ID:** `LCSlider`.

| Setting | Description |
|---------|-------------|
| **min / max** | Range |
| **step** | Snap increment |
| **decimals** | `0` = int · `1–4` = float precision |

Output type `*` (INT or FLOAT depending on decimals).

---

## LC Dynamic Overlay

Compare / composite two images with a **live circular opacity knob** on the node.

| Input | Role |
|-------|------|
| **image_a** | Base image — sets output resolution |
| **image_b** | Overlay — fit-scaled to A (uniform scale, centered, no stretch/crop) |
| **opacity** | 0–1 (driven by the on-node knob; widget is hidden in the UI) |

**Output:** composited `IMAGE` at the current opacity (for the rest of the graph).

### Live preview

1. Queue once with both images connected.
2. Drag the **circular knob** above the preview — overlay updates **immediately** (no re-queue).
3. Opacity sticks when released until you move it again.
4. Center of the knob shows the percentage; blue arc tracks the value.

Graph output still reflects the opacity from the last queue (standard Comfy behaviour). The on-node view is what updates live.

---

## LC Combo Selector

Remote dropdown for another node’s **combo** setting (scheduler, sampler name, upscale method, etc.).

**Reads** the option list from the target — it does not define its own list.

### Setup

1. On the target node, right-click the combo widget → **Convert to input**.
2. Add **LC Combo Selector** and wire its output into that input.
3. The LC Combo Selector dropdown fills with the target’s real options (status shows e.g. `12 options`).
4. Choose a value — it is sent into the target on queue.

### Notes

- Output type is `*` so it can connect to combo inputs (plain `STRING` often cannot).
- Options are taken from the target’s live widget and/or node definition (`INPUT_TYPES`).
- Disconnect → dropdown clears until you connect again.
- After updating the JS, hard-refresh and reconnect (or re-add) the node.

**Class ID:** `LCComboSelector` · **Category:** `LC123/utils`

---

## LC AnySwitch

Top-down priority switch (first connected input wins), similar to rgthree **Any Switch**, with two important differences:

1. **Use Everywhere blocked** — `cg-use-everywhere` will not auto-wire into the switch inputs (avoids circular links and surprise defaults).
2. **Type lock** — the first connection sets the type for every socket and the output. Mismatched types cannot be wired. When **all** inputs are disconnected, the node resets to `*` and accepts a new type.

### Widgets

| Widget | Description |
|--------|-------------|
| **inputcount** | Number of input slots (2–20), same idea as JoinStringMulti |

### Behaviour

| State | Effect |
|-------|--------|
| Blank (no links) | All sockets accept `*` |
| First connection | That type locks **all** inputs + output |
| Further connections | Only the locked type is accepted |
| Fully disconnected | Resets to `*` |

Priority is top-down: `any_01` → `any_02` → … first connected value is passed through.

---

## LC Bypasser

Frontend virtual node (no Python execution). Per-node bypass control with optional remote BOOLEAN sockets.

Replaces the common **Node Collector + Fast Bypasser** pattern without depending on rgthree.

### Layout

Each connection is a pair:

```text
*        → connect any node output (Load Image, etc.)
enable   → optional BOOLEAN (true = active, false = bypass)
*        → next connection…
enable
*        → empty slot ready for another
```

### Behaviour

| Control | Effect |
|---------|--------|
| **Toggle widget** | Click to enable / bypass the linked node |
| **BOOLEAN → enable** | Drives that pair; toggle locks (🔒) and is not clickable |
| Disconnect BOOLEAN | Toggle unlocks again |

- `true` / yes → node mode **ALWAYS** (active)
- `false` / no → node mode **BYPASS** (4)

### Right-click menu

- **Enable all** / **Bypass all** / **Toggle all** (skips locked rows)
- **Restriction:** `default` · `max one` · `always one`

### Notes

- Bypass is client-side only (applied before queue). It cannot change mid-execution.
- `OPT_CONNECTION` output is optional passthrough for chaining.
- After updating the JS file, hard-refresh and re-add the node if behaviour looks stale.

---

## LC Groups Bypasser

Frontend virtual node (no Python execution, **no rgthree dependency**).

Discovers groups in the current workflow and exposes one control row per group.

### Layout

For each group (e.g. `Group 1`, `Group 2`):

```text
Toggle:  Enable Group 1
Socket:  Group 1   (BOOLEAN, optional)
Toggle:  Enable Group 2
Socket:  Group 2   (BOOLEAN, optional)
```

### Behaviour

| Control | Effect |
|---------|--------|
| **Toggle** | Enable / bypass **all nodes inside that group** |
| **BOOLEAN → group socket** | Drives that group only; toggle locks (🔒) |
| Other groups | Remain independently controllable |

### Properties

| Property | Description |
|----------|-------------|
| **matchTitle** | Substring or regex filter on group titles |
| **matchColors** | Comma-separated colour names or hex codes |
| **sort** | `position` (default) or `alphanumeric` |
| **toggleRestriction** | `default` · `max one` · `always one` |

### Right-click menu

- **Refresh groups**
- **Enable all** / **Bypass all** / **Toggle all** (manual rows only)
- **Restriction** / **Sort** cycle

### Notes

- Group membership uses LiteGraph’s group node list when available, otherwise bounding-box overlap.
- New or renamed groups are picked up automatically (periodic scan).
- Same client-side bypass limitation as **LC Bypasser**.
- Hard-refresh after install; delete and re-add the node once if toggles misbehave after an upgrade.

---

## Layout

```text
ComfyUI_LC123_nodes/
├── __init__.py
├── aspect_ratio.py
├── anima_regional_canvas.py      # Anima Regional Inline Canvas
├── krea2_regional_canvas.py      # Krea2 Regional Inline Canvas
├── regional_canvas_common.py     # Shared paint / mask helpers
├── regional_canvas.py            # Compatibility shim
├── slider.py
├── dynamic_overlay.py            # LC Dynamic Overlay
├── lc_any_switch.py              # LC AnySwitch
├── lc_combo.py                   # LC Combo Selector
├── web/
│   ├── inline_regional_canvas.js
│   ├── lc123_slider.js
│   ├── lc_dynamic_overlay.js     # LC Dynamic Overlay UI
│   ├── lc_any_switch.js          # LC AnySwitch UI (type-lock + UE block)
│   ├── lc_combo.js               # LC Combo Selector UI (option discovery + dropdown)
│   ├── lc_bypasser.js            # LC Bypasser
│   └── lc_groups_bypasser.js     # LC Groups Bypasser
├── README.md
├── LICENSE
├── pyproject.toml
├── .gitignore
└── .comfyignore
```

`WEB_DIRECTORY = "./web"` loads every `.js` file in `web/` automatically.

---

## Troubleshooting

### Nodes do not appear after install

1. Folder name must be `ComfyUI_LC123_nodes` under `ComfyUI/custom_nodes/`.
2. Restart ComfyUI fully (not only browser refresh).
3. Hard-refresh UI: `Ctrl+F5` / `Cmd+Shift+R`.
4. Check the terminal for `ImportError` under this pack.
5. Search class IDs: `AspectRatioSimplifier`, `AnimaRegionalCanvasInline`, `Krea2RegionalCanvasInline`, `LCSlider`, `LCDynamicOverlay`, `LCComboSelector`, `LCAnySwitch`, `LC Bypasser`, `LC Groups Bypasser`.

### LC Combo Selector — no dropdown / “N options” but empty field

1. Confirm `web/lc_combo.js` is loaded (console: `[LC123.Combo]`).
2. Target combo must be **Convert to input**, then wire LC Combo Selector into it.
3. Hard-refresh; disconnect and reconnect, or delete and re-add LC Combo Selector.
4. Status under the node: `12 options` = discovery OK · `not connected` · `no options found`.

### LC Dynamic Overlay — no live preview

1. Confirm `web/lc_dynamic_overlay.js` exists and hard-refresh.
2. Queue the node **once** so A and B are cached.
3. Browser console should log the extension on load.
4. Delete and re-add the node after upgrades.

### LC AnySwitch — Use Everywhere still connecting

1. Confirm `web/lc_any_switch.js` is loaded (console: `[LC123.AnySwitch]`).
2. Hard-refresh; delete and re-add the switch node.
3. UE block is re-asserted periodically; if a specific UE version still links, report the version.

### LC Bypasser / LC Groups Bypasser missing

1. Confirm `web/lc_bypasser.js` and `web/lc_groups_bypasser.js` exist.
2. Hard-refresh (`Ctrl+F5`).
3. Open the browser console — look for `[LC123.Bypasser]` / `[LC123.GroupsBypasser] registered`.
4. Virtual nodes only appear in the **Add node** menu after the frontend extension loads.

### LC Groups Bypasser toggles wrong after update

Delete the node and add a fresh **LC Groups Bypasser**. Saved widget state from older JS revisions can be inconsistent.

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

Hard-refresh; delete and re-add the slider node; confirm `web/lc123_slider.js` exists. Search **LC Slider**.

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
