/**
 * Chrome for LC pipes + sampler configure family.
 * Color #707070 for pipes / aspect pipe out / all sampler configures.
 * Does NOT style 📐 Aspect Ratio Simplifier (pipe) [LCAspectRatioPipeOut].
 * Sampler width default 300 on first create only — manual size is retained.
 */
import { app } from "../../scripts/app.js";

const COLOR = "#707070";
const SAMPLER_WIDTH = 300;

const COLOR_TYPES = new Set([
  "LCPipeOut",
  "LCPipeEdit",
  "LCDetailPipeOut",
  "LCAspectRatioPipe",
  "LCMiniMaxH3Pipe",
  "LCMiniMaxH3PipeOut",
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

function rememberSize(node) {
  if (!node.properties) node.properties = {};
  if (node.size) {
    node.properties.lc_w = node.size[0];
    node.properties.lc_h = node.size[1];
  }
  node._lcUserSized = true;
}

function restoreSize(node) {
  const w = node.properties?.lc_w;
  const h = node.properties?.lc_h;
  if (w && h) {
    if (!node.size) node.size = [w, h];
    else {
      node.size[0] = w;
      node.size[1] = h;
    }
    node._lcUserSized = true;
    return true;
  }
  return false;
}

/** Default sampler width once; never overwrite a user-resized node. */
function sizeSampler(node) {
  if (node._lcUserSized || node.properties?.lc_w) {
    restoreSize(node);
    return;
  }
  if (!node.size) node.size = [SAMPLER_WIDTH, 200];
  // Only set default width if still at a tiny/placeholder size
  if ((node.size[0] || 0) < 40) node.size[0] = SAMPLER_WIDTH;
  if ((node.size[0] || 0) === 0) node.size[0] = SAMPLER_WIDTH;
  // Do not force height — let LiteGraph / widgets own it after first layout
}

function hookResize(node) {
  if (node._lcSamplerResizeHooked) return;
  node._lcSamplerResizeHooked = true;
  const prev = node.onResize;
  node.onResize = function (size) {
    const r = prev?.apply(this, arguments);
    rememberSize(this);
    return r;
  };
  const prevCfg = node.onConfigure;
  node.onConfigure = function (data) {
    const r = prevCfg?.apply(this, arguments);
    if (data?.size) {
      if (!this.properties) this.properties = {};
      this.properties.lc_w = data.size[0];
      this.properties.lc_h = data.size[1];
      this._lcUserSized = true;
    }
    restoreSize(this);
    return r;
  };
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
        hookResize(this);
        if (!restoreSize(this)) sizeSampler(this);
      } else {
        requestAnimationFrame(() => paint(this));
      }
      return r;
    };
  },
  nodeCreated(node) {
    const t = node.comfyClass || node.type;
    if (COLOR_TYPES.has(t)) paint(node);
    if (SAMPLER_TYPES.has(t)) {
      hookResize(node);
      if (!restoreSize(node)) sizeSampler(node);
    }
  },
});
