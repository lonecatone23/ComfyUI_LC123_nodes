/**
 * LC AnySwitch — first-connected-wins, dynamic slots.
 * Manual node size is remembered (properties.lc_w / lc_h) and not overwritten.
 */
import { app } from "../../scripts/app.js";

const NODE_CLASS = "LCAnySwitch";
const MAX_INPUTS = 20;
const MIN_INPUTS = 2;
const DEFAULT_WIDTH = 270;
const COLOR = "#28281E";

function inputName(i) {
  return `any_${String(i).padStart(2, "0")}`;
}

function ensureUeBlock(node) {
  if (!node.properties) node.properties = {};
  if (!node.properties.ue_properties) node.properties.ue_properties = {};
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
  const slots = (node.inputs || []).length || MIN_INPUTS;
  const widgets = (node.widgets || []).filter((w) => w && w.type !== "hidden").length;
  return Math.max(60, 34 + widgets * 26 + slots * 22 + 10);
}

/** Only auto-size when force=true (e.g. inputcount change) or never user-sized. */
function fitSize(node, force = false) {
  if (node._lcUserSized && !force) {
    // Still allow width floor
    if (node.size && node.size[0] < DEFAULT_WIDTH) node.size[0] = DEFAULT_WIDTH;
    return;
  }
  const h = desiredHeight(node);
  const w = Math.max(DEFAULT_WIDTH, node.size?.[0] || DEFAULT_WIDTH);
  if (typeof node.setSize === "function") node.setSize([w, h]);
  else if (node.size) {
    node.size[0] = w;
    node.size[1] = h;
  } else {
    node.size = [w, h];
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

function syncInputs(node, { fit = false } = {}) {
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
  if (fit) fitSize(node, true);
  else fitSize(node, false);
  node.setDirtyCanvas?.(true, true);
}

app.registerExtension({
  name: "LC123.AnySwitch",

  async beforeRegisterNodeDef(nodeType, nodeData) {
    if ((nodeData?.name || "") !== NODE_CLASS) return;

    const origCompute = nodeType.prototype.computeSize;
    nodeType.prototype.computeSize = function (out) {
      // Honor saved user size when present
      if (this._lcUserSized && this.properties?.lc_w && this.properties?.lc_h) {
        const size = [this.properties.lc_w, this.properties.lc_h];
        if (out) {
          out[0] = size[0];
          out[1] = size[1];
          return out;
        }
        return size;
      }
      const slots = (this.inputs || []).length || MIN_INPUTS;
      const widgets = (this.widgets || []).filter((w) => w && w.type !== "hidden").length;
      const h = Math.max(60, 34 + widgets * 26 + slots * 22 + 10);
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
      try {
        this.color = COLOR;
        this.bgcolor = COLOR;
      } catch (_) {}
      this._lcLockedType = null;
      ensureUeBlock(this);
      syncInputs(this, { fit: !restoreSize(this) });

      const w = (this.widgets || []).find((x) => x.name === "inputcount");
      if (w && !w._lcBound) {
        w._lcBound = true;
        const prev = w.callback;
        w.callback = (v, ...args) => {
          const out = prev?.apply(w, [v, ...args]);
          this._lcUserSized = false; // allow reflow for new slot count
          syncInputs(this, { fit: true });
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
        ensureUeBlock(this);
        syncInputs(this, { fit: false });
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
        ensureUeBlock(this);
        syncInputs(this, { fit: false });
        restoreSize(this);
      }, 20);
      return r;
    };

    const onConnectionsChange = nodeType.prototype.onConnectionsChange;
    nodeType.prototype.onConnectionsChange = function (type, index, connected) {
      if (type === 1 && connected && this.inputs?.[index]) {
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
      const r = onConnectionsChange?.apply(this, arguments);
      setTimeout(() => {
        refreshTypeLock(this);
        ensureUeBlock(this);
        fitSize(this, false); // do not override user size
      }, 0);
      return r;
    };
  },
});
