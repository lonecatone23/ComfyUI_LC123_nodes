/**
 * LC Text Remove — entrycount find rows; single text input; resize node.
 */

import { app } from "../../scripts/app.js";

const NODE_CLASS = "LCTextRemove";
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
  // title + 1 input row (text) + fixed widgets + find rows
  return Math.max(90, 34 + 22 + BASE_WIDGETS * 28 + count * ROW_H + 14);
}

function fitSize(node, count) {
  const h = desiredHeight(count);
  const w = Math.max(DEFAULT_W, node.size?.[0] || DEFAULT_W);
  if (typeof node.setSize === "function") node.setSize([w, h]);
  else if (node.size) {
    node.size[0] = w;
    node.size[1] = h;
  }
  node.setDirtyCanvas?.(true, true);
  app.graph?.setDirtyCanvas?.(true, true);
  app.canvas?.setDirty?.(true, true);
}

/** forceInput STRING often leaves a widget + duplicate input; keep one socket only */
function fixTextSocket(node) {
  if (node.widgets?.length) {
    node.widgets = node.widgets.filter((w) => w && w.name !== "text");
  }
  if (!node.inputs?.length) return;

  const texts = [];
  const rest = [];
  for (const inp of node.inputs) {
    if (inp?.name === "text") texts.push(inp);
    else rest.push(inp);
  }
  if (!texts.length) return;

  const keep = texts[0];
  keep.type = "STRING";
  keep.name = "text";
  // shape 7 = optional-looking; keep default for required
  for (let i = 1; i < texts.length; i++) {
    const extra = texts[i];
    if (extra.link != null && app.graph) {
      try {
        app.graph.removeLink(extra.link);
      } catch (_) {}
    }
  }
  node.inputs = [keep, ...rest.filter((i) => i.name !== "text")];
}

function syncEntries(node) {
  if (!node.widgets) return;
  fixTextSocket(node);
  const count = getCount(node);

  for (const w of node.widgets) {
    if (!w?.name) continue;
    const m = /^find_(\d+)$/.exec(w.name);
    if (!m) continue;
    const idx = parseInt(m[1], 10);
    const show = idx <= count;

    w.hidden = !show;
    if (show) {
      if (w._lc_type) w.type = w._lc_type;
      else if (w.type === "hidden") w.type = "text";
      if (w._lc_origCompute) w.computeSize = w._lc_origCompute;
      else delete w.computeSize;
    } else {
      if (w.type && w.type !== "hidden") w._lc_type = w.type;
      w.type = "hidden";
      w.computeSize = () => [0, -4];
    }
  }

  const fixed = [];
  const finds = [];
  const hidden = [];
  for (const w of node.widgets) {
    if (/^find_\d+$/.test(w.name || "")) {
      if (w.hidden) hidden.push(w);
      else finds.push(w);
    } else {
      fixed.push(w);
    }
  }
  finds.sort((a, b) => {
    const ia = parseInt(/_(\d+)$/.exec(a.name)[1], 10);
    const ib = parseInt(/_(\d+)$/.exec(b.name)[1], 10);
    return ia - ib;
  });
  node.widgets = fixed.concat(finds, hidden);

  fitSize(node, count);
}

function bindCountWidget(node) {
  const cw = (node.widgets || []).find((x) => x.name === "entrycount");
  if (!cw || cw._lcBound) return;
  cw._lcBound = true;

  const prev = cw.callback;
  cw.callback = function (v, ...rest) {
    const out = prev?.apply(this, [v, ...rest]);
    syncEntries(node);
    requestAnimationFrame(() => syncEntries(node));
    return out;
  };

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
  name: "LC123.TextRemove",

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
          /^find_\d+$/.test(w.name || "") &&
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
        fixTextSocket(this);
        bindCountWidget(this);
        syncEntries(this);
      }, 0);
      setTimeout(() => syncEntries(this), 50);

      return r;
    };

    const onConfigure = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function (data) {
      const r = onConfigure?.apply(this, arguments);
      setTimeout(() => {
        fixTextSocket(this);
        bindCountWidget(this);
        syncEntries(this);
      }, 20);
      return r;
    };

    const onWidgetChanged = nodeType.prototype.onWidgetChanged;
    nodeType.prototype.onWidgetChanged = function (name, value, ...rest) {
      const r = onWidgetChanged?.apply(this, [name, value, ...rest]);
      if (name === "entrycount") {
        syncEntries(this);
        requestAnimationFrame(() => syncEntries(this));
      }
      return r;
    };

    // When a new link connects to text, replace any previous link (single connection)
    const onConnectionsChange = nodeType.prototype.onConnectionsChange;
    nodeType.prototype.onConnectionsChange = function (
      type,
      index,
      connected,
      link_info,
      ...rest
    ) {
      const r = onConnectionsChange?.apply(this, [
        type,
        index,
        connected,
        link_info,
        ...rest,
      ]);
      // type 1 = input
      if (type === 1 && this.inputs?.[index]?.name === "text" && connected) {
        const inp = this.inputs[index];
        // LiteGraph usually replaces; if two links somehow exist, drop older
        if (inp && inp.link != null && link_info && app.graph) {
          // ensure only this link
          inp.link = link_info.id ?? link_info;
        }
      }
      fixTextSocket(this);
      return r;
    };
  },
});
