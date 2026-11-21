/**
 * LC Batch Gate 🚦 + LC Preview Gate 🛑 (lc_batch_gate.py).
 * The Preview Gate shows the cheap first pass as thumbnails (real elements, so classic and Nodes 2.0 alike) and stops
 * the run. Click a thumbnail to drop it. ▶ Continue (or Run, like LC Stop) queues the rest: this file writes
 * phase = "all" and the dropped items into the queued prompt for the gate and every LC Batch Gate above it, and LC
 * Continue (lc_continue.js) hands back the seeds the stopped run used, so the first items come out as previewed.
 * Nothing is written into the workflow itself.
 */
import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { lcContinue } from "./lc_continue.js";

const GATE = "LCPreviewGate";
const BATCH = "LCBatchGate";
const COLOR = "#963232";
const pending = new Map(); // preview gate id -> { owner, total, dropped: Set of shown picture indexes }
const CONTROLS = new Set(["control_after_generate", "control_before_generate"]);
let lastSent = null; // the last queued prompt (API format): the preview run, once a gate stops it
let forceContinue = false; // ▶ pressed: continue even when settings changed

/** The widget's own randomize / increment control (or a Primitive node's feeding it), not on fixed (as LC Continue). */
function moved(node, name) {
  const ws = node?.widgets || [];
  const i = ws.findIndex((w) => w.name === name);
  const w = ws[i];
  const ctl = w ? (w.linkedWidgets || []).find((x) => CONTROLS.has(x.name)) || (CONTROLS.has(ws[i + 1]?.name) ? ws[i + 1] : null) : null;
  if (ctl) return ctl.value !== "fixed";
  const link = node?.inputs?.find((x) => x.name === name)?.link;
  const graph = node?.graph;
  const l = link != null ? graph?.links?.[link] ?? graph?.links?.get?.(link) : null;
  const src = l ? graph.getNodeById(l.origin_id) : null;
  if (src?.type === "PrimitiveNode" && src !== node) return moved(src, src.widgets?.[0]?.name);
  return false;
}

/** Every node above this one (what feeds it), by id as the queued prompt names them. */
function idsAbove(node) {
  const graph = node.graph ?? app.graph;
  const seen = new Set();
  const walk = (n) => {
    for (const inp of n?.inputs || []) {
      const link = inp.link != null ? graph.links?.[inp.link] ?? graph.links?.get?.(inp.link) : null;
      const src = link ? graph.getNodeById(link.origin_id) : null;
      if (!src || seen.has(String(src.id))) continue;
      seen.add(String(src.id));
      walk(src);
    }
  };
  walk(node);
  return seen;
}

/** Did you change anything that feeds the previews since the preview run? A seed or counter that rolled by itself
 * doesn't count, and nothing after the gate does either (post-processing, saving: the previews stay valid). */
function changedSince(base, output, above) {
  if (!base) return false;
  const pick = (o) => Object.keys(o).filter((k) => above.has(k)).sort().join(",");
  if (pick(base) !== pick(output)) return true; // a node above added, removed or switched on / off
  for (const [id, n] of Object.entries(output)) {
    if (!above.has(id)) continue;
    const prev = base[id];
    if (!prev || prev.class_type !== n.class_type) return true;
    const node = app.graph?.getNodeById(Number(id)) ?? app.graph?.getNodeById(id);
    const gate = n.class_type === GATE || n.class_type === BATCH;
    for (const [k, v] of Object.entries(n.inputs || {})) {
      if (gate && (k === "phase" || k === "drop")) continue;
      const pv = prev.inputs?.[k];
      if (JSON.stringify(pv) === JSON.stringify(v)) continue;
      if (!Array.isArray(v) && node && moved(node, k)) continue;
      return true;
    }
  }
  return false;
}

function hideWidget(w) {
  if (!w || w._lcHidden) return;
  w._lcHidden = true;
  w.type = "hidden";
  w.computeSize = () => [0, -4];
  try {
    w.hidden = true;
  } catch (_) {}
  if (w.options) w.options.hidden = true;
  const el = w.element || w.inputEl;
  if (el?.style) el.style.display = "none";
}

const viewUrl = (im) =>
  api.apiURL(`/view?filename=${encodeURIComponent(im.filename)}&subfolder=${encodeURIComponent(im.subfolder || "")}` +
    `&type=${encodeURIComponent(im.type || "temp")}&t=${Date.now()}`);

/** Every LC Batch Gate above this node (any distance up the wires). */
function batchGatesAbove(node) {
  const graph = node.graph ?? app.graph;
  const seen = new Set();
  const found = [];
  const walk = (n) => {
    for (const inp of n?.inputs || []) {
      const link = inp.link != null ? graph.links?.[inp.link] ?? graph.links?.get?.(inp.link) : null;
      const src = link ? graph.getNodeById(link.origin_id) : null;
      if (!src || seen.has(src.id)) continue;
      seen.add(src.id);
      if (src.type === BATCH) found.push(src);
      walk(src);
    }
  };
  walk(node);
  return found;
}

/** Dropped shown pictures -> the list items to drop above (a single batch: pictures = items). */
function droppedItems(p) {
  const owners = new Set(p.owner);
  if (owners.size <= 1) return [...p.dropped].sort((a, b) => a - b);
  const items = [];
  for (const o of owners) {
    const frames = p.owner.map((v, i) => (v === o ? i : -1)).filter((i) => i >= 0);
    if (frames.every((i) => p.dropped.has(i))) items.push(o);
  }
  return items.sort((a, b) => a - b);
}

/** Turn a queued prompt into the continue run of every stopped Preview Gate. */
function patchPrompt(output) {
  for (const [id, p] of pending) {
    const gate = app.graph?.getNodeById(Number(id)) ?? app.graph?.getNodeById(id);
    const gin = output?.[String(id)]?.inputs;
    if (!gate || !gin) continue;
    const above = batchGatesAbove(gate).filter((b) => output[String(b.id)]);
    // the server keeps the previews: with a Batch Gate above, a list renders only its rest and the kept previews go
    // back in front; one picture batch renders whole (noise is by position) and drops here
    gin.phase = above.length ? "all:stored" : "all";
    gin.drop = [...p.dropped].sort((a, b) => a - b).join(",");
    const items = droppedItems(p).join(",");
    for (const b of above) Object.assign(output[String(b.id)].inputs, { phase: "all:" + String(id), drop: items });
    console.log(`[LC Preview Gate] continuing: ${p.dropped.size} dropped, ${above.length} batch gate(s) above`);
  }
  pending.clear();
}

function buildPanel(node) {
  const root = document.createElement("div");
  root.style.cssText = "display:flex;flex-direction:column;gap:6px;width:100%;height:100%;box-sizing:border-box;" +
    "padding:4px;font:12px system-ui,sans-serif;color:#ddd;overflow:hidden";
  const bar = document.createElement("div");
  bar.style.cssText = "display:flex;align-items:center;gap:8px";
  const btn = document.createElement("button");
  btn.textContent = "▶ Continue";
  btn.title = "Run the rest of the batch with the same seeds (Run does the same). Dropped pictures stay out.";
  btn.style.cssText = `background:${COLOR};color:#fff;border:1px solid #c55;border-radius:4px;padding:3px 10px;cursor:pointer;font-weight:600`;
  const clear = document.createElement("button");
  clear.textContent = "✕ Clear";
  clear.title = "Forget this preview: the next Run makes a fresh one (after you changed something, Run does that anyway).";
  clear.style.cssText = "background:#333;color:#ddd;border:1px solid #666;border-radius:4px;padding:3px 10px;cursor:pointer";
  const info = document.createElement("span");
  info.style.cssText = "flex:1;color:#bbb";
  bar.append(btn, clear, info);
  const grid = document.createElement("div");
  grid.style.cssText = "display:grid;grid-template-columns:repeat(auto-fill,minmax(110px,1fr));gap:4px;overflow:auto;flex:1;align-content:start";
  root.append(bar, grid);

  const render = () => {
    const p = pending.get(String(node.id));
    grid.innerHTML = "";
    btn.style.display = p ? "" : "none";
    clear.style.display = p ? "" : "none";
    if (!p) {
      info.textContent = node.__lcGateState === "passed" ? "Passed through: the full run went on." :
        node.__lcGateState === "cleared" ? "Cleared: the next Run makes a fresh preview." :
        "Shows the cheap first pass here and stops. Click a picture to drop it, then ▶.";
      return;
    }
    info.textContent = `${p.images.length - p.dropped.size} of ${p.images.length} kept` +
      (p.total > p.images.length ? ` (${p.total} in the batch, ${p.images.length} shown)` : "") + " · click to drop";
    p.images.forEach((im, i) => {
      const cell = document.createElement("div");
      cell.style.cssText = "position:relative;cursor:pointer;border-radius:3px;overflow:hidden;border:2px solid transparent";
      const img = document.createElement("img");
      img.src = viewUrl(im);
      img.style.cssText = "width:100%;display:block";
      const mark = document.createElement("div");
      mark.textContent = "✕";
      mark.style.cssText = "position:absolute;inset:0;display:none;align-items:center;justify-content:center;font-size:42px;" +
        "color:#ff6060;background:rgba(0,0,0,.55);font-weight:700";
      const num = document.createElement("div");
      num.textContent = String(i + 1);
      num.style.cssText = "position:absolute;left:3px;top:2px;font-size:11px;background:rgba(0,0,0,.6);padding:0 4px;border-radius:3px";
      const paint = () => {
        const off = p.dropped.has(i);
        mark.style.display = off ? "flex" : "none";
        cell.style.borderColor = off ? "#a33" : "transparent";
      };
      cell.onclick = () => {
        if (p.dropped.has(i)) p.dropped.delete(i);
        else p.dropped.add(i);
        paint();
        info.textContent = `${p.images.length - p.dropped.size} of ${p.images.length} kept` +
          (p.total > p.images.length ? ` (${p.total} in the batch, ${p.images.length} shown)` : "") + " · click to drop";
      };
      paint();
      cell.append(img, num, mark);
      grid.appendChild(cell);
    });
  };
  btn.onclick = () => {
    const p = pending.get(String(node.id));
    if (p && p.dropped.size >= p.images.length && p.total <= p.images.length) {
      app.extensionManager?.toast?.add?.({ severity: "warn", summary: "LC Preview Gate",
        detail: "Every picture is dropped: keep at least one, or just don't press ▶.", life: 4000 });
      return;
    }
    forceContinue = true;
    lcContinue();
  };
  clear.onclick = () => {
    pending.delete(String(node.id));
    node.__lcGateState = "cleared";
    render();
  };
  node.__lcGateRender = render;
  render();
  return root;
}

app.registerExtension({
  name: "LC123.BatchGate",

  setup() {
    if (api.__lcBatchGate) return;
    api.__lcBatchGate = true;
    const queuePrompt = api.queuePrompt;
    api.queuePrompt = async function (number, data, ...rest) {
      try {
        if (pending.size && data?.output) {
          const above = new Set();
          for (const id of pending.keys()) {
            const g = app.graph?.getNodeById(Number(id)) ?? app.graph?.getNodeById(id);
            if (g) for (const x of idsAbove(g)) above.add(x);
          }
          if (!forceContinue && changedSince(lastSent, data.output, above)) {
            console.log("[LC Preview Gate] settings changed since the preview: a fresh preview, not a continue");
            for (const id of pending.keys()) {
              const n = app.graph?.getNodeById(Number(id));
              if (n) { n.__lcGateState = "cleared"; n.__lcGateRender?.(); }
            }
            pending.clear();
          } else {
            patchPrompt(data.output);
          }
        }
        if (data?.output) lastSent = JSON.parse(JSON.stringify(data.output));
      } catch (e) {
        console.warn("[LC Preview Gate] continue patch skipped:", e);
        pending.clear();
      }
      forceContinue = false;
      return queuePrompt.call(this, number, data, ...rest);
    };
  },

  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== GATE && nodeData.name !== BATCH) return;
    const onNodeCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const r = onNodeCreated?.apply(this, arguments);
      for (const name of ["phase", "drop"]) hideWidget(this.widgets?.find((w) => w.name === name));
      // the size was worked out with the two hidden fields still in it: fit the node to what is left
      if (nodeData.name === BATCH) this.setSize(this.computeSize());
      if (nodeData.name === GATE) {
        this.color = COLOR;
        this.bgcolor = COLOR;
        const w = this.addDOMWidget("lc_gate_panel", "lc_gate_panel", buildPanel(this), { serialize: false, hideOnZoom: false });
        w.computeSize = (width) => [width, 260];
        this.setSize([Math.max(this.size[0], 360), Math.max(this.size[1], 340)]);
      }
      return r;
    };
    if (nodeData.name !== GATE) return;
    const onExecuted = nodeType.prototype.onExecuted;
    nodeType.prototype.onExecuted = function (message) {
      const r = onExecuted?.apply(this, arguments);
      const g = message?.lc_gate?.[0];
      if (g?.state === "stopped") {
        pending.set(String(this.id), { images: g.images || [], owner: g.owner || [], total: g.total || 0, dropped: new Set() });
        this.__lcGateState = "stopped";
      } else if (g) {
        pending.delete(String(this.id));
        this.__lcGateState = "passed";
      }
      this.__lcGateRender?.();
      return r;
    };
  },
});
