/**
 * LC Show Text — draw multiline text on the node (preserve real newlines).
 * Default size matches LC Join Strings (~270×118).
 */

import { app } from "../../scripts/app.js";

const NODE_CLASS = "LCShowText";
const DEFAULT_W = 270;
const DEFAULT_H = 118;
const PAD = 10;
const TITLE = 30;

app.registerExtension({
  name: "LC123.ShowText",

  async beforeRegisterNodeDef(nodeType, nodeData) {
    if ((nodeData?.name || "") !== NODE_CLASS) return;

    const onCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const r = onCreated?.apply(this, arguments);
      this.color = "#28281E";
      this.bgcolor = "#28281E";
      this._lcShowText = this.properties?.lc_show_text != null
        ? String(this.properties.lc_show_text)
        : "";
      if (typeof this.setSize === "function") {
        this.setSize([DEFAULT_W, DEFAULT_H]);
      } else {
        this.size = [DEFAULT_W, DEFAULT_H];
      }
      return r;
    };

    const onExecuted = nodeType.prototype.onExecuted;
    nodeType.prototype.onExecuted = function (message) {
      const r = onExecuted?.apply(this, arguments);
      let t = null;
      if (message?.text != null) {
        t = Array.isArray(message.text) ? message.text[0] : message.text;
      }
      if (t != null) {
        // Exact content — no trim, no escape interpretation
        this._lcShowText = String(t);
        if (!this.properties) this.properties = {};
        this.properties.lc_show_text = this._lcShowText;
        this.setDirtyCanvas?.(true, true);
      }
      return r;
    };

    const onConfigure = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function (data) {
      const r = onConfigure?.apply(this, arguments);
      if (this.properties?.lc_show_text != null) {
        this._lcShowText = String(this.properties.lc_show_text);
      }
      return r;
    };

    const onDrawFG = nodeType.prototype.onDrawForeground;
    nodeType.prototype.onDrawForeground = function (ctx) {
      if (onDrawFG) onDrawFG.apply(this, arguments);
      const raw = this._lcShowText;
      if (raw == null || raw === "") return;

      const x = PAD;
      const y = TITLE;
      const w = Math.max(1, (this.size?.[0] || DEFAULT_W) - PAD * 2);
      const h = Math.max(1, (this.size?.[1] || DEFAULT_H) - TITLE - PAD);

      ctx.save();
      ctx.beginPath();
      ctx.rect(x, y, w, h);
      ctx.clip();

      ctx.fillStyle = "#e8e8e8";
      ctx.font = "12px monospace";
      ctx.textAlign = "left";
      ctx.textBaseline = "top";

      const lineHeight = 14;
      const lines = String(raw).split("\n");
      let yy = y;
      for (const line of lines) {
        if (yy > y + h) break;
        if (ctx.measureText(line).width <= w) {
          ctx.fillText(line, x, yy);
          yy += lineHeight;
        } else {
          let rest = line;
          while (rest.length && yy <= y + h) {
            let cut = rest.length;
            while (cut > 1 && ctx.measureText(rest.slice(0, cut)).width > w) {
              cut--;
            }
            const space = rest.lastIndexOf(" ", cut);
            if (space > 8 && space < cut) cut = space + 1;
            ctx.fillText(rest.slice(0, cut), x, yy);
            rest = rest.slice(cut);
            yy += lineHeight;
          }
        }
      }
      ctx.restore();
    };
  },
});
