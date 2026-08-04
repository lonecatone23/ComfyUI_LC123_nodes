/**
 * LC Combo Selector — remote dropdown for a target node’s combo
 * -------------------------------------------------------------
 * Reads options from the connected target (scheduler, etc.).
 * Rebuilds a real combo widget so the dropdown is actually usable.
 */

import { app } from "../../scripts/app.js";

const CLASSES = new Set(["LCComboSelector"]);

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

/**
 * Replace the `value` widget with a real combo (or text if no options).
 * Mutating type in-place often does not refresh the UI in modern Comfy.
 */
function setValueWidget(node, options) {
  if (!node.widgets) node.widgets = [];

  const idx = node.widgets.findIndex((w) => w.name === "value");
  const prev =
    idx >= 0 && node.widgets[idx].value != null
      ? String(node.widgets[idx].value)
      : "";

  // Remove existing value widget(s)
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
    // Ensure graph serialization picks it up
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

  // Resize for widget list
  try {
    const size = node.computeSize?.();
    if (size) node.setSize(size);
  } catch (_) {}
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
      return;
    }
    matchOutputType(node, target.input);
    // Only rebuild widget when the list actually changes
    if (!sameOptions(node._lcOptions, target.options)) {
      setValueWidget(node, target.options || null);
    } else if (target.options?.length) {
      node._lcStatus = `${target.options.length} options`;
    }
  } catch (e) {
    console.warn("[LC Combo Selector] refresh", e);
  }
}

app.registerExtension({
  name: "LC123.Combo",

  async beforeRegisterNodeDef(nodeType, nodeData) {
    const name = nodeData?.name || "";
    if (!CLASSES.has(name)) return;

    // Allow connect to any input type
    nodeType.prototype.onConnectOutput = function () {
      return true;
    };

    const onCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const r = onCreated?.apply(this, arguments);
      this._lcOptions = null;
      this._lcStatus = "not connected";
      if (this.outputs?.[0]) {
        this.outputs[0].type = "*";
        this.outputs[0].name = "value";
      }
      setTimeout(() => refresh(this), 40);
      return r;
    };

    const onConfigure = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function () {
      const r = onConfigure?.apply(this, arguments);
      if (this.outputs?.[0]) this.outputs[0].type = "*";
      setTimeout(() => refresh(this), 60);
      setTimeout(() => refresh(this), 300);
      return r;
    };

    const onConnectionsChange = nodeType.prototype.onConnectionsChange;
    nodeType.prototype.onConnectionsChange = function () {
      const r = onConnectionsChange?.apply(this, arguments);
      setTimeout(() => refresh(this), 15);
      setTimeout(() => refresh(this), 120);
      return r;
    };

    const onDrawFG = nodeType.prototype.onDrawForeground;
    nodeType.prototype.onDrawForeground = function (ctx) {
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

// * connects to anything
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

console.log("[LC123.Combo] combo widget rebuild enabled");
