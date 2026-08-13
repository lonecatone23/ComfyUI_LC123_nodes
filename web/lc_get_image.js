/**
 * LC Get Image 📐 — stacked readout aligned to output sockets
 */
import { app } from "../../scripts/app.js";

const DEFAULT_W = 270;
const MIN_H = 140;

app.registerExtension({
  name: "LC123.GetImage",

  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== "LCGetImage") return;

    const onNodeCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      if (onNodeCreated) onNodeCreated.apply(this, arguments);
      this.color = "#324b4b";
      this.bgcolor = "#324b4b";
      this._lcText = "";
      this._lcLines = [];
      this.size = [DEFAULT_W, Math.max(MIN_H, this.size?.[1] || MIN_H)];
    };

    const onExecuted = nodeType.prototype.onExecuted;
    nodeType.prototype.onExecuted = function (message) {
      if (onExecuted) onExecuted.apply(this, arguments);
      if (message?.lc_mp) {
        this._lcDisplay = [
          { k: "megapixels", v: message.lc_mp[0] ?? "—" },
          { k: "width", v: message.lc_w?.[0] ?? "—" },
          { k: "height", v: message.lc_h?.[0] ?? "—" },
          { k: "resolution", v: message.lc_res?.[0] ?? "—" },
          { k: "batch", v: message.lc_batch?.[0] ?? "—" },
          { k: "aspect ratio", v: message.lc_aspect?.[0] ?? "—" },
        ];
      } else if (message?.text) {
        const raw = Array.isArray(message.text)
          ? message.text.join(" ")
          : String(message.text);
        this._lcText = raw;
        this._lcLines = raw.split("|").map((s) => s.trim()).filter(Boolean);
        this._lcDisplay = null;
      }
      this.setDirtyCanvas?.(true, true);
    };

    const onDrawFG = nodeType.prototype.onDrawForeground;
    nodeType.prototype.onDrawForeground = function (ctx) {
      if (onDrawFG) onDrawFG.apply(this, arguments);

      let display = this._lcDisplay;
      if (!display || !display.length) {
        if (this._lcText) {
          display = [{ k: "", v: this._lcText }];
        } else {
          return;
        }
      }

      ctx.save();
      ctx.font = "12px sans-serif";
      ctx.textAlign = "left";
      ctx.textBaseline = "middle";

      const titleH = 30;
      const usable = Math.max(20, this.size[1] - titleH - 8);
      for (let i = 0; i < display.length; i++) {
        const y = titleH + (usable / (display.length + 1)) * (i + 1);
        const line = display[i];
        ctx.fillStyle = "#888";
        ctx.fillText(line.k, 12, y);
        ctx.fillStyle = "#e8e8e8";
        const kw = ctx.measureText(line.k + "  ").width;
        ctx.fillText(String(line.v), 12 + Math.max(kw, 78), y);
      }
      ctx.restore();
    };
  },
});
