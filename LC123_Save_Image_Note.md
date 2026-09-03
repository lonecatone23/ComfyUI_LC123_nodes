## LC Save Image + Metadata

**Save Metadata** → **Save Image** (`metadata` socket)

### Save Metadata
- Optional **pipe** in (LC_PIPE). No pipe out.
- Pipe fills: prompts, seed, steps (`total_steps`), CFG (`cfg_1`), sampler, scheduler, size, denoise.
- Widgets override pipe when set (seed `-1` and steps/cfg `0` = use pipe).
- **models** — one field, comma-separated (`Model 1, Model 2`).
- **civitai_air** — primary Civitai AIR *or* model URL only. No lookup.

### Save Image
- **filename** + **path** (subfolder under Comfy output).
- Optional **filename_prefix** — Easy Folder; used if filename is left default and this is wired.
- PNG: workflow JSON + `parameters` + `civitaiResources` + `civitai_air`.
- JPEG/WebP: short comment only (no full workflow).
- **hash files** — AutoV2 (SHA256 first 10) from live loaders in the graph. Civitai lists resources from hashes, not names.
- Skips muted (2) / bypassed (4) sources. Unplugged slots ignored.

Re-drop old Save Image nodes after pack updates (widget list changed).
