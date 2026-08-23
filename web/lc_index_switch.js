/**
 * LC Any Index Switch — dynamic slots; manual size retained.
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

function desiredHeight(node) {
  const nW = (node.widgets || []).filter((x) => x && x.type !== "hidden").length;
  const nI = (node.inputs || []).length;
  return 28 + nW * 24 + nI * 20 + 8;
}

function applySize(node, force = false) {
  if (!node.size) node.size = [W, desiredHeight(node)];
  node.size[0] = Math.max(W, node.size[0] || W);
  if (force || !node._lcUserSized) {
    node.size[1] = desiredHeight(node);
  }
}

function syncSlots(node, { forceFit = false } = {}) {
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

  applySize(node, forceFit);
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
      if (!restoreSize(this)) {
        this._lcUserSized = false;
        syncSlots(this, { forceFit: true });
      } else {
        syncSlots(this, { forceFit: false });
      }

      const w = (this.widgets || []).find((x) => x.name === "inputcount");
      if (w && !w._lcBound) {
        w._lcBound = true;
        const prev = w.callback;
        w.callback = (v, ...a) => {
          const out = prev?.apply(w, [v, ...a]);
          this._lcUserSized = false;
          syncSlots(this, { forceFit: true });
          return out;
        };
      }

      const prevResize = this.onResize;
      this.onResize = function (size) {
        const out = prevResize?.apply(this, arguments);
        rememberSize(this);
        return out;
      };

      setTimeout(() => {
        syncSlots(this, { forceFit: false });
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
        syncSlots(this, { forceFit: false });
        restoreSize(this);
      }, 20);
      return r;
    };

    const onConn = nodeType.prototype.onConnectionsChange;
    nodeType.prototype.onConnectionsChange = function (...args) {
      const r = onConn?.apply(this, args);
      setTimeout(() => syncSlots(this, { forceFit: false }), 0);
      return r;
    };
  },
});
