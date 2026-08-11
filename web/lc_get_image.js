/**
 * LC Get Image 📐 — stacked readout aligned to output sockets
 */
import { app } from "../../scripts/app.js";

const DEFAULT_W = 270;
const MIN_H = 120;

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
      // Prefer structured fields if present, else parse text
      const lines = [];
      if (message?.lc_mp) {
        this._lcDisplay = [
          { k: "megapixels", v: (message.lc_mp[0] ?? "—") },
          { k: "width", v: (message.lc_w?.[0] ?? "—") },
          { k: "height", v: (message.lc_h?.[0] ?? "—") },
          { k: "batch", v: (message.lc_batch?.[0] ?? "—") },
          { k: "aspect ratio", v: (message.lc_aspect?.[0] ?? "—") },
        ];
      } else if (message?.text) {
        const raw = Array.isArray(message.text) ? message.text.join(" ") : String(message.text);
        this._lcText = raw;
        const parts = raw.split("|").map((s) => s.trim()).filter(Boolean);
        this._lcLines = parts;
        this._lcDisplay = null;
      }
      this.setDirtyCanvas?.(true, true);
    };

    const onDrawFG = nodeType.prototype.onDrawForeground;
    nodeType.prototype.onDrawForeground = function (ctx) {
      if (onDrawFG) onDrawFG.apply(this, arguments);

      // Labels match socket order top→bottom: megapixels, width, height, batch, aspect
      const labels = ["MP", "W", "H", "Batch", "Aspect"];
      let display = this._lcDisplay;
      if (!display || !display.length) {
        const values = this._lcLines || [];
        if (values.length >= 4) {
          const mp = values[0]?.replace(/\s*MP/i, "").trim() || "—";
          let w = "—", h = "—";
          const m = (values[1] || "").match(/(\d+)\s*[×x]\s*(\d+)/);
          if (m) { w = m[1]; h = m[2]; }
          display = [
            { k: "megapixels", v: mp },
            { k: "width", v: w },
            { k: "height", v: h },
            { k: "batch", v: (values[3] || "").replace(/batch\s*/i, "").trim() || "—" },
            { k: "aspect ratio", v: values[2] || "—" },
          ];
        } else if (this._lcText) {
          display = [{ k: "", v: this._lcText }];
        } else {
          return;
        }
      }

      const nOut = (this.outputs || []).length || display.length;
      const slot = LiteGraph?.NODE_SLOT_HEIGHT || 20;
      // First output y roughly at 0 relative to body; LiteGraph draws slots from top
      // Center text vertically on each output row
      const startY = 0; // relative to node body after title — onDrawForeground is body space
      // In Comfy, onDrawForeground coords: origin top-left of node including title offset varies.
      // Use output slot positions when available.
      ctx.save();
      ctx.font = "12px sans-serif";
      ctx.textAlign = "left";
      ctx.textBaseline = "middle";

      for (let i = 0; i < display.length; i++) {
        let y;
        if (this.outputs && this.outputs[i]) {
          // outputs[i].pos may not exist; approximate slot center
          y = LiteGraph.NODE_TITLE_HEIGHT
            ? (LiteGraph.NODE_TITLE_HEIGHT || 30) + 10 + i * (LiteGraph.NODE_SLOT_HEIGHT || 20)
            : 40 + i * 20;
        } else {
          y = 40 + i * 20;
        }
        // Safer: distribute in middle of node body under title
        const titleH = 30;
        const usable = Math.max(20, this.size[1] - titleH - 8);
        y = titleH + (usable / (display.length + 1)) * (i + 1);

        const line = display[i];
        ctx.fillStyle = "#888";
        ctx.fillText(line.k, 12, y);
        ctx.fillStyle = "#e8e8e8";
        const kw = ctx.measureText(line.k + "  ").width;
        ctx.fillText(String(line.v), 12 + Math.max(kw, 70), y);
      }
      ctx.restore();
    };
  },
});
