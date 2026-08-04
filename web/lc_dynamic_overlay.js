/**
 * LC Dynamic Overlay — live opacity preview
 * ------------------------------------------------
 * Circular knob (not a flat bar) above the image.
 * Python opacity widget is hidden; value still drives the graph.
 *
 * ui.images: [0]=A  [1]=B(fit)  [2]=composite
 */

import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const NODE_CLASS = "LCDynamicOverlay";

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

/** Hide widget, keep value for the graph. */
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

/**
 * Map opacity 0..1 ↔ angle on a 270° arc.
 * Bottom-left (−135°) = 0%, bottom-right (+135°) = 100%.
 * Angle is in radians, 0 = east, CCW positive (canvas).
 */
function opacityToAngle(t) {
  // start at 135° (SW) going clockwise to 45° (SE) → use canvas arcs carefully
  // We draw from startAng to endAng clockwise for fill.
  const start = Math.PI * 0.75; // 135°
  const span = Math.PI * 1.5; // 270°
  return start + span * Math.max(0, Math.min(1, t));
}

function angleToOpacity(dx, dy) {
  // atan2 from knob center; convert to 0..1 along the 270° arc
  let a = Math.atan2(dy, dx); // -PI..PI, 0 = east
  // Normalize to [0, 2PI)
  if (a < 0) a += Math.PI * 2;
  const start = Math.PI * 0.75; // 135°
  const span = Math.PI * 1.5; // 270°
  // Offset so start → 0
  let rel = a - start;
  if (rel < 0) rel += Math.PI * 2;
  // Clamp to arc; values past the dead zone snap to ends
  if (rel > span) {
    // In the 90° gap at the bottom — pick nearer end
    const midGap = span + (Math.PI * 2 - span) / 2;
    return rel < midGap ? 1 : 0;
  }
  return Math.max(0, Math.min(1, rel / span));
}

app.registerExtension({
  name: "LC123.DynamicOverlay",

  async beforeRegisterNodeDef(nodeType, nodeData) {
    if ((nodeData?.name || "") !== NODE_CLASS) return;

    const origCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const r = origCreated?.apply(this, arguments);

      this._lc = {
        a: null,
        b: null,
        opacity: 0.5,
        dragging: false,
        draw: null, // { cx, cy, r }
      };

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
        this.setSize?.(this.computeSize?.() || this.size);
      };
      setupOpacity();
      setTimeout(setupOpacity, 30);
      setTimeout(setupOpacity, 120);

      return r;
    };

    const origExecuted = nodeType.prototype.onExecuted;
    nodeType.prototype.onExecuted = function (message) {
      const r = origExecuted?.apply(this, arguments);
      const images = message?.images;
      if (!images?.length) return r;

      const self = this;
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
        self.setDirtyCanvas?.(true, true);
      })();

      return r;
    };

    const origDrawFG = nodeType.prototype.onDrawForeground;
    nodeType.prototype.onDrawForeground = function (ctx) {
      const r = origDrawFG?.apply(this, arguments);
      this._lcPaint(ctx);
      return r;
    };

    const origDrawBG = nodeType.prototype.onDrawBackground;
    nodeType.prototype.onDrawBackground = function (ctx) {
      if (this.imgs) this.imgs = null;
      if (this.imageIndex != null) this.imageIndex = null;
      return origDrawBG?.apply(this, arguments);
    };

    nodeType.prototype._lcPaint = function (ctx) {
      const s = this._lc;
      if (!s?.a) return;

      const margin = 8;
      const knobR = 22; // outer radius of the circle control
      const gap = 8;
      const top = 34;

      const availW = Math.max(48, this.size[0] - margin * 2);
      const srcW = s.a.width;
      const srcH = s.a.height;
      const scale = availW / Math.max(srcW, 1);
      const drawW = Math.round(srcW * scale);
      const drawH = Math.round(srcH * scale);

      const sx = margin;
      // Knob centered above the image
      const cx = sx + drawW / 2;
      const cy = top + knobR;
      const imgY = top + knobR * 2 + gap;

      const needH = imgY + drawH + margin + 4;
      if (this.size[1] < needH) this.size[1] = needH;

      s.draw = { cx, cy, r: knobR + 6 }; // hit radius slightly larger

      const t = Math.max(0, Math.min(1, s.opacity));
      const startAng = Math.PI * 0.75; // 135°
      const span = Math.PI * 1.5; // 270°
      const endAng = startAng + span * t;
      const trackR = knobR - 3;
      const thumbR = 6;

      // ---- circular knob ----
      ctx.save();

      // Outer disc
      ctx.beginPath();
      ctx.arc(cx, cy, knobR, 0, Math.PI * 2);
      ctx.fillStyle = "#1a1a1a";
      ctx.fill();
      ctx.strokeStyle = "#555";
      ctx.lineWidth = 1.5;
      ctx.stroke();

      // Track (full 270° arc, muted)
      ctx.beginPath();
      ctx.arc(cx, cy, trackR, startAng, startAng + span, false);
      ctx.strokeStyle = "#333";
      ctx.lineWidth = 5;
      ctx.lineCap = "round";
      ctx.stroke();

      // Value arc
      if (t > 0.001) {
        ctx.beginPath();
        ctx.arc(cx, cy, trackR, startAng, endAng, false);
        ctx.strokeStyle = "#3d7ab8";
        ctx.lineWidth = 5;
        ctx.lineCap = "round";
        ctx.stroke();
      }

      // Thumb on the arc
      const thumbAng = endAng;
      const tx = cx + Math.cos(thumbAng) * trackR;
      const ty = cy + Math.sin(thumbAng) * trackR;
      ctx.beginPath();
      ctx.arc(tx, ty, thumbR, 0, Math.PI * 2);
      ctx.fillStyle = "#f2f2f2";
      ctx.fill();
      ctx.strokeStyle = "#111";
      ctx.lineWidth = 1;
      ctx.stroke();

      // Center label
      ctx.fillStyle = "#eee";
      ctx.font = "bold 11px sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(`${Math.round(t * 100)}%`, cx, cy);

      ctx.restore();

      // ---- image composite ----
      ctx.save();
      ctx.beginPath();
      ctx.rect(sx, imgY, drawW, drawH);
      ctx.clip();

      ctx.globalAlpha = 1;
      ctx.drawImage(s.a, 0, 0, srcW, srcH, sx, imgY, drawW, drawH);

      if (s.b) {
        ctx.globalAlpha = t;
        ctx.drawImage(s.b, 0, 0, s.b.width, s.b.height, sx, imgY, drawW, drawH);
      }
      ctx.globalAlpha = 1;
      ctx.restore();

      ctx.strokeStyle = "#444";
      ctx.lineWidth = 1;
      ctx.strokeRect(sx, imgY, drawW, drawH);
    };

    nodeType.prototype._lcSetOpacity = function (t) {
      t = Math.max(0, Math.min(1, t));
      this._lc.opacity = t;
      const ow = (this.widgets || []).find((w) => w.name === "opacity");
      if (ow) ow.value = Math.round(t * 100) / 100;
      this.setDirtyCanvas?.(true, true);
    };

    nodeType.prototype._lcHitKnob = function (pos) {
      const d = this._lc?.draw;
      if (!d || !this._lc?.a) return false;
      const [x, y] = pos;
      const dx = x - d.cx;
      const dy = y - d.cy;
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
        if (d) {
          this._lcSetOpacity(angleToOpacity(pos[0] - d.cx, pos[1] - d.cy));
        }
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

console.log("[LC123.DynamicOverlay] circular opacity knob");
