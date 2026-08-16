/**
 * LC Image Crop 🖼️🔪 — interactive crop box
 * Aspect widget only. Global mouseup so drag always releases.
 */

import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const NODE_CLASS = "LCImageCrop";
const DEFAULT_W = 300;
const MIN_W = 260;
const PAD = 16;
const TITLE = 34;
const HANDLE = 12;
const HIT = 16;
const MIN_FRAC = 0.02;

const ASPECT_MAP = {
  free: null,
  original: "original",
  "1:1": 1,
  "4:3": 4 / 3,
  "3:2": 3 / 2,
  "16:9": 16 / 9,
  "3:4": 3 / 4,
  "2:3": 2 / 3,
  "9:16": 9 / 16,
};

let _activeCropNode = null;

function viewUrl(meta) {
  if (!meta) return null;
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
    img.onerror = reject;
    img.src = url;
  });
}

function getW(node, name) {
  return (node.widgets || []).find((x) => x && x.name === name);
}

function hideWidget(w) {
  if (!w || w._lcHidden) return;
  w._lcHidden = true;
  w.computeSize = () => [0, -4];
  w.draw = () => {};
  w.type = "hidden";
  if (w.element) {
    try { w.element.style.display = "none"; } catch (_) {}
  }
}

function readCrop(node) {
  if (node._lcCropLive) return { ...node._lcCropLive };
  const num = (n, d) => {
    const w = getW(node, n);
    const v = w ? Number(w.value) : d;
    return Number.isFinite(v) ? v : d;
  };
  return {
    x: num("x", 0),
    y: num("y", 0),
    w: num("width", 100),
    h: num("height", 100),
    aspect: (getW(node, "aspect")?.value) || "free",
  };
}

function writeCrop(node, c) {
  node._lcCropLive = { ...c };
  for (const [name, val] of [["x", c.x], ["y", c.y], ["width", c.w], ["height", c.h]]) {
    const w = getW(node, name);
    if (w) w.value = Math.round(val * 10) / 10;
  }
}

function widgetsHeight(node) {
  let y = TITLE;
  for (const w of node.widgets || []) {
    if (!w || w.type === "hidden" || w._lcHidden) continue;
    const h =
      typeof w.computeSize === "function"
        ? w.computeSize(node.size[0])?.[1] ?? 24
        : 24;
    y += Math.max(20, h);
  }
  return y;
}

function contentTop(node) {
  return widgetsHeight(node) + PAD;
}

function defaultHeight(node) {
  const innerW = DEFAULT_W - PAD * 2;
  const imgH = Math.round(innerW * (5 / 4));
  return widgetsHeight(node) + PAD + imgH + PAD;
}

function imageLayout(node) {
  const img = node._lcCropImg;
  if (!img) return null;
  const nw = node.size[0];
  const nh = node.size[1];
  const top = contentTop(node);
  const boxX = PAD;
  const boxY = top;
  const boxW = Math.max(1, nw - PAD * 2);
  const boxH = Math.max(1, nh - top - PAD);
  if (boxH < 20) return null;
  const srcW = node._lcSrcW || img.naturalWidth || 1;
  const srcH = node._lcSrcH || img.naturalHeight || 1;
  const scale = Math.min(boxW / srcW, boxH / srcH);
  const dw = srcW * scale;
  const dh = srcH * scale;
  return {
    dx: boxX + (boxW - dw) / 2,
    dy: boxY + (boxH - dh) / 2,
    dw, dh, srcW, srcH, scale,
  };
}

function cropToRect(layout, c) {
  return {
    x: layout.dx + (c.x / 100) * layout.dw,
    y: layout.dy + (c.y / 100) * layout.dh,
    w: (c.w / 100) * layout.dw,
    h: (c.h / 100) * layout.dh,
  };
}

function aspectRatio(layout, key) {
  if (!key || key === "free") return null;
  if (key === "original") return layout.srcW / layout.srcH;
  return ASPECT_MAP[key] ?? null;
}

function clampCrop(c) {
  c.w = Math.max(MIN_FRAC * 100, Math.min(100, c.w));
  c.h = Math.max(MIN_FRAC * 100, Math.min(100, c.h));
  c.x = Math.max(0, Math.min(100 - c.w, c.x));
  c.y = Math.max(0, Math.min(100 - c.h, c.y));
  return c;
}

function applyAspect(c, targetAR, layout, anchor) {
  const pw = (c.w / 100) * layout.srcW;
  const ph = (c.h / 100) * layout.srcH;
  let nw = pw, nh = ph;
  if (pw / ph > targetAR) nw = ph * targetAR;
  else nh = pw / targetAR;
  let x = c.x, y = c.y;
  const dw = c.w - (nw / layout.srcW) * 100;
  const dh = c.h - (nh / layout.srcH) * 100;
  if (anchor.includes("w")) x += dw;
  else if (!anchor.includes("e")) x += dw / 2;
  if (anchor.includes("n")) y += dh;
  else if (!anchor.includes("s")) y += dh / 2;
  return clampCrop({
    x, y,
    w: (nw / layout.srcW) * 100,
    h: (nh / layout.srcH) * 100,
    aspect: c.aspect,
  });
}

const HANDLES = [
  { id: "nw", x: 0, y: 0 }, { id: "n", x: 0.5, y: 0 }, { id: "ne", x: 1, y: 0 },
  { id: "e", x: 1, y: 0.5 }, { id: "se", x: 1, y: 1 }, { id: "s", x: 0.5, y: 1 },
  { id: "sw", x: 0, y: 1 }, { id: "w", x: 0, y: 0.5 },
];

function hitTest(layout, c, px, py) {
  const r = cropToRect(layout, c);
  for (const h of HANDLES) {
    const hx = r.x + h.x * r.w;
    const hy = r.y + h.y * r.h;
    if (Math.abs(px - hx) <= HIT && Math.abs(py - hy) <= HIT)
      return { type: "handle", id: h.id };
  }
  if (px >= r.x && px <= r.x + r.w && py >= r.y && py <= r.y + r.h)
    return { type: "move" };
  return null;
}

function drawPreview(node, ctx) {
  const layout = imageLayout(node);
  if (!layout) return;
  const img = node._lcCropImg;
  const c = readCrop(node);
  ctx.save();
  ctx.drawImage(img, layout.dx, layout.dy, layout.dw, layout.dh);
  const r = cropToRect(layout, c);
  const { dx, dy, dw, dh } = layout;
  ctx.fillStyle = "rgba(0,0,0,0.45)";
  ctx.fillRect(dx, dy, dw, Math.max(0, r.y - dy));
  ctx.fillRect(dx, r.y + r.h, dw, Math.max(0, dy + dh - (r.y + r.h)));
  ctx.fillRect(dx, r.y, Math.max(0, r.x - dx), r.h);
  ctx.fillRect(r.x + r.w, r.y, Math.max(0, dx + dw - (r.x + r.w)), r.h);
  ctx.strokeStyle = "rgba(255,255,255,0.95)";
  ctx.lineWidth = 1.5;
  ctx.strokeRect(r.x + 0.5, r.y + 0.5, Math.max(0, r.w - 1), Math.max(0, r.h - 1));
  ctx.strokeStyle = "rgba(255,255,255,0.25)";
  ctx.beginPath();
  ctx.moveTo(r.x + r.w / 3, r.y); ctx.lineTo(r.x + r.w / 3, r.y + r.h);
  ctx.moveTo(r.x + (2 * r.w) / 3, r.y); ctx.lineTo(r.x + (2 * r.w) / 3, r.y + r.h);
  ctx.moveTo(r.x, r.y + r.h / 3); ctx.lineTo(r.x + r.w, r.y + r.h / 3);
  ctx.moveTo(r.x, r.y + (2 * r.h) / 3); ctx.lineTo(r.x + r.w, r.y + (2 * r.h) / 3);
  ctx.stroke();
  for (const h of HANDLES) {
    const hx = r.x + h.x * r.w;
    const hy = r.y + h.y * r.h;
    ctx.fillStyle = "#fff";
    ctx.strokeStyle = "#111";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.rect(hx - HANDLE / 2, hy - HANDLE / 2, HANDLE, HANDLE);
    ctx.fill();
    ctx.stroke();
  }
  ctx.restore();
}

function processDrag(node, px, py) {
  const drag = node._lcDrag;
  if (!drag) return;
  const layout = drag.layout;
  const o = drag.orig;
  let c = { ...o };
  const dxPct = ((px - drag.start.x) / layout.dw) * 100;
  const dyPct = ((py - drag.start.y) / layout.dh) * 100;
  if (drag.mode === "move") {
    c.x = o.x + dxPct;
    c.y = o.y + dyPct;
    c = clampCrop(c);
  } else {
    const id = drag.handle;
    if (id.includes("w")) { c.x = o.x + dxPct; c.w = o.w - dxPct; }
    if (id.includes("e")) { c.w = o.w + dxPct; }
    if (id.includes("n")) { c.y = o.y + dyPct; c.h = o.h - dyPct; }
    if (id.includes("s")) { c.h = o.h + dyPct; }
    if (c.w < 0) { c.x += c.w; c.w = Math.abs(c.w); }
    if (c.h < 0) { c.y += c.h; c.h = Math.abs(c.h); }
    c = clampCrop(c);
    const ar = aspectRatio(layout, o.aspect);
    if (ar) {
      c.aspect = o.aspect;
      c = applyAspect(c, ar, layout, id);
    }
  }
  writeCrop(node, c);
  node.setDirtyCanvas?.(true, true);
}

function endDrag() {
  if (_activeCropNode) {
    _activeCropNode._lcDrag = null;
    _activeCropNode.setDirtyCanvas?.(true, true);
    _activeCropNode = null;
  }
}

function installGlobalMouseUp() {
  if (window.__lcCropMouseUp) return;
  window.__lcCropMouseUp = true;
  const end = () => endDrag();
  window.addEventListener("pointerup", end, true);
  window.addEventListener("mouseup", end, true);
  window.addEventListener("pointercancel", end, true);
  window.addEventListener("blur", end, true);
}

app.registerExtension({
  name: "LC123.ImageCrop",

  async setup() {
    installGlobalMouseUp();
  },

  async beforeRegisterNodeDef(nodeType, nodeData) {
    if ((nodeData?.name || "") !== NODE_CLASS) return;

    const onCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const r = onCreated?.apply(this, arguments);
      this.color = "#324B4B";
      this.bgcolor = "#324B4B";
      this._lcCropImg = null;
      this._lcSrcW = 0;
      this._lcSrcH = 0;
      this._lcDrag = null;
      this._lcCropLive = null;
      for (const name of ["x", "y", "width", "height"]) hideWidget(getW(this, name));
      this.size = [DEFAULT_W, defaultHeight(this)];

      const aspect = getW(this, "aspect");
      if (aspect) {
        const prev = aspect.callback;
        aspect.callback = (val, ...rest) => {
          const out = prev?.call(this, val, ...rest);
          const layout = imageLayout(this);
          if (layout) {
            const c = readCrop(this);
            c.aspect = val;
            const ar = aspectRatio(layout, val);
            if (ar) writeCrop(this, applyAspect(c, ar, layout, "se"));
            else writeCrop(this, c);
          }
          this.setDirtyCanvas?.(true, true);
          return out;
        };
      }
      return r;
    };

    const onExecuted = nodeType.prototype.onExecuted;
    nodeType.prototype.onExecuted = function (message) {
      const r = onExecuted?.apply(this, arguments);
      const metas = message?.lc_preview || message?.images;
      if (metas?.length) {
        const url = viewUrl(metas[0]);
        if (url) {
          loadImg(url).then((img) => {
            this._lcCropImg = img;
            this.setDirtyCanvas?.(true, true);
          }).catch(() => {});
        }
      }
      const sz = message?.src_size?.[0];
      if (sz) {
        this._lcSrcW = sz.width || 0;
        this._lcSrcH = sz.height || 0;
      }
      return r;
    };

    const onDrawFG = nodeType.prototype.onDrawForeground;
    nodeType.prototype.onDrawForeground = function (ctx) {
      const r = onDrawFG?.apply(this, arguments);
      if (this.flags?.collapsed) return r;
      drawPreview(this, ctx);
      return r;
    };

    nodeType.prototype.onMouseDown = function (e, pos) {
      const layout = imageLayout(this);
      if (!layout) return false;
      const hit = hitTest(layout, readCrop(this), pos[0], pos[1]);
      if (!hit) return false;
      this._lcDrag = {
        mode: hit.type,
        handle: hit.id || null,
        start: { x: pos[0], y: pos[1] },
        orig: { ...readCrop(this) },
        layout,
      };
      _activeCropNode = this;
      return true;
    };

    nodeType.prototype.onMouseMove = function (e, pos) {
      if (!this._lcDrag) return false;
      processDrag(this, pos[0], pos[1]);
      return true;
    };

    nodeType.prototype.onMouseUp = function () {
      if (this._lcDrag) {
        endDrag();
        return true;
      }
      return false;
    };

    const onResize = nodeType.prototype.onResize;
    nodeType.prototype.onResize = function (size) {
      if (size[0] < MIN_W) size[0] = MIN_W;
      return onResize?.apply(this, arguments);
    };
  },
});

console.log("[LC123.ImageCrop] global mouseup + unified layout");
