/**
 * LC123 Performance settings — matches ComfyUI extension settings API
 * https://docs.comfy.org/custom-nodes/js/javascript_settings
 *
 * id: "LC123.Performance.*" → sidebar category LC123, section Performance
 * category: [category, section, label] (3 parts — required for reliable listing)
 *
 * Does NOT affect: Image Compare, Dynamic Overlay, Image Split
 */
import { app } from "../../scripts/app.js";

const ID = {
  noWipe: "LC123.Performance.NoWipe",
  halfRes: "LC123.Performance.HalfRes",
  clampEdge: "LC123.Performance.ClampEdge",
  maxEdge: "LC123.Performance.MaxEdge",
  skipCollapsed: "LC123.Performance.SkipCollapsed",
  hidePreviews: "LC123.Performance.HidePreviews",
  skinFull: "LC123.Performance.SkinBeautyFullPreview",
  recentColors: "LC123.Performance.RecentColors",
  loraInfo: "LC123.Performance.LoraInfoButton",
  minPreview: "LC123.Performance.PreviewMinSize",
};

function dirty() {
  try {
    app.canvas?.setDirty?.(true, true);
  } catch (_) {}
  // generic notify: any LC123 node can listen for this instead of each setting needing its own wiring
  try {
    window.dispatchEvent(new CustomEvent("lc123-perf-changed"));
  } catch (_) {}
}

function get(id, fallback) {
  try {
    // Official API (ComfyUI frontend)
    const em = app.extensionManager?.setting;
    if (em && typeof em.get === "function") {
      const v = em.get(id);
      if (v !== undefined && v !== null) return v;
    }
  } catch (_) {}
  try {
    if (typeof app.ui?.settings?.getSettingValue === "function") {
      const v = app.ui.settings.getSettingValue(id);
      if (v !== undefined && v !== null) return v;
    }
  } catch (_) {}
  return fallback;
}

function policyFor(nodeClass) {
  const skinOverride =
    nodeClass === "LCSkinBeauty" && get(ID.skinFull, true) === true;

  if (skinOverride) {
    return {
      hide: false,
      wipe: get(ID.noWipe, false) !== true,
      halfRes: false,
      maxEdge: 0,
      skipCollapsed: get(ID.skipCollapsed, true) === true,
      skinFull: true,
    };
  }

  const clamp = get(ID.clampEdge, false) === true;
  let maxEdge = Number(get(ID.maxEdge, 768));
  if (!Number.isFinite(maxEdge) || maxEdge < 64) maxEdge = 768;

  return {
    hide: get(ID.hidePreviews, false) === true,
    wipe: get(ID.noWipe, false) !== true,
    halfRes: get(ID.halfRes, false) === true,
    maxEdge: clamp ? maxEdge : 0,
    skipCollapsed: get(ID.skipCollapsed, true) === true,
    skinFull: false,
  };
}

// Preview distance: like canvas text, an on-node image switches off once it is drawn too small on screen to read.
// Size is the image's on-screen area as a square side (sqrt(w*h) * zoom), so a 200x200 preview fades out before a 1000x100 one.
let minPreviewPx = null;
function minPreview() {
  if (minPreviewPx === null) {
    const v = Number(get(ID.minPreview, 40));
    minPreviewPx = Number.isFinite(v) ? v : 40;
  }
  return minPreviewPx;
}

function tooSmall(w, h) {
  const min = minPreview();
  if (!(min > 0)) return false;
  const scale = app.canvas?.ds?.scale ?? 1;
  return Math.sqrt(Math.max(0, w) * Math.max(0, h)) * scale < min;
}

// true = skip the image; draws a flat stand-in so the node does not look empty
function skipImage(ctx, x, y, w, h) {
  if (!tooSmall(w, h)) return false;
  ctx.save();
  ctx.fillStyle = "rgba(0,0,0,0.28)";
  ctx.fillRect(x, y, w, h);
  ctx.restore();
  return true;
}

window.LC123Perf = { ID, get, policyFor, tooSmall, skipImage };

/**
 * Official pattern:
 * category: ["Category name", "Section heading", "Setting label"]
 * See docs.comfy.org — third element is the row label.
 */
app.registerExtension({
  name: "LC123.PerformanceSettings",
  settings: [
    {
      id: ID.noWipe,
      name: "Remove wipe",
      type: "boolean",
      defaultValue: false,
      tooltip:
        "Disable hover wipe on LC image FX previews. Does not affect Image Compare, Image Split, or Dynamic Overlay.",
      category: ["LC123 Settings ⚙️", "Performance", "Remove wipe"],
      onChange: dirty,
    },
    {
      id: ID.halfRes,
      name: "Half-resolution previews",
      type: "boolean",
      defaultValue: false,
      tooltip:
        "Draw FX on-node previews at half the image box size. Output sockets stay full resolution.",
      category: ["LC123 Settings ⚙️", "Performance", "Half-resolution previews"],
      onChange: dirty,
    },
    {
      id: ID.clampEdge,
      name: "Clamp longest side",
      type: "boolean",
      defaultValue: false,
      tooltip: "Downscale on-node FX preview textures to Max edge (below).",
      category: ["LC123 Settings ⚙️", "Performance", "Clamp longest side"],
      onChange: dirty,
    },
    {
      id: ID.maxEdge,
      name: "Max edge (px)",
      type: "number",
      defaultValue: 768,
      attrs: {
        min: 256,
        max: 2048,
        step: 64,
        showButtons: true,
      },
      tooltip: "Used when Clamp longest side is on.",
      category: ["LC123 Settings ⚙️", "Performance", "Max edge (px)"],
      onChange: dirty,
    },
    {
      id: ID.skipCollapsed,
      name: "No preview when collapsed",
      type: "boolean",
      defaultValue: true,
      tooltip: "Skip drawing on-node images for collapsed FX nodes.",
      category: ["LC123 Settings ⚙️", "Performance", "No preview when collapsed"],
      onChange: dirty,
    },
    {
      id: ID.hidePreviews,
      name: "Hide FX on-node previews",
      type: "boolean",
      defaultValue: false,
      tooltip:
        "Hide all LC image FX on-node previews. Compare / Split / Overlay unchanged.",
      category: ["LC123 Settings ⚙️", "Performance", "Hide FX on-node previews"],
      onChange: dirty,
    },
    {
      id: ID.recentColors,
      name: "Recent colors",
      type: "boolean",
      defaultValue: true,
      tooltip:
        "Show your last 8 custom colors in the right-click Colors menu (adds a Custom picker if Custom Scripts isn't installed).",
      category: ["LC123 Settings ⚙️", "Performance", "Recent colors"],
    },
    {
      id: ID.skinFull,
      name: "Skin Beauty full preview override",
      type: "boolean",
      defaultValue: true,
      tooltip:
        "LC Skin Beauty keeps full-quality on-node preview (no half-res / no clamp). Wipe still follows Remove wipe.",
      category: ["LC123 Settings ⚙️", "Performance", "Skin Beauty full preview override"],
      onChange: dirty,
    },
    {
      id: ID.loraInfo,
      name: "LoRA loader info button",
      type: "boolean",
      defaultValue: true,
      tooltip:
        "Show the ℹ info button on LoRA loader rows. The original loader reads local trigger words; LC Group LoRA Loader shows .civitai.info previews and trigger words. Turn off to declutter the rows.",
      category: ["LC123 Settings ⚙️", "Performance", "LoRA loader info button"],
      onChange: dirty,
    },
    {
      id: ID.minPreview,
      name: "Preview distance (px)",
      type: "slider",
      defaultValue: 40,
      attrs: { min: 0, max: 300, step: 5 },
      tooltip:
        "On-node image previews switch off when you zoom out far enough that they are drawn smaller than this on screen, the same way node text does. Smaller previews switch off first. 0 = always draw.",
      category: ["LC123 Settings ⚙️", "Performance", "Preview distance (px)"],
      onChange: () => {
        minPreviewPx = null;
        dirty();
      },
    },
  ],
  async setup() {
    console.log(
      "[LC123] Performance settings registered under Settings → LC123 → Performance"
    );
  },
});
