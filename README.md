# ComfyUI LC123 Nodes

Custom nodes for [ComfyUI](https://github.com/comfyanonymous/ComfyUI) by [lonecatone23](https://github.com/lonecatone23).

- **Repo:** [https://github.com/lonecatone23/ComfyUI_LC123_nodes](https://github.com/lonecatone23/ComfyUI_LC123_nodes)
- **Support:** [Buy me a ☕](https://ko-fi.com/lonecatone)

> Small tools that remove friction — less wire mess, fewer clicks, clearer workflows.

**Version 1.7.2**

For **Anima regional attention**, also install [Sen-sou Anima Regional Conditioning](https://github.com/Sen-sou/Comfyui-Anima-Regional-Conditioning).

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
| **📐 Aspect Ratio Simplifier** | Size from image, mask, or preset. Resize image + mask together. Crop / stretch / pad / total pixels. Empty latent out. Default upscale: **lanczos**. **resolution** = longer side. |
| **LC Aspect Ratio Simplifier 📐(Pipe)** | Same controls, plus a **pipe** output on top for Get/Set routing. |
| **LC Aspect Ratio Pipe Out** | Unpacks an aspect-ratio pipe into image, mask, width, height, latent, batch, resolution. |
| **LC Dimension Resize 📐** | Apply add/subtract/multiply/divide to width and height with one value; rounded INT outs. |
| **LC Get Image 📐** | Megapixels, width, height, batch, aspect ratio, and **resolution** (longer side). |
| **LC Image Crop 🖼️🔪** | Interactive crop with aspect lock; preview on the node; cropped image out. |
| **LC Image Compare 🔎** | Batch A/B compare with one slider (A1↔B1, A2↔B2, …). Layout stays fixed. |
| **LC Last Image Holder** | Holds the last image for before/after. Survives disconnect; clear empties without re-running. |
| **LC Dynamic Overlay** | Overlay B on A; **blended Image** out. After one queue, drag the opacity knob — no re-gen to preview. |
| **LC Watermark 💧** | Image watermark: size, opacity, drag place. Bypasses if no watermark image. |

---

## 🎨 Image FX (on-node preview + before/after wipe)

| Node | What it does |
|------|----------------|
| **LC Image Adjust** | Brightness, contrast, saturation, hue (−1…1 style). |
| **LC Auto White Balance** | Auto white-balance correction. |
| **LC Sharpen Pro** | Adaptive mid-tone / micro-contrast. |
| **LC Lens Effects** | Lens-style FX suite. |
| **LC Lift Gamma Gain** | Lift / gamma / gain adjust. |
| **LC Image RGB** | Per-channel RGB adjust. |
| **LC Film Grain** | Film grain overlay. |
| **LC Vibrance** | Vibrance (smart saturation). |
| **LC Vignette** | Vignette darkening. |
| **LC Bloom** | Bloom / glow. |
| **LC Image Denoise** | Smart denoise. |
| **LC Color Match 🎨** | Match colors to a reference. No reference → bypass. |
| **LC Film Stock (B&W / Color)** | Film stock looks. |
| **LC Lens Profile** | Lens profile character. |
| **LC Chromatic Aberration** | RGB channel split CA. |
| **LC Image Desaturate** | Desaturate. |
| **LC Apply LUT** | Apply a LUT file. |
| **LC Text Overlay** | Place text on the image (drag, font, color, size). |

---

## 🎨 Regional canvas

| Node | What it does |
|------|----------------|
| **Anima Regional Inline Canvas** | Paint R/G/B regions for Sen-sou Anima. |
| **Krea2 Regional Inline Canvas** | Same paint UI for Krea2. **Beta.** |

---

## 🔧 Sampling helpers

| Node | What it does |
|------|----------------|
| **LC Sampler Configure** | total steps, step swap, detailer steps, denoise (0.01 step), CFG 1/2, sampler, scheduler. |
| **LC Sampler Configure (pipe)** | Same + pipe on top. |
| **LC Sampler Configure Pipe Out** | Unpacks a sampler pipe. |
| **LC Split Sigma Scheduler** | High/low sigma schedules; optional 2nd model. |
| **LC Basic Scheduler** | Model + scheduler + steps → SIGMAS (no denoise). |
| **LC Split Sigmas (Advanced)** | Two curves + models; split at step_swap; optional sigma_2/model_2 fallback. |
| **LC VRAM Cache Clear** | Pass-through cache clear. |
| **LC Stop 🛑** | Breakpoint with enable switch. |

---

## 🧵 Pipes

| Node | What it does |
|------|----------------|
| **LC Pipe (in/edit)** | Pack or merge into **LC_PIPE**. |
| **LC Pipe Out** | Unpack full pipe. |
| **LC Detail Pipe Out** | Detailer-oriented unpack. |

Works with **KJ Set/Get**. STRING prompts are not CONDITIONING — encode before packing or after unpack.

---

## ✍️ Prompts, text & conditioning

| Node | What it does |
|------|----------------|
| **Positive / Negative** | Green / red prompt boxes → string. |
| **Prompt to Conditioning** | CLIP-encode a string. |
| **LC Prompt to Conditioning + Zero** | Encode + zero-out socket. |
| **LC Join Strings 🔗** | Join N strings; skip null/empty. |
| **LC Text Replace ✂️** | Up to 20 find/replace pairs. |
| **LC Text Remove 🔪** | Up to 20 finds to delete. Whitespace-only finds skipped; leftover spaces collapsed. |
| **Civitai 🚩🔪** | Strip terms from `assets/lists/` (default civitai list). |
| **LC Show Text 🔤** | Show text; auto pretty-JSON. |
| **📝 LC Save Text** | Write text; Windows path sanitize. |

**Civitai disclaimer:** For compliance assistance only! It is **YOUR** responsibility to abide by CivitAi TOS. Review `assets/lists/civitai_compliance_remove.txt`. No guarantee it is complete, current, or enough for approval. Policies change; metadata and moderation still apply.

---

## 📁 Save paths

| Node | What it does |
|------|----------------|
| **LC Easy Folder 📂** | `filename_prefix` for native Save Image. |
| **LC Advanced Folder 📂** | Split filename + path for Image Saver Simple. |

---

## 🔀 Switches, logic & control

| Node | What it does |
|------|----------------|
| **LC AnySwitch** | First connected input; type-lock; 2–20 inputs. |
| **LC Combo Selector** | Mirrors another node’s combo options. |
| **LC Boolean / Invert Boolean** | Coerce to true/false; show on face. |
| **LC Int Compare / LC Float Compare** | Largest or smallest of two values. |
| **LC Seed Jump 🌱** | Seed + jump → six stepped seeds. |
| **LC Slider** | On-node slider. |
| **LC Notify 🔊** | Play sound from `assets/sounds/` (always / on empty queue). ▶ preview on node. |
| **LC Bypasser / Groups Bypasser / Panel** | Bypass hubs + remote panel. |

---

## 📦 Assets

| Path | Use |
|------|-----|
| `assets/sounds/` | Notification sounds for **LC Notify 🔊** |
| `assets/lists/` | Text lists (Civitai compliance strip) |

---

## 💡 Quick tips

- **Image FX:** fix seed, tune low-res, then full run.
- **Pipes:** if the graph always regenerates, try a direct pipe link (no Get/Set) to test caching.
- **Dual sigma:** encode prompts to CONDITIONING — CFGGuider will not accept empty conds.
- **Notify:** drop `.mp3` / `.wav` into `assets/sounds/`, restart once for dropdown refresh.

---

*Lonecat’s LC123 — less friction, more making.*
