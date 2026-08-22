# ComfyUI LC123 Nodes

Custom nodes for [ComfyUI](https://github.com/comfyanonymous/ComfyUI) by [lonecatone23](https://github.com/lonecatone23).

- **Repo:** [https://github.com/lonecatone23/ComfyUI_LC123_nodes](https://github.com/lonecatone23/ComfyUI_LC123_nodes)
- **Support:** [Buy me a ☕](https://ko-fi.com/lonecatone)
- **Version:** 1.12.0

> Small tools that remove friction — less wire mess, fewer clicks, clearer workflows.

> **"True, nothing is. Permitted, everything is"**  
> — Yoda Auditore, *Assassin's Wars*

For **Anima regional attention**, also install [Sen-sou Anima Regional Conditioning](https://github.com/Sen-sou/Comfyui-Anima-Regional-Conditioning).

---

## What’s new in 1.12.0

| Area | Changes |
|------|---------|
| **🗒️ Prompt Builder suite** | Subject, Subject Array, Scene, Camera, Lighting, Style, Color Palette, **🧩 Assembler** — modular prompt + Krea2/Ideogram JSON |
| **🧩 Assembler** | `prompt` for CLIP; `json` for regional builders; **include_scene_bboxes** (default off = subject boxes only); margin |
| **🎲LC Wildcard** | Random line from `assets/wildcards/`; `base_seed` + `seed_mode` (no seed socket; no double control widget) |
| **🌱LC Seed** | Utility seed with the same seed_mode (partial-run friendly) |
| **Chrome** | Per-node colors for the prompt suite (scene red, lighting gold, style purple, etc.) |
| **Docs** | [`LC_Prompt_Builder_Note.md`](LC_Prompt_Builder_Note.md) |

---

## 🗒️ Prompt Builder (highlight)

Modular stack → one assembler:

```
Subjects + Scene + Camera + Lighting + Style + Palette
        → 🧩LC Prompt Assembler
              → prompt  → conditioning
              → json    → Krea2 / Ideogram builder
```

- Editable lists: `assets/prompt_builder/`, `assets/wildcards/`
- **prompt** = natural language for CLIP. **json** = structured import (subject bboxes by default)
- Full guide: [`LC_Prompt_Builder_Note.md`](LC_Prompt_Builder_Note.md)

---

## ⚙️ LC123 Performance (Settings)

**UI only** — smoother scrolling and lighter on-node previews. Does **not** change generation VRAM or socket output quality.

**Settings → LC123 → Performance**

| Setting | Default | Effect |
|--------|---------|--------|
| **Remove wipe** | Off | No hover wipe on image FX previews |
| **Half-resolution previews** | Off | FX previews at half the node image area |
| **Clamp longest side** | Off | Cap on-node preview bitmap size |
| **Max edge (px)** | 768 | Used when clamp is on |
| **No preview when collapsed** | On | Skip draw on collapsed FX nodes |
| **Hide FX on-node previews** | Off | Hide all LC image FX previews |
| **Skin Beauty full preview override** | On | Skin Beauty keeps full-quality preview |

**Not affected:** LC Image Compare, Dynamic Overlay, Image Split (always full interactive).

Details: [`LC123_Performance_Settings_Note.md`](LC123_Performance_Settings_Note.md)

---

## ✨ LC Skin Beauty

On-node skin polish with presets that drive the sliders. Optional external mask. See pack notes / workflow docs for controls.

---

## 📷 LC Photo Style

Camera / phone **finish** look. Style presets drive the sliders; most controls use **0 = no change**. **Strength** blends with the original.

Presets include Standard, Natural, Dramatic, Quiet, Muted, Amateur, Cool day, Warm evening, Bright open, iPhone, **Nikon Z7 II**, **Canon R5**.

Full control list: [`LC_Photo_Style_Note.md`](LC_Photo_Style_Note.md)

---

## 🔪 LC Sharpen Pro

Photorealism-first: guided + box hybrid, auto halo with sharpen, skin gate. Presets: **Natural, Subtle, Portrait, Product, Landscape, Crisp** + **Lineart, Anime sharp**. Sliders snap to **Custom** when moved.

---

## 🖼️ Image & size

| Node | What it does |
|------|----------------|
| **📐 Aspect Ratio Simplifier** | Size from image, mask, or preset. Resize image + mask. Crop / stretch / pad / total pixels. Empty latent. Default upscale: lanczos. |
| **📐 Aspect Ratio Simplifier (pipe)** | Same + pipe out for Get/Set. |
| **LC Aspect Ratio Pipe Out** | Unpack aspect pipe. |
| **LC Get Image 📐** | Megapixels, width, height, batch, aspect, resolution (longer side). |
| **LC Dimension Resize 📐** | Width + height + one value; add/sub/mul/div both; rounded outs. |
| **LC Image Crop 🖼️🔪** | Interactive crop with aspect lock. |
| **LC Image Compare 🔎** | Batch A/B with one slider. |
| **LC Image Split 🖼️** | Saveable wipe; slider sets split (no drag-on-image). |
| **LC Image Grid 🖼️** | Contact sheet from multiple images. |
| **LC Last Image Holder** | Hold last image; clear without re-run. |
| **LC Dynamic Overlay** | Overlay B on A; opacity knob after one queue. |
| **LC Watermark 💧** | Image watermark; size, opacity, drag place. |

---

## 🎨 Image FX (preview + wipe)

Smart Denoise, Color Match (skin protect), Bloom, Vignette, Image RGB, Lift/Gamma/Gain, Auto White Balance, Vibrance, Chromatic Aberration, Sharpen Pro, Image Adjust, Lens Effects, Lens Profile, Film Stock BW/Color, Film Grain, Desaturate, Apply LUT, Text Overlay, Skin Beauty, Photo Style, and more.

---

## 🧪 Sampling · pipes · folders · logic

Dual sigma / basic scheduler, sampler configure (+ pipe out), prompt→conditioning (+ zero), easy/advanced folders, save text, join strings, show text, text replace/remove, Civitai compliance strip, any-switch, combo, boolean / invert / switch, int/float compare, seed jump, **🌱LC Seed**, slider, notify, bypasser / groups / panel, node snapshot, VRAM cache clear, stop, regional canvases.

---

## 📦 Assets

| Path | Use |
|------|-----|
| `assets/sounds/` | **LC Notify 🔊** |
| `assets/lists/` | e.g. Civitai compliance strip |
| `assets/luts/` | Sample LUTs → copied to **`models/luts/`** on load if missing (never overwrites) |
| `assets/wildcards/` | **🎲LC Wildcard** `.txt` lists |
| `assets/prompt_builder/` | Prompt Builder preset JSON |
| `assets/readme/` | Optional README images |

**LUT path for Apply LUT:** `ComfyUI/models/luts/` (not under custom_nodes).

---

## 💡 Quick tips

- **Prompt Builder:** `prompt` → conditioning; `json` → regional builder only. Leave **include_scene_bboxes** off unless you want furniture boxes.
- **Wildcard / Seed:** use **seed_mode** (fixed / randomize / increment / decrement); works when queueing a single node.
- **Image FX:** fix seed, run low-res, tune, then full run.
- **Performance:** Settings → LC123 if the graph feels heavy while scrolling.
- **Notify:** drop audio into `assets/sounds/`, restart once for the dropdown.

---

**"True, nothing is. Permitted, everything is"**  
_Yoda Auditore. *Assassin's Wars*_
