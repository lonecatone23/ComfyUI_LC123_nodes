/**
 * LC AnySwitch — frontend companion
 * ---------------------------------
 * 1. Dynamic input count (inputcount widget)
 * 2. Blocks cg-use-everywhere from auto-wiring into any_* inputs
 * 3. Type lock: first connection sets the type for ALL sockets + output.
 * 4. Compact default size (2 inputs ≈ 118px tall, width 270)
 *
 * Install: ComfyUI_LC123_nodes/web/lc_any_switch.js
 */

import { app } from "../../scripts/app.js";

const NODE_CLASS = "LCAnySwitch";
const MAX_INPUTS = 20;
const MIN_INPUTS = 2;
const DEFAULT_WIDTH = 270;

function inputName(i) {
  return `any_${String(i).padStart(2, "0")}`;
}

function ensureUeBlock(node) {
  if (!node.properties) node.properties = {};
  if (!node.properties.ue_properties) {
    node.properties.ue_properties = {};
  }
  const ue = node.properties.ue_properties;

  if (!ue.input_ue_unconnectable || typeof ue.input_ue_unconnectable !== "object") {
    ue.input_ue_unconnectable = {};
  }
  for (let i = 1; i <= MAX_INPUTS; i++) {
    ue.input_ue_unconnectable[inputName(i)] = true;
  }

  if (!ue.widget_ue_connectable) ue.widget_ue_connectable = {};
  ue.send_to_any = 0;
  ue.apply_to_unrepeated = 0;
}

/** Compact height: title + widgets + visible input slots only. */
function fitSize(node) {
  const slots = (node.inputs || []).length;
  const widgets = (node.widgets || []).filter(
    (w) => w && w.type !== "hidden" && w.computeSize?.(node.size?.[0] || DEFAULT_WIDTH)?.[1] !== 0
  ).length;
  // ~30 title, ~28 per widget, ~24 per input row, small bottom pad
  const h = Math.max(60, 34 + widgets * 28 + slots * 24 + 8);
  const w = Math.max(DEFAULT_WIDTH, node.size?.[0] || DEFAULT_WIDTH);
  if (typeof node.setSize === "function") {
    node.setSize([w, h]);
  } else if (node.size) {
    node.size[0] = w;
    node.size[1] = h;
  }
}

function typeOfInput(node, inp) {
  if (!inp || inp.link == null) return null;
  const link = app.graph?.links?.[inp.link];
  if (!link) return null;
  const origin = app.graph.getNodeById?.(link.origin_id);
  const out = origin?.outputs?.[link.origin_slot];
  return out?.type || null;
}

function hasAnyConnection(node) {
  for (const inp of node.inputs || []) {
    if (inp?.link != null && app.graph?.links?.[inp.link]) return true;
  }
  return false;
}

function resolveLockedType(node) {
  for (const inp of node.inputs || []) {
    const t = typeOfInput(node, inp);
    if (t) return t;
  }
  return null;
}

function applyTypeLock(node, type) {
  const t = type || "*";
  node._lcLockedType = type;

  for (const inp of node.inputs || []) {
    if (!inp) continue;
    if (inp.link != null) {
      const live = typeOfInput(node, inp);
      inp.type = live || t;
      inp.label = live || (t === "*" ? null : t);
    } else {
      inp.type = t;
      inp.label = t === "*" ? null : t;
    }
  }

  if (node.outputs?.length) {
    node.outputs[0].type = t;
    node.outputs[0].name = t === "*" ? "*" : t;
    node.outputs[0].label = t === "*" ? "*" : t;
  }

  node.setDirtyCanvas?.(true, true);
}

function refreshTypeLock(node) {
  if (!hasAnyConnection(node)) {
    applyTypeLock(node, null);
    return;
  }
  const locked = resolveLockedType(node);
  if (locked) applyTypeLock(node, locked);
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

  const locked = node._lcLockedType || null;
  const slotType = locked || "*";

  const next = [];
  for (let i = 1; i <= count; i++) {
    const name = inputName(i);
    if (byName.has(name)) {
      const inp = byName.get(name);
      if (inp.link == null) {
        inp.type = slotType;
        inp.label = slotType === "*" ? null : slotType;
      }
      // optional shape
      if (inp.shape == null) inp.shape = 7;
      next.push(inp);
    } else {
      next.push({
        name,
        type: slotType,
        label: slotType === "*" ? null : slotType,
        link: null,
        shape: 7,
      });
    }
  }

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
  ensureUeBlock(node);
  refreshTypeLock(node);
  fitSize(node);
  node.setDirtyCanvas?.(true, true);
}

app.registerExtension({
  name: "LC123.AnySwitch",

  async beforeRegisterNodeDef(nodeType, nodeData) {
    if ((nodeData?.name || "") !== NODE_CLASS) return;

    // Prefer a compact size before first layout
    const origCompute = nodeType.prototype.computeSize;
    nodeType.prototype.computeSize = function (out) {
      const slots = (this.inputs || []).length || MIN_INPUTS;
      const widgets = (this.widgets || []).filter(
        (w) => w && w.type !== "hidden"
      ).length;
      const h = Math.max(60, 34 + widgets * 28 + slots * 24 + 8);
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

      this._lcLockedType = null;
      ensureUeBlock(this);

      // Strip the 20 server-defined optional slots down to inputcount immediately
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

      // Second pass after Comfy finishes widget/input setup
      setTimeout(() => {
        ensureUeBlock(this);
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
        ensureUeBlock(this);
        syncInputs(this);
        fitSize(this);
      }, 20);
      return r;
    };

    const onConnectionsChange = nodeType.prototype.onConnectionsChange;
    nodeType.prototype.onConnectionsChange = function (
      type,
      index,
      connected
    ) {
      if (type === 1) {
        if (connected && this.inputs?.[index]) {
          const incoming = typeOfInput(this, this.inputs[index]);
          if (
            this._lcLockedType &&
            incoming &&
            incoming !== this._lcLockedType &&
            this._lcLockedType !== "*"
          ) {
            const linkId = this.inputs[index].link;
            if (linkId != null && app.graph) {
              try {
                app.graph.removeLink(linkId);
              } catch (_) {}
              this.inputs[index].link = null;
              this.inputs[index].type = this._lcLockedType;
              this.inputs[index].label = this._lcLockedType;
              this.setDirtyCanvas?.(true, true);
              return;
            }
          }
        }
      }

      const r = onConnectionsChange?.apply(this, arguments);

      setTimeout(() => {
        refreshTypeLock(this);
        ensureUeBlock(this);
        fitSize(this);
      }, 0);

      return r;
    };

    const onDrawFG = nodeType.prototype.onDrawForeground;
    nodeType.prototype.onDrawForeground = function (ctx) {
      if (!this._lcUeChecked || Date.now() - this._lcUeChecked > 2000) {
        this._lcUeChecked = Date.now();
        ensureUeBlock(this);
      }
      return onDrawFG?.apply(this, arguments);
    };
  },

  async setup() {
    const reblock = () => {
      const graph = app.graph;
      if (!graph?._nodes) return;
      for (const n of graph._nodes) {
        if (n.type === NODE_CLASS || n.comfyClass === NODE_CLASS) {
          ensureUeBlock(n);
        }
      }
    };
    setTimeout(reblock, 500);
    setTimeout(reblock, 2000);
    setInterval(reblock, 5000);
  },
});

console.log("[LC123.AnySwitch] compact size + type-lock + UE block");
