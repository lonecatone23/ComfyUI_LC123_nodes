/**
 * LC Bypass Relay — JS-only virtual node, same registration as LC Bypasser.
 */
import { app } from "../../scripts/app.js";
import { NODE_PROPERTY_EVENT, graphEventsAvailable } from "./lc_graph_events.js";

const TYPE = "LCBypassRelay";
const TYPES = new Set([TYPE]);
const HUBS = new Set(["LC Bypasser", "LC Mute"]);
const COLOR = "#28281E";
const LIVE = 0;
const MUTE = 2;
const BYPASS = 4;

function graph() {
  return app.graph || app.canvas?.graph || null;
}

// the graphs a tick walks: the root and, when a subgraph is open, the one on screen
function tickGraphs() {
  const out = [];
  const root = graph();
  if (root) out.push(root);
  const shown = app.canvas?.graph;
  if (shown && shown !== root) out.push(shown);
  return out;
}

function linkById(g, id) {
  if (!g || id == null) return null;
  if (g.links?.[id]) return g.links[id];
  if (typeof g.getLink === "function") {
    try { return g.getLink(id); } catch (_) {}
  }
  if (g.links && typeof g.links.get === "function") {
    try { return g.links.get(id); } catch (_) {}
  }
  return null;
}

function nodeById(g, id) {
  return g?.getNodeById?.(id) || null;
}

function originOf(g, input) {
  if (!input || input.link == null) return null;
  const l = linkById(g, input.link);
  if (!l) return null;
  return nodeById(g, l.origin_id ?? l.sourceId ?? l.fromId);
}

function allNodes(g) {
  if (!g) return [];
  if (Array.isArray(g._nodes)) return g._nodes;
  if (Array.isArray(g.nodes)) return g.nodes;
  return [];
}

function setMode(n, mode) {
  if (!n || n.mode === mode) return;
  n.mode = mode;
  try {
    n.onModeChange?.(mode);
    n.setDirtyCanvas?.(true, true);
  } catch (_) {}
}

function hug(node) {
  const slots = (node.inputs || []).filter((i) => i && i.type !== "BOOLEAN").length;
  const h = Math.max(52, 28 + slots * 24);
  if (!node.size) node.size = [270, h];
  node.size[0] = Math.max(node.size[0] || 270, 240);
  node.size[1] = h;
}

function grow(node) {
  if (!node.inputs) node.inputs = [];
  const stars = node.inputs.filter((i) => i && i.type !== "BOOLEAN");
  stars.forEach((inp, i) => {
    inp.name = "any_" + (i + 1);
    inp.type = "*";
  });
  if (!stars.length) node.addInput("any_1", "*");
  const last = node.inputs.filter((i) => i && i.type !== "BOOLEAN").pop();
  const filled = last && last.link != null;
  const count = node.inputs.filter((i) => i && i.type !== "BOOLEAN").length;
  if (filled && count < 16) node.addInput("any_" + (count + 1), "*");
  let empty = 0;
  for (let i = node.inputs.length - 1; i >= 0; i--) {
    const inp = node.inputs[i];
    if (!inp || inp.type === "BOOLEAN") continue;
    if (inp.link == null) {
      empty++;
      if (empty > 1) node.removeInput(i);
    }
  }
  hug(node);
}

const OLD_TYPES = new Set([
  "LC Bypass Relay",
  "LC Mute Bypass Relay",
  "LC Mute Bypass Repeater",
  "LC Bypass Fanout",
]);

function remapType(node) {
  if (!node) return;
  if (OLD_TYPES.has(node.type)) {
    node.type = TYPE;
    node.comfyClass = TYPE;
    node.constructor.comfyClass = TYPE;
  }
}

function isRelay(n) {
  return n && TYPES.has(n.type);
}

function patchHubSettle() {
  for (const hubType of HUBS) {
    const cls = LiteGraph.registered_node_types?.[hubType];
    if (!cls || cls.prototype._lcSettlePatched) continue;
    cls.prototype._lcSettlePatched = true;
    // a hub toggle (click, panel, restriction, or its 1 s applyModes) stamps this graph's relays straight away,
    // instead of waiting for the next safety tick
    for (const fn of ["onToggleWidget", "applyModes"]) {
      const orig = cls.prototype[fn];
      if (typeof orig !== "function" || orig._lcRelayWrapped) continue;
      const wrapped = function () {
        // while the hub is mid-way (mode set, widget not yet), mode events wait for this one stamp at the end
        hubBusy++;
        let r;
        try {
          r = orig.apply(this, arguments);
        } finally {
          hubBusy--;
        }
        try {
          stampGraph(this.graph ?? graph());
        } catch (_) {}
        return r;
      };
      wrapped._lcRelayWrapped = true;
      cls.prototype[fn] = wrapped;
    }
    const onCfg = cls.prototype.onConfigure;
    cls.prototype.onConfigure = function (info) {
      const r = onCfg?.apply(this, arguments);
      this._lcHubReady = false;
      clearTimeout(this._lcHubReadyTimer);
      this._lcHubReadyTimer = setTimeout(() => {
        this._lcHubReady = true;
      }, 1500);
      return r;
    };
  }
}

// relay id -> the mode its hub asks for, built once per graph pass instead of once per relay. Same first-match order
// as before: hubs in graph order, pairs in slot order, the first hub pair wired to a relay decides.
function hubControl(g) {
  const map = new Map();
  for (const hub of allNodes(g)) {
    if (!HUBS.has(hub.type)) continue;
    if (hub._lcHubReady === false || hub._lcStabilizing) continue;
    const pairs = Math.floor((hub.inputs?.length || 0) / 2);
    for (let p = 0; p < pairs; p++) {
      const o = originOf(g, hub.inputs[p * 2]);
      if (!o || map.has(o.id)) continue;
      const w = hub.widgets?.[p];
      // A missing widget must not enable the relay during hub reconstruction.
      if (!w) { map.set(o.id, null); continue; }
      const on = w.value !== false;
      map.set(o.id, on ? LIVE : hub.type === "LC Mute" || hub._lcOffMode === MUTE ? MUTE : BYPASS);
    }
  }
  return map;
}

function stamp(relay, control) {
  if (!relay) return;
  const g = relay.graph ?? graph(); // the relay's own graph, so it also works inside a subgraph
  if (!g) return;
  const map = control ?? hubControl(g);
  let mode = map.has(relay.id) ? map.get(relay.id) : null;
  if (mode == null) {
    mode = relay.mode === MUTE || relay.mode === BYPASS ? relay.mode : LIVE;
  }
  relay._lcMode = mode;
  setMode(relay, mode);
  for (const inp of relay.inputs || []) {
    if (!inp || inp.link == null) continue;
    const o = originOf(g, inp);
    if (o && !HUBS.has(o.type) && !isRelay(o)) setMode(o, mode);
  }
}

// stamp every relay in one graph, sharing one hub map; re-entry (a stamped mode firing a mode event) is skipped,
// the outer pass finishes the job
let stamping = false;
let hubBusy = 0;
function stampOne(relay) {
  if (stamping) return stamp(relay);
  stamping = true;
  try {
    stamp(relay);
  } finally {
    stamping = false;
  }
}
function stampGraph(g) {
  if (!g || stamping) return;
  stamping = true;
  try {
    let control = null;
    for (const n of allNodes(g)) {
      if (!isRelay(n)) continue;
      if (!control) control = hubControl(g);
      stamp(n, control);
    }
  } finally {
    stamping = false;
  }
}

// live relays, so the safety tick costs nothing in a workflow without one
const live = new Set();

// Mode changes are announced on each graph (root or subgraph) as "node:property:changed": a relay (or a node under
// one) changed by hand is re-stamped at once, like the old 80 ms tick did a moment later.
// Mode events fired while a workflow loads are ignored (the hubs are not configured yet); the tick stamps after.
const hookedGraphs = new WeakSet();
function isLoading(g) {
  return !!(g?._lcRelayLoading || g?.rootGraph?._lcRelayLoading);
}
function hookGraph(g) {
  if (!graphEventsAvailable(g) || hookedGraphs.has(g)) return;
  hookedGraphs.add(g);
  g.events.addEventListener("configuring", () => {
    // configure runs synchronously, so a zero timer always lands after it (even if the load is cancelled)
    g._lcRelayLoading = true;
    setTimeout(() => {
      g._lcRelayLoading = false;
    }, 0);
  });
  g.events.addEventListener(NODE_PROPERTY_EVENT, (e) => {
    if (e?.detail?.property !== "mode" || !live.size || stamping || hubBusy || isLoading(g)) return;
    try {
      stampGraph(g);
    } catch (_) {}
  });
}

app.registerExtension({
  name: "LC123.BypassRelay",

  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData?.name !== TYPE) return;
    const onCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const r = onCreated?.apply(this, arguments);
      this.color = this.color || COLOR;
      this.bgcolor = this.bgcolor || COLOR;
      if (!this.inputs?.length) this.addInput("", "*");
      if (!this.outputs?.length) this.addOutput("OPT_CONNECTION", "*");
      grow(this);
      this.properties = this.properties || {};
      live.add(this);
      return r;
    };
    const onAdded = nodeType.prototype.onAdded;
    nodeType.prototype.onAdded = function () {
      const r = onAdded?.apply(this, arguments);
      live.add(this);
      hookGraph(this.graph);
      return r;
    };
    const onConfigure = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function () {
      const r = onConfigure?.apply(this, arguments);
      live.add(this);
      hookGraph(this.graph);
      return r;
    };
    const onRemoved = nodeType.prototype.onRemoved;
    nodeType.prototype.onRemoved = function () {
      const r = onRemoved?.apply(this, arguments);
      live.delete(this);
      return r;
    };
    const onConn = nodeType.prototype.onConnectionsChange;
    nodeType.prototype.onConnectionsChange = function () {
      const r = onConn?.apply(this, arguments);
      grow(this);
      stampOne(this);
      return r;
    };
  },

  loadedGraphNode(node) {
    remapType(node);
    // a relay saved under an old type name is remapped here, not built by this node type: track it too
    if (isRelay(node)) {
      live.add(node);
      hookGraph(node.graph);
    }
  },

  async setup() {
    // Safety tick. Hub toggles and mode events stamp at once, so this only catches what has no event (a new wire
    // to a hub, a hub finishing its load settle). A frontend without graph events keeps the old 80 ms pace.
    hookGraph(graph()); // hooked before the first workflow loads, so that load is seen as a load
    // mode changes arrive as events (lc_graph_events.js), so the safety tick only needs 300 ms; 80 ms without events
    const period = graphEventsAvailable(graph()) ? 300 : 80;
    setInterval(() => {
      try {
        patchHubSettle();
        if (!live.size) return;
        for (const n of live) if (!n.graph) live.delete(n); // relays that left without onRemoved (old type names)
        const graphs = tickGraphs();
        for (const g of graphs) {
          hookGraph(g);
          stampGraph(g);
        }
      } catch (_) {}
    }, period);
  },
});

console.log("[LC123.BypassRelay] chrome on LCBypassRelay");
