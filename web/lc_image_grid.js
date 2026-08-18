/**
 * LC Image Grid — image-node color, utility-node launch width.
 */
import { app } from "../../scripts/app.js";

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
        this.color = COLOR;
        this.bgcolor = COLOR;
        // Utility-node default width; height from widgets
        if (!this.size || this.size[0] < 10) {
          this.setSize?.([UTILITY_W, this.size?.[1] || 200]);
        } else {
          this.size[0] = UTILITY_W;
        }
      } catch (_) {}
      return r;
    };
  },
  nodeCreated(node) {
    if (node.comfyClass !== TYPE && node.type !== TYPE) return;
    try {
      node.color = COLOR;
      node.bgcolor = COLOR;
      if (Array.isArray(node.size)) {
        node.size[0] = UTILITY_W;
      }
    } catch (_) {}
  },
});
