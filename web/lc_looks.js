/**
 * LC Looks: picking a look fills that node's sliders from lc_looks.json. Moving one of those sliders
 * switches the node to Custom. A saved workflow set to a look gets that look's current values when it loads,
 * so retuned looks reach old workflows; a node set to Custom is never touched.
 */
import { app } from "../../scripts/app.js";

let LOOKS = null;
const ready = fetch(new URL("./lc_looks.json", import.meta.url))
  .then((r) => r.json())
  .then((j) => (LOOKS = j))
  .catch((e) => console.warn("[LC123] looks not loaded", e));

const wget = (node, name) => (node.widgets || []).find((w) => w.name === name);

function tableFor(node, table) {
  if (!table._by) return table;
  const key = wget(node, table._by)?.value;
  return table[key] || null;
}

function controlledKeys(table) {
  const keys = new Set();
  const add = (t) => Object.values(t).forEach((v) => v && typeof v === "object" && Object.keys(v).forEach((k) => keys.add(k)));
  if (table._by) Object.entries(table).forEach(([k, t]) => k !== "_by" && add(t));
  else add(table);
  return keys;
}

function applyLook(node, table, look) {
  const vals = tableFor(node, table)?.[look];
  if (!vals) return;
  node._lcApplyingLook = true;
  try {
    for (const [k, v] of Object.entries(vals)) {
      const w = wget(node, k);
      if (!w) continue;
      w.value = v;
      try { w.callback?.(v, app.canvas, node); } catch (_) {}
    }
  } finally {
    node._lcApplyingLook = false;
  }
  node.setDirtyCanvas?.(true, true);
}

function hook(node, table) {
  if (node._lcLooksHooked) return;
  node._lcLooksHooked = true;
  const lookW = wget(node, "look");
  if (!lookW) return;
  const prevLook = lookW.callback;
  lookW.callback = function (value, ...rest) {
    if (value && value !== "Custom") applyLook(node, table, value);
    return prevLook?.apply(this, [value, ...rest]);
  };
  for (const key of controlledKeys(table)) {
    const w = wget(node, key);
    if (!w || w._lcLookSnap) continue;
    w._lcLookSnap = true;
    const prev = w.callback;
    w.callback = function (value, ...rest) {
      if (!node._lcApplyingLook && lookW.value !== "Custom") lookW.value = "Custom";
      return prev?.apply(this, [value, ...rest]);
    };
  }
  // Bloom: switching mode keeps the chosen look, with that mode's values
  if (table._by) {
    const byW = wget(node, table._by);
    if (byW) {
      const prev = byW.callback;
      byW.callback = function (value, ...rest) {
        const r = prev?.apply(this, [value, ...rest]);
        if (lookW.value && lookW.value !== "Custom") applyLook(node, table, lookW.value);
        return r;
      };
    }
  }
}

app.registerExtension({
  name: "LC123.Looks",
  async nodeCreated(node) {
    await ready;
    const type = node.comfyClass || node.type;
    const table = LOOKS?.nodes?.[type];
    if (table) hook(node, table);
  },
  async loadedGraphNode(node) {
    await ready;
    const type = node.comfyClass || node.type;
    const table = LOOKS?.nodes?.[type];
    if (!table) return;
    hook(node, table);
    const look = wget(node, "look")?.value;
    if (look && look !== "Custom") applyLook(node, table, look);
  },
});
