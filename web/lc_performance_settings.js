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
};

function dirty() {
  try {
    app.canvas?.setDirty?.(true, true);
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

window.LC123Perf = { ID, get, policyFor };

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
      category: ["LC123", "Performance", "Remove wipe"],
      onChange: dirty,
    },
    {
      id: ID.halfRes,
      name: "Half-resolution previews",
      type: "boolean",
      defaultValue: false,
      tooltip:
        "Draw FX on-node previews at half the image box size. Output sockets stay full resolution.",
      category: ["LC123", "Performance", "Half-resolution previews"],
      onChange: dirty,
    },
    {
      id: ID.clampEdge,
      name: "Clamp longest side",
      type: "boolean",
      defaultValue: false,
      tooltip: "Downscale on-node FX preview textures to Max edge (below).",
      category: ["LC123", "Performance", "Clamp longest side"],
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
      category: ["LC123", "Performance", "Max edge (px)"],
      onChange: dirty,
    },
    {
      id: ID.skipCollapsed,
      name: "No preview when collapsed",
      type: "boolean",
      defaultValue: true,
      tooltip: "Skip drawing on-node images for collapsed FX nodes.",
      category: ["LC123", "Performance", "No preview when collapsed"],
      onChange: dirty,
    },
    {
      id: ID.hidePreviews,
      name: "Hide FX on-node previews",
      type: "boolean",
      defaultValue: false,
      tooltip:
        "Hide all LC image FX on-node previews. Compare / Split / Overlay unchanged.",
      category: ["LC123", "Performance", "Hide FX on-node previews"],
      onChange: dirty,
    },
    {
      id: ID.skinFull,
      name: "Skin Beauty full preview override",
      type: "boolean",
      defaultValue: true,
      tooltip:
        "LC Skin Beauty keeps full-quality on-node preview (no half-res / no clamp). Wipe still follows Remove wipe.",
      category: ["LC123", "Performance", "Skin Beauty full preview override"],
      onChange: dirty,
    },
  ],
  async setup() {
    console.log(
      "[LC123] Performance settings registered under Settings → LC123 → Performance"
    );
  },
});
