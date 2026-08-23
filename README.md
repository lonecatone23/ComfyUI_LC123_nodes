# ComfyUI LC123 Nodes

Custom nodes for [ComfyUI](https://github.com/comfyanonymous/ComfyUI) by [lonecatone23](https://github.com/lonecatone23).

- **Repo:** [https://github.com/lonecatone23/ComfyUI_LC123_nodes](https://github.com/lonecatone23/ComfyUI_LC123_nodes)
- **Support:** [Buy me a ☕](https://ko-fi.com/lonecatone)
- **Version:** 1.14.1

## What’s new in 1.14.1

| Area | Changes |
|------|---------|
| **Node size retention** | Manual node sizes stick across reload/reconnect for Sampler Configure family, AnySwitch, Index Switch, Custom Combo (+ panel), Boolean utils, Image Grid, Node Snapshot. Auto-fit only on first create or when `inputcount` changes. |


> Small tools that remove friction — less wire mess, fewer clicks, clearer workflows.

> **"True, nothing is. Permitted, everything is"**  
> — Yoda Auditore, *Assassin's Wars*

For **Anima regional attention**, also install [Sen-sou Anima Regional Conditioning](https://github.com/Sen-sou/Comfyui-Anima-Regional-Conditioning).

---

## What’s new in 1.14.0

| Area | Changes |
|------|---------|
| **LC Lighting Control** | Post-process relight from normal + depth maps; optional subject mask (virtual-dome normals); depth falloff; optional screen-space cast shadows; interactive light stage (handles, Z via Shift+drag / wheel). |
| **LC Custom Combo** | `inputcount` option slots + choice dropdown → **STRING** + **INDEX** + **OPT_CONNECTION**. |
| **LC Custom Combo Panel** | Compact remote for the combo (hub ← OPT_CONNECTION); choice stays in sync. |
| **LC Any Index Switch** | Index widget (right-click → Convert to Input to wire INDEX) + dynamic `any_*` slots (type-locks from first wire). |
| **LC AnySwitch** | First-connected-wins any-type switch (restored / unchanged). |

### Prior — 1.13.0

| Area | Changes |
|------|---------|
| **LC Sampler Configure Simple** (+ **pipe**) | Single-CFG config: no step_swap / cfg_2. Optional pipe in + pipe out on the pipe variant. |
| **LC Sampler Configure (pipe)** | Optional **pipe in** (left); widgets overwrite sampler keys; other pipe fields pass through. |
| **LC Reference Latent** | Up to 8 optional reference latents → conditioning meta (Klein index). **All slots optional** — if none connected, conditioning passes through unchanged. |
| **LC Denoise 💉** | Latent noise inject with `noise_std = 1 − denoise` (no seed widget). Color `#823282`. |
| **Sigma schedulers** | Chrome color `#1c6d6d` (Split Sigma, Split Sigmas Advanced, Basic Scheduler). |
| **Pipes / sampler chrome** | Pipe family + sampler configures → `#707070` (Aspect Ratio Simplifier pipe excluded). |
| **Docs / examples** | README refresh; update **LC Node examples** workflow on your side when merging. |

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

Full tables remain in earlier release notes and on-node tooltips.

---


## 📂 Example workflows

| File | Description |
|------|-------------|
| [`workflows/LC Lighting Control (BETA).json`](workflows/LC%20Lighting%20Control%20(BETA).json) | Load image → normals / depth / mask → **LC Lighting Control** |
| [`workflows/LC Node examples.json`](workflows/LC%20Node%20examples.json) | Broad tour of LC123 utility / image / prompt nodes |

Load via ComfyUI **Workflow → Open** (or drag onto canvas). External deps for the lighting example: Depth Anything V2, a normal-map node (e.g. Image-Filters), optional remBG / mask blur.

## 📦 Assets

| Path | Use |
|------|-----|
| `assets/sounds/` | LC Notify |
| `assets/lists/` | e.g. Civitai compliance |
| `assets/luts/` | Sample LUTs → `models/luts/` on load if missing |
| `assets/wildcards/` | LC Wildcard |
| `assets/prompt_builder/` | Prompt Builder presets |

---

## 💡 Quick tips

- **Reference Latent:** leave all latent sockets empty to pass conditioning through — safe with bypassers.
- **Denoise 💉:** same denoise number as the sampler; 1.0 = no inject.
- **Simple sampler config:** for single-pass graphs; dual-pass consumers still get `step_swap=0`, `cfg_2=cfg` from the pipe pack.
- **Prompt Builder:** `prompt` → conditioning; `json` → regional builders only.

---

**"True, nothing is. Permitted, everything is"**  
_Yoda Auditore. *Assassin's Wars*_
