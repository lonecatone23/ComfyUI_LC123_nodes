/**
 * LC Boolean Switch / Flip / Value — utility color; size retained after manual resize
 */
import { app } from "../../scripts/app.js";

const TYPES = new Set(["LCBooleanSwitch", "LCBooleanFlip", "LCBooleanValue"]);
const COLOR = "#28281E";
const WIDTH = 270;

function style(node) {
  try {
    node.color = COLOR;
    node.bgcolor = COLOR;
  } catch (_) {}
}

function defaultSizeOnce(node) {
  if (node._lcUserSized || node.properties?.lc_w) {
    const w = node.properties?.lc_w;
    const h = node.properties?.lc_h;
    if (w && h) {
      node.size = node.size || [w, h];
      node.size[0] = w;
      node.size[1] = h;
      node._lcUserSized = true;
    }
    return;
  }
  if (!node.size || (node.size[0] || 0) < 40) {
    node.size = [WIDTH, node.computeSize?.()[1] || 80];
  }
}

function hookResize(node) {
  if (node._lcBoolResizeHooked) return;
  node._lcBoolResizeHooked = true;
  const prev = node.onResize;
  node.onResize = function () {
    const r = prev?.apply(this, arguments);
    if (!this.properties) this.properties = {};
    if (this.size) {
      this.properties.lc_w = this.size[0];
      this.properties.lc_h = this.size[1];
    }
    this._lcUserSized = true;
    return r;
  };
  const prevCfg = node.onConfigure;
  node.onConfigure = function (data) {
    const r = prevCfg?.apply(this, arguments);
    if (data?.size) {
      if (!this.properties) this.properties = {};
      this.properties.lc_w = data.size[0];
      this.properties.lc_h = data.size[1];
      this._lcUserSized = true;
      this.size = [data.size[0], data.size[1]];
    }
    return r;
  };
}

app.registerExtension({
  name: "LC123.BooleanSwitch",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (!TYPES.has(nodeData?.name)) return;
    const onCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const r = onCreated?.apply(this, arguments);
      style(this);
      hookResize(this);
      defaultSizeOnce(this);
      return r;
    };
  },
  nodeCreated(node) {
    if (!TYPES.has(node.comfyClass) && !TYPES.has(node.type)) return;
    style(node);
    hookResize(node);
    defaultSizeOnce(node);
  },
});
