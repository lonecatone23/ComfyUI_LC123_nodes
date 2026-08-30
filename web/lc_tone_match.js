/**
 * LC Tone Match — same color + launch size as LC Color Match / image FX.
 */
import { app } from "../../scripts/app.js";

const COLOR = "#324B4B";
const DEFAULT_W = 300;
const MIN_W = 260;
const PAD = 16;
const TITLE = 34;

function widgetsHeight(node) {
  let y = TITLE;
  for (const w of node.widgets || []) {
    if (!w || w.type === "hidden" || w._lcHidden) continue;
    const h =
      typeof w.computeSize === "function"
        ? w.computeSize(node.size?.[0] || DEFAULT_W)?.[1] ?? 22
        : 22;
    y += Math.max(20, h);
  }
  return y;
}

function defaultHeight(node) {
  const innerW = DEFAULT_W - PAD * 2;
  const imgH = Math.round(innerW * (5 / 4));
  return widgetsHeight(node) + PAD + imgH + PAD;
}

function paint(node) {
  node.color = COLOR;
  node.bgcolor = COLOR;
  const h = Math.max(node.size?.[1] || 0, defaultHeight(node), 470);
  node.size = [Math.max(node.size?.[0] || 0, DEFAULT_W), h];
}

app.registerExtension({
  name: "LC123.ToneMatchChrome",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData?.name !== "LCToneMatch") return;
    const onCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      if (onCreated) onCreated.apply(this, arguments);
      paint(this);
      requestAnimationFrame(() => paint(this));
      setTimeout(() => {
        try {
          paint(this);
          this.setDirtyCanvas?.(true, true);
        } catch (_) {}
      }, 50);
    };
    const origResize = nodeType.prototype.onResize;
    nodeType.prototype.onResize = function (size) {
      if (size && size[0] < MIN_W) size[0] = MIN_W;
      if (origResize) origResize.apply(this, arguments);
    };
  },
});
