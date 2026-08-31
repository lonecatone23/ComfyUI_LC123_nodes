/**
 * LC Custom Combo — inputcount slots + choice combo
 * Panel stays in sync with hub (options + choice)
 */
import { app } from "../../scripts/app.js";
import { lcApplyLaunchColor } from "./lc_color.js";

const HUB = "LCCustomCombo";
const PANEL = "LCCustomComboPanel";
const COLOR = "#28281E";
const MAX = 20;

function opt(i) {
  return `option_${String(i).padStart(2, "0")}`;
}

function wget(node, name) {
  return (node.widgets || []).find((w) => w && w.name === name);
}

function count(node) {
  const w = wget(node, "inputcount");
  let n = w ? parseInt(w.value, 10) : 2;
  if (Number.isNaN(n)) n = 2;
  return Math.max(2, Math.min(MAX, n));
}

function filled(node) {
  const n = count(node);
  const out = [];
  for (let i = 1; i <= n; i++) {
    const w = wget(node, opt(i));
    const s = w?.value != null ? String(w.value).trim() : "";
    if (s) out.push(s);
  }
  return out;
}

function fitHub(node, force = false) {
  const vis = (node.widgets || []).filter((w) => w && w.type !== "hidden").length;
  if (!node.size) node.size = [270, 100];
  node.size[0] = Math.max(270, node.size[0] || 270);
  if (force || !node._lcUserSized) {
    node.size[1] = 34 + vis * 26 + 24;
  }
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

function showSlots(node, forceFit = false) {
  const n = count(node);
  for (let i = 1; i <= MAX; i++) {
    const w = wget(node, opt(i));
    if (!w) continue;
    if (i <= n) {
      w.type = "text";
      w.hidden = false;
      delete w.computeSize;
    } else {
      w.type = "hidden";
      w.hidden = true;
      w.computeSize = () => [0, 0];
    }
  }
  fitHub(node, forceFit);
}

function makeChoiceCombo(node) {
  const values = filled(node);
  const list = values.length ? values : [""];
  const widgets = node.widgets || [];
  const idx = widgets.findIndex((w) => w?.name === "choice");
  if (idx < 0) return;

  let cur = widgets[idx].value;
  if (!list.includes(cur)) cur = list[0];

  if (widgets[idx].type === "combo") {
    widgets[idx].options = widgets[idx].options || {};
    widgets[idx].options.values = list;
    widgets[idx].value = cur;
    return;
  }

  widgets.splice(idx, 1);
  node.addWidget(
    "combo",
    "choice",
    cur,
    () => {
      app.canvas?.setDirty?.(true, true);
      refreshAllPanels();
    },
    { values: list }
  );
  const last = widgets.pop();
  if (last) {
    last.name = "choice";
    last.options = { values: list };
    last.value = cur;
    widgets.splice(idx, 0, last);
  }
}

function applyDefaultColorOnce(node) {
  lcApplyLaunchColor(node, COLOR);
}

function hookHub(node) {
  applyDefaultColorOnce(node);
  restoreSize(node);

  if (!node._lcHooked) {
    node._lcHooked = true;
    if (!node._lcResizeHooked) {
      node._lcResizeHooked = true;
      const prevR = node.onResize;
      node.onResize = function (size) {
        const o = prevR?.apply(this, arguments);
        rememberSize(this);
        return o;
      };
    }
    const ic = wget(node, "inputcount");
    if (ic) {
      const prev = ic.callback;
      ic.callback = function (v, ...a) {
        const o = prev?.apply(this, [v, ...a]);
        node._lcUserSized = false;
        showSlots(node, true);
        makeChoiceCombo(node);
        refreshAllPanels();
        return o;
      };
    }
    for (let i = 1; i <= MAX; i++) {
      const w = wget(node, opt(i));
      if (!w) continue;
      const prev = w.callback;
      w.callback = function (v, ...a) {
        const o = prev?.apply(this, [v, ...a]);
        makeChoiceCombo(node);
        refreshAllPanels();
        return o;
      };
    }
    // When choice changes on hub, push to panels
    const scheduleChoiceHook = () => {
      const cw = wget(node, "choice");
      if (cw && !cw._lcChoiceHook) {
        cw._lcChoiceHook = true;
        const prev = cw.callback;
        cw.callback = function (v, ...a) {
          const o = prev?.apply(this, [v, ...a]);
          refreshAllPanels();
          return o;
        };
      }
    };
    scheduleChoiceHook();
    setTimeout(scheduleChoiceHook, 100);
  }
  showSlots(node);
  makeChoiceCombo(node);
  node.setDirtyCanvas?.(true, true);
}

function getHub(panel) {
  const inp = (panel.inputs || []).find((i) => i?.name === "hub");
  if (!inp?.link) return null;
  const link = app.graph?.links?.[inp.link];
  const origin = link && app.graph.getNodeById?.(link.origin_id);
  const t = origin?.comfyClass || origin?.type;
  return t === HUB || t === "LC Custom Combo" ? origin : null;
}

function syncPanel(panel) {
  applyDefaultColorOnce(panel);

  const hub = getHub(panel);
  const list = hub ? filled(hub) : [""];
  if (!list.length) list.push("");

  let cw = wget(panel, "choice");
  if (!cw) {
    cw = panel.addWidget(
      "combo",
      "choice",
      list[0],
      (v) => {
        const h = getHub(panel);
        if (!h) return;
        makeChoiceCombo(h);
        const hc = wget(h, "choice");
        if (hc) {
          hc.value = v;
          try {
            hc.callback?.(v);
          } catch (_) {}
        }
        h.setDirtyCanvas?.(true, true);
        app.canvas?.setDirty?.(true, true);
      },
      { values: list }
    );
  }

  cw.type = "combo";
  cw.options = cw.options || {};
  // Always refresh values from hub (dynamic)
  cw.options.values = list.slice();
  const hv = hub && wget(hub, "choice")?.value;
  cw.value = list.includes(hv) ? hv : list[0];

  if (panel.size) {
    panel.size[0] = Math.max(220, panel.size[0] || 220);
    if (!panel._lcUserSized) panel.size[1] = 64;
  }
  if (!panel._lcResizeHooked) {
    panel._lcResizeHooked = true;
    const prevR = panel.onResize;
    panel.onResize = function () {
      const o = prevR?.apply(this, arguments);
      rememberSize(this);
      return o;
    };
  }
  panel.setDirtyCanvas?.(true, true);
  app.canvas?.setDirty?.(true, true);
}

function refreshAllPanels() {
  if (!app.graph?.nodes) return;
  for (const n of app.graph.nodes) {
    const t = n.comfyClass || n.type;
    if (t === PANEL || t === "LC Custom Combo Panel") syncPanel(n);
  }
}

function hookPanel(node) {
  if (!node._lcPanelHooked) {
    node._lcPanelHooked = true;
    const prev = node.onConnectionsChange;
    node.onConnectionsChange = function (...a) {
      const r = prev?.apply(this, a);
      setTimeout(() => syncPanel(this), 0);
      return r;
    };
    // Keep panel live while open: refresh on draw
    const prevDraw = node.onDrawForeground;
    node.onDrawForeground = function (ctx) {
      // Throttle: at most every 300ms
      const now = Date.now();
      if (!this._lcPanelNext || now >= this._lcPanelNext) {
        this._lcPanelNext = now + 300;
        syncPanel(this);
      }
      return prevDraw?.apply(this, arguments);
    };
  }
  queueMicrotask(() => syncPanel(node));
  setTimeout(() => syncPanel(node), 50);
}

app.registerExtension({
  name: "LC123.CustomCombo",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    const name = nodeData?.name || "";
    if (name === HUB) {
      const oc = nodeType.prototype.onNodeCreated;
      nodeType.prototype.onNodeCreated = function () {
        const r = oc?.apply(this, arguments);
        queueMicrotask(() => hookHub(this));
        setTimeout(() => hookHub(this), 50);
        return r;
      };
      const ocfg = nodeType.prototype.onConfigure;
      nodeType.prototype.onConfigure = function (d) {
        const r = ocfg?.apply(this, arguments);
        setTimeout(() => hookHub(this), 30);
        return r;
      };
    }
    if (name === PANEL) {
      const oc = nodeType.prototype.onNodeCreated;
      nodeType.prototype.onNodeCreated = function () {
        const r = oc?.apply(this, arguments);
        hookPanel(this);
        return r;
      };
      const ocfg = nodeType.prototype.onConfigure;
      nodeType.prototype.onConfigure = function (d) {
        const r = ocfg?.apply(this, arguments);
        setTimeout(() => hookPanel(this), 30);
        return r;
      };
    }
  },
  nodeCreated(node) {
    const t = node.comfyClass || node.type;
    if (t === HUB) queueMicrotask(() => hookHub(node));
    if (t === PANEL || t === "LC Custom Combo Panel") hookPanel(node);
  },
});
