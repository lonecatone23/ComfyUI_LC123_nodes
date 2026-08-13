/**
 * LC Join Strings — dynamic input count (mirrors KJ JoinStringMulti UX).
 * Only inputcount sockets are visible; null/disconnected → empty string on server.
 */

import { app } from "../../scripts/app.js";

const NODE_CLASS = "LCJoinStrings";
const MAX_INPUTS = 32;
const MIN_INPUTS = 2;
const DEFAULT_WIDTH = 270;

function inputName(i) {
  return `string_${i}`;
}

function fitSize(node) {
  const slots = (node.inputs || []).length;
  const widgets = (node.widgets || []).filter(
    (w) => w && w.type !== "hidden" && w.name !== "return_list"
  ).length;
  // title ~30, ~26 per widget, ~22 per input row, minimal bottom pad
  const h = Math.max(58, 30 + widgets * 26 + slots * 22 + 4);
  const w = Math.max(DEFAULT_WIDTH, node.size?.[0] || DEFAULT_WIDTH);
  if (typeof node.setSize === "function") {
    node.setSize([w, h]);
  } else if (node.size) {
    node.size[0] = w;
    node.size[1] = h;
  }
}

function syncInputs(node) {
  const w = (node.widgets || []).find((x) => x.name === "inputcount");
  let count = w ? parseInt(w.value, 10) : MIN_INPUTS;
  if (Number.isNaN(count)) count = MIN_INPUTS;
  count = Math.max(MIN_INPUTS, Math.min(MAX_INPUTS, count));

  if (!node.inputs) node.inputs = [];

  const byName = new Map();
  for (const inp of node.inputs) {
    if (inp?.name) byName.set(inp.name, inp);
  }

  const next = [];
  for (let i = 1; i <= count; i++) {
    const name = inputName(i);
    if (byName.has(name)) {
      const inp = byName.get(name);
      inp.type = "STRING";
      if (inp.shape == null) inp.shape = 7; // optional
      next.push(inp);
    } else {
      next.push({
        name,
        type: "STRING",
        link: null,
        shape: 7,
      });
    }
  }

  // Disconnect links that would fall off the visible set
  for (let i = count + 1; i <= MAX_INPUTS; i++) {
    const name = inputName(i);
    const old = byName.get(name);
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
  name: "LC123.JoinStrings",

  async beforeRegisterNodeDef(nodeType, nodeData) {
    if ((nodeData?.name || "") !== NODE_CLASS) return;

    const origCompute = nodeType.prototype.computeSize;
    nodeType.prototype.computeSize = function (out) {
      const slots = (this.inputs || []).length || MIN_INPUTS;
      const widgets = (this.widgets || []).filter(
        (w) => w && w.type !== "hidden"
      ).length;
      const h = Math.max(58, 30 + widgets * 26 + slots * 22 + 4);
      const size = origCompute?.apply(this, arguments) || [DEFAULT_WIDTH, h];
      size[0] = Math.max(DEFAULT_WIDTH, size[0] || DEFAULT_WIDTH);
      size[1] = h;
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
      this.color = "#28281E";
      this.bgcolor = "#28281E";

      // Drop obsolete return_list widget if present from older graphs
      if (this.widgets) {
        this.widgets = this.widgets.filter((w) => w && w.name !== "return_list");
      }

      syncInputs(this);
      fitSize(this);

      const w = (this.widgets || []).find((x) => x.name === "inputcount");
      if (w && !w._lcBound) {
        w._lcBound = true;
        const prev = w.callback;
        w.callback = (v, ...args) => {
          const out = prev?.apply(w, [v, ...args]);
          syncInputs(this);
          return out;
        };
      }

      setTimeout(() => {
        syncInputs(this);
        fitSize(this);
      }, 0);
      setTimeout(() => {
        syncInputs(this);
        fitSize(this);
      }, 50);

      return r;
    };

    const onConfigure = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function (data) {
      const r = onConfigure?.apply(this, arguments);
      setTimeout(() => {
        syncInputs(this);
        fitSize(this);
      }, 20);
      return r;
    };
  },
});
