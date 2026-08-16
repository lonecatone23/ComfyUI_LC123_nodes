/**
 * LC Dynamic Overlay — live opacity preview
 * Simple sizing (same idea as lc_image_preview): set default once, free resize after.
 * No setSize wrapper — that was blocking shrink.
 */

import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const NODE_CLASS = "LCDynamicOverlay";
const DEFAULT_W = 300;
const MIN_W = 260;
const PAD = 16;
const KNOB_R = 22;
const GAP = 8;
const TOP = 36;

function defaultHeight() {
  const innerW = DEFAULT_W - PAD * 2;
  const imgH = Math.round(innerW * (5 / 4)); // 4:5 preview like other LC image nodes
  const imgY = TOP + KNOB_R * 2 + GAP;
  return imgY + imgH + PAD;
}

const DEFAULT_H = defaultHeight();

function viewUrl(meta) {
  if (!meta) return null;
  if (typeof meta === "string") return meta;
  const q = new URLSearchParams();
  q.set("filename", meta.filename || "");
  q.set("subfolder", meta.subfolder != null ? meta.subfolder : "");
  q.set("type", meta.type || "temp");
  return api.apiURL(`/view?${q.toString()}`);
}

function loadImg(url) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => resolve(img);
    img.onerror = (e) => reject(e);
    img.src = url;
  });
}

async function metaToCanvas(meta) {
  const url = viewUrl(meta);
  if (!url) return null;
  const img = await loadImg(url);
  const c = document.createElement("canvas");
  c.width = img.naturalWidth;
  c.height = img.naturalHeight;
  c.getContext("2d").drawImage(img, 0, 0);
  return c;
}

function hideWidget(widget) {
  if (!widget || widget._lcHidden) return;
  widget._lcHidden = true;
  widget.computeSize = () => [0, -4];
  widget.draw = () => {};
  if (widget.element) {
    try {
      widget.element.style.display = "none";
    } catch (_) {}
  }
  widget.type = "hidden";
}

function angleToOpacity(dx, dy) {
  let a = Math.atan2(dy, dx);
  if (a < 0) a += Math.PI * 2;
  const start = Math.PI * 0.75;
  const span = Math.PI * 1.5;
  let rel = a - start;
  if (rel < 0) rel += Math.PI * 2;
  if (rel > span) {
    const midGap = span + (Math.PI * 2 - span) / 2;
    return rel < midGap ? 1 : 0;
  }
  return Math.max(0, Math.min(1, rel / span));
}

function killNativePreview(node) {
  try {
    node.imgs = null;
    node.imageIndex = null;
    node.overIndex = null;
  } catch (_) {}
}

function fitRect(srcW, srcH, boxW, boxH) {
  const scale = Math.min(boxW / Math.max(srcW, 1), boxH / Math.max(srcH, 1));
  const drawW = Math.max(1, Math.round(srcW * scale));
  const drawH = Math.max(1, Math.round(srcH * scale));
  return {
    drawW,
    drawH,
    ox: Math.floor((boxW - drawW) / 2),
    oy: Math.floor((boxH - drawH) / 2),
  };
}

function paintKnob(ctx, cx, cy, t) {
  const startAng = Math.PI * 0.75;
  const span = Math.PI * 1.5;
  const endAng = startAng + span * t;
  const trackR = KNOB_R - 3;
  const thumbR = 6;

  ctx.save();
  ctx.beginPath();
  ctx.arc(cx, cy, KNOB_R, 0, Math.PI * 2);
  ctx.fillStyle = "#1a1a1a";
  ctx.fill();
  ctx.strokeStyle = "#555";
  ctx.lineWidth = 1.5;
  ctx.stroke();

  ctx.beginPath();
  ctx.arc(cx, cy, trackR, startAng, startAng + span, false);
  ctx.strokeStyle = "#333";
  ctx.lineWidth = 5;
  ctx.lineCap = "round";
  ctx.stroke();

  if (t > 0.001) {
    ctx.beginPath();
    ctx.arc(cx, cy, trackR, startAng, endAng, false);
    ctx.strokeStyle = "#3d7ab8";
    ctx.lineWidth = 5;
    ctx.lineCap = "round";
    ctx.stroke();
  }

  const tx = cx + Math.cos(endAng) * trackR;
  const ty = cy + Math.sin(endAng) * trackR;
  ctx.beginPath();
  ctx.arc(tx, ty, thumbR, 0, Math.PI * 2);
  ctx.fillStyle = "#f2f2f2";
  ctx.fill();
  ctx.strokeStyle = "#111";
  ctx.lineWidth = 1;
  ctx.stroke();

  ctx.fillStyle = "#eee";
  ctx.font = "bold 11px sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(`${Math.round(t * 100)}%`, cx, cy);
  ctx.restore();
}

app.registerExtension({
  name: "LC123.DynamicOverlay",

  async beforeRegisterNodeDef(nodeType, nodeData) {
    if ((nodeData?.name || "") !== NODE_CLASS) return;

    const origCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const r = origCreated?.apply(this, arguments);
      this.color = "#324B4B";
      this.bgcolor = "#324B4B";

      this._lc = {
        a: null,
        b: null,
        opacity: 0.5,
        dragging: false,
        draw: null,
      };

      // Default size once (same footprint idea as other LC image nodes)
      this.size = [DEFAULT_W, DEFAULT_H];

      const setupOpacity = () => {
        const ow = (this.widgets || []).find((w) => w.name === "opacity");
        if (!ow) return;
        this._lc.opacity = Math.max(0, Math.min(1, Number(ow.value) || 0.5));
        hideWidget(ow);
        if (!ow._lcBound) {
          ow._lcBound = true;
          const prev = ow.callback;
          ow.callback = (v, ...args) => {
            this._lc.opacity = Math.max(0, Math.min(1, Number(v) || 0));
            this.setDirtyCanvas?.(true, true);
            return prev?.apply(ow, [v, ...args]);
          };
        }
      };
      setupOpacity();
      setTimeout(setupOpacity, 30);

      killNativePreview(this);
      return r;
    };

    const origConfigure = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function (data) {
      const r = origConfigure?.apply(this, arguments);
      // Keep size from graph JSON when loading a workflow
      if (data?.size && Array.isArray(data.size) && data.size.length >= 2) {
        this.size = [
          Math.max(MIN_W, data.size[0]),
          Math.max(120, data.size[1]),
        ];
      }
      killNativePreview(this);
      return r;
    };

    const origExecuted = nodeType.prototype.onExecuted;
    nodeType.prototype.onExecuted = function (message) {
      const r = origExecuted?.apply(this, arguments);
      killNativePreview(this);

      const images = message?.images;
      if (!images?.length) return r;

      const self = this;
      const saved = [this.size?.[0], this.size?.[1]];
      (async () => {
        try {
          if (images[0]) self._lc.a = await metaToCanvas(images[0]);
          if (images[1]) self._lc.b = await metaToCanvas(images[1]);
          const ow = (self.widgets || []).find((w) => w.name === "opacity");
          if (ow) {
            self._lc.opacity = Math.max(0, Math.min(1, Number(ow.value) || 0));
            hideWidget(ow);
          }
        } catch (e) {
          console.warn("[LC Overlay] preview load error", e);
        }
        // Do not change size after load — only restore if Comfy blew it up
        killNativePreview(self);
        if (
          saved[0] &&
          saved[1] &&
          self.size &&
          (self.size[1] > saved[1] + 80 || self.size[0] > saved[0] + 80)
        ) {
          self.size[0] = saved[0];
          self.size[1] = saved[1];
        }
        self.setDirtyCanvas?.(true, true);
      })();

      return r;
    };

    const origResize = nodeType.prototype.onResize;
    nodeType.prototype.onResize = function (size) {
      if (size) {
        if (size[0] < MIN_W) size[0] = MIN_W;
        if (size[1] < 120) size[1] = 120;
      }
      return origResize?.apply(this, arguments);
    };

    const origDrawFG = nodeType.prototype.onDrawForeground;
    nodeType.prototype.onDrawForeground = function (ctx) {
      killNativePreview(this);
      const r = origDrawFG?.apply(this, arguments);
      if (this.flags?.collapsed) return r;
      this._lcPaint(ctx);
      return r;
    };

    const origDrawBG = nodeType.prototype.onDrawBackground;
    nodeType.prototype.onDrawBackground = function (ctx) {
      killNativePreview(this);
      return origDrawBG?.apply(this, arguments);
    };

    nodeType.prototype._lcPaint = function (ctx) {
      const s = this._lc || {};
      const nodeW = this.size?.[0] || DEFAULT_W;
      const nodeH = this.size?.[1] || DEFAULT_H;
      const t = Math.max(0, Math.min(1, s.opacity ?? 0.5));

      const imgY = TOP + KNOB_R * 2 + GAP;
      const boxW = Math.max(40, nodeW - PAD * 2);
      const boxH = Math.max(40, nodeH - imgY - PAD);

      const cx = PAD + boxW / 2;
      const cy = TOP + KNOB_R;
      s.draw = { cx, cy, r: KNOB_R + 6 };

      paintKnob(ctx, cx, cy, t);

      ctx.save();
      ctx.fillStyle = "#121212";
      ctx.fillRect(PAD, imgY, boxW, boxH);
      ctx.strokeStyle = "#3a3a3a";
      ctx.lineWidth = 1;
      ctx.strokeRect(PAD, imgY, boxW, boxH);

      if (s.a) {
        const fit = fitRect(s.a.width, s.a.height, boxW, boxH);
        const sx = PAD + fit.ox;
        const sy = imgY + fit.oy;
        ctx.save();
        ctx.beginPath();
        ctx.rect(PAD, imgY, boxW, boxH);
        ctx.clip();
        ctx.drawImage(
          s.a,
          0,
          0,
          s.a.width,
          s.a.height,
          sx,
          sy,
          fit.drawW,
          fit.drawH
        );
        if (s.b) {
          ctx.globalAlpha = t;
          ctx.drawImage(
            s.b,
            0,
            0,
            s.b.width,
            s.b.height,
            sx,
            sy,
            fit.drawW,
            fit.drawH
          );
          ctx.globalAlpha = 1;
        }
        ctx.restore();
        ctx.strokeStyle = "#444";
        ctx.strokeRect(sx, sy, fit.drawW, fit.drawH);
      } else {
        ctx.fillStyle = "#666";
        ctx.font = "12px sans-serif";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(
          "Run once for preview",
          PAD + boxW / 2,
          imgY + boxH / 2
        );
      }
      ctx.restore();
    };

    nodeType.prototype._lcSetOpacity = function (t) {
      t = Math.max(0, Math.min(1, t));
      if (!this._lc) this._lc = {};
      this._lc.opacity = t;
      const ow = (this.widgets || []).find((w) => w.name === "opacity");
      if (ow) ow.value = Math.round(t * 100) / 100;
      this.setDirtyCanvas?.(true, true);
    };

    nodeType.prototype._lcHitKnob = function (pos) {
      const d = this._lc?.draw;
      if (!d) return false;
      const dx = pos[0] - d.cx;
      const dy = pos[1] - d.cy;
      return dx * dx + dy * dy <= d.r * d.r;
    };

    const origDown = nodeType.prototype.onMouseDown;
    nodeType.prototype.onMouseDown = function (e, pos) {
      if (this._lcHitKnob(pos)) {
        this._lc.dragging = true;
        const d = this._lc.draw;
        this._lcSetOpacity(angleToOpacity(pos[0] - d.cx, pos[1] - d.cy));
        return true;
      }
      return origDown?.apply(this, arguments);
    };

    const origMove = nodeType.prototype.onMouseMove;
    nodeType.prototype.onMouseMove = function (e, pos) {
      if (this._lc?.dragging) {
        const d = this._lc.draw;
        if (d) this._lcSetOpacity(angleToOpacity(pos[0] - d.cx, pos[1] - d.cy));
        return true;
      }
      return origMove?.apply(this, arguments);
    };

    const origUp = nodeType.prototype.onMouseUp;
    nodeType.prototype.onMouseUp = function (e, pos) {
      if (this._lc?.dragging) {
        this._lc.dragging = false;
        return true;
      }
      return origUp?.apply(this, arguments);
    };
  },
});

console.log("[LC123.DynamicOverlay] simple size (no setSize lock)");
