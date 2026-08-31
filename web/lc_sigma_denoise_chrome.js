/**
 * Color chrome:
 * - LC Denoise 💉 → #823282
 * - Sigma / basic scheduler nodes → #1c6d6d
 */
import { app } from "../../scripts/app.js";
import { lcApplyLaunchColor } from "./lc_color.js";

const DENOISE = {
  types: new Set(["LCDenoise"]),
  color: "#823282",
};

const SIGMA = {
  types: new Set([
    "LCSplitSigmaScheduler",
    "LCSplitSigmasAdvanced",
    "LCBasicScheduler",
  ]),
  color: "#1c6d6d",
};

function paint(node, color) {
  lcApplyLaunchColor(node, color);
}

function apply(node) {
  const t = node.comfyClass || node.type;
  if (DENOISE.types.has(t)) paint(node, DENOISE.color);
  else if (SIGMA.types.has(t)) paint(node, SIGMA.color);
}

app.registerExtension({
  name: "LC123.SigmaDenoiseChrome",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    const name = nodeData?.name;
    const isD = DENOISE.types.has(name);
    const isS = SIGMA.types.has(name);
    if (!isD && !isS) return;
    const color = isD ? DENOISE.color : SIGMA.color;
    const onCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const r = onCreated?.apply(this, arguments);
      paint(this, color);
      requestAnimationFrame(() => paint(this, color));
      return r;
    };
  },
  nodeCreated(node) {
    apply(node);
  },
});
