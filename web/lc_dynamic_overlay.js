/**
 * LC Dynamic Overlay — live opacity preview
 * ------------------------------------------------
 * Circular knob above the image. Python opacity widget is hidden.
 * Node size is retained across refresh and re-queue.
 *
 * ui.images: [0]=A  [1]=B(fit)  [2]=composite
 */

import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const NODE_CLASS = "LCDynamicOverlay";
const MIN_W = 300;
const MIN_H = 400;
const MARGIN = 16;
const KNOB_R = 22;
const GAP = 8;
const TOP = 34;

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

/** Height needed for current node width + image A aspect. */
function neededSize(node) {
  const a = node._lc?.a;
  const w = Math.max(MIN_W, node.size?.[0] || MIN_W);
  if (!a) {
    return [w, Math.max(MIN_H, node.size?.[1] || MIN_H)];
  }
  const availW = Math.max(48, w - MARGIN * 2);
  const scale = availW / Math.max(a.width, 1);
  const drawH = Math.round(a.height * scale);
  const imgY = TOP + KNOB_R * 2 + GAP;
  const h = imgY + drawH + MARGIN + 4;
  return [w, Math.max(MIN_H, h)];
}

/**
 * Apply size without fighting user resize:
 * - Never shrink below the last good stored size unless force.
 * - Update properties so refresh keeps it.
 */
function applySize(node, force) {
  const [nw, nh] = neededSize(node);
  if (!node.size) node.size = [nw, nh];

  const curW = node.size[0] || MIN_W;
  const curH = node.size[1] || MIN_H;

  // Keep user width if they resized wider; only grow height to fit image
  const w = force ? nw : Math.max(curW, nw);
  const h = force ? nh : Math.max(curH, nh);

  if (typeof node.setSize === "function") {
    node.setSize([w, h]);
  } else {
    node.size[0] = w;
    node.size[1] = h;
  }

  // Persist for configure / refresh
  if (!node.properties) node.properties = {};
  node.properties.lc_overlay_w = w;
  node.properties.lc_overlay_h = h;
  node._lc.lastW = w;
  node._lc.lastH = h;
}

function restoreSavedSize(node) {
  const pw = node.properties?.lc_overlay_w;
  const ph = node.properties?.lc_overlay_h;
  const w = Number(pw) || node._lc?.lastW || node.size?.[0] || MIN_W;
  const h = Number(ph) || node._lc?.lastH || node.size?.[1] || MIN_H;
  if (typeof node.setSize === "function") {
    node.setSize([Math.max(MIN_W, w), Math.max(MIN_H, h)]);
  } else if (node.size) {
    node.size[0] = Math.max(MIN_W, w);
    node.size[1] = Math.max(MIN_H, h);
  }
}

app.registerExtension({
  name: "LC123.DynamicOverlay",

  async beforeRegisterNodeDef(nodeType, nodeData) {
    if ((nodeData?.name || "") !== NODE_CLASS) return;

    // Size from image when available
    const origCompute = nodeType.prototype.computeSize;
    nodeType.prototype.computeSize = function (out) {
      if (this._lc?.a) {
        const [w, h] = neededSize(this);
        const size = [w, h];
        if (out) {
          out[0] = size[0];
          out[1] = size[1];
          return out;
        }
        return size;
      }
      const size = origCompute?.apply(this, arguments) || [MIN_W, MIN_H];
      size[0] = Math.max(MIN_W, size[0] || MIN_W);
      size[1] = Math.max(MIN_H, size[1] || MIN_H);
      if (out) {
        out[0] = size[0];
        out[1] = size[1];
        return out;
      }
      return size;
    };

    const origCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const r = origCreated?.apply(this, arguments);

      this.color = "#324b4b";
      this.bgcolor = "#324b4b";
      this.size = [300, 420];

      this._lc = {
        a: null,
        b: null,
        opacity: 0.5,
        dragging: false,
        draw: null,
        lastW: null,
        lastH: null,
      };

      if (!this.properties) this.properties = {};

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
      setTimeout(setupOpacity, 120);

      // Initial compact size; grow after first preview
      restoreSavedSize(this);
      if (!this.properties.lc_overlay_w) {
        applySize(this, true);
      }

      return r;
    };

    const origConfigure = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function (data) {
      const r = origConfigure?.apply(this, arguments);
      // Prefer size from graph JSON, then properties
      if (data?.size && Array.isArray(data.size) && data.size.length >= 2) {
        if (!this.properties) this.properties = {};
        this.properties.lc_overlay_w = data.size[0];
        this.properties.lc_overlay_h = data.size[1];
      }
      setTimeout(() => {
        restoreSavedSize(this);
        this.setDirtyCanvas?.(true, true);
      }, 0);
      setTimeout(() => restoreSavedSize(this), 50);
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
          // Fit height to image; keep user width if larger
          applySize(self, false);
        } catch (e) {
          console.warn("[LC Overlay] preview load error", e);
        }
        self.setDirtyCanvas?.(true, true);
      })();

      return r;
    };

    // After user resizes, remember
    const origResize = nodeType.prototype.onResize;
    nodeType.prototype.onResize = function (size) {
      const r = origResize?.apply(this, arguments);
      if (size && this._lc) {
        if (!this.properties) this.properties = {};
        this.properties.lc_overlay_w = size[0];
        this.properties.lc_overlay_h = size[1];
        this._lc.lastW = size[0];
        this._lc.lastH = size[1];
      }
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

      const availW = Math.max(48, this.size[0] - MARGIN * 2);
      const srcW = s.a.width;
      const srcH = s.a.height;
      const scale = availW / Math.max(srcW, 1);
      const drawW = Math.round(srcW * scale);
      const drawH = Math.round(srcH * scale);

      const sx = MARGIN;
      const cx = sx + drawW / 2;
      const cy = TOP + KNOB_R;
      const imgY = TOP + KNOB_R * 2 + GAP;

      // Grow only if too short — never collapse on redraw
      const needH = imgY + drawH + MARGIN + 4;
      if (this.size[1] < needH) {
        this.size[1] = needH;
        if (!this.properties) this.properties = {};
        this.properties.lc_overlay_h = needH;
        s.lastH = needH;
      }

      s.draw = { cx, cy, r: KNOB_R + 6 };

      const t = Math.max(0, Math.min(1, s.opacity));
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

      ctx.fillStyle = "#eee";
      ctx.font = "bold 11px sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(`${Math.round(t * 100)}%`, cx, cy);
      ctx.restore();

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

console.log("[LC123.DynamicOverlay] size retention + circular knob");
