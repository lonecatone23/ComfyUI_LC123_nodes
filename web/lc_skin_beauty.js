/**
 * LC Skin Beauty — presets fill sliders; manual change → Custom.
 */
import { app } from "../../scripts/app.js";

const TYPE = "LCSkinBeauty";

const PRESETS = {
  Natural: {
    coolness: 0.22, brightness: 0.12, rosy: 0.08, evenness: 0.18, shadow_lift: 0.15,
    smooth: 0.06, texture_preserve: 0.88, saturation: -0.08, highlight_protect: 0.75,
    mask_sensitivity: 0.55, mask_feather: 0.45,
  },
  Light: {
    coolness: 0.12, brightness: 0.06, rosy: 0.04, evenness: 0.1, shadow_lift: 0.08,
    smooth: 0.04, texture_preserve: 0.94, saturation: -0.04, highlight_protect: 0.85,
    mask_sensitivity: 0.5, mask_feather: 0.35,
  },
  Fresh: {
    coolness: 0.32, brightness: 0.18, rosy: 0.06, evenness: 0.22, shadow_lift: 0.18,
    smooth: 0.08, texture_preserve: 0.86, saturation: -0.1, highlight_protect: 0.7,
    mask_sensitivity: 0.58, mask_feather: 0.5,
  },
  Porcelain: {
    coolness: 0.4, brightness: 0.28, rosy: 0.05, evenness: 0.3, shadow_lift: 0.25,
    smooth: 0.14, texture_preserve: 0.82, saturation: -0.12, highlight_protect: 0.65,
    mask_sensitivity: 0.6, mask_feather: 0.55,
  },
  "Warm keep": {
    coolness: 0.08, brightness: 0.1, rosy: 0.18, evenness: 0.25, shadow_lift: 0.16,
    smooth: 0.08, texture_preserve: 0.9, saturation: -0.04, highlight_protect: 0.8,
    mask_sensitivity: 0.55, mask_feather: 0.45,
  },
  Custom: null,
};

const SLIDER_KEYS = [
  "coolness", "brightness", "rosy", "evenness", "shadow_lift", "smooth",
  "texture_preserve", "saturation", "highlight_protect", "mask_sensitivity", "mask_feather",
];

function widgetByName(node, name) {
  return (node.widgets || []).find((w) => w.name === name);
}

function applyPresetToSliders(node, presetName) {
  const cfg = PRESETS[presetName];
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
  // strength is separate on skin beauty - leave as user set unless in cfg
  node.setDirtyCanvas?.(true, true);
}

function snapToCustom(node) {
  if (node._lcApplyingPreset) return;
  const presetW = widgetByName(node, "preset");
  if (!presetW || presetW.value === "Custom") return;
  presetW.value = "Custom";
  node.setDirtyCanvas?.(true, true);
}

function hookPreset(node) {
  if (node._lcSkinPresetHooked) return;
  node._lcSkinPresetHooked = true;
  const presetW = widgetByName(node, "preset");
  if (presetW) {
    const prev = presetW.callback;
    presetW.callback = function (value, ...rest) {
      if (value && value !== "Custom") applyPresetToSliders(node, value);
      if (typeof prev === "function") return prev.apply(this, [value, ...rest]);
    };
    if (presetW.value && presetW.value !== "Custom") applyPresetToSliders(node, presetW.value);
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
  // strength also counts as manual adjust
  const st = widgetByName(node, "strength");
  if (st && !st._lcSnapCustom) {
    st._lcSnapCustom = true;
    const prev = st.callback;
    st.callback = function (value, ...rest) {
      snapToCustom(node);
      if (typeof prev === "function") return prev.apply(this, [value, ...rest]);
    };
  }
}

app.registerExtension({
  name: "LC123.SkinBeauty",
  nodeCreated(node) {
    if (node.comfyClass !== TYPE && node.type !== TYPE) return;
    hookPreset(node);
  },
});
