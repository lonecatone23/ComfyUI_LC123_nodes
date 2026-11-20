/**
 * Comfy Optimization Report: finds what slows down panning, zooming and dragging on the canvas, across every installed pack.
 *
 * Open it from Settings > LC123 > Optimization, or right-click the empty canvas > Comfy Optimization Report.
 * 1. Live test: pans the canvas by itself for a few seconds (at your zoom, then zoomed out) and times
 *    every node draw, every animation loop and every timer, grouped by the pack it comes from.
 * 2. File scan: reads every pack's front-end files for patterns known to cost frame time.
 * Then it lists the biggest costs first with a suggestion for each. Nothing is changed; the view is put back afterwards.
 */
import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { addCsvButton } from "./lc_report_csv.js";

// ---------------------------------------------------------------- source attribution
const SELF = "lc_optimizer.js";
function packFromStack(stack) {
  if (!stack) return "unknown";
  for (const line of String(stack).split("\n")) {
    if (line.includes(SELF)) continue;
    const m = /\/extensions\/([^/]+)\//.exec(line);
    if (m) return decodeURIComponent(m[1]);
    if (/\/assets\/|\/scripts\//.test(line)) return "ComfyUI (core)";
  }
  return "unknown";
}
function packOfNodeType(type) {
  const def = window.LiteGraph?.registered_node_types?.[type];
  const mod = def?.nodeData?.python_module || def?.python_module;
  if (!mod) {
    // front-end-only nodes carry no Python module: credit the known ones to their pack
    if (/\(rgthree\)/.test(type)) return "rgthree-comfy";
    if (/^LC/.test(type)) return "ComfyUI_LC123_nodes";
    return "ComfyUI (core)";
  }
  if (mod.startsWith("custom_nodes.")) return mod.slice("custom_nodes.".length).split(".")[0];
  return "ComfyUI (core)";
}

// ---------------------------------------------------------------- timers: wrapped from load, only timed during a test
let profiling = false;
const timerStats = new Map(); // pack -> {count, fastest, ms, calls}
const liveTimers = new Map(); // id -> {pack, ms}
const _setInterval = window.setInterval.bind(window);
const _clearInterval = window.clearInterval.bind(window);
window.setInterval = function (fn, ms, ...rest) {
  const pack = packFromStack(new Error().stack);
  if (typeof fn !== "function") return _setInterval(fn, ms, ...rest);
  const wrapped = function () {
    if (!profiling) return fn.apply(this, arguments);
    const t0 = performance.now();
    try {
      return fn.apply(this, arguments);
    } finally {
      const s = timerStats.get(pack) || { ms: 0, calls: 0 };
      s.ms += performance.now() - t0;
      s.calls++;
      timerStats.set(pack, s);
    }
  };
  const id = _setInterval(wrapped, ms, ...rest);
  liveTimers.set(id, { pack, ms: Number(ms) || 0 });
  return id;
};
window.clearInterval = function (id) {
  liveTimers.delete(id);
  return _clearInterval(id);
};
const _clearTimeout = window.clearTimeout.bind(window);
window.clearTimeout = function (id) {
  liveTimers.delete(id);
  return _clearTimeout(id);
};

// ---------------------------------------------------------------- live test
const _raf = window.requestAnimationFrame.bind(window);
// next frame; falls back to a timer when the tab is in the background (no animation frames there)
const frame = () =>
  new Promise((r) => {
    let done = false;
    const fin = () => {
      if (!done) {
        done = true;
        r();
      }
    };
    _raf(fin);
    setTimeout(fin, 50);
  });

let running = null; // {cancelled} while a live test runs

async function liveTest(onStep, token) {
  const c = app.canvas;
  const ds = c.ds;
  const startGraph = c.graph;
  const keep = { scale: ds.scale, offset: [ds.offset[0], ds.offset[1]] };
  // remember exactly what was there (an own property from another pack, or nothing) so it can be put back
  const saved = {};
  for (const fn of ["draw", "drawNode", "drawConnections", "drawGroups"]) {
    saved[fn] = Object.prototype.hasOwnProperty.call(c, fn) ? { own: true, value: c[fn] } : { own: false };
  }
  const prevRaf = window.requestAnimationFrame;
  const rafStats = new Map(); // pack -> ms
  const nodeStats = new Map(); // pack -> {ms, types: Map(type -> ms)}
  const phases = [];

  // animation loops: callbacks registered during the test are timed and credited to their pack
  const rafWrap = (cb) => {
    const pack = packFromStack(new Error().stack);
    return _raf((t) => {
      const t0 = performance.now();
      try {
        cb(t);
      } finally {
        if (pack !== "ComfyUI (core)") rafStats.set(pack, (rafStats.get(pack) || 0) + performance.now() - t0);
      }
    });
  };
  const origDrawNode = c.drawNode;
  const origDraw = c.draw;
  let drawMs = 0;
  let draws = 0;
  // links and group frames are drawn by ComfyUI itself; time them too so the whole frame is accounted for
  const parts = { links: 0, groups: 0 };
  const origParts = {};
  for (const [key, fn] of [["links", "drawConnections"], ["groups", "drawGroups"]]) {
    if (typeof c[fn] !== "function") continue;
    const orig = (origParts[fn] = c[fn]);
    c[fn] = function () {
      const t0 = performance.now();
      try {
        return orig.apply(this, arguments);
      } finally {
        parts[key] += performance.now() - t0;
      }
    };
  }
  c.drawNode = function (node) {
    const t0 = performance.now();
    try {
      return origDrawNode.apply(this, arguments);
    } finally {
      const ms = performance.now() - t0;
      const pack = packOfNodeType(node.type);
      const s = nodeStats.get(pack) || { ms: 0, types: new Map() };
      s.ms += ms;
      s.types.set(node.type, (s.types.get(node.type) || 0) + ms);
      nodeStats.set(pack, s);
    }
  };
  c.draw = function () {
    const t0 = performance.now();
    try {
      return origDraw.apply(this, arguments);
    } finally {
      drawMs += performance.now() - t0;
      draws++;
    }
  };

  const snap = () => ({
    draws,
    drawMs,
    links: parts.links,
    groups: parts.groups,
    raf: new Map(rafStats),
    timers: new Map([...timerStats].map(([k, v]) => [k, { ...v }])),
    nodes: new Map([...nodeStats].map(([k, v]) => [k, { ms: v.ms, types: new Map(v.types) }])),
  });
  const diff = (a, b) => {
    const m = (x, y) => {
      const out = new Map();
      for (const [k, v] of y) out.set(k, v - (x.get(k) || 0));
      return out;
    };
    const nodes = new Map();
    for (const [k, v] of b.nodes) {
      const o = a.nodes.get(k);
      const types = new Map();
      for (const [t, ms] of v.types) types.set(t, ms - (o?.types.get(t) || 0));
      nodes.set(k, { ms: v.ms - (o?.ms || 0), types });
    }
    const timers = new Map();
    for (const [k, v] of b.timers) {
      const o = a.timers.get(k);
      timers.set(k, { ms: v.ms - (o?.ms || 0), calls: v.calls - (o?.calls || 0) });
    }
    return { draws: b.draws - a.draws, drawMs: b.drawMs - a.drawMs, links: b.links - a.links, groups: b.groups - a.groups, raf: m(a.raf, b.raf), timers, nodes };
  };

  const run = async (name, seconds, move) => {
    onStep(name);
    const a = snap();
    const t0 = performance.now();
    let frames = 0;
    let seen = draws;
    while (performance.now() - t0 < seconds * 1000) {
      if (token.cancelled || c.graph !== startGraph) {
        token.cancelled = true; // closed, or another workflow tab was opened: stop and put everything back
        return;
      }
      await frame();
      if (draws === seen) c.draw(true, true); // no animation frame came (background tab): draw by hand
      seen = draws;
      frames++;
      if (move) move((performance.now() - t0) / 1000);
      c.setDirty(true, true);
    }
    if (token.cancelled) return;
    const d = diff(a, snap());
    d.name = name;
    d.seconds = (performance.now() - t0) / 1000;
    d.frames = frames;
    phases.push(d);
  };

  window.requestAnimationFrame = rafWrap;
  profiling = true;
  try {
    await run("Standing still", 1.5, null);
    const s0 = keep.scale;
    await run("Panning at your zoom", 3, (t) => {
      ds.offset[0] = keep.offset[0] + Math.sin(t * 2.2) * (260 / s0);
      ds.offset[1] = keep.offset[1] + Math.cos(t * 1.7) * (140 / s0);
    });
    // zoomed out so the whole workflow is on screen: the worst case for drawing
    const nodes = c.graph?._nodes || [];
    if (nodes.length) {
      let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
      for (const n of nodes) {
        x0 = Math.min(x0, n.pos[0]);
        y0 = Math.min(y0, n.pos[1]);
        x1 = Math.max(x1, n.pos[0] + n.size[0]);
        y1 = Math.max(y1, n.pos[1] + n.size[1]);
      }
      const W = c.canvas.clientWidth || 1200;
      const H = c.canvas.clientHeight || 800;
      const fit = Math.min(keep.scale, Math.max(0.1, Math.min(W / (x1 - x0 + 200), H / (y1 - y0 + 200)))); // never zooms in
      ds.scale = fit;
      const cx = -(x0 + x1) / 2 + W / 2 / fit;
      const cy = -(y0 + y1) / 2 + H / 2 / fit;
      await run("Panning zoomed out (whole workflow)", 3, (t) => {
        ds.offset[0] = cx + Math.sin(t * 2.2) * (200 / fit);
        ds.offset[1] = cy + Math.cos(t * 1.7) * (120 / fit);
      });
    }
  } finally {
    profiling = false;
    window.requestAnimationFrame = prevRaf;
    for (const [fn, st] of Object.entries(saved)) {
      if (st.own) c[fn] = st.value;
      else delete c[fn]; // back to the prototype (and any other pack's patch on it)
    }
    if (c.graph === startGraph) {
      // the view goes back where it was, unless another workflow is open now (it has its own view)
      ds.scale = keep.scale;
      ds.offset[0] = keep.offset[0];
      ds.offset[1] = keep.offset[1];
    }
    c.setDirty(true, true);
  }
  return phases;
}

// ---------------------------------------------------------------- report
function setting(id) {
  try {
    return app.extensionManager?.setting?.get?.(id) ?? app.ui?.settings?.getSettingValue?.(id);
  } catch (_) {
    return undefined;
  }
}

// Settings in other packs that lower their canvas cost: [folder pattern, setting id, is-costly test, what to do]
const RGTHREE = /rgthree/i;
const UE_SHOW = ["All off", "Selected nodes", "Mouseover node", "Selected and mouseover nodes", "All on"];
const UE_ANIM = ["Off", "Dots", "Pulse", "Both"];
// want = what to set it to; live = the effect is already off even though the setting says otherwise
const PACK_SETTINGS = [
  { pack: /KJNodes/i, id: "KJNodes.perf.singleCanvasPan", name: "Single-canvas mode during pan", where: "KJNodes > Performance", bad: (v) => v !== true, want: "On", why: "draws one canvas layer instead of two while you pan" },
  { pack: /KJNodes/i, id: "KJNodes.perf.disableShadows", name: "Disable node shadows", where: "KJNodes > Performance", bad: (v) => v !== true, want: "On", why: "ComfyUI draws a shadow under every node on every frame", live: () => app.canvas?.render_shadows === false },
  { pack: /KJNodes/i, id: "KJNodes.perf.disableConnectionBorders", name: "Disable connection borders", where: "KJNodes > Performance", bad: (v) => v !== true, want: "On", why: "every link is drawn twice (border + line)", live: () => app.canvas?.render_connections_border === false },
  { pack: /KJNodes/i, id: "KJNodes.perf.throttleRenderInfo", name: "Throttle info overlay", where: "KJNodes > Performance", bad: (v) => v !== true && setting("Comfy.Graph.CanvasInfo") !== false, want: "On", why: "the fps / info corner redraws less often" },
  { pack: /KJNodes/i, id: "KJNodes.showSetGetLinks", name: "Show links", where: "KJNodes > Set & Get", bad: (v) => v === "always", want: "Selected or Never", why: "virtual Set/Get links are drawn for every pair" },
  { pack: /use-everywhere/i, id: "Use Everywhere.Graphics.animate", name: "Animate UE links", where: "Use Everywhere", bad: (v) => Number(v) > 0, want: "Off", show: (v) => UE_ANIM[Number(v)] ?? v, why: "animated links redraw the canvas every frame" },
  { pack: /use-everywhere/i, id: "Use Everywhere.Graphics.showlinks", name: "Show links", where: "Use Everywhere", bad: (v) => Number(v) === 4, want: "Selected and mouseover nodes", show: (v) => UE_SHOW[Number(v)] ?? v, why: "All on draws every virtual link all the time" },
  { pack: /use-everywhere/i, id: "Use Everywhere.Graphics.highlight", name: "Highlight connected and connectable inputs", where: "Use Everywhere", bad: (v) => v === true, want: "Off", why: "checks every input on the screen while you drag" },
  { pack: /Pixaroma/i, id: "Pixaroma.Connection.FX", name: "Connection FX", where: "Pixaroma", bad: (v) => v === true, want: "Off", why: "scans every link on every frame (LC Connection FX only draws while a wire is held)" },
  { pack: /Pixaroma/i, id: "Pixaroma.Align.Enabled", name: "Align Pixaroma snap & guides", where: "Pixaroma", bad: (v) => v === true && !!window.LC123Align?.isOn?.(), want: "Off", why: "LC Align is on too, and two snap tools fight over the same drag" },
  { pack: /Pixaroma/i, id: "Pixaroma.RunButton.FX", name: "Run Button FX", where: "Pixaroma", bad: (v) => v && v !== "None", want: "None", why: "the Run button animates" },
  { pack: /VideoHelperSuite/i, id: "VHS.AdvancedPreviews", name: "Advanced Previews", where: "Video Helper Suite", bad: (v) => v === "Always", want: "Input Only or Never", why: "every video preview is re-encoded to fit the node" },
  { pack: /VideoHelperSuite/i, id: "VHS.LatentPreview", name: "Display animated previews when sampling", where: "Video Helper Suite", bad: (v) => v === true, want: "Off", why: "plays animated previews while sampling" },
  { pack: /RedNodeStudio/i, id: "RedNode.Workspace.LowZoomHide", name: "Blank RedNode panels below this zoom", where: "RedNode > Workspace", bad: (v) => Number(v) < 0.5, want: "0.55 or higher", why: "its panels keep drawing when zoomed out" },
  { pack: /vslinx/i, id: "vslinx.modelHoverPreviews", name: "Hover previews", where: "vslinx", bad: (v) => v === true, want: "Off", why: "loads a preview image on every dropdown hover" },
  { pack: /vrgamedevgirl/i, id: "VRGDG.ResourceMonitor.Enabled", name: "Show resource monitor", where: "VRGDG", bad: (v) => v === true, want: "Off", why: "polls the GPU on a timer" },
  { pack: /mtb/i, id: "mtb.Main.image-feed-enabled", name: "Enable Image Feed", where: "mtb", bad: (v) => v === true, want: "Off", why: "keeps an image strip updated on screen" },
  { pack: /EasyColorCorrector/i, id: "EasyColorCorrection.auto_enable_preview", name: "Auto-Enable Preview", where: "Easy Color Corrector", bad: (v) => v === true, want: "Off", why: "renders a live preview on every change" },
  { pack: /EasyColorCorrector/i, id: "EasyColorCorrection.preview_quality", name: "Preview Quality", where: "Easy Color Corrector", bad: (v) => v === "high", want: "medium or low", why: "high quality previews cost the most" },
];
// how much changing each setting gains: 3 big, 2 worthwhile, 1 small (c = {nodes, links} of the open workflow)
const IMPACT = {
  "KJNodes.perf.singleCanvasPan": 2,
  "KJNodes.perf.disableShadows": (c) => (c.nodes > 150 ? 3 : 2),
  "KJNodes.perf.disableConnectionBorders": (c) => (c.links > 200 ? 3 : 2),
  "KJNodes.perf.throttleRenderInfo": 1,
  "KJNodes.showSetGetLinks": 2,
  "Use Everywhere.Graphics.animate": 3,
  "Use Everywhere.Graphics.showlinks": 2,
  "Use Everywhere.Graphics.highlight": 1,
  "Pixaroma.Connection.FX": 2,
  "Pixaroma.Align.Enabled": 2,
  "Pixaroma.RunButton.FX": 1,
  "VHS.AdvancedPreviews": 2,
  "VHS.LatentPreview": 1,
  "RedNode.Workspace.LowZoomHide": 2,
  "vslinx.modelHoverPreviews": 1,
  "VRGDG.ResourceMonitor.Enabled": 1,
  "mtb.Main.image-feed-enabled": 1,
  "EasyColorCorrection.auto_enable_preview": 2,
  "EasyColorCorrection.preview_quality": 1,
};
const ICON = { 3: "⚠️", 2: "✅", 1: "💡", 0: "⚪", "-1": "➖", info: "ℹ️" };
const RANK = (l) => (l === "info" ? -2 : Number(l));
const fmt = (f, v) => (f.show ? f.show(v) : v === true ? "On" : v === false ? "Off" : String(v));

function buildReport(phases, scan) {
  const c = app.canvas;
  const nodes = c.graph?._nodes || [];
  const links = c.graph?.links ? (c.graph.links.size ?? Object.keys(c.graph.links).length) : 0;
  const packs = new Map(); // pack -> {drawMs (per frame, worst phase), raf, timers, domWidgets, nodeCount, scan, types}
  const P = (k) => {
    if (!packs.has(k)) packs.set(k, { draw: 0, raf: 0, timer: 0, timerCount: 0, fastest: 0, dom: 0, nodes: 0, types: new Map(), scan: null });
    return packs.get(k);
  };
  for (const ph of phases) {
    const f = Math.max(1, ph.draws);
    for (const [k, v] of ph.nodes) {
      const p = P(k);
      p.draw = Math.max(p.draw, v.ms / f);
      for (const [t, ms] of v.types) p.types.set(t, Math.max(p.types.get(t) || 0, ms / f));
    }
    for (const [k, ms] of ph.raf) P(k).raf = Math.max(P(k).raf, ms / Math.max(1, ph.frames));
    for (const [k, v] of ph.timers) P(k).timer = Math.max(P(k).timer, v.ms / ph.seconds);
  }
  for (const t of liveTimers.values()) {
    const p = P(t.pack);
    p.timerCount++;
    p.fastest = p.fastest ? Math.min(p.fastest, t.ms) : t.ms;
  }
  for (const n of nodes) {
    const p = P(packOfNodeType(n.type));
    p.nodes++;
    for (const w of n.widgets || []) if (w.element) p.dom++;
  }
  for (const [k, v] of Object.entries(scan?.packs || {})) P(k).scan = v;

  // only packs that have nodes in this workflow are reported (ComfyUI itself always is)
  const used = (k) => k === "ComfyUI (core)" || (packs.get(k)?.nodes || 0) > 0;
  const skipped = [...packs.keys()].filter((k) => !used(k) && k !== "unknown").sort();

  // recommendations, biggest cost first. kind: required | pack | lc123 | comfy
  const tips = [];
  const add = (cost, pack, kind, text, key = kind + ":" + pack + ":" + text.replace(/[\d.,]+/g, "#").slice(0, 50), open = true, level) =>
    tips.push({ cost, pack, kind, text, key, open, level: level ?? (kind === "required" ? "info" : open ? 2 : 0) });
  const ctx = { nodes: nodes.length, links };
  const lcWays = [];
  for (const [k, p] of packs) {
    if (!used(k)) continue;
    const costs = [];
    if (p.draw >= 0.4) {
      const top = [...p.types].sort((a, b) => b[1] - a[1]).slice(0, 3).map(([t, ms]) => `${t} ${ms.toFixed(2)} ms`).join(", ");
      costs.push([p.draw * 10, `its nodes take ${p.draw.toFixed(2)} ms of every frame to draw (${top})`]);
    }
    if (p.raf >= 0.2) costs.push([p.raf * 10, `an animation loop costs ${p.raf.toFixed(2)} ms every frame, even when nothing moves`]);
    if (p.timerCount && (p.timer >= 2 || p.fastest <= 100))
      costs.push([p.timer / 5 + 1, `${p.timerCount} timer${p.timerCount > 1 ? "s" : ""} (fastest every ${p.fastest} ms), ${p.timer.toFixed(1)} ms of work per second`]);
    if (p.dom >= 15) costs.push([p.dom / 10, `${p.dom} DOM widgets, which the browser repositions on every pan and zoom frame`]);
    const sc = p.scan || {};
    if (sc.canvas_patch)
      costs.push([1.5, `patches a canvas draw call (${[...new Set(sc.canvas_patch.examples.map((e) => e.text.split("=")[0].trim().replace("LGraphCanvas.prototype.", "")))].join(", ")}), so its code runs on every frame`]);
    if (sc.blur) costs.push([1, `uses blur / backdrop filters (${sc.blur.count}x), some of the most expensive CSS while panning`]);

    // 2. that pack's own settings, each checked against its current value (and the live effect where possible)
    let firstOpen = true;
    let open = 0;
    for (const f of PACK_SETTINGS.filter((x) => x.pack.test(k))) {
      const v = setting(f.id);
      if (v === undefined) continue;
      const done = !f.bad(v) || !!f.live?.();
      if (!done) open++;
      const measured = !done && firstOpen && costs.length ? ` (measured for this pack: ${costs.map((c) => c[1]).join("; ")})` : "";
      if (!done) firstOpen = false;
      const text = done
        ? `"${f.name}" (${f.where}): already ${fmt(f, v)}${f.live?.() && f.bad(v) ? " (the effect is already off)" : ""}.`
        : `"${f.name}" (${f.where}): currently ${fmt(f, v)}, set to ${f.want}. ${f.why[0].toUpperCase() + f.why.slice(1)}.${measured}`;
      const imp = IMPACT[f.id];
      const level = done ? 0 : typeof imp === "function" ? imp(ctx) : imp ?? 1;
      add(done ? 0.1 : Math.max(1, ...costs.map((c) => c[0])) + 0.5, k, "pack", text, f.id, !done, level);
    }
    const fixes = { length: open };
    if (k === "ComfyUI_LC123_nodes") {
      lcWays.push(...costs);
      continue; // LC123 gets its own recommendations below
    }
    // 1. nothing to switch off: the cost is part of how the pack works
    if (costs.length && !fixes.length) {
      const total = costs.reduce((a, c) => a + c[0], 0);
      const extra = RGTHREE.test(k) ? " rgthree has its own config dialog (Settings > rgthree) with options for its canvas features." : "";
      add(total, k, "required", `${costs.map((c) => c[1]).join("; ")}. This is how its nodes work, there is no setting for it. Collapse or bypass-group the ones you are not using.${extra}`);
    }
  }

  // 3. our own settings: every LC123 optimization setting, with its state and whether it matters for this workflow
  const lc = packs.get("ComfyUI_LC123_nodes");
  if (lc?.nodes) {
    const FX = window.LC123FXClasses || new Set();
    const types = nodes.map((n) => n.type);
    const fx = types.filter((t) => FX.has(t)).length;
    const skin = types.filter((t) => t === "LCSkinBeauty").length;
    const previews = fx + types.filter((t) => /^LC(Preview(Image|Mask)|ImageCompare|ImageSplit|DynamicOverlay|ImageCrop|BatchImageComparer|TextOverlay|Watermark)/.test(t)).length;
    const loras = types.filter((t) => t === "LCLoraLoader").length;
    const on = (id, d) => (setting(id) ?? d) === true;
    const hide = on("LC123.Performance.HidePreviews", false);
    const halfRes = on("LC123.Performance.HalfRes", false);
    const clamp = on("LC123.Performance.ClampEdge", false);
    const minPx = Number(setting("LC123.Performance.PreviewMinSize") ?? 40);
    const maxEdge = Number(setting("LC123.Performance.MaxEdge") ?? 768);
    // [state, name, what it does, relevance for this workflow]; state: "on" | "off" | "na"
    const rows = [];
    const row = (state, name, text, level = 2) => rows.push({ state, name, text, level });
    const fxWord = `${fx} LC FX node${fx === 1 ? "" : "s"} with a preview in this workflow`;
    if (!fx) row("na", "Hide FX on-node previews", "No LC FX preview nodes in this workflow.");
    else if (hide) row("on", "Hide FX on-node previews", `On. The lightest setting: ${fxWord} draw nothing. (Half-res and Clamp have nothing left to do while this is on.)`);
    else row("off", "Hide FX on-node previews", `Off. Turn on for the lightest canvas: ${fxWord} stop drawing. Use Image Compare or Image Split when you need to look.`, lc.draw >= 1 ? 3 : 2);
    if (fx && !hide) {
      row(clamp ? "on" : "off", "Clamp longest side", clamp ? `On (Max edge ${maxEdge}).${maxEdge > 768 ? " Try 512." : ""}` : `Off. Turn on with Max edge 512: big images get a small preview texture (${fxWord}).`);
      row(halfRes ? "on" : "off", "Half-resolution previews", halfRes ? "On." : `Off. Turn on to draw FX previews at half size (${fxWord}).`, 1);
      row(on("LC123.Performance.SkipCollapsed", true) ? "on" : "off", "No preview when collapsed", on("LC123.Performance.SkipCollapsed", true) ? "On." : "Off. Turn on: collapsed FX nodes stop drawing their preview.");
    } else if (fx) row("on", "Clamp / Half-res / No preview when collapsed", "Not needed while Hide FX on-node previews is on.");
    if (previews) row(minPx >= 20 ? "on" : "off", "Preview distance", minPx >= 20 ? `${minPx} px. Previews switch off when zoomed far out.` : `${minPx} px. Set to about 40 px so previews switch off when zoomed far out, like node text (${previews} LC previews here).`);
    else row("na", "Preview distance", "No LC previews in this workflow.");
    if (skin && (halfRes || clamp) && !hide)
      row(on("LC123.Performance.SkinBeautyFullPreview", true) ? "off" : "on", "Skin Beauty full preview override", on("LC123.Performance.SkinBeautyFullPreview", true) ? `On, so ${skin} Skin Beauty node${skin > 1 ? "s ignore" : " ignores"} Half-res and Clamp. Turn off if you do not need to zoom into skin on the canvas.` : "Off. Skin Beauty follows Half-res and Clamp.", 1);
    if (loras) row(on("LC123.Performance.LoraInfoButton", true) ? "off" : "on", "LoRA loader info button", on("LC123.Performance.LoraInfoButton", true) ? "On. Minor: turn off to drop one button per LoRA row." : "Off.", 1);
    row("on", "Connection FX / Align", "Connection FX only draws while you hold a wire. Align redraws only while the cursor is near one of its lines, or while you drag.");
    rows.forEach((r, i) =>
      add(100 - i, "LC123", "lc123", `"${r.name}": ${r.text}`, "lc123:" + r.name, r.state === "off", r.state === "off" ? r.level : r.state === "on" ? 0 : -1)
    );
    if (lcWays.length)
      add(lcWays.reduce((a, c) => a + c[0], 0), "LC123", "required", `${lcWays.map((c) => c[1]).join("; ")}. Needed for LC nodes like the Bypass Relay, Labels and Boolean faces to stay live.`);
  }

  // ComfyUI's own settings
  const linkMs = Math.max(0, ...phases.map((p) => p.links / Math.max(1, p.draws)));
  const linkPatchers = Object.entries(scan?.packs || {})
    .filter(([k, v]) => used(k) && v?.canvas_patch?.examples?.some((e) => /drawConnections|renderLink/.test(e.text)))
    .map(([k]) => k);
  if (linkMs >= 2 && setting("Comfy.LinkRenderMode") === 2)
    add(linkMs * 10, "ComfyUI", "comfy", `Links take ${linkMs.toFixed(1)} ms of every frame (${links} spline links${linkPatchers.length ? `, including link drawing added by ${linkPatchers.join(", ")}` : ""}). Set "Link Render Mode" to Linear or Straight (Lite Graph > Graph).`, undefined, true, linkMs >= 5 ? 3 : 2);
  else if (linkMs >= 2) add(linkMs * 8, "ComfyUI", "comfy", `Links take ${linkMs.toFixed(1)} ms of every frame (${links} links). Hiding links while you pan (Link Render Mode: Hidden) is the only bigger saving.`);
  if (links > 250 && Number(setting("Comfy.Graph.LinkMarkers")) > 0) add(1.2, "ComfyUI", "comfy", `Set "Link midpoint markers" to None (Lite Graph > Graph). ${links} links each draw a marker.`, undefined, true, 1);
  const domAll = [...packs.values()].reduce((a, p) => a + p.dom, 0);
  if (domAll >= 10 && setting("Comfy.DOMClippingEnabled") !== false)
    add(domAll / 8, "ComfyUI", "comfy", `Turn off "Enable DOM element clipping" (Lite Graph > Node Widget). ${domAll} DOM widgets are clipped on every frame; ComfyUI's own tooltip says it may reduce performance.`, undefined, true, domAll >= 30 ? 2 : 1);
  const zoomed = phases.find((p) => p.name.includes("zoomed out"));
  if (zoomed && zoomed.drawMs / Math.max(1, zoomed.draws) > 8 && Number(setting("LiteGraph.Canvas.MinFontSizeForLOD") ?? 8) < 12)
    add(2, "ComfyUI", "comfy", `Raise "Zoom Node Level of Detail - font size threshold" to 12 to 14 (Lite Graph > Canvas). Nodes switch to the simple look sooner when you zoom out.`);
  // sidebar tabs added by packs: they load when opened, some keep working in the background
  const tabs = (app.extensionManager?.getSidebarTabs?.() || []).filter((t) => t.type === "custom").map((t) => t.id);
  if (tabs.includes("mtb-inputs-outputs")) {
    const n = Number(setting("mtb.io-sidebar.count"));
    if (n > 300) add(1.5, "Sidebar: Input & Outputs (mtb)", "sidebar", `Lower "Number of images to fetch" from ${n} to about 200 (mtb > Input & Output Sidebar). Every open of the tab loads that many thumbnails.`, undefined, true, 2);
    const px = Number(setting("mtb.io-sidebar.img-size"));
    if (px > 256) add(1.2, "Sidebar: Input & Outputs (mtb)", "sidebar", `Lower "Resize width of shown images" from ${px} to 256 (mtb > Input & Output Sidebar). Thumbnails that size are plenty for a sidebar.`, undefined, true, 1);
  }
  if (tabs.includes("civitai.generated") && setting("Civitai.enableLink") === true)
    add(1, "Sidebar: CivitAI", "sidebar", `Turn off "CivitAI Link" (CivitAI > Features) if you do not send models from the CivitAI site to ComfyUI. It keeps a live connection open.`, undefined, true, 1);
  if (setting("Comfy.Minimap.Visible") === true) add(1, "ComfyUI", "comfy", `Hide the minimap when you do not need it. It redraws with the canvas.`, undefined, true, 1);
  tips.sort((a, b) => RANK(b.level) - RANK(a.level) || b.cost - a.cost);
  return { phases, packs, tips, skipped, used, nodes: nodes.length, links };
}

// ---------------------------------------------------------------- window
const esc = (s) => String(s).replace(/[&<>"]/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[ch]);

// ---------------------------------------------------------------- last run (one run kept, in this browser)
const LAST_KEY = "lc123.optimizer.lastRun";
function loadLast() {
  try {
    return JSON.parse(localStorage.getItem(LAST_KEY) || "null");
  } catch (_) {
    return null;
  }
}
function saveLast(v) {
  try {
    localStorage.setItem(LAST_KEY, JSON.stringify(v));
  } catch (_) {}
}
function workflowName() {
  try {
    return app.extensionManager?.workflow?.activeWorkflow?.filename || "";
  } catch (_) {
    return "";
  }
}
function snapshot(rep) {
  return {
    workflow: workflowName(),
    phases: rep.phases.map((ph) => ({ name: ph.name, fps: ph.frames / ph.seconds, draw: ph.drawMs / Math.max(1, ph.draws), links: ph.links / Math.max(1, ph.draws) })),
    open: rep.tips.filter((t) => t.open && t.kind !== "required").map((t) => ({ key: t.key, pack: t.pack, text: t.text, level: t.level })),
  };
}
function improvements(prev, now, h, lines) {
  const sameWf = !prev.snap.workflow || !now.workflow || prev.snap.workflow === now.workflow;
  h.push(`<div style="font-weight:600;font-size:14px;margin:6px 0">Since the last run <span style="font-weight:400;color:#9aa3ad;font-size:12px">(${esc(prev.when)}${sameWf ? "" : `, a different workflow: ${esc(prev.snap.workflow)}`})</span></div>`);
  lines.push("", `Since the last run (${prev.when}):`);
  h.push(`<div style="color:#9aa3ad;font-size:12px;margin-bottom:4px">Grey = under 10%, which is normal run-to-run noise. Green = faster, red = slower.</div>`);
  h.push(`<table style="width:100%;border-collapse:collapse;margin-bottom:8px;font-size:12px"><tr style="color:#9aa3ad;text-align:left"><th>Test</th><th>Canvas draw per frame</th><th>Links per frame</th><th>Frames per second</th></tr>`);
  const d = (a, b, lowerIsBetter) => {
    const diff = b - a;
    const pct = a ? Math.round((diff / a) * 100) : 0;
    const good = lowerIsBetter ? diff < 0 : diff > 0;
    const col = Math.abs(pct) < 10 ? "#9aa3ad" : good ? "#86efac" : "#f87171";
    return `<span style="color:${col}">${a.toFixed(a < 100 ? 2 : 0)} → ${b.toFixed(b < 100 ? 2 : 0)} (${pct > 0 ? "+" : ""}${pct}%)</span>`;
  };
  for (const ph of now.phases) {
    const o = prev.snap.phases.find((x) => x.name === ph.name);
    if (!o) continue;
    h.push(`<tr><td>${esc(ph.name)}</td><td>${d(o.draw, ph.draw, true)}</td><td>${d(o.links, ph.links, true)}</td><td>${d(o.fps, ph.fps, false)}</td></tr>`);
    lines.push(`${ph.name}: draw ${o.draw.toFixed(2)} → ${ph.draw.toFixed(2)} ms, links ${o.links.toFixed(2)} → ${ph.links.toFixed(2)} ms`);
  }
  h.push(`</table>`);
  const nowKeys = new Set(now.open.map((t) => t.key));
  const prevKeys = new Set(prev.snap.open.map((t) => t.key));
  const fixed = prev.snap.open.filter((t) => !nowKeys.has(t.key));
  const fresh = now.open.filter((t) => !prevKeys.has(t.key));
  const strip = (t) => {
    const x = t.replace(/^[^\w"]+/, "");
    const m = /^"[^"]+"(\s\([^)]*\))?/.exec(x); // a setting: just its name and where it lives
    return m ? m[0] : x.split(". ")[0];
  };
  if (fixed.length) {
    h.push(`<div style="color:#86efac;margin:4px 0">Fixed since last run (${fixed.length}):</div>`);
    for (const t of fixed) h.push(`<div style="margin:2px 0 2px 10px;color:#86efac">✔ done: <b>${esc(t.pack)}</b>: ${esc(strip(t.text))}</div>`);
    lines.push(`Fixed: ${fixed.map((t) => `${t.pack}: ${strip(t.text)}`).join(" | ")}`);
  }
  if (fresh.length) {
    h.push(`<div style="color:#fbbf24;margin:4px 0">New since last run (${fresh.length}):</div>`);
    for (const t of fresh) h.push(`<div style="margin:2px 0 2px 10px;color:#fbbf24">${ICON[t.level] || "•"} <b>${esc(t.pack)}</b>: ${esc(strip(t.text))}</div>`);
  }
  if (!fixed.length && !fresh.length) h.push(`<div style="color:#9aa3ad;margin:4px 0">Same open recommendations as last time (${now.open.length}).</div>`);
  else h.push(`<div style="color:#9aa3ad;margin:4px 0">Still open: ${now.open.length - fresh.length}.</div>`);
}

function openWindow() {
  const open = document.querySelector(".lc-opt-overlay");
  if (open && running) return; // a run is in progress in that window: keep it
  open?.remove();
  const ov = document.createElement("div");
  ov.className = "lc-opt-overlay";
  ov.style.cssText = "position:fixed;inset:0;z-index:10000;background:rgba(0,0,0,0.55);display:flex;align-items:center;justify-content:center;";
  const box = document.createElement("div");
  box.style.cssText =
    "width:min(920px,94vw);max-height:88vh;overflow:auto;background:#1e2227;color:#dfe3e8;border:1px solid #3a4048;border-radius:10px;padding:18px 22px;font:13px/1.45 system-ui,sans-serif;";
  box.innerHTML = `<div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">
      <div style="font-size:17px;font-weight:600;flex:1">Comfy Optimization Report</div>
      <button class="lc-opt-last p-button p-button-sm p-button-secondary" type="button" style="display:none">Show last run</button>
      <button class="lc-opt-copy p-button p-button-sm" type="button" disabled>Copy report</button>
      <button class="lc-opt-again p-button p-button-sm" type="button" disabled>Run again</button>
      <button class="lc-opt-close p-button p-button-sm p-button-secondary" type="button">Close</button></div>
    <div class="lc-opt-body">Starting…</div>`;
  ov.appendChild(box);
  document.body.appendChild(ov);
  const body = box.querySelector(".lc-opt-body");
  let token = null;
  const close = () => {
    if (token) token.cancelled = true; // a run in progress stops and puts the canvas back
    ov.remove();
  };
  box.querySelector(".lc-opt-close").onclick = close;
  ov.addEventListener("pointerdown", (e) => e.target === ov && !token && close()); // no accidental close mid-run
  let text = "";
  let current = "";
  let showingLast = false;
  const lastBtn = box.querySelector(".lc-opt-last");
  const paintLast = () => {
    const last = loadLast();
    lastBtn.style.display = last?.html ? "" : "none";
    lastBtn.textContent = showingLast ? "Back to this run" : "Show last run";
  };
  lastBtn.onclick = () => {
    const last = loadLast();
    if (!last?.html) return;
    showingLast = !showingLast;
    body.innerHTML = showingLast
      ? `<div style="color:#fbbf24;margin-bottom:8px">Last run: ${esc(last.when)}${last.workflow ? `, ${esc(last.workflow)}` : ""}</div>` + last.html
      : current;
    paintLast();
  };
  box.querySelector(".lc-opt-copy").onclick = () => navigator.clipboard?.writeText(text);
  box.querySelector(".lc-opt-again").onclick = () => go();
  addCsvButton(box, ".lc-opt-copy", ".lc-opt-body", "Comfy Optimization Report");

  async function go() {
    if (running) {
      body.innerHTML = `<div style="padding:30px 0;text-align:center">A report is already running. Wait for it to finish.</div>`;
      return;
    }
    token = running = { cancelled: false };
    showingLast = false;
    paintLast();
    lastBtn.disabled = true;
    box.querySelector(".lc-opt-again").disabled = true;
    box.querySelector(".lc-opt-copy").disabled = true;
    ov.style.background = "transparent";
    box.style.opacity = "0.92";
    let scan = null;
    const scanP = api
      .fetchApi("/lc123/optimizer/scan")
      .then((r) => r.json())
      .then((j) => (scan = j))
      .catch(() => null);
    let phases = [];
    let failed = null;
    try {
      phases = await liveTest((s) => (body.innerHTML = `<div style="padding:30px 0;text-align:center">Live test: <b>${esc(s)}</b>… keep the mouse still.</div>`), token);
    } catch (e) {
      failed = e;
    }
    const cancelled = token.cancelled;
    running = null;
    token = null;
    ov.style.background = "rgba(0,0,0,0.55)";
    box.style.opacity = "1";
    if (cancelled) {
      body.innerHTML = `<div style="padding:30px 0;text-align:center">Stopped. (Another workflow was opened, or the report was closed.)</div>`;
    } else if (failed) {
      body.innerHTML = `<div style="padding:30px 0;text-align:center;color:#f87171">The live test failed: ${esc(failed?.message || failed)}</div>`;
    } else {
      body.innerHTML = `<div style="padding:30px 0;text-align:center">Scanning installed packs…</div>`;
      await scanP;
      try {
        render(buildReport(phases, scan), scan);
      } catch (e) {
        body.innerHTML = `<div style="padding:30px 0;text-align:center;color:#f87171">The report could not be built: ${esc(e?.message || e)}</div>`;
        console.warn("[LC123] Optimization report", e);
      }
    }
    lastBtn.disabled = false;
    box.querySelector(".lc-opt-again").disabled = false;
    box.querySelector(".lc-opt-copy").disabled = false;
  }

  function render(rep, scan) {
    const lines = [];
    const h = [];
    const prev = loadLast();
    h.push(`<div style="color:#fbbf24;font-weight:700;margin-bottom:6px">Only node packs used in this workflow were analyzed.</div>`);
    lines.push("Only node packs used in this workflow were analyzed.");
    h.push(`<div style="color:#9aa3ad;margin-bottom:10px">${rep.nodes} nodes, ${rep.links} links. Times are milliseconds. A smooth 60 fps frame has about 16 ms in total.</div>`);
    h.push(`<table style="width:100%;border-collapse:collapse;margin-bottom:14px">`);
    h.push(`<tr style="color:#9aa3ad;text-align:left"><th>Test</th><th>Frames per second</th><th>Canvas draw per frame</th><th>Nodes</th><th>Links</th><th>Groups</th></tr>`);
    lines.push(`Comfy Optimization Report: ${rep.nodes} nodes, ${rep.links} links`);
    for (const ph of rep.phases) {
      const fps = ph.frames / ph.seconds;
      const per = ph.drawMs / Math.max(1, ph.draws);
      const col = per > 12 ? "#f87171" : per > 6 ? "#fbbf24" : "#86efac";
      const f = Math.max(1, ph.draws);
      let nodeMs = 0;
      for (const v of ph.nodes.values()) nodeMs += v.ms;
      const parts = [nodeMs / f, ph.links / f, ph.groups / f].map((v) => v.toFixed(2) + " ms");
      h.push(`<tr><td>${esc(ph.name)}</td><td>${fps.toFixed(0)}</td><td style="color:${col}">${per.toFixed(2)} ms</td><td>${parts[0]}</td><td>${parts[1]}</td><td>${parts[2]}</td></tr>`);
      lines.push(`${ph.name}: ${fps.toFixed(0)} fps, draw ${per.toFixed(2)} ms/frame (nodes ${parts[0]}, links ${parts[1]}, groups ${parts[2]})`);
    }
    h.push(`</table>`);

    const snap = snapshot(rep);
    if (prev?.snap) improvements(prev, snap, h, lines);

    const KINDS = [
      ["pack", "That pack's own settings (current value checked)", "#60a5fa"],
      ["lc123", "LC optimization settings", "#86efac"],
      ["comfy", "ComfyUI settings", "#c4b5fd"],
      ["sidebar", "Sidebar tabs", "#fbbf24"],
      ["required", "Required to function (no setting, part of how the pack works)", "#9aa3ad"],
    ];
    h.push(`<div style="font-weight:600;font-size:14px;margin:6px 0">Recommendations</div>`);
    h.push(`<div style="color:#9aa3ad;font-size:12px;margin-bottom:4px">⚠️ big gain · ✅ worthwhile gain · 💡 small gain · ⚪ already set · ➖ does not apply · ℹ️ required, no setting</div>`);
    lines.push("", "Recommendations (⚠️ big gain, ✅ worthwhile, 💡 small, ⚪ already set, ➖ does not apply, ℹ️ required):");
    if (!rep.tips.length) h.push(`<div style="color:#86efac">Nothing stands out. The canvas is in good shape.</div>`);
    for (const [kind, title, col] of KINDS) {
      const list = rep.tips.filter((t) => t.kind === kind);
      if (!list.length) continue;
      h.push(`<div style="margin:10px 0 4px;color:${col};font-weight:600">${esc(title)}</div>`);
      lines.push("", title + ":");
      for (const t of list.slice(0, 20)) {
        const icon = ICON[t.level] || "";
        const dim = t.level === 0 || t.level === -1 ? "opacity:0.6;" : "";
        h.push(`<div style="margin:4px 0;padding:6px 10px;background:#252a31;border-left:3px solid ${col};border-radius:4px;${dim}">${icon} <b>${esc(t.pack)}</b>: ${esc(t.text)}</div>`);
        lines.push(`${icon} ${t.pack}: ${t.text}`);
      }
    }

    h.push(`<div style="font-weight:600;font-size:14px;margin:14px 0 6px">By pack</div>`);
    h.push(`<table style="width:100%;border-collapse:collapse;font-size:12px"><tr style="color:#9aa3ad;text-align:left"><th>Pack</th><th>Nodes</th><th>Node draw ms/frame</th><th>Loop ms/frame</th><th>Timers</th><th>DOM widgets</th><th>Found in its files</th></tr>`);
    lines.push("", "By pack (nodes | draw ms/frame | loop ms/frame | timers | DOM widgets | file scan):");
    const rows = [...rep.packs].sort((a, b) => b[1].draw + b[1].raf - (a[1].draw + a[1].raf));
    for (const [k, p] of rows) {
      const sc = p.scan && !p.scan.error ? Object.entries(p.scan).map(([kind, v]) => `${scan.labels[kind] || kind} ×${v.count}`).join("; ") : "";
      if (!rep.used(k) || (!p.draw && !p.raf && !p.timerCount && !p.dom && !sc)) continue;
      const timers = p.timerCount ? `${p.timerCount} (${p.timer.toFixed(1)} ms/s)` : "";
      h.push(`<tr style="border-top:1px solid #2d333b"><td>${esc(k)}</td><td>${p.nodes || ""}</td><td>${p.draw ? p.draw.toFixed(2) : ""}</td><td>${p.raf ? p.raf.toFixed(2) : ""}</td><td>${timers}</td><td>${p.dom || ""}</td><td style="color:#9aa3ad">${esc(sc)}</td></tr>`);
      lines.push(`${k} | ${p.nodes} | ${p.draw.toFixed(2)} | ${p.raf.toFixed(2)} | ${timers || "-"} | ${p.dom} | ${sc || "-"}`);
    }
    h.push(`</table>`);
    h.push(`<div style="color:#9aa3ad;margin-top:10px;font-size:12px">Timers are counted from when LC123 loaded, so a pack that started its timers earlier only shows up in the file scan. The file scan lists what a pack's code can do, not what it is doing right now.</div>`);
    current = h.join("");
    body.innerHTML = current;
    text = lines.join("\n");
    saveLast({ when: new Date().toLocaleString(), workflow: workflowName(), html: current, snap }); // only the last run is kept
    paintLast();
  }
  go();
}

app.registerExtension({
  name: "LC123.Optimizer",
  settings: [
    {
      id: "LC123.Optimization.FastCancel",
      sortOrder: 30, // first under Optimization
      name: "Fast cancel",
      category: ["LC Settings ⚙️", "Optimization", "Fast cancel"],
      type: "boolean",
      defaultValue: true,
      tooltip:
        "Cancel stops a run within a fraction of a step instead of waiting for the whole step to finish (heavy models, USDU, video). Every model block checks the Cancel button. Works with every sampler, nothing to wire.",
    },
    {
      id: "LC123.Optimization.FreeTextEncoder",
      sortOrder: 29, // right under Fast cancel
      name: "Free text encoder before sampling",
      category: ["LC Settings ⚙️", "Optimization", "Free text encoder"],
      type: "boolean",
      defaultValue: true,
      tooltip:
        "When sampling starts, any big text encoder (1 GB or more) still in VRAM is moved to RAM, so the diffusion model gets the whole card. Biggest win on H3 and Krea 2. A new prompt reloads the encoder from RAM in a second or two.",
    },
    {
      id: "LC123.Optimization.Report",
      sortOrder: 20, // above the System & Model Optimization Report
      name: "Comfy Optimization Report",
      category: ["LC Settings ⚙️", "Optimization", "Comfy Optimization Report"],
      defaultValue: "",
      tooltip:
        "Pans the canvas by itself for a few seconds, times what every installed pack draws and runs, scans their files, and lists what slows the canvas down, biggest first. Nothing is changed.",
      type: () => {
        const b = document.createElement("button");
        b.type = "button";
        b.textContent = "Open Comfy Optimization Report";
        b.className = "p-button p-component p-button-sm";
        b.onclick = (e) => {
          e.preventDefault();
          e.stopPropagation();
          // close the settings dialog first so the live test can see the canvas
          document.querySelector('.p-dialog-mask .p-dialog-close-button, .p-dialog .p-dialog-header-close, [role="dialog"] button[aria-label="Close dialog"]')?.click(); // old and new settings dialog
          setTimeout(openWindow, 250);
        };
        return b;
      },
    },
  ],
  getCanvasMenuItems() {
    return [null, { content: "Comfy Optimization Report", callback: () => openWindow() }];
  },
});

window.LC123Optimizer = { open: openWindow };
