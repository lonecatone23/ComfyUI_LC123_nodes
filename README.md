# ComfyUI LC123 Nodes

Custom nodes for [ComfyUI](https://github.com/comfyanonymous/ComfyUI) by [lonecatone23](https://github.com/lonecatone23).

- **Repo:** [https://github.com/lonecatone23/ComfyUI_LC123_nodes](https://github.com/lonecatone23/ComfyUI_LC123_nodes)
- **Civitai:** [lonecatone23](https://civitai.com/user/lonecatone23)
- **Instagram:** [synth.studio.models](https://www.instagram.com/synth.studio.models/)
- **Support:** [Buy me a ☕](https://ko-fi.com/lonecatone)
- **Version:** 1.15.0

## What’s new in 1.15.0

| Area | Changes |
|------|---------|
| **LC Lighting Control** | Widget **X/Y match the frame** (`+X` = from the right, `+Y` = from above). **Per-light shadows** — a light at intensity 0 does not cast. Contact shadows fall on the **opposite** side of the key. Dummy `lc_light_stage` text widget removed (no more missing-input crash). |
| **Example workflow** | Updated [`workflows/LC Lighting Control (BETA).json`](workflows/LC%20Lighting%20Control%20(BETA).json) + [`workflows/LC Node examples.json`](workflows/LC%20Node%20examples.json). |
| **Docs** | README lighting section + example image. Removed leftover root notes (`LC123_Nodes_Note.md`, `README.txt`, `README_worklows.txt`, `README_UTILS.txt`, `CHANGELOG_PUSH.md`, `MERGE_THESE.txt`). |

---

## LC Lighting Control 🔦

Post-process **spotlight relight** from a **normal map** + **depth map** (optional subject mask).

![LC Lighting Control example](assets/readme/LC%20Lighting%20Control%20example.png)

### Required inputs

| Input | Source (typical) |
|--------|------------------|
| **image** | Your photo / render |
| **normal_map** | Strong estimator (e.g. BAE / DSINE). Weak `NormalMapSimple` on smooth CG looks flat. |
| **depth_map** | Depth Anything V2 (recommended). Invert if the preview is bright-near and lighting looks inside-out. |

### Optional

| Input | Role |
|--------|------|
| **mask** | Subject matte (rembg / any MASK). Used only when **mask_enabled**. High **mask_blend** can fringe the silhouette — keep ~0.2–0.45 or leave off. |

**External packs (not bundled):** Depth Anything V2; a normal-map preprocessor; background-removal if you need a mask.

### Light model

| Control | Meaning |
|---------|---------|
| **XYZ** | Beam **aim**. **`+X` = from the right** of the frame · **`+Y` = from above** · **Z is 0…1** (0 = side plane, **1 = front**). |
| **light size** | Cone width: small = spot, large = flood. |
| **intensity** | Key strength. **0 = that light is off** (no light, no shadows). |
| **ambient** | Shadow floor (0 = pure key). ~0.25–0.45 for portraits. |
| **depth_scale** | Far pixels fall off inside the beam (0 = none). Keep low on faces. |
| **cast_shadows** | Screen-space contact from **that light’s** direction (not a global grey wash). |
| **shadow_strength** | 0.3–0.5 for photos; 1.0 is very heavy. |

Two lights: enable **light 2** for a fill/rim. Each light has its own aim and its own shadows.

### Light stage (grid under the params)

- **White** handle = light 1 · **Red** = light 2 (when enabled)
- Drag = **XY** aim
- **Shift+drag** vertical or **wheel** on handle = **Z** (toward camera)

### Quick recipes

| Look | Tips |
|------|------|
| Soft front key | XYZ ≈ `(0, 0.3, 1)`, size high, ambient ~0.25, intensity ~1 |
| Side key | `x` ±0.6–1, lower ambient, **cast_shadows** on ~0.4 |
| Masked subject | Connect mask, **mask_enabled**, blend ~0.2–0.45 |

Outputs: **image** (relit) · **debug_mask** (safe to ignore).

Example graph: [`workflows/LC Lighting Control (BETA).json`](workflows/LC%20Lighting%20Control%20(BETA).json)

---

> Small tools that remove friction — less wire mess, fewer clicks, clearer workflows.

> **"True, nothing is. Permitted, everything is"**  
> — Yoda Auditore, *Assassin's Wars*

For **Anima regional attention**, also install [Sen-sou Anima Regional Conditioning](https://github.com/Sen-sou/Comfyui-Anima-Regional-Conditioning).

---

## What’s new in 1.14.1

| Area | Changes |
|------|---------|
| **Node size retention** | Manual node sizes stick across reload/reconnect for Sampler Configure family, AnySwitch, Index Switch, Custom Combo (+ panel), Boolean utils, Image Grid, Node Snapshot. Auto-fit only on first create or when `inputcount` changes. |

## What’s new in 1.14.0

| Area | Changes |
|------|---------|
| **LC Lighting Control** | First release: relight from normal + depth; optional mask; light stage. |
| **LC Custom Combo** | `inputcount` option slots + choice dropdown → **STRING** + **INDEX** + **OPT_CONNECTION**. |
| **LC Custom Combo Panel** | Compact remote for the combo (hub ← OPT_CONNECTION); choice stays in sync. |
| **LC Any Index Switch** | Index widget (right-click → Convert to Input to wire INDEX) + dynamic `any_*` slots. |
| **LC AnySwitch** | First-connected-wins any-type switch. |

### Prior — 1.13.0

| Area | Changes |
|------|---------|
| **LC Sampler Configure Simple** (+ **pipe**) | Single-CFG config: no step_swap / cfg_2. |
| **LC Sampler Configure (pipe)** | Optional **pipe in**; widgets overwrite sampler keys. |
| **LC Reference Latent** | Up to 8 optional reference latents → conditioning meta. |
| **LC Denoise 💉** | Latent noise inject with `noise_std = 1 − denoise`. |

---

## 🗒️ Prompt Builder

Modular stack → **🧩LC Prompt Assembler** → `prompt` (CLIP) or `json` (Krea2 / Ideogram builders).

See [`LC_Prompt_Builder_Note.md`](LC_Prompt_Builder_Note.md).

| Node | Role |
|------|------|
| 🗒️LC Subject / Subject Array | Character + placement (bbox trailers for JSON) |
| 🗒️LC Scene / Camera / Lighting / Style | Environment & look |
| 🎨LC Color Palette | Preset or sample from image |
| 🎲LC Wildcard | Random line from `assets/wildcards/` |
| 🧩LC Prompt Assembler | `include_scene_bboxes` (default off = subject boxes only) |

---

## 🧪 Sampling · sigma · latent

| Node | What it does |
|------|----------------|
| **LC Sampler Configure** | Dual-pass: steps, swap, detailer, denoise, cfg_1/2, sampler, scheduler |
| **LC Sampler Configure (pipe)** | Same + optional pipe in + pipe out |
| **LC Sampler Configure Simple** | Single CFG — no step_swap / cfg_2 |
| **LC Sampler Configure Simple (pipe)** | Simple + pipe in/out |
| **LC Sampler Configure Pipe Out** | Unpack LC_PIPE → sampler sockets |
| **LC Split Sigma Scheduler** | Dual-model split across sigmas |
| **LC Split Sigmas (Advanced)** | Two sigma curves + models, step swap, denoise |
| **LC Basic Scheduler** | Scheduler + steps → sigmas (no denoise) |
| **LC Reference Latent** | Optional multi-ref latents into conditioning |
| **LC Denoise 💉** | `noise_std = 1 − denoise` into latent |

---

## 🖼️ Image · FX · utility (summary)

**LC Lighting Control** (relight) / aspect ratio / pipes / image compare-split-grid-crop / FX suite (denoise, color match, sharpen pro, skin beauty, photo style, LUT, …) / bypassers / boolean / **Custom Combo** + **Any Index Switch** / join-show text / folders / notify / seed jump / **🌱LC Seed** / performance settings.

See also [`LC_Photo_Style_Note.md`](LC_Photo_Style_Note.md) and [`LC123_Performance_Settings_Note.md`](LC123_Performance_Settings_Note.md).

---

## 📂 Example workflows

| File | Description |
|------|-------------|
| [`workflows/LC Lighting Control (BETA).json`](workflows/LC%20Lighting%20Control%20(BETA).json) | Load image → normals / depth / mask → **LC Lighting Control** |
| [`workflows/LC Node examples.json`](workflows/LC%20Node%20examples.json) | Broad tour of LC123 utility / image / prompt nodes |

Load via ComfyUI **Workflow → Open** (or drag onto canvas). Lighting example extras: Depth Anything V2, a normal-map node, optional remBG.

## 📦 Assets

| Path | Use |
|------|-----|
| `assets/readme/` | README screenshots (lighting example, skin beauty, …) |
| `assets/sounds/` | LC Notify |
| `assets/lists/` | e.g. Civitai compliance |
| `assets/luts/` | Sample LUTs → `models/luts/` on load if missing |
| `assets/wildcards/` | LC Wildcard |
| `assets/prompt_builder/` | Prompt Builder presets |

---

## 💡 Quick tips

- **Lighting:** intensity 1.0–1.2, ambient ~0.25–0.4, shadow strength ~0.4. Turn **mask_enabled** off if you see a grey fringe.
- **Reference Latent:** leave all latent sockets empty to pass conditioning through — safe with bypassers.
- **Denoise 💉:** same denoise number as the sampler; 1.0 = no inject.
- **Prompt Builder:** `prompt` → conditioning; `json` → regional builders only.

---

**"True, nothing is. Permitted, everything is"**  
_Yoda Auditore. *Assassin's Wars*_
