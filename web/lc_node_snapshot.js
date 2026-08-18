/**
 * LC Node Snapshot 📋
 * source link (preferred) OR target title / id → read that node's widgets.
 */
import { app } from "../../scripts/app.js";

const TYPE = "LCNodeSnapshot";

function widgetByName(node, name) {
  return (node.widgets || []).find((w) => w.name === name);
}

function allGraphNodes() {
  const g = app.graph;
  if (!g) return [];
  if (Array.isArray(g._nodes)) return g._nodes;
  if (Array.isArray(g.nodes)) return g.nodes;
  return [];
}

function findTargetFromSource(node) {
  if (!node.inputs) return null;
  const inp = node.inputs.find((i) => i.name === "source");
  if (!inp || inp.link == null) return null;
  const link = app.graph?.links?.[inp.link];
  if (!link) return null;
  const originId = link.origin_id;
  return (
    app.graph?.getNodeById?.(originId) ||
    allGraphNodes().find((n) => n.id == originId) ||
    null
  );
}

/**
 * Resolve target text: numeric id OR node title OR type name.
 * Uses loose id match (string/number). Does not invent nodes.
 */
function findTargetByQuery(query) {
  if (query === undefined || query === null) return null;
  const q = String(query).trim();
  if (!q) return null;

  const nodes = allGraphNodes();
  const g = app.graph;

  // --- numeric id ---
  if (/^\d+$/.test(q)) {
    const idNum = parseInt(q, 10);
    let node =
      g?.getNodeById?.(idNum) ||
      g?.getNodeById?.(q) ||
      null;
    if (!node && g?._nodes_by_id) {
      node = g._nodes_by_id[idNum] || g._nodes_by_id[q] || null;
    }
    if (!node) {
      node = nodes.find((n) => n.id == idNum || String(n.id) === q) || null;
    }
    return node;
  }

  // --- exact title ---
  let hit = nodes.find((n) => (n.title || "") === q);
  if (hit) return hit;

  // --- exact type / class ---
  hit = nodes.find((n) => n.type === q || n.comfyClass === q);
  if (hit) return hit;

  // --- case-insensitive title ---
  const lower = q.toLowerCase();
  hit = nodes.find((n) => (n.title || "").toLowerCase() === lower);
  if (hit) return hit;

  // --- unique title substring ---
  const partial = nodes.filter((n) =>
    (n.title || "").toLowerCase().includes(lower)
  );
  if (partial.length === 1) return partial[0];

  return null;
}

function resolveTarget(node) {
  const fromSource = findTargetFromSource(node);
  if (fromSource) return { node: fromSource, via: "source" };
  const q = widgetByName(node, "target")?.value;
  const fromQuery = findTargetByQuery(q);
  if (fromQuery) return { node: fromQuery, via: "target", query: String(q ?? "").trim() };
  return {
    node: null,
    via: "target",
    query: String(q ?? "").trim(),
  };
}

function listParamWidgetNames(target) {
  if (!target || !Array.isArray(target.widgets)) return [];
  const skip = new Set([
    "target",
    "widget_name",
    "selected_value",
    "lines_dump",
    "json_dump",
    "source",
  ]);
  const names = [];
  const seen = new Set();
  for (const w of target.widgets) {
    if (!w) continue;
    const name = w.name != null ? String(w.name) : "";
    if (!name || skip.has(name) || seen.has(name)) continue;
    if (w.type === "button") continue;
    seen.add(name);
    names.push(name);
  }
  return names;
}

function collectWidgets(target) {
  const out = {};
  if (!target || !Array.isArray(target.widgets)) return out;
  const skip = new Set(["selected_value", "lines_dump", "json_dump"]);
  target.widgets.forEach((w, i) => {
    if (!w || !w.name || w.type === "button") return;
    if (skip.has(w.name)) return;
    let val = w.value;
    if (
      (val === undefined || val === null) &&
      Array.isArray(target.widgets_values) &&
      i < target.widgets_values.length
    ) {
      val = target.widgets_values[i];
    }
    out[String(w.name)] = val;
  });
  return out;
}

function buildDumps(target) {
  const node_id = target?.id ?? null;
  const node_type = target?.comfyClass || target?.type || null;
  const node_title = target?.title || "";
  const widgets = collectWidgets(target);
  const lines = [
    `node_id: ${node_id ?? ""}`,
    `node_type: ${node_type ?? ""}`,
    `node_title: ${node_title}`,
  ];
  for (const [k, v] of Object.entries(widgets)) {
    let val = v;
    if (val !== null && typeof val === "object") {
      try {
        val = JSON.stringify(val);
      } catch (_) {
        val = String(val);
      }
    }
    lines.push(`${k}: ${val}`);
  }
  return {
    lines: lines.join("\n"),
    json: JSON.stringify({ node_id, node_type, node_title, widgets }, null, 2),
    widgets,
    names: Object.keys(widgets),
  };
}

function isComboType(t) {
  return t === "combo" || t === "COMBO" || t === "combobox";
}

function ensureNameCombo(node, names) {
  const opts = names.map((n) => String(n));
  if (!opts.length) opts.push("");

  let w = widgetByName(node, "widget_name");
  let prefer = node._lcSnapWidgetName;
  if (w && w.value && opts.includes(String(w.value))) {
    prefer = String(w.value);
  }
  if (prefer && !opts.includes(prefer)) prefer = null;
  const nextVal = prefer || opts[0] || "";
  node._lcSnapWidgetName = nextVal;

  const onChange = function (v) {
    node._lcSnapWidgetName = v != null ? String(v) : "";
    try {
      refreshSnapshotNode(node);
    } catch (_) {}
  };

  if (w && isComboType(w.type)) {
    w.options = { ...(w.options || {}), values: opts.slice() };
    try {
      w.values = opts.slice();
    } catch (_) {}
    w.value = nextVal;
    w.callback = onChange;
    syncSelectElement(w, opts, nextVal);
    return w;
  }

  if (!w || !node.widgets) return null;
  const idx = node.widgets.indexOf(w);
  if (idx < 0) return null;

  node.widgets.splice(idx, 1);
  const combo = node.addWidget(
    "combo",
    "widget_name",
    nextVal,
    onChange,
    { values: opts.slice() }
  );
  combo.name = "widget_name";
  combo.options = { values: opts.slice() };
  combo.value = nextVal;

  if (node.widgets[node.widgets.length - 1] === combo) {
    node.widgets.pop();
    node.widgets.splice(idx, 0, combo);
  }
  syncSelectElement(combo, opts, nextVal);
  node.setDirtyCanvas?.(true, true);
  return combo;
}

function syncSelectElement(widget, opts, value) {
  const el = widget?.inputEl || widget?.element;
  if (!el || el.tagName !== "SELECT") return;
  const current = String(value ?? "");
  el.innerHTML = "";
  for (const v of opts) {
    const o = document.createElement("option");
    o.value = v;
    o.textContent = v;
    if (v === current) o.selected = true;
    el.appendChild(o);
  }
  el.value = current;
}

function refreshSnapshotNode(node) {
  if (!node || (node.type !== TYPE && node.comfyClass !== TYPE)) return null;

  const resolved = resolveTarget(node);
  const target = resolved.node;
  const names = target ? listParamWidgetNames(target) : [];
  ensureNameCombo(node, names);

  if (!target) {
    const q = resolved.query || "";
    const err =
      q.length > 0
        ? `error: no node matches target "${q}" (use exact title, type, or a real node id)`
        : `error: set target title/id or connect source`;
    const lines = [
      `node_id: `,
      `node_type: `,
      `node_title: `,
      err,
    ].join("\n");
    return {
      selected_value: "",
      lines_dump: lines,
      json_dump: JSON.stringify(
        {
          node_id: null,
          node_type: null,
          node_title: "",
          widgets: {},
          error: err,
        },
        null,
        2
      ),
    };
  }

  const dumps = buildDumps(target);
  let key = String(node._lcSnapWidgetName || widgetByName(node, "widget_name")?.value || "");
  if (key && !(key in dumps.widgets)) {
    key = names.includes(key) ? key : "";
  }
  let selected = "";
  if (key && Object.prototype.hasOwnProperty.call(dumps.widgets, key)) {
    const v = dumps.widgets[key];
    selected =
      v !== null && typeof v === "object" ? JSON.stringify(v) : String(v ?? "");
  }
  return {
    selected_value: selected,
    lines_dump: dumps.lines,
    json_dump: dumps.json,
  };
}

function injectIntoPrompt(prompt) {
  if (!prompt || !prompt.output) return;
  for (const node of allGraphNodes()) {
    if (node.type !== TYPE && node.comfyClass !== TYPE) continue;
    const payload = refreshSnapshotNode(node);
    if (!payload) continue;
    const id = String(node.id);
    const entry = prompt.output[id];
    if (!entry) continue;
    entry.inputs = entry.inputs || {};
    entry.inputs.selected_value = payload.selected_value;
    entry.inputs.lines_dump = payload.lines_dump;
    entry.inputs.json_dump = payload.json_dump;
    entry.inputs.widget_name =
      node._lcSnapWidgetName || widgetByName(node, "widget_name")?.value || "";
  }
}

const UTILITY_W = 270;
const PAYLOAD = new Set(["selected_value", "lines_dump", "json_dump"]);

function hidePayloadWidgets(node) {
  if (!node.widgets) return;
  // Remove payload widgets from the array so they take no layout space
  for (let i = node.widgets.length - 1; i >= 0; i--) {
    const w = node.widgets[i];
    if (!w || !PAYLOAD.has(w.name)) continue;
    w.computeSize = () => [0, -4];
    w.draw = () => {};
    try {
      w.type = "converted-widget";
    } catch (_) {}
    // Keep object for any serializers, but exclude from visible layout height
    node.widgets.splice(i, 1);
  }
}

/** Fit height to visible widgets + standard padding (utility width). */
function trimNodeSize(node) {
  hidePayloadWidgets(node);
  try {
    node.size = node.size || [UTILITY_W, 120];
    node.size[0] = UTILITY_W;
    // Let LiteGraph compute from widgets, then clamp excess empty space
    if (typeof node.computeSize === "function") {
      const computed = node.computeSize(UTILITY_W);
      if (Array.isArray(computed) && computed[1] > 0) {
        node.size[1] = computed[1];
      }
    } else {
      const nVis = (node.widgets || []).filter(
        (w) => w && w.type !== "converted-widget" && !PAYLOAD.has(w.name)
      ).length;
      // title + slots + widgets + padding
      const slotH = Math.max((node.inputs?.length || 0), (node.outputs?.length || 0)) * 20;
      node.size[1] = Math.max(80, 40 + slotH + nVis * 28 + 16);
    }
    node.setDirtyCanvas?.(true, true);
  } catch (_) {}
}

function scheduleRefresh(node) {
  const run = () => {
    try {
      refreshSnapshotNode(node);
      trimNodeSize(node);
    } catch (e) {
      console.warn("[LC Node Snapshot] refresh", e);
    }
  };
  run();
  setTimeout(run, 40);
  setTimeout(run, 200);
}

function hookRefresh(node) {
  if (node._lcSnapHooks) return;
  node._lcSnapHooks = true;

  const targetW = widgetByName(node, "target");
  if (targetW && !targetW._lcSnapHooked) {
    targetW._lcSnapHooked = true;
    const prev = targetW.callback;
    // Debounce typing in target field
    let t = null;
    targetW.callback = function (v, ...rest) {
      if (t) clearTimeout(t);
      t = setTimeout(() => scheduleRefresh(node), 100);
      if (typeof prev === "function") return prev.apply(this, [v, ...rest]);
    };
  }

  const onConnections = node.onConnectionsChange;
  node.onConnectionsChange = function () {
    const r = onConnections?.apply(this, arguments);
    scheduleRefresh(node);
    return r;
  };

  const onCfg = node.onConfigure;
  node.onConfigure = function () {
    const r = onCfg?.apply(this, arguments);
    scheduleRefresh(node);
    return r;
  };
}

app.registerExtension({
  name: "LC123.NodeSnapshot",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData?.name !== TYPE) return;
    const onNodeCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const r = onNodeCreated?.apply(this, arguments);
      try {
        this.bgcolor = "#28281E";
        this.color = "#28281E";
      } catch (_) {}
      trimNodeSize(this);
      hidePayloadWidgets(this);
      hookRefresh(this);
      scheduleRefresh(this);
      setTimeout(() => trimNodeSize(this), 0);
      setTimeout(() => trimNodeSize(this), 50);
      return r;
    };
  },
  nodeCreated(node) {
    if (node.comfyClass !== TYPE && node.type !== TYPE) return;
    trimNodeSize(node);
    hidePayloadWidgets(node);
    hookRefresh(node);
    scheduleRefresh(node);
    setTimeout(() => trimNodeSize(node), 0);
    setTimeout(() => trimNodeSize(node), 50);
  },
  async setup() {
    if (app.graphToPrompt && !app._lcSnapPromptHooked) {
      app._lcSnapPromptHooked = true;
      const orig = app.graphToPrompt.bind(app);
      app.graphToPrompt = async function (...args) {
        const prompt = await orig(...args);
        try {
          injectIntoPrompt(prompt);
        } catch (e) {
          console.warn("[LC Node Snapshot] inject failed", e);
        }
        return prompt;
      };
    }
  },
});
