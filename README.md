# ComfyUI LC123 Nodes

Custom nodes for [ComfyUI](https://github.com/comfyanonymous/ComfyUI) by [lonecatone23](https://github.com/lonecatone23).

- **Repo:** [https://github.com/lonecatone23/ComfyUI_LC123_nodes](https://github.com/lonecatone23/ComfyUI_LC123_nodes)
- **Support:** [Buy me a ☕](https://ko-fi.com/lonecatone)
- **Version:** 1.11.0

> Small tools that remove friction — less wire mess, fewer clicks, clearer workflows.

> **"True, nothing is. Permitted, everything is"**  
> — Yoda Auditore, *Assassin's Wars*

For **Anima regional attention**, also install [Sen-sou Anima Regional Conditioning](https://github.com/Sen-sou/Comfyui-Anima-Regional-Conditioning).

---

## What’s new (since the last morning push)

| Area | Changes |
|------|---------|
| **LC Sharpen Pro** | Photorealism-first rewrite: guided + box hybrid high-pass, **auto halo** with sharpen, stronger skin gate. Presets: **Natural, Subtle, Portrait, Product, Landscape, Crisp** + art **Lineart, Anime sharp**. Sliders snap to **Custom** when moved. |
| **LC Image Split 🖼️** | Wipe position is **slider-only** (no accidental drag on the image); still live while you adjust. |
| **LC Image Grid 🖼️** | Contact-sheet grid from multiple images (columns, gap, pad, outline/border). |
| **LC Node Snapshot 📋** | Read another node’s widgets → selected value, full string dump, JSON (source link or target id/title). |
| **LC Join Strings 🔗** | Null/empty inputs skip the delimiter (no `a,,c`). `\n` works in the delimiter field. |
| **LC Show Text 🔤** | pysssss-style display; keeps node size across loads/queues. |
| **LC Text Overlay** | Alignment left/center/right (bottom default); legacy workflows kept working. |
| **LC Apply LUT** | Strength range tuned; sample LUTs can seed into `models/luts/` on load **without overwriting** existing files. |
| **Docs** | This README, performance note, Photo Style / Skin Beauty notes. |

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
| **Hide FX on-node previews** | Off | Hide all LC image FX on-node previews |
| **Skin Beauty full preview override** | On | Skin Beauty stays full quality on-node |

**Not affected:** LC Image Compare · LC Dynamic Overlay · LC Image Split  

Full directions: [`LC123_Performance_Settings_Note.md`](LC123_Performance_Settings_Note.md)

---

## ✨ LC Skin Beauty

Mask-aware skin cooling and brightening in **CIELAB**. Grades **skin**, not the whole frame. Presets + full slider control; optional external mask.

---

## 📷 LC Photo Style

Camera / phone **finish** look (not lens geometry). Style presets drive the sliders; most controls use **0 = no change**. **Strength** blends with the original.

Presets include Standard, Natural, Dramatic, Quiet, Muted, Amateur, Cool day, Warm evening, Bright open, iPhone, **Nikon Z7 II**, **Canon R5**.

Full control list: [`LC_Photo_Style_Note.md`](LC_Photo_Style_Note.md)

---

## 🔪 LC Sharpen Pro — quick use

- **Default path (realism / influencers / NSFW):** start on **Natural** or **Portrait**. Raise **clarity** before **sharpen**. Keep **halo** and **skin_protect** up on faces.
- **Crisp:** photo snap, not ink outlines (higher halo, moderate sharpen).
- **Lineart / Anime sharp:** deliberate edge punch for art workflows — lower skin/halo on purpose.
- Moving any slider after a preset → **Custom**.
- **strength** at 1.0 = full effect; use a bypasser if you want a hard off switch.

---

## 🖼️ Image & size
> **Aspect ratio presets:** Dropdown shows the current list only. Older workflows with removed preset labels still run — unknown names fall back to **custom** width×height.


| Node | What it does |
|------|----------------|
| **📐 Aspect Ratio Simplifier** | Size from image, mask, or preset. Resize image + mask together. Crop / stretch / pad / total pixels. Empty latent out. Default upscale: **lanczos**. `resolution` = longer side. |
| **📐 Aspect Ratio Simplifier (pipe)** | Same controls, plus a **pipe** output on top for Get/Set routing. |
| **LC Aspect Ratio Pipe Out** | Unpacks an aspect-ratio pipe into image, mask, width, height, latent, batch, resolution. |
| **LC Get Image 📐** | Reads an image; shows megapixels, width, height, batch, aspect ratio, and resolution (longer side). |
| **LC Dimension Resize 📐** | Width + height + one value; add / subtract / multiply / divide both sides; rounded width & height out. |
| **LC Image Crop 🖼️🔪** | Interactive crop with aspect lock; preview on the node; cropped image out. |
| **LC Image Compare 🔎** | Batch A/B compare with one slider (A1↔B1, A2↔B2, …). Layout stays fixed. |
| **LC Image Split 🖼️** | Saveable wipe: **slider only** sets the split; position sticks until you change it. Output = split image. |
| **LC Image Grid 🖼️** | Multi-image contact sheet (max columns, gap, cell pad, outline/border colors). |
| **LC Last Image Holder** | Holds the last image for before/after. Survives disconnect; clear empties without re-running. Modes: hold last generation / hold until cleared. |
| **LC Dynamic Overlay** | Overlay B on A (A sets resolution). After one queue, drag the opacity knob — no re-gen to preview. Output: **blended Image**. |
| **LC Watermark 💧** | Image watermark: size, opacity, drag place. Bypasses if no watermark image. |

---

## 🎨 Image FX (on-node preview + before/after wipe)

Most show the result on the node. Hover to wipe against the original  
(see **LC123 Performance** to lighten UI load).

| Node | What it does |
|------|----------------|
| **LC Image Adjust** | Brightness, contrast, saturation, hue, etc. (−1…1 style controls). |
| **LC Auto White Balance** | Auto white-balance correction. |
| **LC Sharpen Pro** | **Photorealism-first** clarity + edge sharpen. Guided + box hybrid high-pass; auto halo; skin protect. Presets: Natural, Subtle, Portrait, Product, Landscape, Crisp, **Lineart**, **Anime sharp**. |
| **LC Lens Effects** | Lens-style FX suite. |
| **LC Lens Profile** | Lens profile / correction style FX. |
| **LC Lift Gamma Gain** | Lift / gamma / gain color-wheel style adjust. |
| **LC Image RGB** | Per-channel RGB adjust. |
| **LC Film Grain** | Film grain overlay. |
| **LC Film Stock (B&W)** | B&W film stock look. |
| **LC Film Stock (Color)** | Color film stock look. |
| **LC Vibrance** | Vibrance (smart saturation). |
| **LC Vignette** | Vignette darkening. |
| **LC Bloom** | Soft bloom / glow. |
| **LC Chromatic Aberration** | RGB fringe / CA control. |
| **LC Image Denoise** | Detail-preserving denoise. |
| **LC Color Match 🎨** | Match colors to a reference; strength; skin-protect aware. |
| **LC Image Desaturate** | Desaturate (Essentials-style). |
| **LC Skin Beauty ✨** | Skin-focused beauty pass (see above). |
| **LC Photo Style 📷** | Camera / phone finish (see above). |
| **LC Apply LUT** | Apply a LUT from **`ComfyUI/models/luts/`**. Pack may seed samples into that folder on load without overwriting. Ship extras under `assets/luts/` as assets only. |
| **LC Text Overlay** | Text on image; font size/color; **alignment** left/center/right (bottom default); drag + widgets. |

---

## 🧬 Sampling, sigma & pipes

| Node | What it does |
|------|----------------|
| **LC Sampler Configure** | total steps, step swap, detailer steps, denoise (0.01 steps), CFG1/2, sampler, scheduler. |
| **LC Sampler Configure (pipe)** | Same, pipe-oriented layout. |
| **LC Sampler Configure Pipe Out** | Unpacks sampler configure pipe. |
| **LC Pipe (in/edit)** | Pack/edit full LC pipe (models, clips, VAEs, size, latent, prompts, conds, seed, steps, CFGs, sampler…). |
| **LC Pipe Out** | Unpack full LC pipe. |
| **LC Detail Pipe Out** | Detailer-oriented unpack (model/clip/vae, prompts, conds, seed, cfg, sampler, scheduler, detailer steps). |
| **LC Split Sigma Scheduler** | Split one schedule across two models at step swap. |
| **LC Split Sigmas (Advanced)** | Two sigma curves in (sigma 1 / sigma 2); model 1 / model 2; step swap + denoise; sigmas high/low out. Missing model/sigma 2 falls back to 1. |
| **LC Basic Scheduler** | Scheduler + steps → sigmas (no denoise). |
| **Prompt to Conditioning** | String → conditioning. |
| **LC Prompt to Conditioning + Zero** | Encode + zero-out style second socket. |
| **Positive / Negative** | Prompt boxes (green / red). |

---

## 📁 Save paths & text

| Node | What it does |
|------|----------------|
| **LC Easy Folder 📂** | Builds `filename_prefix` for native Save Image (`Folder\prefix_suffix_timestamp`). |
| **LC Advanced Folder 📂** | Split filename + path (Image Saver Simple style). |
| **📝 LC Save Text** | Write text to a file; **sanitizes** illegal path characters. |
| **LC Join Strings 🔗** | Join N strings with a delimiter; empty/null slots skip the delimiter; `\n` allowed. |
| **LC Show Text 🔤** | Display text on the node (list-friendly). |
| **LC Text Replace ✂️** | Up to 20 find/replace pairs; grows/shrinks with entry count. |
| **LC Text Remove 🔪** | Same layout as replace, remove-only. |
| **Civitai 🚩🔪** | Compliance strip from `assets/lists/civitai_compliance_remove.txt`. **Your** responsibility to meet Civitai TOS; list is not guaranteed complete. |

---

## 🔀 Switches, logic & control

| Node | What it does |
|------|----------------|
| **LC AnySwitch** | First connected input among many; type-locks from first wire; 2–20 inputs. |
| **LC Combo Selector** | Dropdown that mirrors another node’s combo options. |
| **LC Boolean** | Coerce boolean / int / float → true/false; shows result on the face. |
| **LC Invert Boolean** | Same coercion, then invert. |
| **LC Boolean Switch** | `state` picks **on_true** or **on_false** (any type) → `*`. |
| **LC Boolean Flip** | Boolean widget → BOOLEAN out. |
| **LC Boolean Value** | Boolean widget → BOOLEAN out (primitive-style source). |
| **LC Int Compare** | Two INT inputs → largest or smallest. |
| **LC Float Compare** | Two FLOAT inputs → largest or smallest. |
| **LC Seed Jump 🌱** | One seed + jump size → six stepped seed outputs. |
| **LC Slider** | On-node slider; min/max/step/decimals in settings. INT or FLOAT. |
| **LC Node Snapshot 📋** | Wire a **source** node (or type id/title); pick a **widget**; outputs selected value, full newline string, and JSON (includes node id). Multiple snapshots can target the same node. |
| **LC Notify 🔊** | Play a sound from `assets/sounds/` on run; ▶ preview on the node. |
| **LC Bypasser** | Bypass linked nodes; toggle restriction: default / max one / always one. |
| **LC Groups Bypasser** | Same for graph groups. |
| **LC Bypasser Panel** | Widgets-only remote for a bypasser hub. |
| **LC Stop 🛑** | Pause until button (with enable/bypass). |
| **LC VRAM Cache Clear** | Clear VRAM / cache; any-in / any-out pass-through. |

---

## 🎨 Regional canvas

| Node | What it does |
|------|----------------|
| **Anima Regional Inline Canvas** | RGB paint canvas for Sen-sou Anima regional conditioning. |
| **Krea2 Regional Inline Canvas** | Same idea for Krea2 CLIP regions (**beta**). |

---

## 📦 Assets

| Path | Use |
|------|-----|
| `assets/sounds/` | Notification sounds for **LC Notify 🔊** |
| `assets/lists/` | Text lists (e.g. Civitai compliance strip) |
| `assets/luts/` | Sample LUTs shipped with the pack (copied to **`models/luts/`** on load if missing — never overwrites) |
| `assets/readme/` | Images used in this README (optional) |

**LUT path for Apply LUT:** `ComfyUI/models/luts/` (not under custom_nodes).

---

## 💡 Quick tips

- **Image FX:** fix seed, run low-res, tune, then full run.
- **Sharpen Pro:** realism users live on Natural/Portrait; art users use Lineart/Anime sharp.
- **Bypasser:** wire hubs; optional Panel so the hub can stay collapsed.
- **Save Text / folders:** avoid `? < > : " | *` in names — Save Text sanitizes; folders still prefer clean names.
- **Pipes + Get/Set:** if a graph “always regenerates,” try a direct pipe link to confirm caching.
- **Dual sigma:** encode prompts to CONDITIONING before CFGGuider — empty conds fail.
- **Notify:** drop `.mp3` / `.wav` into `assets/sounds/`, restart once so the dropdown refreshes.
- **Snapshot:** optional `source` input preferred; target id/title still works when linked resolution succeeds.

---

**"True, nothing is. Permitted, everything is"**  
_Yoda Auditore. *Assassin's Wars*_
