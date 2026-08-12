/**
 * LC Combo Selector — remote dropdown for a target node’s combo
 * -------------------------------------------------------------
 * Reads options from the connected target. Rebuilds a real combo widget.
 * Node size is retained across reload, scroll, and option refresh.
 */

import { app } from "../../scripts/app.js";

const CLASSES = new Set(["LCComboSelector"]);
const MIN_W = 200;
const MIN_H = 60;

function normalizeValues(values) {
  if (!Array.isArray(values) || !values.length) return null;
  return values.map((v) => {
    if (v == null) return "";
    if (typeof v === "object") {
      if (v.value != null) return String(v.value);
      if (v.name != null) return String(v.name);
      if (v.label != null) return String(v.label);
    }
    return String(v);
  });
}

function optionsFromWidget(widget) {
  if (!widget) return null;
  const opt = widget.options || {};
  let values =
    opt.values ||
    opt.options ||
    widget.values ||
    widget.comboValues ||
    (Array.isArray(opt) ? opt : null);
  if (!values && typeof widget.getOptions === "function") {
    try {
      values = widget.getOptions();
    } catch (_) {}
  }
  return normalizeValues(values);
}

function optionsFromNodeDef(targetNode, inputName) {
  if (!targetNode || !inputName) return null;

  const trySection = (section) => {
    if (!section?.[inputName]) return null;
    const spec = section[inputName];
    if (!Array.isArray(spec) || !spec.length) return null;
    const first = spec[0];
    if (
      Array.isArray(first) &&
      first.length &&
      (typeof first[0] === "string" || typeof first[0] === "number")
    ) {
      return normalizeValues(first);
    }
    return null;
  };

  const data =
    targetNode.constructor?.nodeData || targetNode.nodeData || null;
  if (data?.input) {
    const a = trySection(data.input.required);
    if (a) return a;
    const b = trySection(data.input.optional);
    if (b) return b;
  }

  try {
    const reg = LiteGraph?.registered_node_types?.[targetNode.type];
    const rd = reg?.nodeData;
    if (rd?.input) {
      const a = trySection(rd.input.required);
      if (a) return a;
      const b = trySection(rd.input.optional);
      if (b) return b;
    }
  } catch (_) {}

  return null;
}

function targetInputName(targetNode, slot) {
  const inp = targetNode?.inputs?.[slot];
  if (!inp) return null;
  return inp.widget?.name || inp.widgetName || inp.name || null;
}

function findTargetWidget(targetNode, slot) {
  const name = targetInputName(targetNode, slot);
  if (name && targetNode.widgets) {
    const w = targetNode.widgets.find((x) => x.name === name);
    if (w) return w;
  }
  for (const w of targetNode.widgets || []) {
    if (optionsFromWidget(w)) return w;
  }
  return null;
}

function firstTarget(node) {
  const out = node.outputs?.[0];
  if (!out?.links?.length) return null;

  for (const linkId of out.links) {
    const link = app.graph?.links?.[linkId];
    if (!link) continue;
    const tNode = app.graph.getNodeById?.(link.target_id);
    if (!tNode) continue;
    const slot = link.target_slot;
    const inp = tNode.inputs?.[slot];
    const inputName = targetInputName(tNode, slot);

    let opts = optionsFromWidget(findTargetWidget(tNode, slot));
    if (!opts?.length) opts = optionsFromNodeDef(tNode, inputName);

    if (!opts?.length && tNode.constructor?.nodeData?.input) {
      for (const key of ["required", "optional"]) {
        const section = tNode.constructor.nodeData.input[key];
        if (!section) continue;
        for (const [k, spec] of Object.entries(section)) {
          if (inputName && k !== inputName) continue;
          if (Array.isArray(spec?.[0]) && typeof spec[0][0] === "string") {
            opts = normalizeValues(spec[0]);
            break;
          }
        }
        if (opts?.length) break;
      }
    }

    return { node: tNode, slot, input: inp, inputName, options: opts };
  }
  return null;
}

function matchOutputType(node, targetInput) {
  if (!node.outputs?.length) return;
  const out = node.outputs[0];
  if (!targetInput) {
    out.type = "*";
    out.name = "value";
    out.label = "value";
    return;
  }
  const t = targetInput.type;
  if (typeof t === "string" && t && t !== "STRING") {
    out.type = t;
    out.label = t;
  } else {
    out.type = "*";
    out.label = "value";
  }
}

function rememberSize(node) {
  if (!node.properties) node.properties = {};
  if (node.size?.[0]) node.properties.lc_combo_w = node.size[0];
  if (node.size?.[1]) node.properties.lc_combo_h = node.size[1];
}

function restoreSize(node) {
  if (!node.properties) node.properties = {};
  const w = Number(node.properties.lc_combo_w) || node.size?.[0] || MIN_W;
  const h = Number(node.properties.lc_combo_h) || node.size?.[1] || MIN_H;
  const nw = Math.max(MIN_W, w);
  const nh = Math.max(MIN_H, h);
  if (typeof node.setSize === "function") {
    node.setSize([nw, nh]);
  } else if (node.size) {
    node.size[0] = nw;
    node.size[1] = nh;
  }
}

/**
 * Replace the value widget. Does NOT reset node size (preserves user resize).
 */
function setValueWidget(node, options) {
  if (!node.widgets) node.widgets = [];

  const idx = node.widgets.findIndex((w) => w.name === "value");
  const prev =
    idx >= 0 && node.widgets[idx].value != null
      ? String(node.widgets[idx].value)
      : "";

  for (let i = node.widgets.length - 1; i >= 0; i--) {
    if (node.widgets[i]?.name === "value") {
      node.widgets.splice(i, 1);
    }
  }

  if (options?.length) {
    const val = options.includes(prev) ? prev : options[0];
    const w = node.addWidget(
      "combo",
      "value",
      val,
      function (v) {
        this.value = v;
        node.setDirtyCanvas?.(true, true);
      },
      { values: options.slice() }
    );
    w.serialize = true;
    node._lcOptions = options.slice();
    node._lcStatus = `${options.length} options`;
  } else {
    const w = node.addWidget(
      "text",
      "value",
      prev || "",
      function (v) {
        this.value = v;
      },
      {}
    );
    w.serialize = true;
    node._lcOptions = null;
    node._lcStatus = node.outputs?.[0]?.links?.length
      ? "no options found"
      : "not connected";
  }

  // Keep existing size — only grow if the node is still at default tiny height
  restoreSize(node);
  if (node.size && node.size[1] < MIN_H) node.size[1] = MIN_H;
  node.setDirtyCanvas?.(true, true);
}

function sameOptions(a, b) {
  if (!a && !b) return true;
  if (!a || !b || a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) {
    if (a[i] !== b[i]) return false;
  }
  return true;
}

function refresh(node) {
  try {
    const target = firstTarget(node);
    if (!target) {
      matchOutputType(node, null);
      if (node._lcOptions) setValueWidget(node, null);
      else {
        node._lcStatus = "not connected";
        node.setDirtyCanvas?.(true, true);
      }
      restoreSize(node);
      return;
    }
    matchOutputType(node, target.input);
    if (!sameOptions(node._lcOptions, target.options)) {
      setValueWidget(node, target.options || null);
    } else if (target.options?.length) {
      node._lcStatus = `${target.options.length} options`;
    }
    restoreSize(node);
  } catch (e) {
    console.warn("[LC Combo Selector] refresh", e);
  }
}

app.registerExtension({
  name: "LC123.Combo",

  async beforeRegisterNodeDef(nodeType, nodeData) {
    const name = nodeData?.name || "";
    if (!CLASSES.has(name)) return;

    nodeType.prototype.onConnectOutput = function () {
      return true;
    };

    const onCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const r = onCreated?.apply(this, arguments);
      this.color = "#28281E";
      this.bgcolor = "#28281E";
      this._lcOptions = null;
      this._lcStatus = "not connected";
      if (!this.properties) this.properties = {};
      if (this.outputs?.[0]) {
        this.outputs[0].type = "*";
        this.outputs[0].name = "value";
      }
      restoreSize(this);
      setTimeout(() => refresh(this), 40);
      return r;
    };

    const onConfigure = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function (data) {
      const r = onConfigure?.apply(this, arguments);
      if (!this.properties) this.properties = {};
      if (data?.size?.[0]) this.properties.lc_combo_w = data.size[0];
      if (data?.size?.[1]) this.properties.lc_combo_h = data.size[1];
      if (this.outputs?.[0]) this.outputs[0].type = "*";
      setTimeout(() => {
        restoreSize(this);
        refresh(this);
      }, 60);
      setTimeout(() => {
        restoreSize(this);
        refresh(this);
      }, 300);
      return r;
    };

    const onResize = nodeType.prototype.onResize;
    nodeType.prototype.onResize = function (size) {
      const r = onResize?.apply(this, arguments);
      rememberSize(this);
      return r;
    };

    const onConnectionsChange = nodeType.prototype.onConnectionsChange;
    nodeType.prototype.onConnectionsChange = function () {
      const r = onConnectionsChange?.apply(this, arguments);
      rememberSize(this);
      setTimeout(() => refresh(this), 15);
      setTimeout(() => refresh(this), 120);
      return r;
    };

    const onDrawFG = nodeType.prototype.onDrawForeground;
    nodeType.prototype.onDrawForeground = function (ctx) {
      // Re-assert size if something collapsed it (scroll / layout pass)
      if (
        this.properties?.lc_combo_w &&
        this.size &&
        (Math.abs(this.size[0] - this.properties.lc_combo_w) > 2 ||
          Math.abs(this.size[1] - this.properties.lc_combo_h) > 2)
      ) {
        // Only restore if we shrank — allow intentional growth
        if (
          this.size[0] < this.properties.lc_combo_w - 2 ||
          this.size[1] < this.properties.lc_combo_h - 2
        ) {
          restoreSize(this);
        }
      }

      const r = onDrawFG?.apply(this, arguments);
      if (this._lcStatus) {
        ctx.save();
        ctx.font = "10px sans-serif";
        ctx.fillStyle = this._lcOptions ? "#8c8" : "#a88";
        ctx.textAlign = "left";
        ctx.fillText(this._lcStatus, 10, this.size[1] - 6);
        ctx.restore();
      }
      if (
        this.outputs?.[0]?.links?.length &&
        !this._lcOptions &&
        (!this._lcRetry || Date.now() - this._lcRetry > 2000)
      ) {
        this._lcRetry = Date.now();
        refresh(this);
      }
      return r;
    };
  },
});

(function () {
  try {
    const orig = LiteGraph.isValidConnection;
    if (typeof orig === "function" && !LiteGraph._lcComboValidPatched) {
      LiteGraph._lcComboValidPatched = true;
      LiteGraph.isValidConnection = function (a, b) {
        if (a === "*" || b === "*") return true;
        return orig.apply(this, arguments);
      };
    }
  } catch (_) {}
})();

console.log("[LC123.Combo] size retention enabled");
