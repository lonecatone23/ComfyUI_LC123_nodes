/**
 * LC Photo Style — style preset loads all sliders (Skin Beauty pattern).
 */
import { app } from "../../scripts/app.js";
import { lcApplyLaunchColor } from "./lc_color.js";

const PRESETS = {
  Standard: {
    wb_temperature: 0.08, wb_tint: 0, exposure: 0.04, contrast: 0.12,
    shadows: 0.25, highlights: 0.3, hdr_local: 0.2, vibrance: 0.22,
    skin_protect: 0.65, shadow_cool: 0.1, highlight_warm: 0.12,
    texture: 0.18, clarity: 0.12, vignette: 0.14, grain: 0.1, black_lift: 0, natural: 0, auto_wb: 0, phone_sharpen: 0, noise_smear: 0, compression: 0, lens: 0, resolution: 0, clip: 0,
  },
  Natural: {
    wb_temperature: 0.03, wb_tint: 0, exposure: 0.02, contrast: 0.06,
    shadows: 0.18, highlights: 0.22, hdr_local: 0.1, vibrance: 0.1,
    skin_protect: 0.75, shadow_cool: 0.04, highlight_warm: 0.06,
    texture: 0.08, clarity: 0.05, vignette: 0.06, grain: 0.05, black_lift: 0, natural: 0, auto_wb: 0, phone_sharpen: 0, noise_smear: 0, compression: 0, lens: 0, resolution: 0, clip: 0,
  },
  Dramatic: {
    wb_temperature: 0.02, wb_tint: 0, exposure: -0.06, contrast: 0.28,
    shadows: 0.08, highlights: 0.45, hdr_local: 0.25, vibrance: 0.15,
    skin_protect: 0.6, shadow_cool: 0.18, highlight_warm: 0.1,
    texture: 0.22, clarity: 0.22, vignette: 0.28, grain: 0.12, black_lift: 0, natural: 0, auto_wb: 0, phone_sharpen: 0, noise_smear: 0, compression: 0, lens: 0, resolution: 0, clip: 0,
  },
  Quiet: {
    wb_temperature: -0.1, wb_tint: 0.04, exposure: -0.04, contrast: 0.04,
    shadows: 0.2, highlights: 0.2, hdr_local: 0.08, vibrance: 0.02,
    skin_protect: 0.8, shadow_cool: 0.16, highlight_warm: 0.02,
    texture: 0.06, clarity: 0.04, vignette: 0.12, grain: 0.08, black_lift: 0, natural: 0, auto_wb: 0, phone_sharpen: 0, noise_smear: 0, compression: 0, lens: 0, resolution: 0, clip: 0,
  },
  Muted: {
    wb_temperature: 0.0, wb_tint: 0, exposure: 0.0, contrast: 0.08,
    shadows: 0.15, highlights: 0.25, hdr_local: 0.08, vibrance: -0.2,
    skin_protect: 0.7, shadow_cool: 0.08, highlight_warm: 0.04,
    texture: 0.08, clarity: 0.06, vignette: 0.08, grain: 0.06, black_lift: 0, natural: 0, auto_wb: 0, phone_sharpen: 0, noise_smear: 0, compression: 0, lens: 0, resolution: 0, clip: 0,
  },
  Amateur: {
    wb_temperature: 0.22, wb_tint: -0.08, exposure: 0.08, contrast: 0.24,
    shadows: 0.1, highlights: 0.18, hdr_local: 0.05, vibrance: 0.3,
    skin_protect: 0.25, shadow_cool: 0.02, highlight_warm: 0.22,
    texture: 0.28, clarity: 0.18, vignette: 0.32, grain: 0.22, black_lift: 0, natural: 0, auto_wb: 0, phone_sharpen: 0, noise_smear: 0, compression: 0, lens: 0, resolution: 0, clip: 0,
  },
  "Cool day": {
    wb_temperature: -0.35, wb_tint: 0.12, exposure: 0.02, contrast: 0.14,
    shadows: 0.22, highlights: 0.35, hdr_local: 0.18, vibrance: 0.12,
    skin_protect: 0.55, shadow_cool: 0.22, highlight_warm: 0.04,
    texture: 0.16, clarity: 0.14, vignette: 0.16, grain: 0.1, black_lift: 0, natural: 0, auto_wb: 0, phone_sharpen: 0, noise_smear: 0, compression: 0, lens: 0, resolution: 0, clip: 0,
  },
  "Warm evening": {
    wb_temperature: 0.4, wb_tint: -0.08, exposure: 0.06, contrast: 0.16,
    shadows: 0.28, highlights: 0.28, hdr_local: 0.15, vibrance: 0.18,
    skin_protect: 0.6, shadow_cool: 0.02, highlight_warm: 0.28,
    texture: 0.14, clarity: 0.12, vignette: 0.2, grain: 0.12, black_lift: 0, natural: 0, auto_wb: 0, phone_sharpen: 0, noise_smear: 0, compression: 0, lens: 0, resolution: 0, clip: 0,
  },
  "Bright open": {
    wb_temperature: -0.02, wb_tint: -0.19, exposure: 0.37, contrast: 0.14,
    shadows: 0.79, highlights: 0.82, hdr_local: 0.51, vibrance: 0.12,
    skin_protect: 0.61, shadow_cool: 0.22, highlight_warm: 0.04,
    texture: 0.32, clarity: 0.33, vignette: 0.24, grain: 0.16, black_lift: 0, natural: 0, auto_wb: 0, phone_sharpen: 0, noise_smear: 0, compression: 0, lens: 0, resolution: 0, clip: 0,
  },
  "iPhone": { wb_temperature: 0.1, wb_tint: -0.02, exposure: 0.08, contrast: 0.12, shadows: 0.42, highlights: 0.48, hdr_local: 0.32, vibrance: 0.28, skin_protect: 0.72, shadow_cool: 0.14, highlight_warm: 0.16, texture: 0.22, clarity: 0.16, vignette: 0.08, grain: 0.06, black_lift: 0.13, natural: 0.35, auto_wb: 0.4, phone_sharpen: 0.2, noise_smear: 0.15, compression: 0, lens: 0.12, resolution: 0, clip: 0 },
  "iPhone Luminous": { wb_temperature: 0.14, wb_tint: -0.02, exposure: 0.22, contrast: 0.06, shadows: 0.54, highlights: 0.48, hdr_local: 0.32, vibrance: 0.32, skin_protect: 0.72, shadow_cool: 0.14, highlight_warm: 0.16, texture: 0.22, clarity: 0.16, vignette: 0.08, grain: 0.06, black_lift: 0.13, natural: 0.35, auto_wb: 0.4, phone_sharpen: 0.2, noise_smear: 0.15, compression: 0, lens: 0.12, resolution: 0, clip: 0 },
  "iPhone Vibrant": { wb_temperature: 0.1, wb_tint: -0.02, exposure: 0.08, contrast: 0.2, shadows: 0.42, highlights: 0.48, hdr_local: 0.32, vibrance: 0.5, skin_protect: 0.72, shadow_cool: 0.14, highlight_warm: 0.16, texture: 0.22, clarity: 0.22, vignette: 0.08, grain: 0.06, black_lift: 0.13, natural: 0.35, auto_wb: 0.4, phone_sharpen: 0.2, noise_smear: 0.15, compression: 0, lens: 0.12, resolution: 0, clip: 0 },
  "iPhone Cozy": { wb_temperature: 0.26, wb_tint: -0.02, exposure: 0.08, contrast: 0.07, shadows: 0.42, highlights: 0.48, hdr_local: 0.32, vibrance: 0.31, skin_protect: 0.72, shadow_cool: 0.14, highlight_warm: 0.26, texture: 0.22, clarity: 0.16, vignette: 0.08, grain: 0.06, black_lift: 0.13, natural: 0.35, auto_wb: 0.4, phone_sharpen: 0.2, noise_smear: 0.15, compression: 0, lens: 0.12, resolution: 0, clip: 0 },
  "iPhone Ethereal": { wb_temperature: -0.02, wb_tint: 0.03, exposure: 0.2, contrast: 0.04, shadows: 0.5, highlights: 0.55, hdr_local: 0.32, vibrance: 0.14, skin_protect: 0.72, shadow_cool: 0.18, highlight_warm: 0.08, texture: 0.22, clarity: 0.08, vignette: 0.08, grain: 0.06, black_lift: 0.13, natural: 0.35, auto_wb: 0.4, phone_sharpen: 0.2, noise_smear: 0.15, compression: 0, lens: 0.12, resolution: 0, clip: 0 },
  "iPhone Amber": { wb_temperature: 0.4, wb_tint: -0.12, exposure: 0.08, contrast: 0.12, shadows: 0.42, highlights: 0.48, hdr_local: 0.32, vibrance: 0.28, skin_protect: 0.72, shadow_cool: 0.14, highlight_warm: 0.26, texture: 0.22, clarity: 0.16, vignette: 0.08, grain: 0.06, black_lift: 0.13, natural: 0.35, auto_wb: 0.4, phone_sharpen: 0.2, noise_smear: 0.15, compression: 0, lens: 0.12, resolution: 0, clip: 0 },
  "iPhone Gold": { wb_temperature: 0.3, wb_tint: -0.02, exposure: 0.08, contrast: 0.12, shadows: 0.42, highlights: 0.48, hdr_local: 0.32, vibrance: 0.32, skin_protect: 0.72, shadow_cool: 0.14, highlight_warm: 0.34, texture: 0.22, clarity: 0.16, vignette: 0.08, grain: 0.06, black_lift: 0.13, natural: 0.35, auto_wb: 0.4, phone_sharpen: 0.2, noise_smear: 0.15, compression: 0, lens: 0.12, resolution: 0, clip: 0 },
  "iPhone Rose Gold": { wb_temperature: 0.2, wb_tint: 0.43, exposure: 0.08, contrast: 0.12, shadows: 0.42, highlights: 0.48, hdr_local: 0.32, vibrance: 0.28, skin_protect: 0.72, shadow_cool: 0.14, highlight_warm: 0.16, texture: 0.22, clarity: 0.16, vignette: 0.08, grain: 0.06, black_lift: 0.13, natural: 0.35, auto_wb: 0.4, phone_sharpen: 0.2, noise_smear: 0.15, compression: 0, lens: 0.12, resolution: 0, clip: 0 },
  "iPhone Cool Rose": { wb_temperature: -0.06, wb_tint: 0.38, exposure: 0.08, contrast: 0.12, shadows: 0.42, highlights: 0.48, hdr_local: 0.32, vibrance: 0.28, skin_protect: 0.72, shadow_cool: 0.14, highlight_warm: 0.16, texture: 0.22, clarity: 0.16, vignette: 0.08, grain: 0.06, black_lift: 0.13, natural: 0.35, auto_wb: 0.4, phone_sharpen: 0.2, noise_smear: 0.15, compression: 0, lens: 0.12, resolution: 0, clip: 0 },
  "iPhone Neutral": { wb_temperature: -0.08, wb_tint: -0.02, exposure: 0.08, contrast: 0.12, shadows: 0.42, highlights: 0.48, hdr_local: 0.32, vibrance: 0.28, skin_protect: 0.72, shadow_cool: 0.02, highlight_warm: 0.02, texture: 0.22, clarity: 0.16, vignette: 0.08, grain: 0.06, black_lift: 0.13, natural: 0.35, auto_wb: 0.4, phone_sharpen: 0.2, noise_smear: 0.15, compression: 0, lens: 0.12, resolution: 0, clip: 0 },
  "Selfie": { wb_temperature: 0.16, wb_tint: -0.02, exposure: 0.12, contrast: 0.12, shadows: 0.47, highlights: 0.48, hdr_local: 0.32, vibrance: 0.28, skin_protect: 0.82, shadow_cool: 0.14, highlight_warm: 0.16, texture: 0.14, clarity: 0.12, vignette: 0.04, grain: 0.1, black_lift: 0.13, natural: 0.35, auto_wb: 0.4, phone_sharpen: 0.45, noise_smear: 0.45, compression: 0, lens: 0.3, resolution: 0, clip: 0 },
  "Shared": { wb_temperature: 0.1, wb_tint: -0.02, exposure: 0.08, contrast: 0.16, shadows: 0.42, highlights: 0.48, hdr_local: 0.32, vibrance: 0.34, skin_protect: 0.72, shadow_cool: 0.14, highlight_warm: 0.16, texture: 0.18, clarity: 0.16, vignette: 0.08, grain: 0.06, black_lift: 0.13, natural: 0.35, auto_wb: 0.4, phone_sharpen: 0.35, noise_smear: 0.3, compression: 0.65, lens: 0.15, resolution: 0, clip: 0 },
  "Samsung Galaxy": { wb_temperature: -0.18, wb_tint: 0.02, exposure: 0.14, contrast: 0.16, shadows: 0.55, highlights: 0.55, hdr_local: 0.48, vibrance: 0.48, skin_protect: 0.7, shadow_cool: 0.1, highlight_warm: 0.02, texture: 0.14, clarity: 0.22, vignette: 0.04, grain: 0.03, black_lift: 0.06, natural: 0.3, auto_wb: 0.55, phone_sharpen: 0.45, noise_smear: 0.35, compression: 0, lens: 0.1, resolution: 0, clip: 0 },
  "2000s Digicam": { wb_temperature: -0.15, wb_tint: -0.04, exposure: 0.22, contrast: 0.2, shadows: 0.05, highlights: 0, hdr_local: 0, vibrance: 0.25, skin_protect: 0.4, shadow_cool: 0.15, highlight_warm: 0, texture: 0.1, clarity: 0.05, vignette: 0.1, grain: 0.15, black_lift: 0, natural: 0.3, auto_wb: 0, phone_sharpen: 0.55, noise_smear: 0.2, compression: 0.55, lens: 0.55, resolution: 0.35, clip: 0.6 },
  "Early Phone": { wb_temperature: 0.22, wb_tint: -0.06, exposure: 0.06, contrast: 0.06, shadows: 0.1, highlights: 0.1, hdr_local: 0, vibrance: -0.1, skin_protect: 0.5, shadow_cool: 0, highlight_warm: 0.15, texture: -0.2, clarity: -0.15, vignette: 0.25, grain: 0.35, black_lift: 0.08, natural: 0.3, auto_wb: 0, phone_sharpen: 0.35, noise_smear: 0.7, compression: 0.45, lens: 0.7, resolution: 0.5, clip: 0.45 },
  "Webcam": { wb_temperature: -0.05, wb_tint: -0.18, exposure: 0.12, contrast: -0.05, shadows: 0.2, highlights: 0, hdr_local: 0, vibrance: -0.35, skin_protect: 0.4, shadow_cool: 0, highlight_warm: 0, texture: -0.1, clarity: -0.1, vignette: 0.2, grain: 0.45, black_lift: 0.12, natural: 0.3, auto_wb: 0, phone_sharpen: 0.25, noise_smear: 0.55, compression: 0.8, lens: 0.4, resolution: 0.85, clip: 0.35 },
  "2012 Filter": { wb_temperature: 0.15, wb_tint: 0.03, exposure: 0.06, contrast: -0.1, shadows: 0.35, highlights: 0.3, hdr_local: 0.1, vibrance: 0.05, skin_protect: 0.65, shadow_cool: 0.45, highlight_warm: 0.4, texture: 0.08, clarity: 0.1, vignette: 0.45, grain: 0.12, black_lift: 0.8, natural: 0.3, auto_wb: 0.2, phone_sharpen: 0.1, noise_smear: 0.1, compression: 0.25, lens: 0.1, resolution: 0.2, clip: 0 },
  "Nikon Z7 II": {
    wb_temperature: -0.04, wb_tint: 0, exposure: 0.02, contrast: 0.18,
    shadows: 0.22, highlights: 0.38, hdr_local: 0.14, vibrance: 0.08,
    skin_protect: 0.7, shadow_cool: 0.12, highlight_warm: 0.06,
    texture: 0.2, clarity: 0.18, vignette: 0.1, grain: 0.05, black_lift: 0, natural: 0, auto_wb: 0, phone_sharpen: 0, noise_smear: 0, compression: 0, lens: 0, resolution: 0, clip: 0,
  },
  "Canon R5": {
    wb_temperature: 0.14, wb_tint: -0.04, exposure: 0.05, contrast: 0.14,
    shadows: 0.32, highlights: 0.42, hdr_local: 0.2, vibrance: 0.2,
    skin_protect: 0.68, shadow_cool: 0.06, highlight_warm: 0.18,
    texture: 0.16, clarity: 0.14, vignette: 0.08, grain: 0.05, black_lift: 0, natural: 0, auto_wb: 0, phone_sharpen: 0, noise_smear: 0, compression: 0, lens: 0, resolution: 0, clip: 0,
  },
};

const SLIDER_KEYS = Object.keys(PRESETS.Standard);
const NEW_KEYS = ["black_lift", "natural", "auto_wb", "phone_sharpen", "noise_smear", "compression", "lens", "resolution", "clip"];
const SAVED_KEYS = SLIDER_KEYS.filter((k) => !NEW_KEYS.includes(k)); // sliders older workflows saved

function widgetByName(node, name) {
  return (node.widgets || []).find((w) => w.name === name);
}

function applyPresetToSliders(node, presetName) {
  const cfg = PRESETS[presetName];
  if (!cfg) return;
  node.properties = node.properties || {};
  node.properties.lc_style_clean = true; // on a named style, untouched: later versions may update its values
  for (const key of SLIDER_KEYS) {
    const w = widgetByName(node, key);
    if (!w || cfg[key] === undefined) continue;
    w.value = cfg[key];
    if (typeof w.callback === "function") {
      try {
        w.callback(w.value, node, app.canvas);
      } catch (_) {}
    }
  }
  node.setDirtyCanvas?.(true, true);
}

function hookPreset(node) {
  if (node._lcPhoneLookHooked) return;
  node._lcPhoneLookHooked = true;
  const styleW = widgetByName(node, "style");
  if (!styleW) return;
  const prev = styleW.callback;
  styleW.callback = function (value, ...rest) {
    node._lcApplying = true;
    try {
      applyPresetToSliders(node, value);
    } finally {
      node._lcApplying = false;
    }
    if (typeof prev === "function") return prev.apply(this, [value, ...rest]);
  };
  // moving a slider makes it your own look
  for (const key of SLIDER_KEYS) {
    const w = widgetByName(node, key);
    if (!w || w._lcSnapCustom) continue;
    w._lcSnapCustom = true;
    const prevW = w.callback;
    w.callback = function (value, ...rest) {
      if (!node._lcApplying && styleW.value !== "Custom") {
        styleW.value = "Custom";
        node.properties = node.properties || {};
        node.properties.lc_style_clean = false;
      }
      if (typeof prevW === "function") return prevW.apply(this, [value, ...rest]);
    };
  }
  if (styleW.value) {
    node._lcApplying = true;
    try {
      applyPresetToSliders(node, styleW.value);
    } finally {
      node._lcApplying = false;
    }
  }
}

// wb_tint used to run backwards (positive = green, the tooltip said magenta). Fixed 2026-11: a node saved before the
// fix gets its tint sign flipped once on load, so it looks exactly as it did; new saves carry lc_tint_v2.
function migrateTint(node) {
  node.properties = node.properties || {};
  if (node._lcSavedTintV2 !== true) {
    const w = widgetByName(node, "wb_tint");
    if (w && typeof w.value === "number" && w.value !== 0) w.value = -w.value;
  }
  node.properties.lc_tint_v2 = true;
}

// on load a named style gets its current values; a saved node whose sliders were tweaked before Custom existed
// (they no longer match its style) switches to Custom, so its numbers are kept
function reapplyOnLoad(node) {
  const styleW = widgetByName(node, "style");
  const cfg = PRESETS[styleW?.value];
  if (!cfg) return;
  const tweaked = node._lcSavedClean !== true && SAVED_KEYS.some((k) => {
    const w = widgetByName(node, k);
    return w && cfg[k] !== undefined && Math.abs(Number(w.value) - cfg[k]) > 1e-6;
  });
  if (tweaked) {
    styleW.value = "Custom";
    return;
  }
  node._lcApplying = true;
  try {
    applyPresetToSliders(node, styleW.value);
  } finally {
    node._lcApplying = false;
  }
}

app.registerExtension({
  name: "LC123.PhotoStyle",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData?.name !== "LCPhoneLook") return;
    const onNodeCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const r = onNodeCreated?.apply(this, arguments);
      lcApplyLaunchColor(this, "#324B4B");
      this.properties = this.properties || {};
      this.properties.lc_tint_v2 = true; // a new node is made with the fixed tint
      return r;
    };
    // the saved markers, read from the file itself (configure merges properties into the new node's)
    const onConfigure = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function (info) {
      this._lcSavedClean = info?.properties?.lc_style_clean === true;
      this._lcSavedTintV2 = info?.properties?.lc_tint_v2 === true;
      return onConfigure?.apply(this, arguments);
    };
  },
  nodeCreated(node) {
    if (node.comfyClass !== "LCPhoneLook" && node.type !== "LCPhoneLook") return;
    hookPreset(node);
  },
  loadedGraphNode(node) {
    if (node.comfyClass !== "LCPhoneLook" && node.type !== "LCPhoneLook") return;
    migrateTint(node); // before the "tweaked?" check, so an old saved tint matches its style again
    hookPreset(node);
    reapplyOnLoad(node);
  },
});
