# ComfyUI LC123 Nodes

Custom nodes for [ComfyUI](https://github.com/comfyanonymous/ComfyUI) by [lonecatone23](https://github.com/lonecatone23).

- **Repo:** https://github.com/lonecatone23/ComfyUI_LC123_nodes
- **Support:** [Buy me a ☕](https://ko-fi.com/lonecatone)

> Small tools that remove friction — less wire mess, fewer clicks, clearer workflows.

For **Anima regional attention**, also install [Sen-sou Anima Regional Conditioning](https://github.com/Sen-sou/Comfyui-Anima-Regional-Conditioning).

**Version 1.5.0**

---

## Install

1. Clone or unzip into `ComfyUI/custom_nodes/ComfyUI_LC123_nodes`
2. Restart ComfyUI
3. Hard-refresh the browser (Ctrl+F5)

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/lonecatone23/ComfyUI_LC123_nodes.git
```

---

## 🖼️ Image & size

| Node | What it does |
|------|----------------|
| **📐 Aspect Ratio Simplifier** | Size from image/mask/preset. Resize together. Crop/stretch/pad/total pixels. Empty latent. Default upscale: **lanczos**. |
| **📐 Aspect Ratio Simplifier (pipe)** | Same + pipe out for Get/Set. |
| **LC Aspect Ratio Pipe** | Unpack aspect pipe. |
| **LC Get Image 📐** | Megapixels, width, height, batch, aspect. |
| **LC Image Crop 🖼️🔪** | Interactive crop + aspect lock. |
| **LC Image Compare 🔎** | Batch A/B compare, one slider. |
| **LC Last Image Holder** | Hold last image for before/after. |
| **LC Dynamic Overlay** | Overlay B on A; live opacity after one run. |

## 🎨 Image FX

On-node preview; most support before/after wipe (hover). **Text Overlay** and **Watermark** use live drag (no wipe).

| Node | Notes |
|------|--------|
| LC Image Adjust, Auto White Balance, Sharpen Pro, Lens Effects, Lift Gamma Gain, Image RGB | Color / tone / sharpen |
| Film Grain, Vibrance, Vignette, Bloom, Denoise, Desaturate | Texture / polish |
| Color Match 🎨 | Reference match; no ref = bypass |
| Film Stock B&W / Color, Lens Profile, Chromatic Aberration | Looks |
| Apply LUT | LUT file |
| **LC Text Overlay** | Drag text; live size/color/position |
| **LC Watermark 💧** | Drag watermark; live size/opacity; 2nd queue applies baked result; no watermark = bypass |

## 🎨 Regional canvas

| Node | Notes |
|------|--------|
| Anima Regional Inline Canvas | R/G/B paint → Sen-sou conditioning |
| Krea2 Regional Inline Canvas | Krea2 CLIP regions (**beta**) |

## 🔧 Sampling helpers

| Node | Notes |
|------|--------|
| LC Sampler Configure (+ pipe variants) | Dual-pass steps/CFG/denoise/sampler |
| LC Split Sigma Scheduler | High/low sigmas; optional 2nd model |
| LC VRAM Cache Clear | Clear cache between stages |
| LC Stop 🛑 | Queue breakpoint + enable bypass |

## 🧵 Pipes

**LC Pipe In / Out / Edit** — pack models, clips, VAEs, size, latent, prompts, seed, steps, CFGs, sampler. KJ Get/Set friendly.

## ✍️ Prompts & text

| Node | Notes |
|------|--------|
| Positive / Negative | Colored prompt boxes |
| Prompt to Conditioning (+ Zero) | Encode (+ zero-out) |
| **LC Join Strings 🔗** | Null-safe join; empty slots skipped |
| **LC Show Text 🔤** | On-node text; optional pretty JSON |
| **📝 LC Save Text** | Write text; Windows path sanitization |

## 📁 Folders

| Node | Notes |
|------|--------|
| LC Easy Folder 📂 | prefix for native Save Image |
| LC Advanced Folder 📂 | filename + path for Image Saver Simple |

## 🔀 Logic & control

| Node | Notes |
|------|--------|
| LC AnySwitch, Combo Selector, Boolean, Invert Boolean, Slider | Routing / values |
| **LC Bypasser** | `*` + enable BOOLEAN + toggles; collapse OK; labels follow renames |
| **LC Groups Bypasser** | Same for graph groups |
| **LC Bypasser Panel** | Widgets-only remote via `OPT_CONNECTION` → `hub` |

---

## Example workflows

See the `workflows/` folder for aspect ratio, dual sigma, regional canvas, and post-processing examples.

---

## Changelog (1.5.0)

- LC Watermark 💧 (live drag / size / opacity)
- LC Join Strings, LC Show Text (pretty JSON)
- LC Bypasser Panel; bypasser rename-aware labels; flicker fixes
- Save Text path sanitization
- Aspect Ratio default upscale → lanczos
- Docs refresh

---

MIT · [ko-fi.com/lonecatone](https://ko-fi.com/lonecatone)
