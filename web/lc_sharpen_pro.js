/**
 * LC Sharpen Pro — preset fills sliders; any manual slider change → Custom.
 */
import { app } from "../../scripts/app.js";
import { lcApplyLaunchColor } from "./lc_color.js";

const TYPE = "LCClarity";

const PRESETS = {
  // Realism / influencer — structure without plastic edges
  Natural: {
    clarity: 0.42, sharpen: 0.08, strength: 1.0, halo: 0.58, skin_protect: 0.72,
    radius: 0.42, blend_mode: "Soft Light", shadow_protect: 0.34, highlight_protect: 0.32,
  },
  Subtle: {
    clarity: 0.32, sharpen: 0.06, strength: 1.0, halo: 0.55, skin_protect: 0.60,
    radius: 0.38, blend_mode: "Soft Light", shadow_protect: 0.30, highlight_protect: 0.28,
  },
  Portrait: {
    clarity: 0.38, sharpen: 0.06, strength: 1.0, halo: 0.65, skin_protect: 0.85,
    radius: 0.36, blend_mode: "Soft Light", shadow_protect: 0.42, highlight_protect: 0.40,
  },
  Product: {
    clarity: 0.55, sharpen: 0.22, strength: 1.0, halo: 0.48, skin_protect: 0.25,
    radius: 0.36, blend_mode: "Soft Light", shadow_protect: 0.24, highlight_protect: 0.30,
  },
  Landscape: {
    clarity: 0.62, sharpen: 0.20, strength: 1.0, halo: 0.40, skin_protect: 0.12,
    radius: 0.55, blend_mode: "Overlay", shadow_protect: 0.18, highlight_protect: 0.22,
  },
  // Photo crisp — not illustration outlines
  Crisp: {
    clarity: 0.28, sharpen: 0.36, strength: 1.0, halo: 0.72, skin_protect: 0.55,
    radius: 0.24, blend_mode: "Soft Light", shadow_protect: 0.30, highlight_protect: 0.32,
  },
  // Art / anime — deliberate edge punch (use when you want the "line" look)
  Lineart: {
    clarity: 0.18, sharpen: 0.78, strength: 1.0, halo: 0.28, skin_protect: 0.12,
    radius: 0.14, blend_mode: "Overlay", shadow_protect: 0.12, highlight_protect: 0.15,
  },
  "Anime sharp": {
    clarity: 0.48, sharpen: 0.58, strength: 1.0, halo: 0.38, skin_protect: 0.22,
    radius: 0.22, blend_mode: "Overlay", shadow_protect: 0.16, highlight_protect: 0.18,
  },
  Custom: null,
};

const SLIDER_KEYS = [
  "clarity", "sharpen", "strength", "halo", "skin_protect",
  "radius", "blend_mode", "shadow_protect", "highlight_protect",
];

function widgetByName(node, name) {
  return (node.widgets || []).find((w) => w.name === name);
}

function applyPreset(node, name) {
  const cfg = PRESETS[name];
  if (!cfg) return;
  node._lcApplyingPreset = true;
  try {
    for (const key of SLIDER_KEYS) {
      const w = widgetByName(node, key);
      if (!w || cfg[key] === undefined) continue;
      w.value = cfg[key];
      if (typeof w.callback === "function") {
        try { w.callback(w.value, node, app.canvas); } catch (_) {}
      }
    }
  } finally {
    node._lcApplyingPreset = false;
  }
  node.setDirtyCanvas?.(true, true);
}

function snapToCustom(node) {
  if (node._lcApplyingPreset) return;
  const presetW = widgetByName(node, "preset");
  if (!presetW) return;
  if (presetW.value === "Custom") return;
  presetW.value = "Custom";
  if (typeof presetW.callback === "function") {
    try { presetW.callback("Custom", node, app.canvas); } catch (_) {}
  }
  node.setDirtyCanvas?.(true, true);
}

function hook(node) {
  if (node._lcSharpenHooked) return;
  node._lcSharpenHooked = true;
  const presetW = widgetByName(node, "preset");
  if (presetW) {
    const prev = presetW.callback;
    presetW.callback = function (value, ...rest) {
      if (value && value !== "Custom") applyPreset(node, value);
      if (typeof prev === "function") return prev.apply(this, [value, ...rest]);
    };
    if (presetW.value && presetW.value !== "Custom") applyPreset(node, presetW.value);
  }
  for (const key of SLIDER_KEYS) {
    const w = widgetByName(node, key);
    if (!w || w._lcSnapCustom) continue;
    w._lcSnapCustom = true;
    const prev = w.callback;
    w.callback = function (value, ...rest) {
      snapToCustom(node);
      if (typeof prev === "function") return prev.apply(this, [value, ...rest]);
    };
  }
}

app.registerExtension({
  name: "LC123.SharpenPro",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData?.name !== TYPE) return;
    const onNodeCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const r = onNodeCreated?.apply(this, arguments);
      try { lcApplyLaunchColor(this, "#324B4B"); } catch (_) {}
      return r;
    };
  },
  nodeCreated(node) {
    if (node.comfyClass !== TYPE && node.type !== TYPE) return;
    hook(node);
  },
});
