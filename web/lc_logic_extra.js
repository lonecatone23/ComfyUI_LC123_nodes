import { app } from "../../scripts/app.js";
import { lcApplyLaunchColor } from "./lc_color.js";

const COLOR = "#28281E";
const TYPES = new Set(["LCAnyEmptyBool", "LCAnyEmptyInt", "LCAnyEmptyFloat", "LCIntSplit"]);

app.registerExtension({
  name: "LC123.LogicExtra",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (!TYPES.has(nodeData?.name || "")) return;
    const origCompute = nodeType.prototype.computeSize;
    nodeType.prototype.computeSize = function (out) {
      const base = origCompute?.apply(this, arguments) || [210, 80];
      const size = [Math.max(180, base[0] || 210), Math.max(60, base[1] || 60)];
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
      return r;
    };
  },
});
