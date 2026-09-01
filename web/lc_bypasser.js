/**
 * LC Bypasser + LC Mute + LC Bypasser Panel
 * --------------------------------
 * LC Bypasser — * + enable sockets AND toggle widgets. Off = bypass (pass-through).
 * LC Mute     — identical, Off = mute (never run).
 * LC Bypasser Panel — widgets-only remote for Bypasser, Mute, or Groups Bypasser.
 */

import { app } from "../../scripts/app.js";

function lcApplyLaunchColor(node, color, bgcolor) {
  if (!node) return;
  const c = String(node.color || "").trim().toLowerCase();
  const stock = !c || c === "undefined" || c === "null" ||
    ["#333", "#333333", "#353535", "#232", "#223", "#222", "#222222"].includes(c);
  if (!stock) return;
  try {
    node.color = color;
    node.bgcolor = bgcolor || color;
  } catch (_) {}
}

const HUB_TYPE = "LC Bypasser";
const MUTE_TYPE = "LC Mute";
const GROUPS_TYPE = "LC Groups Bypasser";
const PANEL_TYPE = "LC Bypasser Panel";
const MODE_ALWAYS = 0;
const MODE_NEVER = 2; // Comfy mute
const MODE_BYPASS = 4;

function isNodeHub(type) {
  return type === HUB_TYPE || type === MUTE_TYPE;
}

function changeMode(node, mode) {
  if (!node || node.mode === mode) return;
  node.mode = mode;
  try {
    node.setDirtyCanvas?.(true, true);
  } catch (_) {}
}

function getLinkedOrigin(graph, input) {
  if (!input || input.link == null || !graph) return null;
  const link = graph.links?.[input.link];
  if (!link) return null;
  return graph.getNodeById?.(link.origin_id) || null;
}

function coerceBool(v) {
  if (v === true || v === false) return v;
  if (v === 1 || v === "1" || v === "true" || v === "yes" || v === "on") return true;
  if (v === 0 || v === "0" || v === "false" || v === "no" || v === "off") return false;
  return null;
}

function isInvertNode(node) {
  if (!node) return false;
  const s = `${node.type || ""} ${node.comfyClass || ""} ${node.title || ""}`.toLowerCase();
  return /invert|flip|negate|boolean.?not|not.?boolean|lcinvert/.test(s);
}

function readBooleanFromWidgets(origin) {
  if (!origin?.widgets?.length) return null;
  const preferred = ["value", "boolean", "boolean_value", "toggle", "enabled", "enable"];
  for (const name of preferred) {
    const w = origin.widgets.find((x) => x && x.name === name);
    if (!w) continue;
    const c = coerceBool(w.value);
    if (c !== null) return c;
    if (w.type === "toggle") return !!w.value;
  }
  for (const w of origin.widgets) {
    if (!w) continue;
    const c = coerceBool(w.value);
    if (c !== null) return c;
    if (w.type === "toggle") return !!w.value;
  }
  return null;
}

function resolveBoolean(graph, input, depth = 0) {
  if (!input || input.link == null || !graph || depth > 24) return null;
  const link = graph.links?.[input.link];
  if (!link) return null;
  const origin = graph.getNodeById?.(link.origin_id);
  if (!origin) return null;
  const invert = isInvertNode(origin);
  const boolIns = (origin.inputs || []).filter(
    (i) => i && (i.type === "BOOLEAN" || /bool|enable/i.test(i.name || ""))
  );
  if (boolIns.length) {
    for (const bi of boolIns) {
      const v = resolveBoolean(graph, bi, depth + 1);
      if (v !== null) return invert ? !v : v;
    }
  }
  const fromW = readBooleanFromWidgets(origin);
  if (fromW !== null) return invert ? !fromW : fromW;
  return null;
}

function setWidgetLocked(w, locked) {
  if (!w) return;
  w._lcLocked = !!locked;
  w.disabled = !!locked;
  const base = (w._lcNameClean || w.name || "").replace(/^\s*🔒\s*/, "");
  w._lcNameClean = base;
  w.name = locked ? `🔒 ${base}` : base;
}

function nodeHubTargets(hub, graph) {
  const out = [];
  if (!hub?.inputs) return out;
  const pairCount = Math.floor(hub.inputs.length / 2);
  for (let p = 0; p < pairCount; p++) {
    const t = hub.inputs[p * 2];
    const e = hub.inputs[p * 2 + 1];
    if (!t || t.link == null) continue;
    const origin = getLinkedOrigin(graph, t);
    if (!origin) continue;
    out.push({
      kind: "node",
      origin,
      enableInput: e,
      index: p,
      title: origin.title || origin.type || `Slot ${p + 1}`,
    });
  }
  return out;
}

/** Groups bypasser: one widget/input index per group */
function groupsHubTargets(hub) {
  const out = [];
  if (!hub) return out;
  const groups = hub._lcGroups || [];
  const n = Math.max(groups.length, (hub.widgets || []).length);
  for (let i = 0; i < n; i++) {
    const g = groups[i];
    const title = g?.title || hub.widgets?.[i]?._lcNameClean || hub.widgets?.[i]?.name || `Group ${i + 1}`;
    const clean = String(title).replace(/^\s*🔒\s*/, "").replace(/^Enable\s+/i, "");
    out.push({
      kind: "group",
      group: g,
      enableInput: hub.inputs?.[i] || null,
      index: i,
      title: clean,
    });
  }
  return out;
}

function resolveHub(node, graph) {
  if (!node) return null;
  if (isNodeHub(node.type) || node.type === GROUPS_TYPE) return node;
  return null;
}

app.registerExtension({
  name: "LC123.Bypasser",

  registerCustomNodes() {
    // ═══════════ LC Bypasser (classic: sockets + widgets) ═══════════
    class LCBypasser extends LGraphNode {
      constructor() {
        // LiteGraph always does `new Class(title)` — ignore that arg.
        super();
        this._lcOffMode = this.constructor.lcOffMode ?? MODE_BYPASS;
        this._lcOffMenu = this.constructor.lcOffMenu || "Bypass all";
        this.isVirtualNode = true;
        this.serialize_widgets = true;
        this.properties = this.properties || {};
        if (!this.properties.toggleRestriction) {
          this.properties.toggleRestriction = "default";
        }
        // Properties panel: combo dropdown
        try {
          this.addProperty(
            "toggleRestriction",
            this.properties.toggleRestriction || "default",
            "combo",
            { values: ["default", "max one", "always one"] }
          );
        } catch (_) {
          this.properties.toggleRestriction =
            this.properties.toggleRestriction || "default";
        }
        this.addInput("", "*");
        this.addInput("enable", "BOOLEAN");
        this.addOutput("OPT_CONNECTION", "*");
        lcApplyLaunchColor(this, "#28281E");
        this.size = [270, 50];
        this._lcTimer = null;
        this.description = LCBypasser.desc || this.description;
      }

      onNodeCreated() {
        this.scheduleStabilize(30);
      }
      onConfigure() {
        this.scheduleStabilize(80);
        this.scheduleStabilize(300);
      }

      onResize(size) {
        // Keep height at fitted minimum for current slot count
        const fitH = this._lcPanelFitH || Math.max(56, 34 + (this.widgets?.length || 0) * 24 + 20);
        if (size && size[1] < fitH) size[1] = fitH;
        if (size && size[0] < 260) size[0] = 260;
        return size;
      }
      scheduleStabilize(ms = 20) {
        clearTimeout(this._lcTimer);
        this._lcTimer = setTimeout(() => {
          try {
            this.stabilize();
            this.applyModes();
          } catch (e) {
            console.warn("[LC Bypasser] stabilize", e);
          }
        }, ms);
      }

      stabilize() {
        const graph = app.graph;
        const inputs = this.inputs || [];
        const targets = [];
        const enables = [];
        for (const inp of inputs) {
          if (!inp) continue;
          if (inp.type === "BOOLEAN") enables.push(inp);
          else targets.push(inp);
        }
        while (enables.length < targets.length) {
          enables.push({ name: "enable", type: "BOOLEAN", link: null });
        }
        const next = [];
        for (let i = 0; i < targets.length; i++) {
          const t = targets[i];
          if (t.link == null) continue;
          const origin = getLinkedOrigin(graph, t);
          t.name = origin ? origin.title || "" : t.name || "";
          t.type = "*";
          next.push(t);
          const e = enables[i] || { name: "enable", type: "BOOLEAN", link: null };
          e.name = "enable";
          e.type = "BOOLEAN";
          next.push(e);
        }
        next.push({ name: "", type: "*", link: null });
        next.push({ name: "enable", type: "BOOLEAN", link: null });
        this.inputs = next;
        this.syncWidgets();
        this.setDirtyCanvas?.(true, true);
      }

      syncWidgets() {
        if (!this.widgets) this.widgets = [];
        const graph = app.graph;
        const pairCount = Math.floor((this.inputs?.length || 0) / 2);
        let filled = 0;
        for (let p = 0; p < pairCount; p++) {
          if (this.inputs[p * 2]?.link != null) filled++;
        }
        while (this.widgets.length < filled) {
          const pair = this.widgets.length;
          this.addWidget(
            "toggle",
            `Enable ${pair + 1}`,
            true,
            (val) => this.onToggleWidget(pair, val),
            { on: "yes", off: "no" }
          );
        }
        while (this.widgets.length > filled) this.widgets.pop();

        for (let p = 0; p < filled; p++) {
          const t = this.inputs[p * 2];
          const e = this.inputs[p * 2 + 1];
          const w = this.widgets[p];
          const origin = getLinkedOrigin(graph, t);
          const title = origin?.title || origin?.type || `Slot ${p + 1}`;
          const driven = e?.link != null;
          w._lcNameClean = null;
          w.name = `Enable ${title}`;
          let enabled = w.value !== false;
          if (driven) {
            const bv = resolveBoolean(graph, e);
            if (bv !== null) enabled = bv;
            else if (origin) enabled = origin.mode === MODE_ALWAYS;
          } else if (origin) {
            enabled = origin.mode === MODE_ALWAYS;
          }
          w.value = enabled;
          setWidgetLocked(w, driven);
          if (!w._lcCallbackWrapped) {
            w._lcCallbackWrapped = true;
            const orig = w.callback;
            w.callback = (val, ...rest) => {
              if (w._lcLocked || w.disabled) return;
              return orig?.call(w, val, ...rest);
            };
          }
        }
        const minH = 70 + filled * 30;
        if (!this.size) this.size = [240, minH];
        if (this.size[1] < minH) this.size[1] = minH;
      }

      onToggleWidget(pair, value) {
        const e = this.inputs?.[pair * 2 + 1];
        if (e?.link != null) return;
        if (this.widgets?.[pair]?._lcLocked) return;
        const graph = app.graph;
        const t = this.inputs?.[pair * 2];
        const origin = getLinkedOrigin(graph, t);
        if (!origin) return;

        // Always commit hub widget first so panel + applyModes stay in sync
        if (this.widgets?.[pair]) this.widgets[pair].value = !!value;

        const restriction = this.properties?.toggleRestriction || "default";
        if (value && String(restriction).includes("one")) {
          for (let p = 0; p < (this.widgets || []).length; p++) {
            if (p === pair) continue;
            if (this.widgets[p]?.value && !this.widgets[p]._lcLocked) {
              this.widgets[p].value = false;
              const o = getLinkedOrigin(graph, this.inputs[p * 2]);
              if (o) changeMode(o, this._lcOffMode ?? MODE_BYPASS);
            }
          }
        }
        if (!value && restriction === "always one") {
          const anyOn = (this.widgets || []).some(
            (w, i) => i !== pair && w && w.value && !w._lcLocked
          );
          if (!anyOn) {
            if (this.widgets[pair]) this.widgets[pair].value = true;
            changeMode(origin, MODE_ALWAYS);
            return;
          }
        }
        changeMode(origin, value ? MODE_ALWAYS : this._lcOffMode ?? MODE_BYPASS);
        this.setDirtyCanvas?.(true, true);
      }


      /** Update * slot labels when a linked node is renamed (no rewire needed). */
      refreshSlotNames() {
        const graph = app.graph;
        if (!graph || !this.inputs) return;
        let changed = false;
        const pairCount = Math.floor(this.inputs.length / 2);
        for (let p = 0; p < pairCount; p++) {
          const t = this.inputs[p * 2];
          if (!t || t.link == null) continue;
          const origin = getLinkedOrigin(graph, t);
          if (!origin) continue;
          const title = origin.title || origin.type || "";
          if (t.name !== title) {
            t.name = title;
            changed = true;
          }
          const w = this.widgets?.[p];
          if (w && !w._lcLocked) {
            const want = `Enable ${title || `Slot ${p + 1}`}`;
            // Keep lock prefix if present
            const locked = !!w._lcLocked;
            const base = want;
            w._lcNameClean = base;
            const next = locked ? `🔒 ${base}` : base;
            if (w.name !== next) {
              w.name = next;
              changed = true;
            }
          } else if (w) {
            const base = `Enable ${title || `Slot ${p + 1}`}`;
            w._lcNameClean = base;
            const next = w._lcLocked ? `🔒 ${base}` : base;
            if (w.name !== next) {
              w.name = next;
              changed = true;
            }
          }
        }
        if (changed) this.setDirtyCanvas?.(true, true);
      }

      applyModes() {
        const graph = app.graph;
        if (!graph) return;
        const pairCount = Math.floor((this.inputs?.length || 0) / 2);
        for (let p = 0; p < pairCount; p++) {
          const t = this.inputs[p * 2];
          const e = this.inputs[p * 2 + 1];
          if (!t || t.link == null) continue;
          const origin = getLinkedOrigin(graph, t);
          if (!origin) continue;
          const driven = e?.link != null;
          let enabled =
            this.widgets?.[p] != null
              ? !!this.widgets[p].value
              : origin.mode === MODE_ALWAYS;
          if (driven) {
            const bv = resolveBoolean(graph, e);
            if (bv !== null) enabled = bv;
          }
          changeMode(origin, enabled ? MODE_ALWAYS : this._lcOffMode ?? MODE_BYPASS);
          if (this.widgets?.[p]) {
            this.widgets[p].value = enabled;
            setWidgetLocked(this.widgets[p], driven);
          }
        }
      }

      onConnectionsChange() {
        this.scheduleStabilize(15);
        this.scheduleStabilize(80);
      }

      getExtraMenuOptions(canvas, options) {
        options.push(
          {
            content: "Enable all",
            callback: () => {
              for (let i = 0; i < (this.widgets || []).length; i++) {
                if (this.widgets[i]._lcLocked) continue;
                this.widgets[i].value = true;
                this.onToggleWidget(i, true);
              }
            },
          },
          {
            content: this._lcOffMenu || "Bypass all",
            callback: () => {
              for (let i = 0; i < (this.widgets || []).length; i++) {
                if (this.widgets[i]._lcLocked) continue;
                this.widgets[i].value = false;
                this.onToggleWidget(i, false);
              }
            },
          },
          {
            content: "Toggle all",
            callback: () => {
              for (let i = 0; i < (this.widgets || []).length; i++) {
                if (this.widgets[i]._lcLocked) continue;
                const v = !this.widgets[i].value;
                this.widgets[i].value = v;
                this.onToggleWidget(i, v);
              }
            },
          },
          null,
          {
            content:
              "Restriction: " +
              (this.properties.toggleRestriction || "default"),
            callback: () => {
              const order = ["default", "max one", "always one"];
              const cur = this.properties.toggleRestriction || "default";
              this.properties.toggleRestriction =
                order[(order.indexOf(cur) + 1) % order.length];
            },
          }
        );
        return options;
      }
    }

    LCBypasser.title = HUB_TYPE;
    LCBypasser.type = HUB_TYPE;
    LCBypasser.category = "LC123/utils";
    LCBypasser.comfyClass = HUB_TYPE;
    LCBypasser.collapsable = true;
    LCBypasser.lcOffMode = MODE_BYPASS;
    LCBypasser.lcOffMenu = "Bypass all";
    LCBypasser.desc = `Bypass linked nodes from one place.\n\n• * inputs — connect any output from the node you want to control.\n• enable (BOOLEAN, optional) — when wired, drives that slot: true = run, false = bypass. The matching toggle shows 🔒 and is locked to this signal.\n• Enable toggles — yes = node active (mode always), no = node bypassed. Right-click: Enable all / Bypass all / Toggle all.\n• Restriction (right-click) — default | max one | always one.\n• OPT_CONNECTION — optional link to LC Bypasser Panel for a widgets-only remote.\nSlot labels update when you rename the linked node. Fully collapsible.`;
    LCBypasser.description = LCBypasser.desc;
    LCBypasser["@toggleRestriction"] = {
      type: "combo",
      values: ["default", "max one", "always one"],
    };
    LiteGraph.registerNodeType(HUB_TYPE, LCBypasser);

    class LCMute extends LCBypasser {
      constructor() {
        super();
        this.description = LCMute.desc || this.description;
      }
    }
    LCMute.title = MUTE_TYPE;
    LCMute.type = MUTE_TYPE;
    LCMute.category = "LC123/utils";
    LCMute.comfyClass = MUTE_TYPE;
    LCMute.collapsable = true;
    LCMute.lcOffMode = MODE_NEVER;
    LCMute.lcOffMenu = "Mute all";
    LCMute.desc = `Mute linked nodes from one place.\n\nIdentical to LC Bypasser, except Off = mute (never run) instead of bypass (pass-through).\n\n• * inputs — connect any output from the node you want to control.\n• enable (BOOLEAN, optional) — when wired, drives that slot: true = run, false = mute. The matching toggle shows 🔒 and is locked to this signal.\n• Enable toggles — yes = node active, no = node muted. Right-click: Enable all / Mute all / Toggle all.\n• Restriction (right-click) — default | max one | always one.\n• OPT_CONNECTION — optional link to LC Bypasser Panel for a widgets-only remote.\nSlot labels update when you rename the linked node. Fully collapsible.`;
    LCMute.description = LCMute.desc;
    LCMute["@toggleRestriction"] = {
      type: "combo",
      values: ["default", "max one", "always one"],
    };
    LiteGraph.registerNodeType(MUTE_TYPE, LCMute);

    // ═══════════ LC Bypasser Panel (widgets only, both hubs) ═══════════
    class LCBypasserPanel extends LGraphNode {
      constructor() {
        super(PANEL_TYPE);
        this.isVirtualNode = true;
        this.serialize_widgets = true;
        this.properties = this.properties || {};
        this.addInput("hub", "*");
        this.addOutput("OPT_CONNECTION", "*");
        lcApplyLaunchColor(this, "#28281E");
        this.size = [260, 48];
        this._lcTimer = null;
        this._lcKind = null; // "node" | "group"
        this.description = LCBypasserPanel.desc || this.description;
      }

      onNodeCreated() {
        this.scheduleStabilize(30);
      }
      onConfigure() {
        this.scheduleStabilize(80);
        this.scheduleStabilize(300);
      }

      onResize(size) {
        // Keep height at fitted minimum for current slot count
        const fitH = this._lcPanelFitH || Math.max(56, 34 + (this.widgets?.length || 0) * 24 + 20);
        if (size && size[1] < fitH) size[1] = fitH;
        if (size && size[0] < 260) size[0] = 260;
        return size;
      }

      getHub() {
        const hubInp = (this.inputs || []).find((i) => i && i.name === "hub");
        return resolveHub(getLinkedOrigin(app.graph, hubInp), app.graph);
      }

      scheduleStabilize(ms = 20) {
        clearTimeout(this._lcTimer);
        this._lcTimer = setTimeout(() => {
          try {
            this.syncFromHub();
            this.applyModes();
          } catch (e) {
            console.warn("[LC Bypasser Panel]", e);
          }
        }, ms);
      }

      getTargets() {
        const hub = this.getHub();
        if (!hub) return [];
        if (isNodeHub(hub.type)) {
          this._lcKind = "node";
          return nodeHubTargets(hub, app.graph);
        }
        if (hub.type === GROUPS_TYPE) {
          this._lcKind = "group";
          return groupsHubTargets(hub);
        }
        this._lcKind = null;
        return [];
      }

      syncFromHub() {
        if (!this.widgets) this.widgets = [];
        const graph = app.graph;
        const targets = this.getTargets();

        while (this.widgets.length < targets.length) {
          const pair = this.widgets.length;
          this.addWidget(
            "toggle",
            `Enable ${pair + 1}`,
            true,
            (val) => this.onToggleWidget(pair, val),
            { on: "yes", off: "no" }
          );
        }
        while (this.widgets.length > targets.length) this.widgets.pop();

        for (let p = 0; p < targets.length; p++) {
          const item = targets[p];
          const w = this.widgets[p];
          const driven = item.enableInput?.link != null;
          w._lcNameClean = null;
          w.name = `Enable ${item.title}`;
          let enabled = w.value !== false;

          if (item.kind === "node") {
            if (driven) {
              const bv = resolveBoolean(graph, item.enableInput);
              if (bv !== null) enabled = bv;
              else if (item.origin) enabled = item.origin.mode === MODE_ALWAYS;
            } else if (item.origin) {
              // Prefer hub widget if present
              const hub = this.getHub();
              if (hub?.widgets?.[item.index] != null) {
                enabled = !!hub.widgets[item.index].value;
              } else {
                enabled = item.origin.mode === MODE_ALWAYS;
              }
            }
          } else if (item.kind === "group") {
            const hub = this.getHub();
            if (driven) {
              const bv = resolveBoolean(graph, item.enableInput);
              if (bv !== null) enabled = bv;
            } else if (hub?.widgets?.[item.index] != null) {
              enabled = !!hub.widgets[item.index].value;
            }
          }

          w.value = enabled;
          setWidgetLocked(w, driven);
          if (!w._lcCallbackWrapped) {
            w._lcCallbackWrapped = true;
            const orig = w.callback;
            w.callback = (val, ...rest) => {
              if (w._lcLocked || w.disabled) return;
              return orig?.call(w, val, ...rest);
            };
          }
        }

        // Height tracks connection count: grow/shrink to exact fit when slots change.
        // No optional trim — min height IS the fitted height (avoids 10px shrink + reload snap).
        const n = this.widgets.length;
        const fitH = Math.max(56, 34 + Math.max(n, 0) * 24 + 20);
        const minW = 260;
        const prevN = this._lcPanelSlotCount;
        this._lcPanelSlotCount = n;
        this._lcPanelFitH = fitH;

        if (!this.size) this.size = [minW, fitH];
        const width = Math.max(minW, this.size[0] || minW);
        // Always lock height to fitted size for current connections (no trim / no snap fight)
        const h = fitH;

        if (Math.abs((this.size[0] || 0) - width) > 1 || Math.abs((this.size[1] || 0) - h) > 1) {
          if (typeof this.setSize === "function") this.setSize([width, h]);
          else {
            this.size[0] = width;
            this.size[1] = h;
          }
          this.setDirtyCanvas?.(true, true);
        }
      }


      /** Poll-friendly: rebuild only if count changed; labels only when title string changes. */
      refreshFromHubLight() {
        const targets = this.getTargets();
        const count = targets.length;
        if (count !== (this.widgets || []).length) {
          this.syncFromHub();
          return;
        }
        // Titles only — no setSize, no applyModes, minimal dirty
        let dirty = false;
        for (let p = 0; p < targets.length; p++) {
          const item = targets[p];
          const w = this.widgets[p];
          if (!w) continue;
          const driven = item.enableInput?.link != null;
          const wantName = `Enable ${item.title}`;
          const nextName = driven ? `🔒 ${wantName}` : wantName;
          if (w.name !== nextName) {
            w._lcNameClean = wantName;
            w.name = nextName;
            dirty = true;
          }
          const shouldLock = driven;
          if (!!w._lcLocked !== shouldLock) {
            setWidgetLocked(w, shouldLock);
            dirty = true;
          }
        }
        if (dirty) this.setDirtyCanvas?.(true, false);
      }

      onToggleWidget(pair, value) {
        if (this.widgets?.[pair]?._lcLocked) return;
        const targets = this.getTargets();
        const item = targets[pair];
        if (!item) return;
        if (item.enableInput?.link != null) return;

        // Hub owns restriction + authoritative widget state
        const hub = this.getHub();
        if (hub && typeof hub.onToggleWidget === "function") {
          // Optimistic panel value (hub may reject under "always one")
          if (this.widgets?.[pair]) this.widgets[pair].value = !!value;
          hub.onToggleWidget(item.index, value);
          // Mirror full hub state back onto panel (restriction may have flipped others)
          this._syncWidgetsFromHub(hub, targets);
          this.setDirtyCanvas?.(true, true);
          return;
        }

        this._applyOne(item, value);
      }

      _syncWidgetsFromHub(hub, targets) {
        const list = targets || this.getTargets();
        for (let p = 0; p < list.length; p++) {
          const it = list[p];
          const hw = hub?.widgets?.[it.index];
          const pw = this.widgets?.[p];
          if (hw == null || !pw || pw._lcLocked) continue;
          pw.value = !!hw.value;
        }
      }

      _applyOne(item, enabled) {
        if (!item) return;
        if (item.kind === "node" && item.origin) {
          const off = this.getHub()?._lcOffMode ?? MODE_BYPASS;
          changeMode(item.origin, enabled ? MODE_ALWAYS : off);
        } else if (item.kind === "group") {
          const hub = this.getHub();
          // Groups bypasser owns applyModes for groups
          if (hub?.onToggleWidget) {
            try {
              hub.onToggleWidget(item.index, enabled);
            } catch (_) {}
          } else if (hub?.applyModes) {
            if (hub.widgets?.[item.index]) hub.widgets[item.index].value = enabled;
            hub.applyModes();
          }
        }
      }

      applyModes() {
        const targets = this.getTargets();
        const graph = app.graph;
        for (let p = 0; p < targets.length; p++) {
          const item = targets[p];
          const driven = item.enableInput?.link != null;
          let enabled =
            this.widgets?.[p] != null ? !!this.widgets[p].value : true;
          if (driven) {
            const bv = resolveBoolean(graph, item.enableInput);
            if (bv !== null) enabled = bv;
          }
          this._applyOne(item, enabled);
          if (this.widgets?.[p]) {
            if (this.widgets[p].value !== enabled) this.widgets[p].value = enabled;
            if (!!this.widgets[p]._lcLocked !== driven) {
              setWidgetLocked(this.widgets[p], driven);
            }
          }
        }
      }

      onConnectionsChange() {
        this.scheduleStabilize(15);
        this.scheduleStabilize(80);
      }

      getExtraMenuOptions(canvas, options) {
        options.push(
          {
            content: "Enable all",
            callback: () => {
              for (let i = 0; i < (this.widgets || []).length; i++) {
                if (this.widgets[i]._lcLocked) continue;
                this.widgets[i].value = true;
                this.onToggleWidget(i, true);
              }
            },
          },
          {
            content: this.getHub()?._lcOffMenu || "Bypass all",
            callback: () => {
              for (let i = 0; i < (this.widgets || []).length; i++) {
                if (this.widgets[i]._lcLocked) continue;
                this.widgets[i].value = false;
                this.onToggleWidget(i, false);
              }
            },
          },
          {
            content: "Toggle all",
            callback: () => {
              for (let i = 0; i < (this.widgets || []).length; i++) {
                if (this.widgets[i]._lcLocked) continue;
                const v = !this.widgets[i].value;
                this.widgets[i].value = v;
                this.onToggleWidget(i, v);
              }
            },
          },
        );
        return options;
      }
    }

    LCBypasserPanel.title = PANEL_TYPE;
    LCBypasserPanel.type = PANEL_TYPE;
    LCBypasserPanel.category = "LC123/utils";
    LCBypasserPanel.comfyClass = PANEL_TYPE;
    LCBypasserPanel.collapsable = true;
    LCBypasserPanel.desc = `Widgets-only remote for LC Bypasser, LC Mute, or LC Groups Bypasser.\n\n• hub — connect OPT_CONNECTION from LC Bypasser, LC Mute, or LC Groups Bypasser.\n• Toggles mirror the hub (switches only).\n• Toggle restriction (default / max one / always one) is set on the hub, not this panel.\n• If the hub has an enable BOOLEAN wired for that slot, the panel toggle is 🔒 locked to it.\n• Right-click: Enable all / Bypass all (or Mute all) / Toggle all.\nCollapse the hub to hide sockets; keep this panel open for controls.`;
    LCBypasserPanel.description = LCBypasserPanel.desc;
    LiteGraph.registerNodeType(PANEL_TYPE, LCBypasserPanel);

    console.log(
      `[LC123.Bypasser] registered "${HUB_TYPE}" + "${MUTE_TYPE}" + "${PANEL_TYPE}" (panel also supports Groups)`
    );
  },

  async setup() {
    setInterval(() => {
      const graph = app.graph;
      if (!graph?._nodes) return;
      for (const n of graph._nodes) {
        if (isNodeHub(n.type)) {
          try {
            n.refreshSlotNames?.();
            n.applyModes?.();
          } catch (_) {}
        } else if (n.type === PANEL_TYPE) {
          try {
            // Labels/count only — never applyModes here (avoids flicker)
            n.refreshFromHubLight?.();
          } catch (_) {}
        }
      }
    }, 1000);
  },
});
