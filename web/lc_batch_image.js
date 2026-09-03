/**
 * LC Batch Image — autogrow IMAGE slots. Keep one empty socket.
 * computeSize returns the minimum only. this.size may grow and shrink to that min.
 * Height hugs the last socket. Launch width 270; shrink min ~180.
 */
import { app } from "../../scripts/app.js";
import { lcApplyLaunchColor } from "./lc_color.js";

const NODE_CLASS = "LCBatchImage";
const MAX_INPUTS = 20;
const MIN_INPUTS = 2;
const LAUNCH_WIDTH = 270;
const MIN_WIDTH = 180;
const COLOR = "#324B4B";

function inputName(i) {
  return `image_${String(i).padStart(2, "0")}`;
}

function slotHeight() {
  return (typeof LiteGraph !== "undefined" && LiteGraph.NODE_SLOT_HEIGHT) || 20;
}

function titleHeight() {
  return (typeof LiteGraph !== "undefined" && LiteGraph.NODE_TITLE_HEIGHT) || 30;
}

/** Minimum box that still shows every socket — hugs the last one. */
function desiredHeight(slots) {
  const n = Math.max(slots || 0, MIN_INPUTS);
  return titleHeight() + n * slotHeight() + 6;
}

function slotCount(node) {
  return (node.inputs || []).filter((i) => i && String(i.name || "").startsWith("image_")).length;
}

function setSize(node, w, h) {
  w = Math.max(MIN_WIDTH, w || MIN_WIDTH);
  h = Math.max(desiredHeight(MIN_INPUTS), h || desiredHeight(MIN_INPUTS));
  if (typeof node.setSize === "function") node.setSize([w, h]);
  else if (node.size) {
    node.size[0] = w;
    node.size[1] = h;
  } else {
    node.size = [w, h];
  }
}

function countFilled(node) {
  let n = 0;
  for (const inp of node.inputs || []) {
    if (inp?.name && String(inp.name).startsWith("image_") && inp.link != null) n++;
  }
  return n;
}

function hugHeight(node) {
  const n = slotCount(node) || MIN_INPUTS;
  const minH = desiredHeight(n);
  const w = Math.max(MIN_WIDTH, node.size?.[0] || LAUNCH_WIDTH);
  setSize(node, w, minH);
}

function syncInputs(node) {
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
  hugHeight(node);
  node.setDirtyCanvas?.(true, true);
}

app.registerExtension({
  name: "LC123.BatchImage",

  async beforeRegisterNodeDef(nodeType, nodeData) {
    if ((nodeData?.name || "") !== NODE_CLASS) return;

    const origCompute = nodeType.prototype.computeSize;
    nodeType.prototype.computeSize = function (out) {
      const slots = slotCount(this) || MIN_INPUTS;
      const minW = MIN_WIDTH;
      const minH = desiredHeight(slots);
      // Minimum only — never feed saved lc_h back or the node cannot shrink.
      const size = [minW, minH];
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
      if (!this.size) this.size = [LAUNCH_WIDTH, desiredHeight(MIN_INPUTS)];
      else this.size[0] = Math.max(MIN_WIDTH, this.size[0] || LAUNCH_WIDTH);
      if (!this.size[0] || this.size[0] < LAUNCH_WIDTH) this.size[0] = LAUNCH_WIDTH;
      syncInputs(this);
      const prevResize = this.onResize;
      this.onResize = function (size) {
        if (size) {
          if (size[0] < MIN_WIDTH) size[0] = MIN_WIDTH;
          const minH = desiredHeight(slotCount(this) || MIN_INPUTS);
          if (size[1] < minH) size[1] = minH;
        }
        return prevResize?.apply(this, arguments);
      };
      setTimeout(() => syncInputs(this), 0);
      return r;
    };

    const onConfigure = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function (data) {
      const r = onConfigure?.apply(this, arguments);
      setTimeout(() => {
        syncInputs(this);
        if (data?.size?.[0]) {
          const w = Math.max(MIN_WIDTH, data.size[0]);
          setSize(this, w, desiredHeight(slotCount(this) || MIN_INPUTS));
        }
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
