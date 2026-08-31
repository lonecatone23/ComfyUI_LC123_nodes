/**
 * LC Show Text 🔤 — ShowText 🐍 style display.
 * Does NOT reset node size on load or after generation (user size is kept).
 */
import { app } from "../../scripts/app.js";
import { ComfyWidgets } from "../../scripts/widgets.js";
import { lcApplyLaunchColor } from "./lc_color.js";

const TYPE = "LCShowText";
const COLOR = "#28281E";
const DEFAULT_W = 270;
const DEFAULT_H = 120;

function applyColor(node) {
  lcApplyLaunchColor(node, COLOR);
}

function ensureDisplayWidget(node) {
  let widget = node.widgets?.find((w) => w.name === "text");
  if (widget) return widget;
  // forceInput hides the linked input; add a read-only multiline face widget
  try {
    widget = ComfyWidgets["STRING"](
      node,
      "text",
      ["STRING", { multiline: true }],
      app
    ).widget;
  } catch (_) {
    return null;
  }
  if (widget?.inputEl) {
    widget.inputEl.readOnly = true;
    widget.inputEl.style.opacity = "0.85";
  }
  // Don't let the widget force a huge default height every time
  if (typeof widget.computeSize === "function") {
    const orig = widget.computeSize.bind(widget);
    widget.computeSize = function (width) {
      // Prefer current node height contribution over expanding forever
      try {
        return orig(width);
      } catch (_) {
        return [width, 60];
      }
    };
  }
  return widget;
}

function setDisplayText(node, display) {
  // Strip old experimental widgets if any
  if (node.widgets) {
    for (let i = node.widgets.length - 1; i >= 0; i--) {
      const n = node.widgets[i]?.name;
      if (n === "lc_show_display" || n === "show_display") {
        node.widgets.splice(i, 1);
      }
    }
  }

  const widget = ensureDisplayWidget(node);
  if (!widget) return;
  widget.value = display;
  if (widget.inputEl) {
    widget.inputEl.value = display;
    widget.inputEl.readOnly = true;
  }
}

app.registerExtension({
  name: "LC123.ShowText",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData?.name !== TYPE) return;

    const onNodeCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const r = onNodeCreated?.apply(this, arguments);
      applyColor(this);
      // Default size only when brand-new (not restored from workflow)
      if (!this._lcShowSized) {
        this._lcShowSized = true;
        if (!this.size || this.size[0] < 40) {
          this.size = [DEFAULT_W, DEFAULT_H];
        }
      }
      return r;
    };

    const onConfigure = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function (data) {
      // Capture size from workflow BEFORE anything else mutates it
      const saved =
        data?.size && Array.isArray(data.size)
          ? [data.size[0], data.size[1]]
          : this.size
            ? [this.size[0], this.size[1]]
            : null;
      const r = onConfigure?.apply(this, arguments);
      applyColor(this);
      if (saved && saved[0] > 40 && saved[1] > 40) {
        this.size = saved;
        this._lcShowSized = true;
      }
      return r;
    };

    const onExecuted = nodeType.prototype.onExecuted;
    nodeType.prototype.onExecuted = function (message) {
      // Remember user size before updating text
      const keepW = this.size?.[0];
      const keepH = this.size?.[1];

      onExecuted?.apply(this, arguments);

      let texts = message?.text;
      if (texts === undefined || texts === null) return;
      if (!Array.isArray(texts)) texts = [String(texts)];
      const display = texts.map((t) => (t == null ? "" : String(t))).join("");

      setDisplayText(this, display);

      // Restore dimensions — never snap to computeSize()
      if (keepW > 40 && keepH > 40) {
        this.size[0] = keepW;
        this.size[1] = keepH;
      }
      app.graph?.setDirtyCanvas?.(true, true);
    };
  },
});
