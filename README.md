# ComfyUI LC123 Nodes — RocketM fork

English | [简体中文](README.zh-CN.md)

## Changes compared with upstream

| Modified node | Changes |
| --- | --- |
| LC Save Image 💾 | `Size` uses original generation dimensions from the metadata pipe; output dimensions are a fallback only. Keeps prompts unchanged, records LoRA versions and weights in `Civitai resources`, and preserves separate model/CLIP strengths in compact PNG metadata. Resource collection follows the saved image branch, with cache-based LC/rgthree switch selection. No AddNet fields or duplicate primary model/VAE aliases. |
| LC Group LoRA Loader Stack 🎚️ | Grouped selection with the same visual library and independent weights; emits standard `(name, model strength, CLIP strength)` tuples for LC Apply LoRA Stack and compatible nodes. |
| LC Group LoRA Loader 🎚️ | Separate node with groups, drag sorting, a resizable batch picker, .civitai.info previews and independent model/CLIP strengths. The original loader and stack retain their original UI and loading behavior. |
| LC LoRA Loader 🎚️ | Connects its row settings to strength metadata and LoRA hash collection, respecting row switches, strengths, and model-only or CLIP-only connections. The loader's sampling behavior is unchanged. |

Metadata is written when `embed_civitai` is enabled, without changing sampling prompts or image dimensions. LC LoRA Loader 🎚️ and LC Group LoRA Loader 🎚️ use dedicated adapters; other loaders are detected by their input fields. LC LoRA Stack / LC Group LoRA Loader Stack / LC Apply LoRA Stack are not supported by the strength metadata collector. Graph ancestry does not prove execution, so structured records use `execution_verified: false`.

Workflows saved by the earlier feature version with `lc_lora_groups` on LC LoRA Loader migrate to LC Group LoRA Loader when opened. Ordinary original-loader workflows are unchanged.

## Installation

Run inside `ComfyUI/custom_nodes`:

```sh
git clone --branch main https://github.com/RocketM/ComfyUI_LC123_nodes.git
```

Install only one LC123 copy. Restart ComfyUI and refresh the browser after installation.

## Upstream node documentation

For node usage, images, and examples, see the [upstream README](https://github.com/lonecatone23/ComfyUI_LC123_nodes#readme). Original nodes and assets are by [lonecatone23](https://github.com/lonecatone23); this fork retains the original [license](LICENSE).
