/**
 * LC Save Image / LC Save Metadata
 * Seed widget is seed_value — strip control_after_generate if the frontend injects it.
 */
import { app } from "../../scripts/app.js";
import { lcApplyLaunchColor } from "./lc_color.js";

const COLOR = "#28281E";
const TYPES = new Set(["LCSaveImage", "LCSaveImageMetadata"]);

function stripSeedControl(node) {
  if (!node?.widgets) return;
  node.widgets = node.widgets.filter((w) => {
    if (!w) return false;
    const n = String(w.name || "");
    if (n === "control_after_generate" || n === "control after generate") return false;
    return true;
  });
  const seed = node.widgets.find((w) => w && (w.name === "seed_value" || w.name === "seed"));
  if (seed) {
    seed.options = seed.options || {};
    seed.options.control_after_generate = false;
    delete seed.linkedWidgets;
  }
}

app.registerExtension({
  name: "LC123.SaveImage",

  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (!TYPES.has(nodeData?.name || "")) return;

    const origCompute = nodeType.prototype.computeSize;
    nodeType.prototype.computeSize = function (out) {
      const base = origCompute?.apply(this, arguments) || [270, 160];
      const size = [Math.max(220, base[0] || 270), Math.max(80, base[1] || 80)];
      if (out) {
        out[0] = size[0];
        out[1] = size[1];
        return out;
      }
      return size;
    };

    const onCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const r = onCreated?.apply(this, arguments);
      try {
        lcApplyLaunchColor(this, COLOR);
      } catch (_) {}
      stripSeedControl(this);
      setTimeout(() => stripSeedControl(this), 0);
      return r;
    };

    const onConfig = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function () {
      const r = onConfig?.apply(this, arguments);
      stripSeedControl(this);
      return r;
    };
  },
});
