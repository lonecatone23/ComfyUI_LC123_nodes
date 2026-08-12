// LC Slider — full DOM face (decimals + INT/FLOAT label work under Nodes 2.0)
import { app } from "../../scripts/app.js";

const NODE_NAMES = new Set(["LCSlider"]);
const HIDE = new Set(["value", "min", "max", "step", "decimals", "snap"]);
const DEFAULTS = { min: 0, max: 100, step: 1, decimals: 0 };

function findWidget(node, name) {
  return (node.widgets || []).find((w) => w && w.name === name);
}

function num(v, fb) {
  const n = Number(v);
  return Number.isFinite(n) ? n : fb;
}

function snapValue(value, lo, hi, step) {
  if (lo > hi) [lo, hi] = [hi, lo];
  const st = step > 0 ? step : 1;
  let v = lo + Math.round((value - lo) / st) * st;
  v = Math.round(v * 1e10) / 1e10;
  if (v < lo) v = lo;
  if (v > hi) v = hi;
  return v;
}

function formatByDecimals(v, decimals) {
  const d = Math.max(0, Math.min(4, Math.floor(Number(decimals) || 0)));
  if (d <= 0) return String(Math.round(Number(v)));
  return Number(v).toFixed(d);
}

function ensureProps(node) {
  node.properties = node.properties || {};
  for (const [k, v] of Object.entries(DEFAULTS)) {
    if (node.properties[k] === undefined || node.properties[k] === null) {
      const w = findWidget(node, k);
      node.properties[k] =
        w !== undefined && w.value !== undefined && w.value !== null ? w.value : v;
    }
  }
  if ("snap" in node.properties) delete node.properties.snap;
}

function hideBackendWidgets(node) {
  for (const w of node.widgets || []) {
    if (!w || !HIDE.has(w.name)) continue;
    if (w.name === "lc123_settings" || w.name === "lc123_face") continue;
    w.type = "hidden";
    w.computeSize = () => [0, -4];
    if (w.options) w.options.hidden = true;
    try {
      Object.defineProperty(w, "hidden", {
        configurable: true,
        get: () => true,
        set: () => {},
      });
    } catch (_) {
      w.hidden = true;
    }
  }
}

function readConfig(node) {
  ensureProps(node);
  let lo = num(node.properties.min, 0);
  let hi = num(node.properties.max, 100);
  if (lo > hi) [lo, hi] = [hi, lo];
  let st = num(node.properties.step, 1);
  if (!(st > 0)) st = 1;
  const decimals = Math.max(
    0,
    Math.min(4, Math.floor(num(node.properties.decimals, 0)))
  );
  return { lo, hi, st, decimals };
}

function writeValueWidget(node, v) {
  const w = findWidget(node, "value");
  if (w) w.value = v;
  // keep hidden config widgets in sync for execution
  const { lo, hi, st, decimals } = readConfig(node);
  const map = { min: lo, max: hi, step: st, decimals };
  for (const [k, val] of Object.entries(map)) {
    const cw = findWidget(node, k);
    if (cw) cw.value = val;
  }
}

function updateOutputType(node, _decimals) {
  const out = node.outputs?.[0];
  if (!out) return;
  // Static any-type socket (matches mxSlider). Runtime INT/FLOAT switching is unreliable in Nodes 2.0.
  out.type = "*";
  out.name = "*";
  out.localized_name = "*";
  out.label = "*";
}

function applyFace(node) {
  const ui = node._lc123Face;
  if (!ui) return;
  const { lo, hi, st, decimals } = readConfig(node);
  let v = num(findWidget(node, "value")?.value, lo);
  v = snapValue(v, lo, hi, st);
  if (decimals <= 0) v = Math.round(v);
  else {
    const rn = Math.pow(10, decimals);
    v = Math.round(v * rn) / rn;
  }
  writeValueWidget(node, v);
  ui.range.min = String(lo);
  ui.range.max = String(hi);
  ui.range.step = String(st);
  ui.range.value = String(v);
  ui.label.textContent = formatByDecimals(v, decimals);
  updateOutputType(node, decimals);
  layoutFace(node);
}

function setFromFace(node, raw) {
  const { lo, hi, st, decimals } = readConfig(node);
  let v = snapValue(num(raw, lo), lo, hi, st);
  if (decimals <= 0) v = Math.round(v);
  else {
    const rn = Math.pow(10, decimals);
    v = Math.round(v * rn) / rn;
  }
  writeValueWidget(node, v);
  const ui = node._lc123Face;
  if (ui) {
    ui.range.value = String(v);
    ui.label.textContent = formatByDecimals(v, decimals);
  }
  updateOutputType(node, decimals);
  node.setDirtyCanvas?.(true, true);
  try {
    node.graph?.setisChangedFlag?.(node.id);
  } catch (_) {}
}

function openSettingsModal(node) {
  ensureProps(node);
  const p = node.properties;
  document.getElementById("lc123-slider-modal")?.remove();

  const overlay = document.createElement("div");
  overlay.id = "lc123-slider-modal";
  overlay.style.cssText =
    "position:fixed;inset:0;z-index:100000;background:rgba(0,0,0,0.55);display:flex;align-items:center;justify-content:center;font-family:system-ui,sans-serif;";

  const panel = document.createElement("div");
  panel.style.cssText =
    "background:#1e1e1e;color:#eee;border:1px solid #444;border-radius:10px;padding:16px 18px;min-width:280px;max-width:90vw;box-shadow:0 12px 40px rgba(0,0,0,0.5);";

  const title = document.createElement("div");
  title.textContent = "Slider settings";
  title.style.cssText = "font-size:15px;font-weight:600;margin-bottom:12px;";
  panel.appendChild(title);

  const fields = [
    { key: "min", label: "Min" },
    { key: "max", label: "Max" },
    { key: "step", label: "Step" },
    { key: "decimals", label: "Decimals (0 = INT)" },
  ];
  const inputs = {};
  for (const f of fields) {
    const row = document.createElement("label");
    row.style.cssText =
      "display:flex;align-items:center;justify-content:space-between;gap:12px;margin:8px 0;font-size:13px;";
    const span = document.createElement("span");
    span.textContent = f.label;
    span.style.minWidth = "130px";
    const input = document.createElement("input");
    input.type = "number";
    input.step = f.key === "decimals" ? "1" : "any";
    input.value = String(p[f.key] ?? DEFAULTS[f.key]);
    input.style.cssText =
      "width:120px;padding:4px 8px;border-radius:6px;border:1px solid #555;background:#111;color:#eee;";
    row.appendChild(span);
    row.appendChild(input);
    panel.appendChild(row);
    inputs[f.key] = input;
  }

  const actions = document.createElement("div");
  actions.style.cssText = "display:flex;justify-content:flex-end;gap:8px;margin-top:12px;";

  const cancel = document.createElement("button");
  cancel.type = "button";
  cancel.textContent = "Cancel";
  cancel.style.cssText =
    "padding:6px 12px;border-radius:6px;border:1px solid #555;background:#2a2a2a;color:#ddd;cursor:pointer;";

  const ok = document.createElement("button");
  ok.type = "button";
  ok.textContent = "Apply";
  ok.style.cssText =
    "padding:6px 14px;border-radius:6px;border:1px solid #3a7;background:#1a4;color:#fff;cursor:pointer;font-weight:600;";

  const close = () => overlay.remove();
  cancel.addEventListener("click", close);
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) close();
  });
  const onKey = (e) => {
    if (e.key === "Escape") {
      close();
      window.removeEventListener("keydown", onKey);
    }
  };
  window.addEventListener("keydown", onKey);

  ok.addEventListener("click", () => {
    let min = num(inputs.min.value, p.min);
    let max = num(inputs.max.value, p.max);
    let step = num(inputs.step.value, p.step);
    let decimals = num(inputs.decimals.value, p.decimals);
    if (min > max) [min, max] = [max, min];
    if (!(step > 0)) step = 1;
    decimals = Math.max(0, Math.min(4, Math.floor(decimals)));
    node.properties.min = min;
    node.properties.max = max;
    node.properties.step = step;
    node.properties.decimals = decimals;
    applyFace(node);
    close();
    window.removeEventListener("keydown", onKey);
  });

  actions.appendChild(cancel);
  actions.appendChild(ok);
  panel.appendChild(actions);
  overlay.appendChild(panel);
  document.body.appendChild(overlay);
  inputs.min.focus();
  inputs.min.select();
}

function layoutFace(node) {
  const ui = node._lc123Face;
  if (!ui) return;
  // Classic LiteGraph pins a fixed pixel width on the DOM widget host; force it to the node body width.
  const pad = 20; // left/right margins inside node
  const w = Math.max(80, (node.size?.[0] || 240) - pad);
  const host = ui.wrap.parentElement;
  if (host) {
    host.style.width = w + "px";
    host.style.maxWidth = w + "px";
    host.style.boxSizing = "border-box";
  }
  ui.wrap.style.width = "100%";
  ui.wrap.style.maxWidth = "100%";
  ui.row.style.width = "100%";
  ui.range.style.width = "100%";
  ui.range.style.flex = "1 1 auto";
}

function attachFace(node) {
  if (node._lc123FaceAttached) {
    applyFace(node);
    layoutFace(node);
    return;
  }
  node._lc123FaceAttached = true;

  const wrap = document.createElement("div");
  wrap.style.cssText =
    "display:flex;flex-direction:column;gap:6px;padding:4px 6px;width:100%;max-width:100%;box-sizing:border-box;";

  const row = document.createElement("div");
  row.style.cssText =
    "display:flex;align-items:center;gap:8px;width:100%;max-width:100%;box-sizing:border-box;";

  const range = document.createElement("input");
  range.type = "range";
  range.style.cssText =
    "flex:1 1 auto;min-width:0;width:100%;cursor:pointer;box-sizing:border-box;";

  const label = document.createElement("div");
  label.style.cssText =
    "flex:0 0 auto;min-width:56px;max-width:88px;text-align:right;font-variant-numeric:tabular-nums;font-size:13px;color:#eee;padding:2px 4px;";

  range.addEventListener("input", () => setFromFace(node, range.value));

  label.style.cursor = "text";
  label.title = "Click to type a value";
  label.addEventListener("click", (e) => {
    e.stopPropagation();
    const cur = label.textContent;
    const next = window.prompt("Value", cur);
    if (next === null || next === "") return;
    setFromFace(node, next);
  });

  row.appendChild(range);
  row.appendChild(label);

  const bar = document.createElement("div");
  bar.style.cssText = "display:flex;justify-content:flex-end;width:100%;";
  const btn = document.createElement("button");
  btn.type = "button";
  btn.textContent = "⚙ Settings";
  btn.style.cssText =
    "cursor:pointer;font-size:12px;padding:2px 8px;border-radius:4px;border:1px solid #555;background:#2a2a2a;color:#eee;";
  btn.addEventListener("click", (e) => {
    e.preventDefault();
    e.stopPropagation();
    openSettingsModal(node);
  });
  bar.appendChild(btn);

  wrap.appendChild(row);
  wrap.appendChild(bar);

  node._lc123Face = { range, label, wrap, row };

  try {
    const domWidget = node.addDOMWidget("lc123_face", "LC123_FACE", wrap, {
      getMinHeight: () => 56,
      getHeight: () => 56,
      serialize: false,
      // classic LiteGraph resize hook
      afterResize: () => layoutFace(node),
    });
    node._lc123DomWidget = domWidget;
  } catch (e) {
    console.warn("LC Slider face widget failed", e);
  }

  // Chain onResize for Nodes 1.0
  const prevResize = node.onResize;
  node.onResize = function (size) {
    prevResize?.apply(this, arguments);
    layoutFace(this);
  };

  // Also refresh on draw (covers some 1.0 paths that skip onResize)
  const prevDraw = node.onDrawForeground;
  node.onDrawForeground = function (ctx, graphCanvas) {
    const r = prevDraw?.apply(this, arguments);
    layoutFace(this);
    return r;
  };

  applyFace(node);
  layoutFace(node);
  // deferred — host element exists after first layout pass
  requestAnimationFrame(() => layoutFace(node));
  setTimeout(() => layoutFace(node), 50);
}

function boot(node) {
  ensureProps(node);
  hideBackendWidgets(node);
  attachFace(node);
  applyFace(node);
  try {
    const w = Math.max(node.size?.[0] || 280, 240);
    node.setSize?.([w, 100]);
    if (node.size) {
      node.size[0] = w;
      node.size[1] = 100;
    }
  } catch (_) {}
}

app.registerExtension({
  name: "LC123.Slider",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (!NODE_NAMES.has(nodeData.name)) return;

    const onNodeCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      onNodeCreated?.apply(this, arguments);
      this.color = "#28281E";
      this.bgcolor = "#28281E";

      requestAnimationFrame(() => boot(this));
      setTimeout(() => boot(this), 0);
      setTimeout(() => boot(this), 100);
      setTimeout(() => boot(this), 400);

      const prevProp = this.onPropertyChanged;
      this.onPropertyChanged = function () {
        prevProp?.apply(this, arguments);
        applyFace(this);
      };

      const onConfigure = this.onConfigure;
      this.onConfigure = function () {
        onConfigure?.apply(this, arguments);
        requestAnimationFrame(() => {
          for (const key of ["value", "min", "max", "step", "decimals"]) {
            const w = findWidget(this, key);
            if (w !== undefined && w.value !== undefined && w.value !== null) {
              if (key === "value") {
                // value stays in widget; config → properties
              } else {
                this.properties[key] = w.value;
              }
            }
          }
          boot(this);
        });
      };

      const getExtra = this.getExtraMenuOptions;
      this.getExtraMenuOptions = function (_, options) {
        getExtra?.apply(this, arguments);
        options.push({
          content: "🎚️ Slider settings…",
          callback: () => openSettingsModal(this),
        });
      };
    };
  },

  async nodeCreated(node) {
    if (!NODE_NAMES.has(node.comfyClass) && !NODE_NAMES.has(node.type)) return;
    requestAnimationFrame(() => boot(node));
  },
});
