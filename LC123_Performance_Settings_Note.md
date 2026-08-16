# LC123 Performance Settings ⚙️

> **UI only** — smoother scrolling and lighter on-node previews.  
> These settings do **not** change generation VRAM, model load, or output image quality on the sockets.

---

## Where to find them

1. Open **ComfyUI Settings** (gear).
2. In the sidebar, open **LC123**.
3. Open **Performance**.

If you don’t see the full list: restart ComfyUI, then **Ctrl+F5** (hard refresh) so the updated `web/lc_performance_settings.js` loads.

---

## What each option does

| Setting | Default | What it does |
|--------|---------|----------------|
| **Remove wipe** | Off | Turns off hover A/B wipe on **image FX** nodes. Last result still shows. |
| **Half-resolution previews** | Off | Draws FX previews at **half** the node’s image area (less GPU/CPU work while panning). |
| **Clamp longest side** | Off | Downscales the **on-node** preview bitmap so the longest side ≤ **Max edge**. |
| **Max edge (px)** | 768 | Used only when **Clamp longest side** is on. Try 512–1024 on heavy graphs. |
| **No preview when collapsed** | On | Collapsed FX nodes skip drawing previews (less work while scrolling). |
| **Hide FX on-node previews** | Off | Hides all LC **image FX** on-node previews. Socket outputs are unchanged. |
| **Skin Beauty full preview override** | On | **LC Skin Beauty** keeps a **full-quality** on-node preview even if half-res / clamp are on (for zooming skin detail). Wipe still follows **Remove wipe**. |

---

## What is *not* affected

These stay fully interactive and are **not** driven by the Performance toggles:

- **LC Image Compare 🔎**
- **LC Dynamic Overlay**
- **LC Image Split 🖼️**

Generation, Save Image, and every **IMAGE** output socket still use full resolution.

---

## Suggested setups

### Default (shipped)
Leave everything at default: full FX previews, wipe on, Skin Beauty override on.

### Heavy graph / laggy scroll
1. Turn **Half-resolution previews** **On**  
2. Turn **Clamp longest side** **On** (Max edge **512** or **768**)  
3. Keep **No preview when collapsed** **On**  
4. Leave **Skin Beauty full preview override** **On** if you still inspect skin on the node  

### Maximum UI lightness
1. **Hide FX on-node previews** **On**  
2. Or use **Remove wipe** + half-res + clamp  
3. Use **Image Compare** / **Image Split** when you need a wipe  

---

## Notes

- Changes apply on the next canvas redraw (panning or queue is enough; no reinstall needed).
- Optional SAM / LayerStyle / big models are separate from these settings; they still use their own VRAM.
- Pack files: `web/lc_performance_settings.js`, `web/lc_image_preview.js`

---

*Lonecat’s LC123 — less friction, more making.*
