/**
 * Chrome for LC pipes + sampler configure family.
 * Color #707070 for pipes / aspect pipe out / all sampler configures.
 * Does NOT style 📐 Aspect Ratio Simplifier (pipe) [LCAspectRatioPipeOut].
 * Sampler configure nodes share a fixed default width so Simple matches Full.
 */
import { app } from "../../scripts/app.js";

const COLOR = "#707070";
const SAMPLER_WIDTH = 300;

const COLOR_TYPES = new Set([
  "LCPipeOut",
  "LCPipeEdit",
  "LCDetailPipeOut",
  "LCAspectRatioPipe", // LC Aspect Ratio Pipe Out only
  "LCSamplerConfigure",
  "LCSamplerConfigurePipeOut",
  "LCSamplerConfigurePipe",
  "LCSamplerConfigureSimple",
  "LCSamplerConfigureSimplePipeOut",
]);

const SAMPLER_TYPES = new Set([
  "LCSamplerConfigure",
  "LCSamplerConfigurePipeOut",
  "LCSamplerConfigurePipe",
  "LCSamplerConfigureSimple",
  "LCSamplerConfigureSimplePipeOut",
]);

function paint(node) {
  try {
    node.color = COLOR;
    node.bgcolor = COLOR;
  } catch (_) {}
}

function sizeSampler(node) {
  if (!node.size) node.size = [SAMPLER_WIDTH, 200];
  node.size[0] = SAMPLER_WIDTH;
  // Keep height from widget layout; only lock width on first create
  try {
    if (typeof node.computeSize === "function") {
      const s = node.computeSize();
      if (s && s[1]) node.size[1] = Math.max(node.size[1] || 0, s[1]);
    }
  } catch (_) {}
}

app.registerExtension({
  name: "LC123.PipeSamplerChrome",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    const name = nodeData?.name;
    if (!COLOR_TYPES.has(name) && !SAMPLER_TYPES.has(name)) return;

    const onCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const r = onCreated?.apply(this, arguments);
      if (COLOR_TYPES.has(name)) paint(this);
      if (SAMPLER_TYPES.has(name)) {
        sizeSampler(this);
        requestAnimationFrame(() => {
          paint(this);
          sizeSampler(this);
        });
      } else {
        requestAnimationFrame(() => paint(this));
      }
      return r;
    };
  },
  nodeCreated(node) {
    const t = node.comfyClass || node.type;
    if (COLOR_TYPES.has(t)) paint(node);
    if (SAMPLER_TYPES.has(t)) sizeSampler(node);
  },
});
