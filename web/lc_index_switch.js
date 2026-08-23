/**
 * LC Any Index Switch — dynamic slots, tight size, size remembered
 */
import { app } from "../../scripts/app.js";

const NODE_CLASS = "LCIndexSwitch";
const MAX = 20;
const MIN = 2;
const COLOR = "#28281E";
const W = 270;

function slotName(i) {
  return `any_${String(i).padStart(2, "0")}`;
}

function typeOf(node, inp) {
  if (!inp?.link) return null;
  const link = app.graph?.links?.[inp.link];
  if (!link) return null;
  const origin = app.graph.getNodeById?.(link.origin_id);
  return origin?.outputs?.[link.origin_slot]?.type || null;
}

function desiredHeight(node) {
  const nW = (node.widgets || []).filter((x) => x && x.type !== "hidden").length;
  const nI = (node.inputs || []).length;
  // tight: title ~28, ~24/widget, ~20/input, small pad
  return 28 + nW * 24 + nI * 20 + 8;
}

function applySize(node, forceHeight) {
  if (!node.size) return;
  node.size[0] = Math.max(W, node.size[0] || W);
  if (forceHeight || !node._lcUserSized) {
    node.size[1] = desiredHeight(node);
  }
  // Persist
  if (!node.properties) node.properties = {};
  node.properties.lc_size_w = node.size[0];
  node.properties.lc_size_h = node.size[1];
}

function syncSlots(node) {
  const w = (node.widgets || []).find((x) => x.name === "inputcount");
  let count = w ? parseInt(w.value, 10) : MIN;
  if (Number.isNaN(count)) count = MIN;
  count = Math.max(MIN, Math.min(MAX, count));

  const byName = new Map();
  for (const inp of node.inputs || []) {
    if (inp?.name) byName.set(inp.name, inp);
  }

  const preserved = [];
  for (const inp of node.inputs || []) {
    if (inp?.name && !inp.name.startsWith("any_")) preserved.push(inp);
  }

  const locked = node._lcLockedType || "*";
  const slots = [];
  for (let i = 1; i <= count; i++) {
    const name = slotName(i);
    if (byName.has(name)) {
      const inp = byName.get(name);
      if (!inp.link) {
        inp.type = locked;
        inp.label = locked === "*" ? null : locked;
      }
      slots.push(inp);
    } else {
      slots.push({ name, type: locked, link: null, shape: 7 });
    }
  }

  for (let i = count + 1; i <= MAX; i++) {
    const old = byName.get(slotName(i));
    if (old?.link != null) {
      try {
        app.graph.removeLink(old.link);
      } catch (_) {}
    }
  }

  node.inputs = [...preserved, ...slots];

  for (const inp of node.inputs || []) {
    if (!inp) continue;
    if (inp.name === "index" || inp.name === "inputcount") {
      if (inp.name === "index") {
        inp.type = "INT";
        inp.label = "index";
      }
      continue;
    }
    if (inp.link != null) {
      const live = typeOf(node, inp);
      if (live) {
        node._lcLockedType = live;
        inp.type = live;
        inp.label = live;
      }
    } else if (node._lcLockedType) {
      inp.type = node._lcLockedType;
      inp.label = node._lcLockedType;
    }
  }
  if (node.outputs?.[0]) {
    const t = node._lcLockedType || "*";
    node.outputs[0].type = t;
    node.outputs[0].name = t === "*" ? "*" : t;
  }

  // Only auto-height when inputcount changes, not every connection
  applySize(node, !!node._lcForceFit);
  node._lcForceFit = false;
  node.setDirtyCanvas?.(true, true);
}

app.registerExtension({
  name: "LC123.IndexSwitch",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData?.name !== NODE_CLASS) return;

    const onCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const r = onCreated?.apply(this, arguments);
      this.color = COLOR;
      this.bgcolor = COLOR;
      this._lcLockedType = null;
      this._lcUserSized = false;
      this._lcForceFit = true;
      syncSlots(this);

      const w = (this.widgets || []).find((x) => x.name === "inputcount");
      if (w && !w._lcBound) {
        w._lcBound = true;
        const prev = w.callback;
        w.callback = (v, ...a) => {
          const out = prev?.apply(w, [v, ...a]);
          this._lcForceFit = true; // grow/shrink with slot count
          this._lcUserSized = false;
          syncSlots(this);
          return out;
        };
      }

      // Remember manual resize
      const prevResize = this.onResize;
      this.onResize = function (size) {
        this._lcUserSized = true;
        if (!this.properties) this.properties = {};
        this.properties.lc_size_w = size?.[0] ?? this.size?.[0];
        this.properties.lc_size_h = size?.[1] ?? this.size?.[1];
        return prevResize?.apply(this, arguments);
      };

      setTimeout(() => syncSlots(this), 0);
      return r;
    };

    const onConfigure = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function (data) {
      const r = onConfigure?.apply(this, arguments);
      // Restore saved size after reload
      const pw = this.properties?.lc_size_w;
      const ph = this.properties?.lc_size_h;
      if (pw && ph && this.size) {
        this.size[0] = pw;
        this.size[1] = ph;
        this._lcUserSized = true;
      }
      setTimeout(() => {
        syncSlots(this);
        // Re-apply saved size after slot sync
        if (this._lcUserSized && this.properties?.lc_size_w) {
          this.size[0] = this.properties.lc_size_w;
          this.size[1] = this.properties.lc_size_h;
        }
      }, 20);
      return r;
    };

    const onConn = nodeType.prototype.onConnectionsChange;
    nodeType.prototype.onConnectionsChange = function (...args) {
      const r = onConn?.apply(this, args);
      setTimeout(() => syncSlots(this), 0);
      return r;
    };
  },
});
