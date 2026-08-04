/**
 * LC Bypasser
 * -----------
 * Virtual frontend node for ComfyUI_LC123_nodes.
 * (Formerly "LC Node Collector")
 *
 * Per-node bypass control with optional BOOLEAN sockets:
 *
 *   * slot     → connect any node output
 *   enable     → BOOLEAN under it (optional). true = active, false = bypass
 *   * (empty)  → ready for the next connection
 *
 * Toggle widgets mirror each pair. When a BOOLEAN is wired in, that
 * toggle is locked (🔒) and driven only by the socket.
 *
 * Right-click: Enable all / Bypass all / Toggle all / restriction cycle.
 *
 * Install:
 *   ComfyUI/custom_nodes/ComfyUI_LC123_nodes/web/lc_bypasser.js
 * Hard-refresh (Ctrl+F5). Add node: "LC Bypasser"
 */

import { app } from "../../scripts/app.js";

const NODE_TYPE = "LC Bypasser";
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

function readBooleanFromOrigin(origin) {
  if (!origin?.widgets) return null;
  for (const w of origin.widgets) {
    if (!w) continue;
    if (typeof w.value === "boolean") return !!w.value;
    if (w.type === "toggle") return !!w.value;
    if (w.value === "yes" || w.value === "true" || w.value === 1) return true;
    if (w.value === "no" || w.value === "false" || w.value === 0) return false;
  }
  return null;
}

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

app.registerExtension({
  name: "LC123.Bypasser",

  registerCustomNodes() {
    class LCBypasser extends LGraphNode {
      constructor() {
        super(NODE_TYPE);
        this.isVirtualNode = true;
        this.serialize_widgets = true;
        this.properties = this.properties || {};
        if (!this.properties.toggleRestriction) {
          this.properties.toggleRestriction = "default";
        }

        this.addInput("", "*");
        this.addInput("enable", "BOOLEAN");
        this.addOutput("OPT_CONNECTION", "*");

        this.color = "#3d3a2f";
        this.bgcolor = "#2a281f";
        this.size = [240, 100];

        this._lcTimer = null;
      }

      onNodeCreated() {
        this.scheduleStabilize(30);
      }

      onConfigure() {
        this.scheduleStabilize(80);
        this.scheduleStabilize(300);
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
          const origin = getLinkedOrigin(graph, t);
          if (origin) {
            t.name = origin.title || "";
          } else if (t.link == null) {
            t.name = "";
          }
          t.type = "*";
          next.push(t);

          const e = enables[i];
          e.name = "enable";
          e.type = "BOOLEAN";
          next.push(e);
        }

        const lastT = next.length >= 2 ? next[next.length - 2] : null;
        if (!lastT || lastT.link != null) {
          next.push({ name: "", type: "*", link: null });
          next.push({ name: "enable", type: "BOOLEAN", link: null });
        }

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
        while (this.widgets.length > filled) {
          this.widgets.pop();
        }

        for (let p = 0; p < filled; p++) {
          const t = this.inputs[p * 2];
          const e = this.inputs[p * 2 + 1];
          const w = this.widgets[p];
          const origin = getLinkedOrigin(graph, t);
          const title =
            origin?.title || origin?.type || `Slot ${p + 1}`;

          const driven = e?.link != null;

          w._lcNameClean = null;
          w.name = `Enable ${title}`;

          let enabled = true;
          if (driven) {
            const bv = readBooleanFromOrigin(getLinkedOrigin(graph, e));
            if (bv !== null) enabled = bv;
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

        const restriction = this.properties?.toggleRestriction || "default";

        if (value && String(restriction).includes("one")) {
          for (let p = 0; p < (this.widgets || []).length; p++) {
            if (p === pair) continue;
            if (this.widgets[p]?.value && !this.widgets[p]._lcLocked) {
              this.widgets[p].value = false;
              const o = getLinkedOrigin(graph, this.inputs[p * 2]);
              if (o) changeMode(o, MODE_BYPASS);
            }
          }
        }

        if (!value && restriction === "always one") {
          const anyOn = (this.widgets || []).some(
            (w, i) => i !== pair && w.value && !w._lcLocked
          );
          if (!anyOn) {
            if (this.widgets[pair]) this.widgets[pair].value = true;
            changeMode(origin, MODE_ALWAYS);
            return;
          }
        }

        changeMode(origin, value ? MODE_ALWAYS : MODE_BYPASS);
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
          let enabled = true;
          if (driven) {
            const bv = readBooleanFromOrigin(getLinkedOrigin(graph, e));
            if (bv !== null) enabled = bv;
          } else if (this.widgets?.[p] != null) {
            enabled = !!this.widgets[p].value;
          }

          changeMode(origin, enabled ? MODE_ALWAYS : MODE_BYPASS);

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
            content: "Bypass all",
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

    LCBypasser.title = NODE_TYPE;
    LCBypasser.type = NODE_TYPE;
    LCBypasser.category = "LC123/utils";
    LCBypasser.comfyClass = NODE_TYPE;
    LCBypasser.collapsable = true;

    LiteGraph.registerNodeType(NODE_TYPE, LCBypasser);
    console.log(`[LC123.Bypasser] registered "${NODE_TYPE}"`);
  },

  async setup() {
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
  },
});
