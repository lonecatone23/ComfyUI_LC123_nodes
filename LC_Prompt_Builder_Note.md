# 🗒️ LC Prompt Builder

Modular prompt tools for ComfyUI. Build a clean **text prompt** and optional **Krea2 / Ideogram-style JSON** without drawing boxes by hand.

> Wire each block → **Assembler** → use **prompt** for normal conditioning, **json** for regional builders.

---

## 🔗 Basic flow

```
Subject(s) ──┐
Scene ───────┤
Camera ──────┼──► 🧩LC Prompt Assembler ──► prompt  → CLIP / conditioning
Lighting ────┤                           ──► json    → Krea2 / Ideogram builder
Style ───────┤
Color palette┘
```

Optional: **🎲LC Wildcard** into a subject description (or any STRING) for random lines from `assets/wildcards/`.

---

## 👤 Subjects

| Node | What it does |
|------|----------------|
| **🗒️LC Subject** | One person/character: description, pose, action, outfit, position (H/V/depth). Live prompt preview. |
| **🗒️LC Subject Array** | Merge several subjects for the assembler. |

**Tips:** Set pose/action/outfit to **none** when typing freely or using a wildcard. **Position** drives subject bboxes in JSON.

---

## 🌆 Scene · 📷 Camera · 💡 Lighting · 🎨 Style

| Node | Role |
|------|------|
| **🗒️LC Scene Builder** | Environment presets + time of day + weather |
| **🗒️LC Camera** | Angle, distance, depth of field |
| **🗒️LC Lighting** | Style + direction |
| **🗒️LC Style Selector** | Category, preset, quality |

---

## 🎨 Color palette · 🎲 Wildcard · 🌱 Seed

| Node | Role |
|------|------|
| **🎨LC Color Palette** | Preset or sample from image → hex prompt + preview |
| **🎲LC Wildcard** | Random line from `assets/wildcards/` (`base_seed` + `seed_mode`) |
| **🌱LC Seed** | Utility INT seed with the same seed_mode (partial-run friendly) |

---

## 🧩 Assembler

| Output | Use |
|--------|-----|
| **prompt** | Plain text → CLIP / conditioning |
| **json** | Import into Krea2 / Ideogram builders |

| Widget | Meaning |
|--------|---------|
| **include_scene_bboxes** | Default **off** — subject boxes only. On = also scene furniture boxes |
| **margin** | Inset boxes from frame edge (default 5%) |

**JSON is for builders.** The model does not natively “read” JSON; use **prompt** for string→conditioning.

---

## 📁 Assets

```
assets/wildcards/          ← .txt lists for Wildcard
assets/prompt_builder/     ← editable preset JSON
```

---

**"True, nothing is. Permitted, everything is"**  
_Yoda Auditore · Assassin's Wars_
