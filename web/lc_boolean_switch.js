/**
 * LC Boolean Switch / Flip / Value — utility color + width
 */
import { app } from "../../scripts/app.js";

const TYPES = new Set(["LCBooleanSwitch", "LCBooleanFlip", "LCBooleanValue"]);
const COLOR = "#28281E";
const WIDTH = 270;

function style(node) {
  try {
    node.color = COLOR;
    node.bgcolor = COLOR;
    if (!node.size) node.size = [WIDTH, 60];
    else if ((node.size[0] || 0) < 40) node.size[0] = WIDTH;
  } catch (_) {}
}

app.registerExtension({
  name: "LC123.BooleanSwitch",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (!TYPES.has(nodeData?.name)) return;
    const onCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const r = onCreated?.apply(this, arguments);
      style(this);
      if (!this.size || this.size[0] < 40) {
        this.size = [WIDTH, this.computeSize?.()[1] || 80];
      } else {
        this.size[0] = WIDTH;
      }
      return r;
    };
  },
  nodeCreated(node) {
    if (!TYPES.has(node.comfyClass) && !TYPES.has(node.type)) return;
    style(node);
  },
});
