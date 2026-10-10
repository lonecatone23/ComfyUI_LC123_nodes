/**
 * LC Sharpen Pro — preset fills sliders; any manual slider change → Custom.
 */
import { app } from "../../scripts/app.js";
import { lcApplyLaunchColor } from "./lc_color.js";

const TYPE = "LCClarity";

const PRESETS = {
  // Realism: capture sharpening, a little texture
  Natural: { clarity: 0.2, sharpen: 0.3, strength: 0.7, halo: 0.7, skin_protect: 0.6, radius: 0.3, blend_mode: "Soft Light", shadow_protect: 0.25, highlight_protect: 0.25, texture: 0.15 },
  Subtle: { clarity: 0.1, sharpen: 0.2, strength: 0.6, halo: 0.8, skin_protect: 0.7, radius: 0.3, blend_mode: "Soft Light", shadow_protect: 0.3, highlight_protect: 0.3, texture: 0.05 },
  Portrait: { clarity: 0.1, sharpen: 0.2, strength: 0.6, halo: 0.8, skin_protect: 1.0, radius: 0.35, blend_mode: "Soft Light", shadow_protect: 0.35, highlight_protect: 0.35, texture: 0.0 },
  // Hard surfaces and fabric
  Product: { clarity: 0.4, sharpen: 0.5, strength: 0.7, halo: 0.55, skin_protect: 0.1, radius: 0.3, blend_mode: "Soft Light", shadow_protect: 0.2, highlight_protect: 0.2, texture: 0.35 },
  Landscape: { clarity: 0.5, sharpen: 0.45, strength: 0.7, halo: 0.5, skin_protect: 0.1, radius: 0.45, blend_mode: "Overlay", shadow_protect: 0.15, highlight_protect: 0.2, texture: 0.45 },
  Crisp: { clarity: 0.2, sharpen: 0.7, strength: 0.7, halo: 0.5, skin_protect: 0.4, radius: 0.2, blend_mode: "Soft Light", shadow_protect: 0.25, highlight_protect: 0.25, texture: 0.2 },
  // Line art and sketches: crisp lines, no skin logic
  Lineart: { clarity: 0.1, sharpen: 0.85, strength: 0.7, halo: 0.3, skin_protect: 0.0, radius: 0.1, blend_mode: "Overlay", shadow_protect: 0.05, highlight_protect: 0.1, texture: 0.05 },
  // Anime: clean lines, flat fills stay flat
  "Anime sharp": { clarity: 0.35, sharpen: 0.65, strength: 0.7, halo: 0.45, skin_protect: 0.0, radius: 0.2, blend_mode: "Overlay", shadow_protect: 0.1, highlight_protect: 0.15, texture: 0.1 },
  // Painted and semi-real illustration: lines plus texture
  Illustration: { clarity: 0.3, sharpen: 0.5, strength: 0.7, halo: 0.5, skin_protect: 0.0, radius: 0.3, blend_mode: "Soft Light", shadow_protect: 0.15, highlight_protect: 0.15, texture: 0.35 },
  Custom: null,
};

const SLIDER_KEYS = [
  "clarity", "sharpen", "strength", "halo", "skin_protect",
  "radius", "blend_mode", "shadow_protect", "highlight_protect", "texture",
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
  // a saved workflow set to a preset gets that preset's current values; only Custom keeps what was saved
  loadedGraphNode(node) {
    if (node.comfyClass !== TYPE && node.type !== TYPE) return;
    hook(node);
    const preset = widgetByName(node, "preset")?.value;
    if (preset && preset !== "Custom") applyPreset(node, preset);
  },
});
