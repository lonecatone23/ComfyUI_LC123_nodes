# LC Photo Style 📷

Standalone **camera / phone finish** look. Pick a **style**, then tweak the sliders.  
Most controls use **0 = no change**. **Strength** blends with the original image.

Not a lens tool — color, tone, texture, vignette, and grain only.

Internal node type remains `LCPhoneLook` (existing graphs keep working). Display name: **LC Photo Style 📷**.

---

## Widgets

| Widget | What it does |
|--------|----------------|
| **style** | Starting preset (fills the sliders). Customize freely after. |
| **strength** | 0 = original image · 1 = full processed look. |
| **seed** | Grain seed only (same seed = same grain pattern). |
| **wb_temperature** | 0 = no change. − cooler · + warmer. |
| **wb_tint** | 0 = no change. − green · + magenta. |
| **exposure** | 0 = no change. Overall brightness (EV-style). |
| **contrast** | 0 = no change. + punches midtones · − flattens. |
| **shadows** | 0 = off. Lifts **dark areas only** (no white haze). |
| **highlights** | 0 = off. Softly compresses bright areas. |
| **hdr_local** | 0 = off. Mild local tone (opens shadows a bit / softens local contrast). |
| **vibrance** | 0 = no change. + boosts muted colors · − pulls them down. |
| **skin_protect** | Limits vibrance on skin hues (only matters when vibrance ≠ 0). |
| **shadow_cool** | 0 = off. Cool (blue) tint in mid-shadows — skips pure black. |
| **highlight_warm** | 0 = off. Warm tint in highlights. |
| **texture** | 0 = no change. Fine detail · − softens. |
| **clarity** | 0 = no change. Mid-scale local contrast · − softens. |
| **vignette** | 0 = off. Darkens the corners. |
| **grain** | 0 = off. Neutral mono grain (stronger in shadows). |

---

## Styles (presets)

| Style | Intent |
|-------|--------|
| **Standard** | Balanced default |
| **Natural** | Soft / restrained |
| **Dramatic** | Darker, more contrast and vignette |
| **Quiet** | Cool, low-key |
| **Muted** | Flatter / less saturation |
| **Amateur** | Uneven WB, stronger grain and vignette |
| **Cool day** | Cool / cyan lean |
| **Warm evening** | Amber / warm lean |
| **Bright open** | High exposure, lifted shadows and highlights |
| **iPhone** | Modern phone-style: shadow lift, soft highlights, skin-safe color |
| **Nikon Z7 II** | Neutral-cool, firmer mid contrast, clean texture |
| **Canon R5** | Mild warm, skin-friendly, soft highlight roll-off |

---

## Quick tips

- Start with a **style**, set **strength** ~0.7–0.9, then nudge one or two sliders.
- All zeros + any strength → image unchanged.
- **Shadows** opens blacks; it does **not** add a white fog.
- For a softer result without changing the preset, lower **strength** first.
- Pair with **LC Image Split** or **LC Image Compare** for a fixed before/after.

---

**"True, nothing is. Permitted, everything is"**  
_Yoda Auditore · Assassin's Wars_
