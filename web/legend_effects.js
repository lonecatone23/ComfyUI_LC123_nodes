/**
 * Legend Effects: only the chosen look's settings show (each setting is named <look prefix>_<name>, the label drops
 * the prefix). Switching looks keeps the preview the same size: the node grows or shrinks by the rows that change.
 * The preview + wipe itself is lc_image_preview.js (LegendEffects is in its NODE_CLASSES).
 */

import { app } from "../../scripts/app.js";

const TYPE = "LegendEffects";
const PREFIX = {
  "VHS TV": "vhs_",
  Pixelation: "pixel_",
  "Digital Glitch": "glitch_",
  "Night Vision": "nv_",
  Blueprint: "bp_",
  "Frosted Glass": "frost_",
  Gameboy: "gb_",
  "Edge-Preserving Blur": "blur_",
  Morphology: "morph_",
  Quantize: "quant_",
};
const ALL = Object.values(PREFIX);
const ROW = 24; // one widget row (20 px widget + 4 px gap)
const TITLE = 34;
const PAD = 16;
const PREVIEW_H = 335; // the LC image preview: 268 wide at 4:5 on a 300-wide node

function owned(w) {
  return !!w?.name && ALL.some((p) => w.name.startsWith(p));
}

function setVisible(w, on) {
  if (w._lcOrigType == null) w._lcOrigType = w.type;
  // order matters on new frontends: a hidden = false written while the type is still "hidden" doesn't count
  if (on) {
    w.type = w._lcOrigType;
    delete w.computeSize;
    w.hidden = false;
    w._lcHidden = false;
  } else {
    w.hidden = true;
    w._lcHidden = true;
    w.type = "hidden"; // older frontends only hide by type
    w.computeSize = () => [0, -4];
  }
}

function visibleCount(node) {
  return (node.widgets || []).filter((w) => owned(w) && !w._lcHidden).length;
}

function apply(node, resize) {
  const fx = (node.widgets || []).find((w) => w.name === "effect");
  const prefix = PREFIX[fx?.value] || "";
  const before = visibleCount(node);
  for (const w of node.widgets || []) {
    if (!owned(w)) continue;
    if (!w._lcLabeled) {
      w.label = w.name.slice(ALL.find((p) => w.name.startsWith(p)).length).replace(/_/g, " ");
      w._lcLabeled = true;
    }
    setVisible(w, !!prefix && w.name.startsWith(prefix));
  }
  if (resize && node.size) {
    const delta = (visibleCount(node) - before) * ROW;
    if (delta) node.setSize?.([node.size[0], Math.max(120, node.size[1] + delta)]);
  }
  node.setDirtyCanvas?.(true, true);
}

function hook(node, resize) {
  if (!node._lcLegendHooked) {
    node._lcLegendHooked = true;
    const fx = (node.widgets || []).find((w) => w.name === "effect");
    if (fx) {
      const prev = fx.callback;
      fx.callback = function () {
        const r = prev?.apply(this, arguments);
        apply(node, true);
        return r;
      };
    }
  }
  apply(node, resize);
}

function fitNew(node) {
  // a brand-new node: the rows it shows + the standard preview (a node from a saved workflow keeps its size)
  if (node._lcLegendLoaded || !node.size) return;
  const rows = (node.widgets || []).filter((w) => !w._lcHidden && w.type !== "hidden").length;
  node.setSize?.([Math.max(node.size[0], 300), TITLE + rows * ROW + PAD + PREVIEW_H + PAD]);
  node.setDirtyCanvas?.(true, true);
}

app.registerExtension({
  name: "LC123.LegendEffects",
  nodeCreated(node) {
    if ((node.comfyClass || node.type) !== TYPE) return;
    hook(node, false);
    // after lc_image_preview's own first sizing (its zero-delay grow runs after this one) and after a load's configure
    setTimeout(() => fitNew(node), 60);
  },
  loadedGraphNode(node) {
    if ((node.comfyClass || node.type) !== TYPE) return;
    node._lcLegendLoaded = true;
    hook(node, false); // a saved node keeps its saved size
  },
});
