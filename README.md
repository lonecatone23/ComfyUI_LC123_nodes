# ComfyUI LC123 Nodes

Custom nodes for [ComfyUI](https://github.com/comfyanonymous/ComfyUI) by [lonecatone23](https://github.com/lonecatone23).

- **Repo:** https://github.com/lonecatone23/ComfyUI_LC123_nodes
- **Support:** [Buy me a ☕](https://ko-fi.com/lonecatone)

> Small tools that remove friction — less wire mess, fewer clicks, clearer workflows.

For **Anima regional attention**, also install [Sen-sou Anima Regional Conditioning](https://github.com/Sen-sou/Comfyui-Anima-Regional-Conditioning).

**Version 1.6.0**

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
| **📐 Aspect Ratio Simplifier** | Size from image/mask/preset. Crop/stretch/pad/total pixels. Empty latent. Default upscale: **lanczos**. **resolution** = longer side. |
| **LC Aspect Ratio Simplifier 📐(Pipe)** | Same + pipe out. |
| **LC Aspect Ratio Pipe Out** | Unpack aspect pipe. |
| **LC Get Image 📐** | Megapixels, width, height, batch, aspect, resolution. |
| **LC Image Crop 🖼️🔪** | Interactive crop + aspect lock. |
| **LC Image Compare 🔎** | Batch A/B compare, one slider. |
| **LC Last Image Holder** | Hold last image for before/after. |
| **LC Dynamic Overlay** | Overlay B on A; live opacity knob; fixed node size, letterboxed preview. |
| **LC Watermark 💧** | Image watermark: size, opacity, drag place. |

## 🎨 Image FX / post

| Node | What it does |
|------|----------------|
| Adjust, RGB, desaturate, vibrance, vignette, bloom, denoise, color match, LUT, film grain/stock, lens FX/profile, chromatic aberration, sharpen/clarity, lift-gamma-gain, auto white balance, text overlay | On-node preview (and wipe where applicable). |

## 🧪 Sampling & sigmas

| Node | What it does |
|------|----------------|
| **LC Sampler Configure** / **(pipe)** | total_steps, step_swap, detailer_steps, denoise (0.01 step), CFG1/2, sampler, scheduler. |
| **LC Sampler Configure Pipe Out** | Unpack sampler pipe. |
| **LC Split Sigma Scheduler** | Dual-model sigma split at step_swap. |
| **LC Basic Scheduler** | model + scheduler + steps → SIGMAS (no denoise). |
| **LC Split Sigmas (Advanced)** | Two curves + models; split at step_swap; denoise; sigmas_2/model_2 optional → fall back to first. |

## 📦 Pipes

| Node | What it does |
|------|----------------|
| **LC Pipe (in/edit)** | Pack or merge LC_PIPE (KJ Get/Set friendly). |
| **LC Pipe Out** | Unpack full pipe. |
| **LC Detail Pipe Out** | Detailer-oriented unpack. |

## 📝 Text & prompts

| Node | What it does |
|------|----------------|
| **LC Text Replace ✂️** | Up to 20 find/replace pairs. |
| **LC Text Remove 🔪** | Up to 20 finds to delete. |
| **LC Join Strings** / **LC Show Text 🔤** | Join / display (auto pretty JSON). |
| **LC Save Text** | Write text (sanitized paths). |
| **Prompt boxes / Prompt→Conditioning (+ zero)** | Prompt helpers. |

## 🔀 Logic & control

| Node | What it does |
|------|----------------|
| **LC AnySwitch**, **Combo Selector**, **Boolean / Invert Boolean** | Switching & coercion. |
| **LC Bypasser**, **Groups Bypasser**, **Bypasser Panel** | Bypass hubs; restriction on hub only. |
| **LC Slider**, **LC Stop 🛑**, **VRAM cache clear** | UI helpers. |
| **LC Int Compare** / **LC Float Compare** | largest / smallest of two values. |
| **LC Seed Jump 🌱** | seed + jump → six stepped seeds. |

## 📁 Folders

| Node | What it does |
|------|----------------|
| **LC Easy Folder 📂** / **LC Advanced Folder 📂** | Path builders for savers. |

## 🎛️ Other

| Node | What it does |
|------|----------------|
| **Anima / Krea2 Regional Inline Canvas** | Paint regional conditioning (Anima needs Sen-sou pack). |
| **LC Slider** | On-node slider. |

---

## Workflows

See `workflows/` for examples (dual sigma, aspect ratio, post FX, regional canvas, etc.).

---

## License

MIT — see `LICENSE`.
