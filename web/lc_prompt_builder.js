/**
 * LC Prompt Builder — chrome + live composed prompt preview (fits node)
 */
import { app } from "../../scripts/app.js";
import { lcApplyLaunchColor } from "./lc_color.js";
import { LC_PROMPT_DATA as D } from "./lc_prompt_builder_data.js";

const PROMPT_TYPES = new Set([
  "LCWildcard",
  "LCSubject", "LCSubjectArray", "LCCamera", "LCLighting",
  "LCStyleSelector", "LCSceneBuilder", "LCPromptAssembler",
]);

/** Per-node chrome from workflow reference (header + body). */
const NODE_COLORS = {
  LCSubject:        { color: "#326432", bgcolor: "#326432" },
  LCSubjectArray:   { color: "#141914", bgcolor: "#000500" },
  LCCamera:         { color: "#4c3d3d", bgcolor: "#382929" },
  LCLighting:       { color: "#534317", bgcolor: "#3f2f03" },
  LCStyleSelector:  { color: "#5d2a64", bgcolor: "#491650" },
  LCSceneBuilder:   { color: "#551e1e", bgcolor: "#410a0a" },
  LCPromptAssembler:{ color: "#141914", bgcolor: "#000500" },
  LCWildcard:       { color: "#625a9f", bgcolor: "#4e468b" },
  LCColorPalette:   { color: "#324B4B", bgcolor: "#324B4B" },
};
const COLOR_PROMPT = "#326432"; // fallback
const COLOR_IMAGE = "#324B4B";
const WIDTH = 340;
const PREVIEW_H = 88; // fixed textarea height inside node

function style(node, colorOrPair) {
  if (!node || !colorOrPair) return;
  if (colorOrPair && typeof colorOrPair === "object") {
    lcApplyLaunchColor(node, colorOrPair.color, colorOrPair.bgcolor ?? colorOrPair.color);
  } else {
    lcApplyLaunchColor(node, colorOrPair);
  }
}

function colorFor(type) {
  return NODE_COLORS[type] || { color: COLOR_PROMPT, bgcolor: COLOR_PROMPT };
}

function wval(node, name) {
  const w = node.widgets?.find((x) => x.name === name);
  return w ? w.value : "";
}

function joinParts(parts) {
  return parts.map((p) => (p || "").toString().trim()).filter(Boolean).join(", ");
}

function stripClashes(text, timeOfDay, weather) {
  let t = text || "";
  if (timeOfDay) {
    t = t.replace(/\bat night\b/gi, "")
      .replace(/\bnighttime\b/gi, "")
      .replace(/\bin daylight\b/gi, "")
      .replace(/\bdaytime\b/gi, "")
      .replace(/\bmidday\b/gi, "")
      .replace(/\bgolden hour\b/gi, "")
      .replace(/\bat dawn\b/gi, "")
      .replace(/\bin the morning\b/gi, "")
      .replace(/\bin the evening\b/gi, "")
      .replace(/\bblue hour\b/gi, "")
      .replace(/\blate-afternoon\b/gi, "")
      .replace(/\blate afternoon\b/gi, "");
  }
  if (weather) {
    t = t.replace(/\brainy\b/gi, "")
      .replace(/\bovercast\b/gi, "")
      .replace(/\bfoggy\b/gi, "")
      .replace(/\bsnowy\b/gi, "")
      .replace(/\bclear sky\b/gi, "")
      .replace(/\bpartly cloudy\b/gi, "");
  }
  return t.replace(/\s{2,}/g, " ").replace(/\s+,/g, ",").trim().replace(/^[,\s]+|[,\s]+$/g, "");
}

function composeScene(node) {
  const preset = wval(node, "scene_preset");
  const desc = wval(node, "description");
  let tod = wval(node, "time_of_day");
  let weather = wval(node, "weather");
  const env = wval(node, "environment_details");
  if (String(tod).toLowerCase() === "none") tod = "";
  if (String(weather).toLowerCase() === "none") weather = "";
  let base = D.scene_presets?.[preset] || preset || "";
  base = stripClashes(base, tod, weather);
  const body = desc && String(desc).trim() ? `${base}. ${String(desc).trim()}` : base;
  const parts = [body];
  if (tod) parts.push(D.time_detail?.[tod] || `time: ${tod}`);
  if (weather) parts.push(D.weather_detail?.[weather] || `weather: ${weather}`);
  if (env) parts.push(env);
  return joinParts(parts);
}

function composeCamera(node) {
  const prompt = wval(node, "prompt");
  const angle = wval(node, "angle");
  const distance = wval(node, "distance");
  const dof = wval(node, "depth_of_field");
  const parts = [
    prompt,
    D.camera_angle_detail?.[angle] || (angle ? `camera angle: ${angle}` : ""),
    D.camera_distance_detail?.[distance] || (distance ? `framing: ${distance}` : ""),
  ];
  if (dof && String(dof).toLowerCase() !== "none") {
    parts.push(`depth of field: ${dof}`);
  }
  return joinParts(parts);
}

function composeLighting(node) {
  const prompt = wval(node, "prompt");
  const lighting = wval(node, "lighting");
  const dir = wval(node, "light_direction");
  return joinParts([
    prompt,
    D.lighting_detail?.[lighting] || (lighting ? `lighting: ${lighting}` : ""),
    D.light_direction_detail?.[dir] || (dir ? `light direction: ${dir}` : ""),
  ]);
}

function composeStyle(node) {
  const prompt = wval(node, "prompt");
  const cat = wval(node, "style_category");
  const preset = wval(node, "style_preset");
  const quality = wval(node, "quality_level");
  return joinParts([
    prompt,
    cat,
    D.style_presets?.[preset] || preset,
    D.quality_detail?.[quality] || quality,
  ]);
}

function composeSubject(node) {
  const description = wval(node, "description");
  const pose = wval(node, "pose");
  const action = wval(node, "action");
  const outfit = wval(node, "outfit");
  const ph = wval(node, "position_horizontal");
  const pv = wval(node, "position_vertical");
  const pd = wval(node, "position_depth");
  const parts = [description];
  if (pose && pose !== "none") parts.push(`pose: ${pose}`);
  if (action && action !== "none") parts.push(`action: ${action}`);
  if (outfit && outfit !== "none") {
    const label = String(outfit).includes("/") ? String(outfit).split("/").pop() : outfit;
    parts.push(`wearing ${label}`);
  }
  parts.push(`position: ${ph}, ${pv}, ${pd}`);
  return joinParts(parts);
}

function composerFor(type) {
  if (type === "LCSceneBuilder") return composeScene;
  if (type === "LCCamera") return composeCamera;
  if (type === "LCLighting") return composeLighting;
  if (type === "LCStyleSelector") return composeStyle;
  if (type === "LCSubject") return composeSubject;
  return null;
}

function ensurePreview(node) {
  if (node._lcLivePromptEl) return node._lcLivePromptEl;
  const el = document.createElement("textarea");
  el.className = "lc-prompt-live-preview";
  el.readOnly = true;
  el.rows = 4;
  el.style.cssText = [
    "width:100%",
    `height:${PREVIEW_H}px`,
    "max-height:" + PREVIEW_H + "px",
    "min-height:" + PREVIEW_H + "px",
    "box-sizing:border-box",
    "resize:none",
    "overflow:auto",
    "background:#1a1a1a",
    "color:#d8d8d8",
    "border:1px solid #444",
    "border-radius:4px",
    "padding:6px",
    "font-size:11px",
    "line-height:1.35",
    "font-family:inherit",
    "margin:0",
  ].join(";");
  const widget = node.addDOMWidget("lc_live_prompt", "customtext", el, {
    getValue() {
      return el.value;
    },
    setValue(v) {
      el.value = v ?? "";
    },
    getMinHeight() {
      return PREVIEW_H + 8;
    },
    serialize: false,
  });
  // Keep DOM widget height stable so LiteGraph computeSize includes it
  widget.computeSize = function (width) {
    return [width || WIDTH, PREVIEW_H + 10];
  };
  node._lcLivePromptEl = el;
  node._lcLivePromptWidget = widget;
  return el;
}

function refreshPreview(node) {
  const type = node.comfyClass || node.type;
  const fn = composerFor(type);
  if (!fn) return;
  const el = ensurePreview(node);
  try {
    el.value = fn(node) || "";
  } catch (_) {
    el.value = "";
  }
  // Recompute node size so the preview stays inside the frame
  try {
    if (typeof node.computeSize === "function") {
      const sz = node.computeSize();
      if (sz && sz.length === 2) {
        node.size[0] = Math.max(node.size[0] || WIDTH, sz[0], WIDTH);
        node.size[1] = Math.max(sz[1], node.size[1] || 0);
      }
    }
  } catch (_) {}
  node.setDirtyCanvas?.(true, true);
}

function hookWidgets(node) {
  if (node._lcPromptHooked) return;
  node._lcPromptHooked = true;
  const type = node.comfyClass || node.type;
  if (!composerFor(type)) return;
  ensurePreview(node);
  for (const w of node.widgets || []) {
    if (w.name === "lc_live_prompt") continue;
    const prev = w.callback;
    w.callback = function () {
      const r = prev?.apply(this, arguments);
      refreshPreview(node);
      return r;
    };
  }
  const onCfg = node.onConfigure;
  node.onConfigure = function () {
    const r = onCfg?.apply(this, arguments);
    setTimeout(() => {
      ensurePreview(this);
      refreshPreview(this);
    }, 0);
    return r;
  };
  // After widgets exist, force size once
  setTimeout(() => {
    ensurePreview(node);
    refreshPreview(node);
    try {
      const sz = node.computeSize?.(node.size?.[0] || WIDTH);
      if (sz) {
        node.setSize?.([Math.max(WIDTH, sz[0]), sz[1]]);
        if (!node.setSize) {
          node.size[0] = Math.max(WIDTH, sz[0]);
          node.size[1] = sz[1];
        }
      }
    } catch (_) {}
    node.setDirtyCanvas?.(true, true);
  }, 50);
}

app.registerExtension({
  name: "LC123.PromptBuilder",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    const name = nodeData?.name;
    if (!PROMPT_TYPES.has(name) && name !== "LCColorPalette") return;
    const onCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const r = onCreated?.apply(this, arguments);
      style(this, colorFor(name));
      if (name === "LCColorPalette") {
        this.size = [WIDTH, 280];
      } else {
        this.size = [WIDTH, this.size?.[1] || 200];
        if (composerFor(name)) hookWidgets(this);
      }
      return r;
    };
  },
  nodeCreated(node) {
    const t = node.comfyClass || node.type;
    if (t === "LCColorPalette" || PROMPT_TYPES.has(t)) {
      style(node, colorFor(t));
      if (composerFor(t)) hookWidgets(node);
    }
  },
});
