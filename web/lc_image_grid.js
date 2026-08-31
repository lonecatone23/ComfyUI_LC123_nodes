/**
 * LC Image Grid — image-node color, utility-node launch width.
 */
import { app } from "../../scripts/app.js";
import { lcApplyLaunchColor } from "./lc_color.js";

const TYPE = "LCImageGrid";
const COLOR = "#324B4B";
const UTILITY_W = 270;

app.registerExtension({
  name: "LC123.ImageGrid",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData?.name !== TYPE) return;
    const onNodeCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const r = onNodeCreated?.apply(this, arguments);
      try {
        lcApplyLaunchColor(this, COLOR);
        // Utility-node default width; height from widgets
        if (!this._lcUserSized && (!this.size || this.size[0] < 10)) {
          this.setSize?.([UTILITY_W, this.size?.[1] || 200]);
        }
      } catch (_) {}
      return r;
    };
  },
  nodeCreated(node) {
    if (node.comfyClass !== TYPE && node.type !== TYPE) return;
    try {
      lcApplyLaunchColor(node, COLOR);
      if (Array.isArray(node.size) && !node._lcUserSized && (node.size[0] || 0) < 10) {
        node.size[0] = UTILITY_W;
      }
    } catch (_) {}
  },
});
