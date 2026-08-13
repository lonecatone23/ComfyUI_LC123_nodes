/**
 * LC Groups Bypasser
 * -----------------
 * Mirrors the working LC Bypasser control pattern, but targets groups.
 *
 * For each group in the graph:
 *   - One toggle widget  ("Enable <title>")
 *   - One BOOLEAN input  (named <title>) for optional remote control
 *
 * Toggle click  → bypass/enable nodes in THAT group only
 * BOOLEAN in    → locks that row (🔒) and drives it; other rows untouched
 *
 * Install:
 *   ComfyUI/custom_nodes/ComfyUI_LC123_nodes/web/lc_groups_bypasser.js
 * Hard-refresh (Ctrl+F5). Delete & re-add the node once.
 */

import { app } from "../../scripts/app.js";

const NODE_TYPE = "LC Groups Bypasser";
const MODE_ALWAYS = 0;
const MODE_BYPASS = 4;

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
    (i) =>
      i &&
      (i.type === "BOOLEAN" ||
        i.type === "boolean" ||
        String(i.name || "").toLowerCase().includes("bool") ||
        String(i.name || "").toLowerCase() === "value")
  );
  for (const bi of boolIns) {
    if (bi.link == null) continue;
    const up = resolveBoolean(graph, bi, depth + 1);
    if (up !== null) return invert ? !up : up;
  }
  if (!boolIns.some((i) => i.link != null)) {
    for (const bi of origin.inputs || []) {
      if (!bi || bi.link == null) continue;
      const up = resolveBoolean(graph, bi, depth + 1);
      if (up !== null) return invert ? !up : up;
    }
  }

  const local = readBooleanFromWidgets(origin);
  if (local !== null) return invert ? !local : local;
  return null;
}

function readBooleanFromOrigin(origin) {
  return readBooleanFromWidgets(origin);
}

/** Same lock helper as LC Bypasser */
function setWidgetLocked(widget, locked) {
  if (!widget) return;
  widget.disabled = !!locked;
  widget.readOnly = !!locked;
  if (locked) {
    widget._lcLocked = true;
    if (widget.name && !widget.name.startsWith("🔒 ")) {
      widget._lcNameClean = widget.name;
      widget.name = "🔒 " + widget.name;
    }
  } else {
    widget._lcLocked = false;
    if (widget._lcNameClean) {
      widget.name = widget._lcNameClean;
      widget._lcNameClean = null;
    } else if (widget.name?.startsWith("🔒 ")) {
      widget.name = widget.name.slice(2);
    }
  }
}

function groupStableId(group) {
  if (!group) return "unknown";
  if (group.id != null && group.id !== "") return "id:" + String(group.id);
  if (!group._lcStableId) {
    group._lcStableId =
      "lcg_" +
      Math.random().toString(36).slice(2, 9) +
      "_" +
      String(group.title || "").slice(0, 24);
  }
  return group._lcStableId;
}

function collectGroups(graph) {
  if (!graph) return [];
  const out = [];
  for (const g of graph._groups || graph.groups || []) {
    if (g) out.push(g);
  }
  for (const n of graph._nodes || []) {
    if (n?.subgraph) {
      for (const g of collectGroups(n.subgraph)) out.push(g);
    }
  }
  return out;
}

function groupBounds(group) {
  if (group.bounding?.length >= 4) {
    return {
      x: group.bounding[0],
      y: group.bounding[1],
      w: group.bounding[2],
      h: group.bounding[3],
    };
  }
  if (group._bounding?.length >= 4) {
    return {
      x: group._bounding[0],
      y: group._bounding[1],
      w: group._bounding[2],
      h: group._bounding[3],
    };
  }
  const pos = group.pos || [0, 0];
  const size = group.size || [200, 200];
  return { x: pos[0], y: pos[1], w: size[0], h: size[1] };
}

function nodesInGroup(graph, group) {
  if (!group || !graph) return [];

  try {
    group.recomputeInsideNodes?.();
  } catch (_) {}

  if (Array.isArray(group._nodes) && group._nodes.length) {
    return group._nodes.filter((n) => n && n.type !== NODE_TYPE);
  }
  if (Array.isArray(group.nodes) && group.nodes.length) {
    return group.nodes.filter((n) => n && n.type !== NODE_TYPE);
  }

  const { x, y, w, h } = groupBounds(group);
  const result = [];
  for (const node of graph._nodes || []) {
    if (!node || node.type === NODE_TYPE) continue;
    const nx = node.pos?.[0] ?? 0;
    const ny = node.pos?.[1] ?? 0;
    const nw = node.size?.[0] ?? 0;
    const nh = node.size?.[1] ?? 0;
    if (nx + nw > x && nx < x + w && ny + nh > y && ny < y + h) {
      result.push(node);
    }
  }
  return result;
}

function normalizeColor(c) {
  if (!c) return "";
  c = String(c).trim().toLowerCase().replace("#", "");
  if (c.length === 3) c = c.replace(/(.)(.)(.)/, "$1$1$2$2$3$3");
  return c;
}

app.registerExtension({
  name: "LC123.GroupsBypasser",

  registerCustomNodes() {
    class LCGroupsBypasser extends LGraphNode {
      constructor() {
        super(NODE_TYPE);
        this.isVirtualNode = true;
        this.serialize_widgets = true;
        this.properties = this.properties || {};
        if (this.properties.matchTitle === undefined)
          this.properties.matchTitle = "";
        if (this.properties.matchColors === undefined)
          this.properties.matchColors = "";
        if (this.properties.sort === undefined)
          this.properties.sort = "position";
        if (this.properties.toggleRestriction === undefined)
          this.properties.toggleRestriction = "default";
        try {
          this.addProperty(
            "toggleRestriction",
            this.properties.toggleRestriction || "default",
            "combo",
            { values: ["default", "max one", "always one"] }
          );
        } catch (_) {}

        this.addOutput("OPT_CONNECTION", "*");

        this.color = "#28281E";
        this.bgcolor = "#28281E";
        this.size = [270, 90];

        this._lcTimer = null;
        this._lcGroups = []; // parallel to widgets / inputs
        this.description = LCGroupsBypasser.desc || this.description;
      }

      onNodeCreated() {
        this.scheduleStabilize(40);
      }

      onConfigure() {
        this.scheduleStabilize(100);
        this.scheduleStabilize(400);
      }

      onAdded() {
        this.scheduleStabilize(40);
      }

      scheduleStabilize(ms = 20) {
        clearTimeout(this._lcTimer);
        this._lcTimer = setTimeout(() => {
          try {
            this.stabilize();
            this.applyModes();
          } catch (e) {
            console.warn("[LC Groups Bypasser]", e);
          }
        }, ms);
      }

      /** Filtered / sorted groups (same idea as filled * targets in LC Bypasser) */
      listGroups() {
        let groups = collectGroups(app.graph);

        const titleFilter = (this.properties.matchTitle || "").trim();
        if (titleFilter) {
          try {
            const re = new RegExp(titleFilter, "i");
            groups = groups.filter((g) => re.test(g.title || ""));
          } catch (_) {
            const low = titleFilter.toLowerCase();
            groups = groups.filter((g) =>
              (g.title || "").toLowerCase().includes(low)
            );
          }
        }

        const colorFilter = (this.properties.matchColors || "")
          .split(",")
          .map(normalizeColor)
          .filter(Boolean);
        if (colorFilter.length) {
          groups = groups.filter((g) => {
            const gc = normalizeColor(g.color || g.bgcolor || "");
            return colorFilter.some((c) => gc.includes(c) || c.includes(gc));
          });
        }

        if ((this.properties.sort || "position") === "alphanumeric") {
          groups.sort((a, b) =>
            (a.title || "").localeCompare(b.title || "")
          );
        } else {
          groups.sort((a, b) => {
            const ba = groupBounds(a);
            const bb = groupBounds(b);
            if (ba.y !== bb.y) return ba.y - bb.y;
            return ba.x - bb.x;
          });
        }
        return groups;
      }

      /**
       * Stabilize structure — mirrors LC Bypasser.stabilize / syncWidgets.
       * Widgets get a FIXED index callback at creation time (never rebound).
       */
      stabilize() {
        const graph = app.graph;
        const groups = this.listGroups();
        this._lcGroups = groups;
        if (!this.properties) this.properties = {};
        if (!this.properties.lcBindings) this.properties.lcBindings = {};
        const bindings = this.properties.lcBindings;

        if (!this.inputs) this.inputs = [];
        if (!this.widgets) this.widgets = [];

        // Snapshot current slot → stable group id before rebuild
        const prevIds = (this._lcSlotIds || []).slice();
        for (let i = 0; i < prevIds.length; i++) {
          const id = prevIds[i];
          if (!id) continue;
          const origin = getLinkedOrigin(graph, this.inputs[i]);
          bindings[id] = {
            value:
              this.widgets[i] != null ? !!this.widgets[i].value : true,
            originId: origin?.id ?? null,
          };
        }

        // ---- BOOLEAN inputs (one per group), in-place ----
        while (this.inputs.length > groups.length) {
          const idx = this.inputs.length - 1;
          if (this.inputs[idx]?.link != null && graph) {
            try {
              graph.removeLink(this.inputs[idx].link);
            } catch (_) {}
          }
          try {
            LGraphNode.prototype.removeInput.call(this, idx);
          } catch (_) {
            this.inputs.pop();
          }
        }
        while (this.inputs.length < groups.length) {
          const i = this.inputs.length;
          const title = groups[i].title || `Group ${i + 1}`;
          this.addInput(title, "BOOLEAN");
        }

        this._lcSlotIds = [];
        for (let i = 0; i < groups.length; i++) {
          const g = groups[i];
          const id = groupStableId(g);
          this._lcSlotIds[i] = id;
          const title = g.title || `Group ${i + 1}`;
          this.inputs[i].name = title;
          this.inputs[i].type = "BOOLEAN";
        }

        // ---- Widgets ----
        while (this.widgets.length < groups.length) {
          const pair = this.widgets.length;
          this.addWidget(
            "toggle",
            `Enable ${pair + 1}`,
            true,
            (val) => this.onToggleWidget(pair, val),
            { on: "yes", off: "no" }
          );
        }
        while (this.widgets.length > groups.length) {
          this.widgets.pop();
        }

        // Restore values / try to reattach boolean by origin node id
        for (let i = 0; i < groups.length; i++) {
          const w = this.widgets[i];
          const inp = this.inputs[i];
          const id = this._lcSlotIds[i];
          const title = groups[i].title || `Group ${i + 1}`;
          const saved = bindings[id] || {};

          const base = `Enable ${title}`;
          if (w._lcLocked && w._lcNameClean) {
            w._lcNameClean = base;
            w.name = "🔒 " + base;
          } else {
            w.name = base;
            w._lcNameClean = null;
          }

          // Reconnect boolean from saved origin if slot empty
          if (inp.link == null && saved.originId != null && graph) {
            const origin = graph.getNodeById?.(saved.originId);
            const outSlot = origin?.outputs?.findIndex(
              (o) =>
                o &&
                (o.type === "BOOLEAN" ||
                  o.type === "*" ||
                  o.type === "boolean")
            );
            if (origin && outSlot >= 0) {
              try {
                origin.connect(outSlot, this, i);
              } catch (_) {}
            }
          }

          const driven = inp?.link != null;
          if (driven) {
            const bv = resolveBoolean(graph, inp);
            if (bv !== null) w.value = bv;
            else if (saved.value != null) w.value = !!saved.value;
            setWidgetLocked(w, true);
          } else {
            if (saved.value != null) w.value = !!saved.value;
            setWidgetLocked(w, false);
          }

          // persist
          const origin = getLinkedOrigin(graph, inp);
          bindings[id] = {
            value: !!w.value,
            originId: origin?.id ?? null,
          };
        }

        const minH = 60 + Math.max(groups.length, 1) * 30;
        if (!this.size) this.size = [260, minH];
        if (this.size[1] < minH) this.size[1] = minH;

        this.setDirtyCanvas?.(true, true);
      }

      /**
       * Same contract as LC Bypasser.onToggleWidget:
       * only the clicked index is changed.
       */
      onToggleWidget(index, value) {
        const inp = this.inputs?.[index];
        if (inp?.link != null) return;
        if (this.widgets?.[index]?._lcLocked) return;

        const restriction = this.properties?.toggleRestriction || "default";

        if (value && String(restriction).includes("one")) {
          for (let i = 0; i < (this.widgets || []).length; i++) {
            if (i === index) continue;
            if (this.inputs?.[i]?.link != null) continue;
            if (this.widgets[i]?._lcLocked) continue;
            if (!this.widgets[i]?.value) continue;
            this.widgets[i].value = false;
            this.setGroupEnabled(i, false);
          }
        }

        if (!value && restriction === "always one") {
          const anyOn = (this.widgets || []).some((w, i) => {
            if (i === index) return false;
            if (this.inputs?.[i]?.link != null || w._lcLocked) return false;
            return !!w.value;
          });
          if (!anyOn) {
            if (this.widgets[index]) this.widgets[index].value = true;
            this.setGroupEnabled(index, true);
            return;
          }
        }

        if (this.widgets[index]) this.widgets[index].value = value;
        this.setGroupEnabled(index, value);
      }

      setGroupEnabled(index, enabled) {
        const group = this._lcGroups?.[index];
        if (!group) return;
        const members = nodesInGroup(app.graph, group);
        const mode = enabled ? MODE_ALWAYS : MODE_BYPASS;
        for (const n of members) changeMode(n, mode);
      }

      /**
       * Driven rows only (BOOLEAN connected):
       *   read socket → apply mode → lock widget
       * Manual rows are applied exclusively in onToggleWidget (no 300ms rewrite
       * that was causing lag + visual coupling).
       */
      applyModes() {
        const graph = app.graph;
        if (!graph) return;

        for (let i = 0; i < (this._lcGroups || []).length; i++) {
          const inp = this.inputs?.[i];
          const w = this.widgets?.[i];
          if (!w) continue;

          const driven = inp?.link != null;

          if (!driven) {
            if (w._lcLocked) setWidgetLocked(w, false);
            continue;
          }

          const bv = resolveBoolean(graph, inp);
          if (bv === null) continue;
          if (w.value !== bv) w.value = bv;
          this.setGroupEnabled(i, bv);
          setWidgetLocked(w, true);
        }
      }

      onConnectionsChange() {
        this.scheduleStabilize(15);
        this.scheduleStabilize(80);
      }

      onPropertyChanged() {
        this.scheduleStabilize(40);
      }



      getExtraMenuOptions(canvas, options) {
        options.push(
          {
            content: "Refresh groups",
            callback: () => this.scheduleStabilize(5),
          },
          {
            content: "Enable all",
            callback: () => {
              for (let i = 0; i < (this.widgets || []).length; i++) {
                if (this.widgets[i]._lcLocked) continue;
                if (this.inputs?.[i]?.link != null) continue;
                this.widgets[i].value = true;
                this.onToggleWidget(i, true);
              }
            },
          },
          {
            content: "Bypass all",
            callback: () => {
              for (let i = 0; i < (this.widgets || []).length; i++) {
                if (this.widgets[i]._lcLocked) continue;
                if (this.inputs?.[i]?.link != null) continue;
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
                if (this.inputs?.[i]?.link != null) continue;
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
          },
          {
            content: "Sort: " + (this.properties.sort || "position"),
            callback: () => {
              const order = ["position", "alphanumeric"];
              const cur = this.properties.sort || "position";
              this.properties.sort =
                order[(order.indexOf(cur) + 1) % order.length];
              this.scheduleStabilize(5);
            },
          }
        );
        return options;
      }
    }

    LCGroupsBypasser.title = NODE_TYPE;
    LCGroupsBypasser.type = NODE_TYPE;
    LCGroupsBypasser.category = "LC123/utils";
    LCGroupsBypasser.comfyClass = NODE_TYPE;
    LCGroupsBypasser.collapsable = true;
    LCGroupsBypasser.desc = `Bypass whole groups from one place.\n\n• Discovers groups on the graph (optional title/color filters in properties).\n• One toggle per group — yes = group active, no = all nodes in that group bypassed.\n• enable (BOOLEAN) under each group — when wired, drives that group; toggle shows 🔒.\n• Right-click: Enable all / Bypass all / Toggle all; Restriction; Sort (position | alphanumeric).\n• OPT_CONNECTION — link to LC Bypasser Panel for a widgets-only remote.\nFully collapsible.`;
    LCGroupsBypasser.description = LCGroupsBypasser.desc;

    LCGroupsBypasser["@matchTitle"] = { type: "string" };
    LCGroupsBypasser["@matchColors"] = { type: "string" };
    LCGroupsBypasser["@sort"] = {
      type: "combo",
      values: ["position", "alphanumeric"],
    };
    LCGroupsBypasser["@toggleRestriction"] = {
      type: "combo",
      values: ["default", "max one", "always one"],
    };

    LiteGraph.registerNodeType(NODE_TYPE, LCGroupsBypasser);
    console.log(`[LC123.GroupsBypasser] registered (LC Bypasser pattern)`);
  },

  async setup() {
    // Same cadence as LC Bypasser — applyModes only, no structure rebuild
    setInterval(() => {
      const graph = app.graph;
      if (!graph?._nodes) return;
      for (const n of graph._nodes) {
        if (n.type !== NODE_TYPE) continue;
        try {
          n.applyModes?.();
        } catch (_) {}
      }
    }, 300);

    // Occasional structure refresh for new groups (rare)
    setInterval(() => {
      const graph = app.graph;
      if (!graph?._nodes) return;
      for (const n of graph._nodes) {
        if (n.type !== NODE_TYPE) continue;
        try {
          n.stabilize?.();
        } catch (_) {}
      }
    }, 5000);
  },
});
