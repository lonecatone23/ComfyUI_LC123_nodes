/**
 * LC Sampler Configure — turn _gap1 / _gap2 into ~5px visual spacers.
 */

import { app } from "../../scripts/app.js";

const CLASSES = new Set([
  "LCSamplerConfigure",
  "LCSamplerConfigurePipeOut",
]);


function forceDenoiseStep(node) {
  if (!node?.widgets) return;
  for (const w of node.widgets) {
    if (w?.name !== "denoise") continue;
    w.options = w.options || {};
    w.options.step = 0.01;
    w.options.round = 0.01;
    if (typeof w.step !== "undefined") w.step = 0.01;
  }
}

function applyGaps(node) {
  if (!node.widgets) return;
  for (const w of node.widgets) {
    if (!w || (w.name !== "_gap1" && w.name !== "_gap2")) continue;
    w.hidden = false;
    w.type = "converted-widget"; // avoid normal text field chrome when possible
    w.computeSize = () => [node.size?.[0] || 200, 5];
    w.draw = function (ctx, n, width, y) {
      // empty 5px band
      return y + 5;
    };
    // Prevent serializing noise into prompts
    w.serializeValue = async () => "";
    w.options = w.options || {};
  }
}

app.registerExtension({
  name: "LC123.SamplerConfigureGaps",

  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (!CLASSES.has(nodeData?.name || "")) return;

    const onCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const r = onCreated?.apply(this, arguments);
      applyGaps(this);
      forceDenoiseStep(this);
      setTimeout(() => { applyGaps(this); forceDenoiseStep(this); }, 0);
      return r;
    };

    const onConfigure = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function (o) {
      const r = onConfigure?.apply(this, arguments);
      setTimeout(() => { applyGaps(this); forceDenoiseStep(this); }, 0);
      return r;
    };
  },
});
