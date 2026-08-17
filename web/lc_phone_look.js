/**
 * LC Photo Style — style preset loads all sliders (Skin Beauty pattern).
 */
import { app } from "../../scripts/app.js";

const PRESETS = {
  Standard: {
    wb_temperature: 0.08, wb_tint: 0.0, exposure: 0.04, contrast: 0.12,
    shadows: 0.25, highlights: 0.3, hdr_local: 0.2, vibrance: 0.22,
    skin_protect: 0.65, shadow_cool: 0.1, highlight_warm: 0.12,
    texture: 0.18, clarity: 0.12, vignette: 0.14, grain: 0.1,
  },
  Natural: {
    wb_temperature: 0.03, wb_tint: 0.0, exposure: 0.02, contrast: 0.06,
    shadows: 0.18, highlights: 0.22, hdr_local: 0.1, vibrance: 0.1,
    skin_protect: 0.75, shadow_cool: 0.04, highlight_warm: 0.06,
    texture: 0.08, clarity: 0.05, vignette: 0.06, grain: 0.05,
  },
  Dramatic: {
    wb_temperature: 0.02, wb_tint: 0.0, exposure: -0.06, contrast: 0.28,
    shadows: 0.08, highlights: 0.45, hdr_local: 0.25, vibrance: 0.15,
    skin_protect: 0.6, shadow_cool: 0.18, highlight_warm: 0.1,
    texture: 0.22, clarity: 0.22, vignette: 0.28, grain: 0.12,
  },
  Quiet: {
    wb_temperature: -0.1, wb_tint: -0.04, exposure: -0.04, contrast: 0.04,
    shadows: 0.2, highlights: 0.2, hdr_local: 0.08, vibrance: 0.02,
    skin_protect: 0.8, shadow_cool: 0.16, highlight_warm: 0.02,
    texture: 0.06, clarity: 0.04, vignette: 0.12, grain: 0.08,
  },
  Muted: {
    wb_temperature: 0.0, wb_tint: 0.0, exposure: 0.0, contrast: 0.08,
    shadows: 0.15, highlights: 0.25, hdr_local: 0.08, vibrance: -0.2,
    skin_protect: 0.7, shadow_cool: 0.08, highlight_warm: 0.04,
    texture: 0.08, clarity: 0.06, vignette: 0.08, grain: 0.06,
  },
  Amateur: {
    wb_temperature: 0.22, wb_tint: 0.08, exposure: 0.08, contrast: 0.24,
    shadows: 0.1, highlights: 0.18, hdr_local: 0.05, vibrance: 0.3,
    skin_protect: 0.25, shadow_cool: 0.02, highlight_warm: 0.22,
    texture: 0.28, clarity: 0.18, vignette: 0.32, grain: 0.22,
  },
  "Cool day": {
    wb_temperature: -0.35, wb_tint: -0.12, exposure: 0.02, contrast: 0.14,
    shadows: 0.22, highlights: 0.35, hdr_local: 0.18, vibrance: 0.12,
    skin_protect: 0.55, shadow_cool: 0.22, highlight_warm: 0.04,
    texture: 0.16, clarity: 0.14, vignette: 0.16, grain: 0.1,
  },
  "Warm evening": {
    wb_temperature: 0.4, wb_tint: 0.08, exposure: 0.06, contrast: 0.16,
    shadows: 0.28, highlights: 0.28, hdr_local: 0.15, vibrance: 0.18,
    skin_protect: 0.6, shadow_cool: 0.02, highlight_warm: 0.28,
    texture: 0.14, clarity: 0.12, vignette: 0.2, grain: 0.12,
  },
  "Bright open": {
    wb_temperature: -0.02, wb_tint: 0.19, exposure: 0.37, contrast: 0.14,
    shadows: 0.79, highlights: 0.82, hdr_local: 0.51, vibrance: 0.12,
    skin_protect: 0.61, shadow_cool: 0.22, highlight_warm: 0.04,
    texture: 0.32, clarity: 0.33, vignette: 0.24, grain: 0.16,
  },
  iPhone: {
    wb_temperature: 0.1, wb_tint: 0.02, exposure: 0.08, contrast: 0.12,
    shadows: 0.42, highlights: 0.48, hdr_local: 0.32, vibrance: 0.28,
    skin_protect: 0.72, shadow_cool: 0.14, highlight_warm: 0.16,
    texture: 0.22, clarity: 0.16, vignette: 0.08, grain: 0.06,
  },
  "Nikon Z7 II": {
    wb_temperature: -0.04, wb_tint: 0.0, exposure: 0.02, contrast: 0.18,
    shadows: 0.22, highlights: 0.38, hdr_local: 0.14, vibrance: 0.08,
    skin_protect: 0.7, shadow_cool: 0.12, highlight_warm: 0.06,
    texture: 0.2, clarity: 0.18, vignette: 0.1, grain: 0.05,
  },
  "Canon R5": {
    wb_temperature: 0.14, wb_tint: 0.04, exposure: 0.05, contrast: 0.14,
    shadows: 0.32, highlights: 0.42, hdr_local: 0.2, vibrance: 0.2,
    skin_protect: 0.68, shadow_cool: 0.06, highlight_warm: 0.18,
    texture: 0.16, clarity: 0.14, vignette: 0.08, grain: 0.05,
  },
};

const SLIDER_KEYS = Object.keys(PRESETS.Standard);

function widgetByName(node, name) {
  return (node.widgets || []).find((w) => w.name === name);
}

function applyPresetToSliders(node, presetName) {
  const cfg = PRESETS[presetName];
  if (!cfg) return;
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
    applyPresetToSliders(node, value);
    if (typeof prev === "function") return prev.apply(this, [value, ...rest]);
  };
  if (styleW.value) applyPresetToSliders(node, styleW.value);
}

app.registerExtension({
  name: "LC123.PhotoStyle",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData?.name !== "LCPhoneLook") return;
    const onNodeCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const r = onNodeCreated?.apply(this, arguments);
      try {
        this.bgcolor = "#324B4B";
        this.color = "#324B4B";
      } catch (_) {}
      return r;
    };
  },
  nodeCreated(node) {
    if (node.comfyClass !== "LCPhoneLook" && node.type !== "LCPhoneLook") return;
    hookPreset(node);
  },
});
