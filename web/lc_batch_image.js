/**
 * LC Batch Image — autogrow IMAGE slots. Keep one empty socket.
 * Manual size remembered (lc_w / lc_h).
 */
import { app } from "../../scripts/app.js";
import { lcApplyLaunchColor } from "./lc_color.js";

const NODE_CLASS = "LCBatchImage";
const MAX_INPUTS = 20;
const MIN_INPUTS = 2;
const DEFAULT_WIDTH = 270;
const COLOR = "#324B4B";

function inputName(i) {
  return `image_${String(i).padStart(2, "0")}`;
}

function applySize(node, w, h) {
  w = Math.max(DEFAULT_WIDTH, w || DEFAULT_WIDTH);
  h = Math.max(56, h || 56);
  if (typeof node.setSize === "function") node.setSize([w, h]);
  else if (node.size) {
    node.size[0] = w;
    node.size[1] = h;
  } else {
    node.size = [w, h];
  }
  if (!node.properties) node.properties = {};
  node.properties.lc_w = w;
  node.properties.lc_h = h;
}

function slotCount(node) {
  return (node.inputs || []).filter((i) => i && String(i.name || "").startsWith("image_")).length;
}

function rememberSize(node) {
  if (!node.properties) node.properties = {};
  if (node.size) {
    node.properties.lc_w = node.size[0];
    node.properties.lc_h = Math.max(node.size[1] || 0, desiredHeight(slotCount(node)));
  }
  node._lcUserSized = true;
}

function restoreSize(node) {
  const w = node.properties?.lc_w;
  const h = node.properties?.lc_h;
  const needH = desiredHeight(slotCount(node) || MIN_INPUTS);
  if (w) {
    applySize(node, w, Math.max(h || 0, needH));
    node._lcUserSized = true;
    return true;
  }
  return false;
}

function desiredHeight(slots) {
  return Math.max(56, 34 + Math.max(slots, MIN_INPUTS) * 24 + 16);
}

function fitSize(node) {
  const n = slotCount(node) || MIN_INPUTS;
  const needH = desiredHeight(n);
  const w = Math.max(DEFAULT_WIDTH, node.size?.[0] || DEFAULT_WIDTH, node.properties?.lc_w || 0);
  const h = Math.max(needH, node._lcUserSized ? (node.size?.[1] || 0) : 0);
  applySize(node, w, h);
}

function countFilled(node) {
  let n = 0;
  for (const inp of node.inputs || []) {
    if (inp?.name && String(inp.name).startsWith("image_") && inp.link != null) n++;
  }
  return n;
}

function syncInputs(node, { fit = false } = {}) {
  if (!node.inputs) node.inputs = [];
  const byName = new Map();
  const keepOther = [];
  for (const inp of node.inputs) {
    if (!inp) continue;
    if (String(inp.name || "").startsWith("image_")) byName.set(inp.name, inp);
    else keepOther.push(inp);
  }

  const filled = countFilled(node);
  let want = Math.max(MIN_INPUTS, filled + 1);
  want = Math.min(MAX_INPUTS, want);

  const next = keepOther.slice();
  for (let i = 1; i <= want; i++) {
    const name = inputName(i);
    if (byName.has(name)) {
      const inp = byName.get(name);
      inp.type = "IMAGE";
      inp.name = name;
      next.push(inp);
    } else {
      next.push({ name, type: "IMAGE", link: null });
    }
  }
  for (let i = want + 1; i <= MAX_INPUTS; i++) {
    const old = byName.get(inputName(i));
    if (old?.link != null && app.graph) {
      try {
        app.graph.removeLink(old.link);
      } catch (_) {}
    }
  }
  node.inputs = next;
  fitSize(node);
  node.setDirtyCanvas?.(true, true);
}

app.registerExtension({
  name: "LC123.BatchImage",

  async beforeRegisterNodeDef(nodeType, nodeData) {
    if ((nodeData?.name || "") !== NODE_CLASS) return;

    const origCompute = nodeType.prototype.computeSize;
    nodeType.prototype.computeSize = function (out) {
      const slots = slotCount(this) || MIN_INPUTS;
      const minH = desiredHeight(slots);
      const w = Math.max(DEFAULT_WIDTH, this.properties?.lc_w || this.size?.[0] || DEFAULT_WIDTH);
      const h = Math.max(minH, this.properties?.lc_h || 0);
      const size = [w, h];
      if (out) {
        out[0] = size[0];
        out[1] = size[1];
        return out;
      }
      return size;
    };

    const onCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const r = onCreated?.apply(this, arguments);
      try {
        lcApplyLaunchColor(this, COLOR);
      } catch (_) {}
      syncInputs(this);
      const prevResize = this.onResize;
      this.onResize = function () {
        const out = prevResize?.apply(this, arguments);
        rememberSize(this);
        return out;
      };
      setTimeout(() => {
        syncInputs(this);
        restoreSize(this);
      }, 0);
      return r;
    };

    const onConfigure = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function (data) {
      const r = onConfigure?.apply(this, arguments);
      if (data?.size) {
        if (!this.properties) this.properties = {};
        this.properties.lc_w = data.size[0];
        this.properties.lc_h = data.size[1];
        this._lcUserSized = true;
      }
      setTimeout(() => {
        syncInputs(this);
        restoreSize(this);
      }, 20);
      return r;
    };

    const onConnectionsChange = nodeType.prototype.onConnectionsChange;
    nodeType.prototype.onConnectionsChange = function () {
      const r = onConnectionsChange?.apply(this, arguments);
      setTimeout(() => syncInputs(this), 0);
      return r;
    };
  },
});
