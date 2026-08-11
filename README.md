# ComfyUI LC123 Nodes

Custom nodes for [ComfyUI](https://github.com/comfyanonymous/ComfyUI) by [lonecatone23](https://github.com/lonecatone23).

- **Repo:** [https://github.com/lonecatone23/ComfyUI_LC123_nodes](https://github.com/lonecatone23/ComfyUI_LC123_nodes)
- **Support:** [Buy me a ☕](https://ko-fi.com/lonecatone)
- **Version:** 1.4.0

> Small tools that remove friction — less wire mess, fewer clicks, clearer workflows.

For **Anima regional attention**, also install [Sen-sou Anima Regional Conditioning](https://github.com/Sen-sou/Comfyui-Anima-Regional-Conditioning).

---

## 🖼️ Image & size

| Node | What it does |
|------|----------------|
| **📐 Aspect Ratio Simplifier** | Size from image, mask, or preset. Resize image + mask together. Crop / stretch / pad / total pixels. Empty latent out. |
| **📐 Aspect Ratio Simplifier (pipe)** | Same controls with a **pipe** output for Get/Set routing. |
| **LC Aspect Ratio Pipe** | Unpacks an aspect-ratio pipe into image, mask, width, height, latent, batch. |
| **LC Get Image 📐** | Reads megapixels, width, height, batch, aspect ratio from an image. |
| **LC Image Compare 🔎** | Batch compare with one synchronized pair slider (Aₙ ↔ Bₙ). Fixed layout. |
| **LC Last Image Holder** | Holds the last generated image for before/after. Clear without re-running. |
| **LC Dynamic Overlay** | Overlay B on A (A sets resolution). Live opacity knob after one queue. |
| **LC Image Crop 🖼️🔪** | Interactive crop with aspect lock. Drag handles on the preview. |

---

## 🎨 Regional canvas

| Node | What it does |
|------|----------------|
| **Anima Regional Inline Canvas** | Paint R/G/B regions on the node. GLOBAL / RED / GREEN / BLUE conditioning + masks for Sen-sou Anima. Pauses until Apply. |
| **Krea2 Regional Inline Canvas** | Same paint UI for Krea2 CLIP regional work. **Beta.** |

---

## 🎞️ Post-processing (on-node preview)

Most of these show the result on the node and support a **hover wipe** (after vs before). Defaults match a practical grading stack.

| Node | What it does |
|------|----------------|
| **LC Image Adjust** | Hue / saturation / brightness / contrast / sharpness (−1…1). |
| **LC Auto White Balance** | Gray-world / shades-of-gray style WB. |
| **LC Sharpen Pro** | Clarity FX–style midtone structure with blend-if + dark/light intensity. |
| **LC Lens Effects** | Chromatic aberration, vignette, grain in one pass. |
| **LC Lift Gamma Gain** | Classic lift / gamma / gain / offset. |
| **LC Image RGB** | Per-channel RGB gain. |
| **LC Film Grain** | Controllable grain size, strength, color grain, softness. |
| **LC Vibrance** | Vibrance + saturation with optional skin protection. |
| **LC Vignette** | Soft / cos⁴ vignette with midpoint, roundness, tint. |
| **LC Bloom** | Soft bloom / glow. |
| **LC Image Denoise** | Edge-aware denoise (blur strength, edge preservation, strength). |
| **LC Color Match 🎨** | Match colors to a reference (AdaIN / mean-std). No reference = **bypass**. |
| **LC Film Stock (B&W)** | B&W film stock emulation + color filter. |
| **LC Film Stock (Color)** | Color negative / slide stock curves + split tone. |
| **LC Lens Profile** | Lens distortion / CA / vignette profile (add or correct). |
| **LC Chromatic Aberration** | Per-channel R/G/B shift (horizontal / vertical). |
| **LC Image Desaturate** | Essentials-style desaturate (Rec.709, average, lightness, …). |
| **LC Apply LUT** | Apply a `.cube` LUT with strength + optional log path. |
| **LC Text Overlay** | Text on image: curated fonts, wrap, margins, drag placement, live preview. |

---

## 🔧 Sampling helpers

| Node | What it does |
|------|----------------|
| **LC Sampler Configure** | Dual-pass settings: total steps, CFGs, denoise, step swap, sampler, scheduler. |
| **LC Sampler Configure (pipe)** | Same widgets + **pipe** out. |
| **LC Sampler Configure Pipe** | Unpacks a sampler pipe. |
| **LC Split Sigma Scheduler** | Split sigmas across two models at a step swap (high / low). |
| **LC Pipe In / Out / Edit** | Bundle model, CLIP, VAE, latent, prompts, seed, steps, CFG, sampler… Get/Set friendly. |
| **Prompt to Conditioning** | String → conditioning. |
| **LC Prompt to Conditioning + Zero** | Same + zero-out conditioning socket. |

---

## 📁 Save & folders

| Node | What it does |
|------|----------------|
| **LC Easy Folder 📂** | Simple path + filename for native save nodes (timestamp options). |
| **LC Advanced Folder 📂** | Split path / filename for Image Saver style nodes. |
| **📝 LC Save Text** | Save text to disk with prefix / suffix helpers. |

---

## ✍️ Prompts

| Node | What it does |
|------|----------------|
| **Positive** | Green positive prompt box. |
| **Negative** | Red negative prompt box. |

---

## 🛑 Control & memory

| Node | What it does |
|------|----------------|
| **LC Stop 🛑** | Pause the graph until you press ▶️ (optional bypass switch). |
| **LC VRAM Cache Clear** | Clear VRAM + cache; any-in / any-out pass-through. |

---

## 🔀 Routing & UI

| Node | What it does |
|------|----------------|
| **LC AnySwitch** | First connected input among many. Type-locks. Blocks Use Everywhere auto-wire. |
| **LC Combo Selector** | Dropdown that mirrors another node’s combo options. |
| **LC Boolean** | Coerce bool / int / float → true/false. Shows result on face. |
| **LC Invert Boolean** | Same, inverted. |
| **LC Bypasser** | Bypass nodes from one place. Optional BOOLEAN enables. |
| **LC Groups Bypasser** | Same for graph groups. |
| **LC Slider** | On-node slider. Min / max / step / decimals. INT or FLOAT. Nodes 2.0 friendly. |

---

## Install

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/lonecatone23/ComfyUI_LC123_nodes.git
```

Restart ComfyUI. Nodes appear under **LC123** categories.

---

## Workflows

Example graphs live in `workflows/`:

- Aspect Ratio Simplifier
- Anima / Krea2 Inline Regional Canvas
- LC Dual Sigma
- LC Node examples
- Post processing LC nodes

---

## Notes

- Image tool nodes use a shared on-node preview (≈300px wide, padded). Hover for before/after wipe where both frames exist.
- Pipe Get/Set is **not** bundled — use **KJ Set/Get** or a direct pipe wire.
- Default colors group nodes by role (utilities, image, folders, prompts, stop).
- Questions → GitHub issues, or find me on the usual channels.

*Thanks for using LC123. Go make something weird.* 🐱
