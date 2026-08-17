# ComfyUI LC123 Nodes

Custom nodes for [ComfyUI](https://github.com/comfyanonymous/ComfyUI) by [lonecatone23](https://github.com/lonecatone23).

- **Repo:** [https://github.com/lonecatone23/ComfyUI_LC123_nodes](https://github.com/lonecatone23/ComfyUI_LC123_nodes)
- **Support:** [Buy me a ☕](https://ko-fi.com/lonecatone)
- **Version:** 1.10.0

> Small tools that remove friction — less wire mess, fewer clicks, clearer workflows.

> **"True, nothing is. Permitted, everything is"**  
> — Yoda Auditore, *Assassin's Wars*

For **Anima regional attention**, also install [Sen-sou Anima Regional Conditioning](https://github.com/Sen-sou/Comfyui-Anima-Regional-Conditioning).

---

## ⚙️ LC123 Performance (Settings)

**UI only** — smoother scrolling and lighter on-node previews. Does **not** change generation VRAM or socket output quality.

**Settings → LC123 → Performance**

![LC123 Performance settings](assets/readme/lc123_performance_settings.png)

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

Mask-aware skin cooling and brightening in **CIELAB**. Grades **skin**, not the whole frame.

![Before / After](assets/readme/lc_skin_beauty_before_after.png)

Presets + full slider control; optional external mask. See workflow image under `assets/readme/`.

---

## 📷 LC Photo Style

Camera / phone **finish** look (not lens geometry). Style presets drive the sliders; most controls use **0 = no change**. **Strength** blends with the original.

Presets include Standard, Natural, Dramatic, Quiet, Muted, Amateur, Cool day, Warm evening, Bright open, iPhone, **Nikon Z7 II**, **Canon R5**.

Full control list: [`LC_Photo_Style_Note.md`](LC_Photo_Style_Note.md)

---

## 🖼️ Image & size

| Node | What it does |
|------|----------------|
| **📐 Aspect Ratio Simplifier** | Size from image, mask, or preset. Resize image + mask together. Crop / stretch / pad / total pixels. Empty latent out. Default upscale: lanczos. `resolution` = longer side. |
| **LC Aspect Ratio Simplifier 📐(Pipe)** | Same controls, plus a **pipe** output on top for Get/Set routing. |
| **LC Aspect Ratio Pipe Out** | Unpacks an aspect-ratio pipe into image, mask, width, height, latent, batch, resolution. |
| **LC Get Image 📐** | Reads an image; shows megapixels, width, height, batch, aspect ratio, and resolution (longer side). |
| **LC Dimension Resize 📐** | Width + height + one value; add / subtract / multiply / divide both sides; rounded width & height out. |
| **LC Image Crop 🖼️🔪** | Interactive crop with aspect lock; preview on the node; cropped image out. |
| **LC Image Compare 🔎** | Batch A/B compare with one slider (A1↔B1, A2↔B2, …). Layout stays fixed. |
| **LC Image Split 🖼️** | Saveable wipe: slider sets the split; position sticks until you change it. Output = split image. |
| **LC Last Image Holder** | Holds the last image for before/after. Survives disconnect; clear empties without re-running. |
| **LC Dynamic Overlay** | Overlay B on A (A sets resolution). After one queue, drag the opacity knob — no re-gen to preview. |
| **LC Watermark 💧** | Image watermark: size, opacity, drag place. Bypasses if no watermark image. |

---

## 🎨 Image FX (on-node preview + before/after wipe)

Most of these show the result on the node. Hover to wipe against the original input  
(see **LC123 Performance** settings to lighten UI load).

| Node | What it does |
|------|----------------|
| **LC Image Adjust** | Brightness, contrast, saturation, hue, etc. (−1…1 style controls). |
| **LC Auto White Balance** | Auto white-balance correction. |
| **LC Sharpen Pro** | Adaptive mid-tone / micro-contrast. Radius, strength, blend, shadow/highlight. |
| **LC Lens Effects** | Lens-style FX suite. |
| **LC Lift Gamma Gain** | Lift / gamma / gain color-wheel style adjust. |
| **LC Image RGB** | Per-channel RGB adjust. |
| **LC Film Grain** | Film grain overlay. |
| **LC Vibrance** | Vibrance (smart saturation). |
| **LC Vignette** | Vignette darkening. |
| **LC Bloom** | Bloom / glow. |
| **LC Image Denoise** | Smart denoise — blur strength, edge preservation, blend strength. |
| **LC Color Match 🎨** | Match colors to a reference (e.g. AdaIN). Optional skin protect. No reference → bypass (pass-through). |
| **LC Film Stock (B&W)** | B&W film stock look. |
| **LC Film Stock (Color)** | Color film stock look. |
| **LC Lens Profile** | Lens profile correction / character. |
| **LC Chromatic Aberration** | RGB channel split CA. |
| **LC Image Desaturate** | Desaturate (Essentials-style). |
| **LC Apply LUT** | Apply a LUT file. |
| **LC Text Overlay** | Place text on the image (drag, font, color, size). Multiline-safe. |
| **LC Skin Beauty ✨** | Skin-focused soft / beauty grade with auto mask and presets. |
| **LC Photo Style 📷** | Camera / phone finish look (presets + sliders). Strength blends with original. |

---

## 🎨 Regional canvas

| Node | What it does |
|------|----------------|
| **Anima Regional Inline Canvas** | Paint R/G/B regions on the node. GLOBAL / RED / GREEN / BLUE conditioning + masks for Sen-sou Anima. Pauses until Apply. |
| **Krea2 Regional Inline Canvas** | Same paint UI for Krea2 CLIP regional work. **Beta.** |

---

## 🔧 Sampling helpers

| Node | What it does |
|------|----------------|
| **LC Sampler Configure** | Dual-pass settings: total steps, step swap, detailer steps, denoise (0.01 step), CFG 1/2, sampler, scheduler. |
| **LC Sampler Configure (pipe)** | Same widgets + **pipe** on top for Get/Set. |
| **LC Sampler Configure Pipe Out** | Unpacks a sampler pipe into individual sockets. |
| **LC Split Sigma Scheduler** | High/low sigma schedules for two-pass custom samplers. Optional 2nd model (falls back to 1st). |
| **LC Basic Scheduler** | Model + scheduler + steps → SIGMAS (no denoise). Feed into advanced split. |
| **LC Split Sigmas (Advanced)** | Two sigma curves + models; split at step_swap; denoise. Optional sigma_2 / model_2 → falls back to the first curve/model. |
| **LC VRAM Cache Clear** | Pass-through; clears GPU/model cache when it runs. |
| **LC Stop 🛑** | Breakpoint with enable switch. Stops the queue; continue from play/queue. Bypass = pass through without stopping. |

---

## 🧵 Pipes

| Node | What it does |
|------|----------------|
| **LC Pipe (in/edit)** | Pack or merge models, clips, VAEs, size, latent, prompts, conditioning, seed, steps, CFGs, sampler, detailer steps… into one `LC_PIPE`. |
| **LC Pipe Out** | Unpack that pipe (same order top → bottom). |
| **LC Detail Pipe Out** | Detailer-oriented unpack (model/clip/vae/prompts/conds/seed/cfg/sampler/scheduler). |

Works with **KJ Set/Get**. Prefer a direct In/Edit → Out link when you need rock-solid caching.

> **Reminder:** `STRING` prompts in the pipe are **not** CONDITIONING. Encode with CLIP (or **Prompt to Conditioning**) before packing, or encode after unpack from the string + clip outputs.

---

## ✍️ Prompts, text & conditioning

| Node | What it does |
|------|----------------|
| **Positive** | Green prompt box → string. |
| **Negative** | Red prompt box → string. |
| **Prompt to Conditioning** | CLIP-encode a string (socket only). |
| **LC Prompt to Conditioning + Zero** | Encode + zero out conditioning socket. |
| **LC Join Strings 🔗** | Join N strings with a delimiter. Null/empty slots skipped (no `a,,c`). Dynamic input count. |
| **LC Text Replace ✂️** | Up to 20 find/replace pairs; node grows/shrinks with entry count. |
| **LC Text Remove 🔪** | Up to 20 finds to delete (no replacement value). |
| **Civitai 🚩🔪** | Strip terms from an external list under `assets/lists/` (default: `civitai_compliance_remove.txt`). |
| **LC Show Text 🔤** | Show text on the node. Keeps newlines; auto pretty-JSON when it looks like JSON. Pass-through string out. |
| **📝 LC Save Text** | Write text to disk. Illegal path characters are sanitized for Windows. |

### Civitai 🚩🔪 disclaimer

For compliance assistance only! It is **YOUR** responsibility to abide by CivitAi TOS. Review the list at `assets/lists/civitai_compliance_remove.txt`. There is no guarantee it is complete, current, or enough for Civitai approval. Policies change; metadata and moderation still apply.

---

## 📁 Save paths

| Node | What it does |
|------|----------------|
| **LC Easy Folder 📂** | Builds `filename_prefix` for native Save Image (`Folder\prefix_suffix_timestamp`). Creates folders as needed. |
| **LC Advanced Folder 📂** | Split **filename** + **path** for Image Saver Simple. Optional prefix-in-path. |

---

## 🔀 Switches, logic & control

| Node | What it does |
|------|----------------|
| **LC AnySwitch** | First connected input among many. Type-locks from first wire. Blocks Use Everywhere auto-wire. 2–20 inputs. |
| **LC Combo Selector** | Dropdown that mirrors another node’s combo (scheduler, sampler, …) when wired into a converted combo input. |
| **LC Boolean** | Coerce boolean / int / float → true/false. Shows result on the face. |
| **LC Invert Boolean** | Same coercion, then invert. Shows true/false on the face. |
| **LC Int Compare** | Two INT inputs → largest or smallest. |
| **LC Float Compare** | Two FLOAT inputs → largest or smallest. |
| **LC Seed Jump 🌱** | One seed in + jump size → six stepped seed outputs. |
| **LC Slider** | On-node slider; min/max/step/decimals in settings. INT or FLOAT. Nodes 2.0 friendly. |
| **LC Notify 🔊** | Play a sound from `assets/sounds/` on run (always / on empty queue). ▶ preview on the node. |
| **LC Bypasser** | Bypass linked nodes from one place. Toggle restriction: default / max one / always one. |
| **LC Groups Bypasser** | Same idea for **groups** on the graph. |
| **LC Bypasser Panel** | Widgets-only remote control. Connect `OPT_CONNECTION` from a bypasser hub → panel. Collapse the hub; drive toggles from the panel. |

---

## 📦 Assets

| Path | Use |
|------|-----|
| `assets/sounds/` | Notification sounds for **LC Notify 🔊** |
| `assets/lists/` | Text lists (e.g. Civitai compliance strip) |
| `assets/readme/` | README images (performance UI, Skin Beauty examples) |

---

## 💡 Quick tips

- **Image FX nodes:** fix seed, run low-res, tune, then full run.
- **Bypasser:** wire nodes into the hub; optionally use **Bypasser Panel** so the hub can stay collapsed.
- **Save Text / folders:** avoid `? < > : " | *` in names — Save Text sanitizes; folders still prefer clean names.
- **Pipes + Get/Set:** great for routing; if a graph “always regenerates,” try a direct pipe link to confirm caching.
- **Dual sigma:** encode prompts to CONDITIONING before or after the pipe — CFGGuider will not accept empty conds.
- **Notify:** drop `.mp3` / `.wav` files into `assets/sounds/`, then restart once so the dropdown refreshes.
- **Photo Style / Skin Beauty:** start with a preset, lower **strength** if the look is too strong, then nudge one or two sliders.
- **Laggy canvas:** turn on half-res + clamp (or hide FX previews) under **Settings → LC123 → Performance**.

---

**"True, nothing is. Permitted, everything is"**  
_Yoda Auditore · Assassin's Wars_
