# ComfyUI LC123 Nodes

Custom nodes for [ComfyUI](https://github.com/comfyanonymous/ComfyUI) by [lonecatone23](https://github.com/lonecatone23).

- **Repo:** [https://github.com/lonecatone23/ComfyUI_LC123_nodes](https://github.com/lonecatone23/ComfyUI_LC123_nodes)
- **Support:** [Buy me a ☕](https://ko-fi.com/lonecatone)
- **Version:** 1.9.0 · **~65 nodes**

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

**What it does**

- Auto skin mask (eyes/lips protected; busy fabric suppressed)
- Optional **external MASK** (e.g. SAM person) → intersects with auto skin so beauty stays on skin *inside* the person
- Presets load the sliders; then **what you see is what runs**
- Strength, coolness, brightness, rosy, evenness, shadow lift, smooth, texture preserve, saturation, highlight protect, mask sensitivity / feather
- On-node wipe preview; outputs **image** + **skin_mask**

**Simple path:** Image → LC Skin Beauty → preview / save  
**Stronger path:** Image → Segment Anything (person) → mask into LC Skin Beauty, plus Image Split + labels for before/after

![Example workflow](assets/readme/lc_skin_beauty_workflow.png)

Example graphs: `workflows/LC Skin Beauty.json`, `workflows/LC Skin Beauty basic (no deps).json`

| Goal | Tip |
|------|-----|
| Natural cleanup | Preset **Natural** or **Warm keep**, strength ~0.7–1.0 |
| Less plastic | Lower **smooth**, raise **texture_preserve** |
| Fabric leaks | Lower **mask_sensitivity**, or feed a person/skin **MASK** |
| Check targeting | Inspect **skin_mask** output |

---

## 🖼️ Image Split

**LC Image Split 🖼️** — sticky A|B wipe you can **save**.

- Live wipe on the node (drag; does not snap back)
- Output **`split 🖼️`** is the baked composite
- Standalone (no Skin Beauty or SAM required)

---

## 🖼️ Image & size

| Node | What it does |
|------|----------------|
| **📐 Aspect Ratio Simplifier** | Size from image, mask, or preset. Resize image + mask. Crop / stretch / pad / total pixels. Empty latent. |
| **📐 Aspect Ratio Simplifier (pipe)** | Same + pipe out for Get/Set. |
| **LC Aspect Ratio Pipe Out** | Unpacks aspect-ratio pipe. |
| **LC Get Image 📐** | Megapixels, width, height, batch, aspect, long-side resolution. |
| **LC Dimension Resize 📐** | Apply + − × ÷ once to width and height. |
| **LC Image Crop 🖼️🔪** | Interactive crop with aspect lock. |
| **LC Image Compare 🔎** | Batch A/B compare, one slider per pair. |
| **LC Image Split 🖼️** | Sticky saveable A\|B wipe. |
| **LC Last Image Holder** | Hold last image for before/after. |
| **LC Dynamic Overlay** | Overlay B on A; live opacity; **blended Image** out. |

---

## 🎨 Image FX & post

| Node | What it does |
|------|----------------|
| **LC Skin Beauty ✨** | Skin-only cool/brighten under mask (see above). |
| **LC Film Grain**, **LUT**, **Vibrance**, **Vignette**, **Bloom** | Post looks. |
| **LC Image Adjust**, **RGB**, **Lift Gamma Gain**, **Desaturate** | Color / tone. |
| **LC Sharpen / Clarity-style**, **Denoise**, **Lens FX / Profile**, **Chromatic Aberration** | Detail & optics. |
| **LC Film Stock Color / BW**, **Color Match**, **Auto WB** | Stock & match. |
| **LC Text Overlay**, **LC Watermark 💧** | Type and marks on image. |

---

## 🧠 Sampling & pipes

| Node | What it does |
|------|----------------|
| **LC Sampler Configure** / **(pipe)** / **Pipe Out** | Steps, swap, detailer, denoise, CFGs, sampler, scheduler. |
| **LC Split Sigma Scheduler** | High/low sigmas; optional 2nd model. |
| **LC Split Sigmas (Advanced)** | Two sigma curves + models; denoise; fallbacks. |
| **LC Basic Scheduler** | Scheduler + steps → sigmas (no denoise). |
| **LC Pipe (in/edit)** / **Pipe Out** / **Detail Pipe Out** | Bundle model/clip/vae/prompts/seed/steps… Get/Set friendly. |
| **LC Prompt → Conditioning** (+ Zero) | String → conditioning. |
| **LC Seed Jump 🌱** | Seed + step → six offsets. |

---

## 📁 Save paths & text

| Node | What it does |
|------|----------------|
| **LC Easy / Advanced Folder 📂** | Path helpers for native save / Image Saver. |
| **📝 LC Save Text** | Write text; sanitizes illegal path characters. |
| **LC Join Strings**, **Show Text 🔤**, **Text Replace**, **Text Remove 🔪** | String tools (null-safe join). |
| **Civitai 🚩🔪** | Compliance word strip from external list — **your** TOS responsibility. See `assets/lists/`. |

---

## 🔀 Switches, logic & control

| Node | What it does |
|------|----------------|
| **LC AnySwitch**, **Combo Selector**, **Boolean** / **Invert Boolean** | Routing and truthiness. |
| **LC Int / Float Compare** | Largest or smallest of two values. |
| **LC Slider** | On-node slider. |
| **LC Bypasser** / **Groups Bypasser** / **Bypasser Panel** | Remote bypass; restrictions on hub. |
| **LC Stop 🛑**, **VRAM Cache Clear**, **Notify 🔊** | Control, cleanup, sounds under `assets/sounds/`. |

---

## 💡 Quick tips

- **Performance:** heavy graphs → half-res + clamp, or hide FX previews; leave Skin Beauty override on if you zoom the node.
- **Skin Beauty:** fix seed, tune at moderate res, check **skin_mask**, then full run.
- **Image Split:** set wipe once; queue; Save Image on **`split 🖼️`**.
- **Pipes + Get/Set:** if a graph always regenerates, try a direct link to confirm caching.

---

## Install

```text
ComfyUI/custom_nodes/ComfyUI_LC123_nodes/
```

Restart ComfyUI. Optional workflows in `workflows/`.

**Requirements:** ComfyUI’s normal Python env (`torch`, `numpy`). No extra pip packages. Optional SAM / LayerStyle for external masks are separate installs.

---

## License

MIT — see `LICENSE`.

**"True, nothing is. Permitted, everything is"**  
— Yoda Auditore, *Assassin's Wars*
