/**
 * LC Text Replace — show only entrycount find/replace pairs; resize node.
 */

import { app } from "../../scripts/app.js";

const NODE_CLASS = "LCTextReplace";
const MAX = 20;
const MIN = 1;
const DEFAULT_W = 300;
const ROW_H = 26;
const BASE_WIDGETS = 3; // entrycount, use_regex, count

function getCount(node) {
  const cw = (node.widgets || []).find((x) => x.name === "entrycount");
  let count = cw ? parseInt(cw.value, 10) : MIN;
  if (Number.isNaN(count)) count = MIN;
  return Math.max(MIN, Math.min(MAX, count));
}

function desiredHeight(count) {
  // title + fixed widgets + 2 rows per entry + padding
  return Math.max(90, 34 + BASE_WIDGETS * 28 + count * 2 * ROW_H + 14);
}

function fitSize(node, count) {
  const h = desiredHeight(count);
  const w = Math.max(DEFAULT_W, node.size?.[0] || DEFAULT_W);
  if (typeof node.setSize === "function") {
    node.setSize([w, h]);
  } else if (node.size) {
    node.size[0] = w;
    node.size[1] = h;
  }
  node.setDirtyCanvas?.(true, true);
  app.graph?.setDirtyCanvas?.(true, true);
  app.canvas?.setDirty?.(true, true);
}

function fixTextSocket(node) {
  if (node.widgets?.length) {
    node.widgets = node.widgets.filter((w) => w && w.name !== "text");
  }
  if (!node.inputs?.length) return;
  const texts = node.inputs.filter((i) => i?.name === "text");
  const rest = node.inputs.filter((i) => i?.name !== "text");
  if (!texts.length) return;
  const keep = texts[0];
  keep.type = "STRING";
  for (let i = 1; i < texts.length; i++) {
    if (texts[i].link != null && app.graph) {
      try { app.graph.removeLink(texts[i].link); } catch (_) {}
    }
  }
  node.inputs = [keep, ...rest];
}

function syncEntries(node) {
  if (!node.widgets) return;
  fixTextSocket(node);
  const count = getCount(node);

  for (const w of node.widgets) {
    if (!w?.name) continue;
    const m = /^(find|replace)_(\d+)$/.exec(w.name);
    if (!m) continue;
    const idx = parseInt(m[2], 10);
    const show = idx <= count;

    w.hidden = !show;

    // Keep type as text when shown; mark hidden for layout
    if (show) {
      if (w._lc_type) w.type = w._lc_type;
      else if (w.type === "hidden") w.type = "text";
      w.computeSize = w._lc_origCompute || undefined;
    } else {
      if (w.type && w.type !== "hidden") w._lc_type = w.type;
      w.type = "hidden";
      w.computeSize = () => [0, -4];
    }
  }

  // Reorder: fixed widgets first, then visible pairs in order, then hidden
  const fixed = [];
  const pairs = [];
  const hidden = [];
  for (const w of node.widgets) {
    if (/^(find|replace)_\d+$/.test(w.name || "")) {
      if (w.hidden) hidden.push(w);
      else pairs.push(w);
    } else {
      fixed.push(w);
    }
  }
  pairs.sort((a, b) => {
    const ia = parseInt(/_(\d+)$/.exec(a.name)[1], 10);
    const ib = parseInt(/_(\d+)$/.exec(b.name)[1], 10);
    if (ia !== ib) return ia - ib;
    return a.name.startsWith("find") ? -1 : 1;
  });
  node.widgets = fixed.concat(pairs, hidden);

  fitSize(node, count);
}

function bindCountWidget(node) {
  const cw = (node.widgets || []).find((x) => x.name === "entrycount");
  if (!cw || cw._lcBound) return;
  cw._lcBound = true;

  const prev = cw.callback;
  cw.callback = function (v, ...rest) {
    const out = prev?.apply(this, [v, ...rest]);
    // Immediate + rAF so value is committed
    syncEntries(node);
    requestAnimationFrame(() => syncEntries(node));
    return out;
  };

  // Number widgets also update on mouse release without always firing callback the same way
  const prevMouse = cw.mouse;
  if (typeof prevMouse === "function") {
    cw.mouse = function (...args) {
      const r = prevMouse.apply(this, args);
      syncEntries(node);
      return r;
    };
  }
}

app.registerExtension({
  name: "LC123.TextReplace",

  async beforeRegisterNodeDef(nodeType, nodeData) {
    if ((nodeData?.name || "") !== NODE_CLASS) return;

    const origCompute = nodeType.prototype.computeSize;
    nodeType.prototype.computeSize = function (out) {
      const count = getCount(this);
      const h = desiredHeight(count);
      const size = origCompute?.apply(this, arguments) || [DEFAULT_W, h];
      size[0] = Math.max(DEFAULT_W, size[0] || DEFAULT_W);
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

      for (const w of this.widgets || []) {
        if (
          /^(find|replace)_\d+$/.test(w.name || "") &&
          typeof w.computeSize === "function" &&
          !w._lc_origCompute
        ) {
          w._lc_origCompute = w.computeSize.bind(w);
        }
      }

      fixTextSocket(this);
      bindCountWidget(this);
      syncEntries(this);

      setTimeout(() => {
        bindCountWidget(this);
        syncEntries(this);
      }, 0);
      setTimeout(() => syncEntries(this), 30);
      setTimeout(() => syncEntries(this), 100);

      return r;
    };

    const onConfigure = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function (data) {
      const r = onConfigure?.apply(this, arguments);
      setTimeout(() => {
        bindCountWidget(this);
        syncEntries(this);
      }, 20);
      return r;
    };

    // Catch widget changes from the graph UI path
    const onWidgetChanged = nodeType.prototype.onWidgetChanged;
    nodeType.prototype.onWidgetChanged = function (name, value, ...rest) {
      const r = onWidgetChanged?.apply(this, [name, value, ...rest]);
      if (name === "entrycount") {
        syncEntries(this);
        requestAnimationFrame(() => syncEntries(this));
      }
      return r;
    };
  },
});
