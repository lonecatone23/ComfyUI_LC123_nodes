/**
 * LC Speed Boost: what it did on the last run, under the node. A model it can't work on gets a ⚠️ line and a toast,
 * so "nothing happened" never looks like "Speed Boost is slow". Cleared when a new run starts.
 */
import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const CLASSES = ["LCSpeedBoost", "LCSpeedBoostKSampler"];
const COLORS = { warn: "#f0b040", info: "#9aa4b2", ok: "#6fd3a0" };

function findNode(id) {
  const key = String(id).split(":").pop();
  const graphs = [app.graph, ...((app.graph?._subgraphs && [...app.graph._subgraphs.values()]) || [])];
  for (const g of graphs) {
    const n = g?.getNodeById?.(key) ?? g?.getNodeById?.(Number(key));
    if (n && CLASSES.includes(n.comfyClass || n.type)) return n;
  }
  return null;
}

function wrap(ctx, text, width) {
  const words = text.split(" ");
  const lines = [];
  let cur = "";
  for (const w of words) {
    const t = cur ? cur + " " + w : w;
    if (ctx.measureText(t).width > width && cur) {
      lines.push(cur);
      cur = w;
    } else cur = t;
  }
  if (cur) lines.push(cur);
  return lines.slice(0, 4);
}

api.addEventListener("lc_speed_boost_status", (e) => {
  const d = e.detail || {};
  const n = findNode(d.node);
  if (n) {
    n._lcBoostStatus = { text: d.text, level: d.level };
    n.setDirtyCanvas?.(true, true);
  }
  if (d.level === "warn") {
    try {
      app.extensionManager?.toast?.add({ severity: "warn", summary: "LC Speed Boost", detail: d.text, life: 9000 });
    } catch (_e) {}
  }
});

api.addEventListener("execution_start", () => {
  for (const n of app.graph?._nodes || []) {
    if (n._lcBoostStatus) {
      n._lcBoostStatus = null;
      n.setDirtyCanvas?.(true, true);
    }
  }
});

app.registerExtension({
  name: "LC.SpeedBoost.Status",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (!CLASSES.includes(nodeData.name)) return;
    const draw = nodeType.prototype.onDrawForeground;
    nodeType.prototype.onDrawForeground = function (ctx) {
      const r = draw?.apply(this, arguments);
      const st = this._lcBoostStatus;
      if (!st || this.flags?.collapsed) return r;
      ctx.save();
      ctx.font = "12px sans-serif";
      ctx.fillStyle = COLORS[st.level] || COLORS.info;
      ctx.textAlign = "left";
      const lines = wrap(ctx, st.text, Math.max(160, this.size[0] - 8));
      lines.forEach((ln, i) => ctx.fillText(ln, 4, this.size[1] + 16 + i * 15));
      ctx.restore();
      return r;
    };
  },
});
