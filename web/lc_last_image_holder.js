/**
 * LC Last Image Holder — frontend
 * Clear button + default size. Does not re-run workflow on clear.
 */

import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const NODE_TYPE = "LCLastImageHolder";
const DEFAULT_W = 300;
const DEFAULT_H = 420;

function clearNodePreview(node) {
  if (node.imgs) node.imgs = [];
  if (node.imageIndex !== undefined) node.imageIndex = null;
  if (node.overwroteProperties) delete node.overwroteProperties;
  node.setDirtyCanvas?.(true, true);
  app.graph?.setDirtyCanvas?.(true, true);
}

app.registerExtension({
  name: "LC123.LastImageHolder",

  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== NODE_TYPE) return;

    const onNodeCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      if (onNodeCreated) onNodeCreated.apply(this, arguments);

      this.color = "#324B4B";
      this.bgcolor = "#324B4B";
      this.size = [DEFAULT_W, DEFAULT_H];

      const node = this;

      const btn = node.addWidget("button", "Clear held image", "clear_btn", async () => {
        const nodeId = String(node.id);
        try {
          await api.fetchApi("/lc123/last_image_holder/clear", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ node_id: nodeId }),
          });
        } catch (err) {
          console.warn("[LC Last Image Holder] clear API failed:", err);
        }
        clearNodePreview(node);
      });

      if (btn) {
        btn.tooltip =
          "Delete the stored image and clear the preview. Does not re-run the workflow.";
      }
    };

    const onExecuted = nodeType.prototype.onExecuted;
    nodeType.prototype.onExecuted = function (message) {
      if (onExecuted) onExecuted.apply(this, arguments);
      if (message && Array.isArray(message.images) && message.images.length === 0) {
        clearNodePreview(this);
      }
    };
  },
});

console.log("[LC123.LastImageHolder] ready");
