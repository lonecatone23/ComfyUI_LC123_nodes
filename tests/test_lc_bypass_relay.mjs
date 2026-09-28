// Deterministic frontend lifecycle tests; no server, GPU, or workflow writes.
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import { test } from "node:test";

const sourceRoot = process.env.LC_TEST_WEB_DIR
  ? new URL(`file:///${process.env.LC_TEST_WEB_DIR.replaceAll("\\", "/")}/`)
  : new URL("../web/", import.meta.url);

async function harness(workflow) {
  const extensions = [], timers = new Map(), intervals = [];
  let timerId = 0;
  class Node {
    constructor(title) {
      Object.assign(this, { title, inputs: [], outputs: [], widgets: [], properties: {}, mode: 0 });
    }
    addInput(name, type) { this.inputs.push({ name, type, link: null }); }
    addOutput(name, type) { this.outputs.push({ name, type, links: [] }); }
    removeInput(index) { this.inputs.splice(index, 1); }
    addProperty(name, value) { this.properties[name] = value; }
    addWidget(type, name, value, callback, options) {
      const widget = { type, name, value, callback, options };
      this.widgets.push(widget);
      return widget;
    }
    setDirtyCanvas() {}
  }
  const graph = { _nodes: [], links: {}, getNodeById(id) { return this._nodes.find(n => n.id === id); } };
  const app = { graph, registerExtension(ext) { extensions.push(ext); } };
  const LiteGraph = { registered_node_types: {}, registerNodeType(type, cls) { this.registered_node_types[type] = cls; } };
  const context = vm.createContext({
    app, LiteGraph, window: {}, LGraphNode: Node, lcHasSavedColor: () => false,
    console: { log() {}, warn(...args) { throw new Error(args.join(" ")); } },
    setTimeout(fn) { timers.set(++timerId, fn); return timerId; },
    clearTimeout(id) { timers.delete(id); },
    setInterval(fn) { intervals.push(fn); },
  });
  const bridge = fs.readFileSync(new URL("lc_graph_events.js", sourceRoot), "utf8").replace(/^export /gm, "");
  vm.runInContext(bridge, context, { filename: "lc_graph_events.js" });
  for (const file of ["lc_bypasser.js", "lc_mode_relay.js"]) {
    const source = fs.readFileSync(new URL(file, sourceRoot), "utf8").replace(/^import .*;\r?\n/gm, "");
    vm.runInContext(`(() => {${source}\n})()`, context, { filename: file });
  }
  extensions[0].registerCustomNodes();
  class Relay extends Node {}
  await extensions[1].beforeRegisterNodeDef(Relay, { name: "LCBypassRelay" });
  for (const ext of extensions) await ext.setup();
  const create = (type, id, mode = 4) => {
    const Cls = type === "LCBypassRelay" ? Relay : LiteGraph.registered_node_types[type] || Node;
    const node = new Cls(type);
    Object.assign(node, { type, id, mode, graph });
    graph._nodes.push(node);
    node.onAdded?.();
    return node;
  };
  if (workflow) {
    for (const data of workflow.nodes) {
      const node = create(data.type, data.id, data.mode);
      for (const key of ["title", "inputs", "outputs", "properties", "size"]) {
        if (data[key] != null) node[key] = structuredClone(data[key]);
      }
      node.widgets = (data.widgets_values || []).map(value => ({ value }));
    }
    for (const [id, origin_id, origin_slot, target_id, target_slot, type] of workflow.links) {
      graph.links[id] = { id, origin_id, origin_slot, target_id, target_slot, type };
    }
  }
  const tick = () => intervals.forEach(fn => fn());
  const settle = () => {
    for (const [id, fn] of [...timers]) { timers.delete(id); fn(); }
    tick();
  };
  const connect = (origin, target, slot) => {
    const id = Math.max(0, ...Object.keys(graph.links).map(Number)) + 1;
    graph.links[id] = { id, origin_id: origin.id, origin_slot: 0, target_id: target.id, target_slot: slot };
    target.inputs[slot].link = id;
    return id;
  };
  return { graph, create, tick, settle, connect };
}

async function fixture(type = "LC Bypasser", mode = 4) {
  const h = await harness();
  const hub = h.create(type, 1, 0), relay = h.create("LCBypassRelay", 2, mode);
  relay.onNodeCreated();
  const child = h.create("Skin", 3, mode);
  h.connect(child, relay, 0);
  h.connect(relay, hub, 0);
  return { ...h, hub, relay, child };
}

test("missing hub widget preserves bypass before either connection callback", async () => {
  const h = await fixture();
  h.relay.onConnectionsChange();
  assert.equal(h.relay.mode, 4);
  assert.equal(h.child.mode, 4);
  h.hub.onConnectionsChange();
  h.settle();
  assert.equal(h.hub.widgets[0].value, false);
  assert.equal(h.child.mode, 4);
});

test("connection rebuild ignores stale enabled widgets, including periodic hub sync", async () => {
  const h = await fixture();
  h.hub.widgets = [{ value: true }];
  h.hub.onConnectionsChange();
  h.tick();
  h.relay.onConnectionsChange();
  assert.equal(h.child.mode, 4);
  h.settle();
  assert.equal(h.hub.widgets[0].value, false);
  for (let i = 0; i < 20; i++) h.tick();
  assert.equal(h.child.mode, 4);
});

for (const [type, off] of [["LC Bypasser", 4], ["LC Mute", 2]]) {
  test(`${type}: rebuild preserves off, explicit toggles still propagate`, async () => {
    const h = await fixture(type, off);
    h.hub.onConnectionsChange();
    h.relay.onConnectionsChange();
    h.settle();
    assert.equal(h.child.mode, off);
    h.hub.onToggleWidget(0, true);
    h.tick();
    assert.equal(h.child.mode, 0);
    h.hub.onToggleWidget(0, false);
    h.tick();
    assert.equal(h.child.mode, off);
  });
}

test("BOOLEAN input still controls the relay after rebuilding", async () => {
  const h = await fixture();
  const bool = h.create("Boolean", 4, 0);
  bool.widgets = [{ name: "value", value: true }];
  h.connect(bool, h.hub, 1);
  h.hub.onConnectionsChange();
  h.settle();
  assert.equal(h.child.mode, 0);
  bool.widgets[0].value = false;
  h.tick();
  assert.equal(h.child.mode, 4);
});

test("unconnected relay continues to propagate its own mode", async () => {
  const h = await fixture();
  h.hub.inputs[0].link = null;
  h.relay.onConnectionsChange();
  assert.equal(h.child.mode, 4);
  h.relay.mode = 0;
  h.tick();
  assert.equal(h.child.mode, 0);
});

test("Krea2 Skin Upscaler reconnect stays bypassed", { skip: !process.env.LC_TEST_WORKFLOW }, async () => {
  const workflow = JSON.parse(fs.readFileSync(process.env.LC_TEST_WORKFLOW, "utf8"));
  const h = await harness(workflow);
  const hub = h.graph.getNodeById(3469), relay = h.graph.getNodeById(3467);
  const skin = h.graph.getNodeById(3420), model = h.graph.getNodeById(3419);
  const states = () => [relay.mode, skin.mode, model.mode];
  assert.deepEqual(states(), [4, 4, 4]);
  const oldSlot = hub.inputs.findIndex(inp => h.graph.links[inp.link]?.origin_id === relay.id);
  const oldLink = hub.inputs[oldSlot].link;
  hub.inputs[oldSlot].link = null;
  delete h.graph.links[oldLink];
  hub.onConnectionsChange();
  h.settle();
  const newSlot = hub.inputs.length - 2;
  h.connect(relay, hub, newSlot);
  hub.onConnectionsChange();
  relay.onConnectionsChange();
  assert.deepEqual(states(), [4, 4, 4]);
  h.tick();
  assert.deepEqual(states(), [4, 4, 4]);
  h.settle();
  assert.equal(hub.widgets[newSlot / 2].value, false);
  for (let i = 0; i < 50; i++) h.tick();
  assert.deepEqual(states(), [4, 4, 4]);
  hub.onToggleWidget(newSlot / 2, true);
  h.tick();
  assert.deepEqual(states(), [0, 0, 0]);
  hub.onToggleWidget(newSlot / 2, false);
  h.tick();
  assert.deepEqual(states(), [4, 4, 4]);
});
