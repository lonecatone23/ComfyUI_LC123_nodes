// LC Size Pad 📐: a 2D slider for width x height. The frame is pinned bottom-left; drag (or click) its top-right corner. The model preset snaps the size
// to its step and stops the drag at its megapixel limit ("Max megapixels reached"); an aspect ratio locks the shape;
// ⇄ flips portrait / landscape. Interaction ported from LC Outpaint's frame (LC MaskMaker). The pad is a DOM canvas
// widget, so it works the same in the classic canvas and in Nodes 2.0.
import { app } from "../../scripts/app.js";

const TYPE = "LCSizePad";
const PAD_H = 230;
const HANDLE = 11;
const PRESETS = {
  "MiniMax H3": { step: 32, mp: 1.03, max: 1.6 },
  "Krea 2": { step: 16, mp: 1.05, max: 2.0 },
  SDXL: { step: 64, mp: 1.05, max: 1.5 },
  LTX: { step: 32, mp: 0.9, max: 2.1 },
  "Klein 9B": { step: 16, mp: 1.05, max: 4.0 },
  "Wan 2.2": { step: 16, mp: 0.92, max: 0.93 },
  Custom: { step: 8, mp: 1.0, max: 16.0 },
};
const FLIP = { "4:5": "5:4", "5:4": "4:5", "2:3": "3:2", "3:2": "2:3", "3:4": "4:3", "4:3": "3:4", "9:16": "16:9", "16:9": "9:16", "9:21": "21:9", "21:9": "9:21" };

const W = (node, name) => (node.widgets || []).find((w) => w.name === name);
const preset = (node) => PRESETS[W(node, "model")?.value] || PRESETS.Custom;
const ratioOf = (a) => {
  const m = /^(\d+):(\d+)$/.exec(String(a || ""));
  return m ? Number(m[1]) / Number(m[2]) : null;
};
// the shape the frame is locked to: a ratio, the plugged-in picture's shape (known after a run), or null (free)
const ratioNode = (node) => {
  const a = W(node, "aspect")?.value;
  if (a === "image") return node._lcSpImg ? node._lcSpImg.iw / node._lcSpImg.ih : null;
  return ratioOf(a);
};
const snap = (v, step) => Math.max(step, Math.round(v / step) * step);
const minSide = (p) => Math.max(p.step * 2, 128);

function size(node) {
  return { w: Number(W(node, "width")?.value) || 1024, h: Number(W(node, "height")?.value) || 1024 };
}

/** Snapped size of `mp` megapixels at shape `r`, kept under the limit. */
function sizeFor(mp, r, p) {
  const area = Math.min(mp, p.max) * 1e6;
  let w = Math.sqrt(area * r), h = w / r;
  w = snap(w, p.step);
  h = snap(h, p.step);
  while (w * h > p.max * 1e6 + 1 && w > p.step && h > p.step) {
    if (w / h > r) w -= p.step;
    else h -= p.step;
  }
  return { w, h };
}

function setSize(node, w, h, quiet) {
  const p = preset(node);
  w = Math.max(minSide(p), w);
  h = Math.max(minSide(p), h);
  const ww = W(node, "width"), hh = W(node, "height"), mp = W(node, "megapixels");
  if (ww) ww.value = w;
  if (hh) hh.value = h;
  if (mp) mp.value = Math.round((w * h) / 1e4) / 100;
  if (!quiet) node.setDirtyCanvas?.(true, true);
  draw(node);
}

// ---------------------------------------------------------------- layout and drawing
// Like mxSlider2D: the frame is pinned to the pad's bottom-left corner and its top-right corner is the handle.
// The pad shows up to the model's limit (a 2.4:1 frame at the limit fits across, a 9:16 one up), or for Custom a few
// megapixels around the current size. Frozen while dragging so the scale doesn't jump.
const M = 12;
function layout(node) {
  if (node._lcSpDrag) return node._lcSpDrag.lay;
  const cv = node._lcSp?.cv;
  const p = preset(node);
  const { w, h } = size(node);
  const shown = p.max <= 4 ? p.max : Math.max(4, (w * h) / 1e6 * 1.6);
  const cw = cv.clientWidth, ch = cv.clientHeight - 22; // the size line sits under the pad
  const scale = Math.min((cw - 2 * M) / Math.sqrt(shown * 1e6 * 2.4), (ch - 2 * M) / Math.sqrt(shown * 1e6 * 16 / 9));
  return { scale, ox: M, oy: ch - M, cw, ch };
}

function draw(node) {
  const sp = node._lcSp;
  if (!sp?.cv?.isConnected) return;
  const cv = sp.cv;
  const dpr = window.devicePixelRatio || 1;
  const cw = cv.clientWidth, ch = cv.clientHeight;
  if (!cw || !ch) return;
  if (cv.width !== Math.round(cw * dpr) || cv.height !== Math.round(ch * dpr)) {
    cv.width = Math.round(cw * dpr);
    cv.height = Math.round(ch * dpr);
  }
  const ctx = cv.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, cw, ch);
  const p = preset(node);
  const lay = layout(node);
  const { w, h } = node._lcSpLive || size(node);

  // the pad, with a grid running from the corner
  ctx.fillStyle = "#151719";
  ctx.beginPath();
  ctx.roundRect ? ctx.roundRect(0, 0, cw, lay.ch, 6) : ctx.rect(0, 0, cw, lay.ch);
  ctx.fill();
  ctx.strokeStyle = "rgba(255,255,255,0.05)";
  ctx.lineWidth = 1;
  for (let gx = lay.ox; gx < cw; gx += 24) { ctx.beginPath(); ctx.moveTo(gx + 0.5, 0); ctx.lineTo(gx + 0.5, lay.ch); ctx.stroke(); }
  for (let gy = lay.oy; gy > 0; gy -= 24) { ctx.beginPath(); ctx.moveTo(0, gy + 0.5); ctx.lineTo(cw, gy + 0.5); ctx.stroke(); }
  ctx.strokeStyle = "rgba(255,255,255,0.18)";
  ctx.beginPath();
  ctx.moveTo(lay.ox + 0.5, 0);
  ctx.lineTo(lay.ox + 0.5, lay.oy + 0.5);
  ctx.lineTo(cw, lay.oy + 0.5);
  ctx.stroke();

  // the aspect lock: the line the corner slides along
  const r = ratioNode(node);
  if (r) {
    ctx.setLineDash([2, 4]);
    ctx.strokeStyle = "rgba(255,255,255,0.25)";
    ctx.beginPath();
    ctx.moveTo(lay.ox, lay.oy);
    const far = 1e5;
    ctx.lineTo(lay.ox + far * r * lay.scale, lay.oy - far * lay.scale);
    ctx.stroke();
    ctx.setLineDash([]);
  }

  // the model's limit (dashed): width x height = limit, where the drag stops
  ctx.setLineDash([4, 4]);
  ctx.strokeStyle = "rgba(243,201,105,0.5)";
  ctx.beginPath();
  let started = false;
  for (let x = lay.ox + 2; x <= cw; x += 2) {
    const ww = (x - lay.ox) / lay.scale;
    const y = lay.oy - ((p.max * 1e6) / ww) * lay.scale;
    if (y < 0) continue;
    if (!started) {
      ctx.moveTo(x, y);
      started = true;
    } else ctx.lineTo(x, y);
  }
  ctx.stroke();
  ctx.setLineDash([]);

  // the frame, from the corner
  const cx = lay.ox + w * lay.scale, cy = lay.oy - h * lay.scale;
  ctx.fillStyle = "rgba(128,128,128,0.55)";
  ctx.fillRect(lay.ox, cy, cx - lay.ox, lay.oy - cy);
  ctx.strokeStyle = "rgba(255,255,255,0.95)";
  ctx.lineWidth = 1.5;
  ctx.strokeRect(lay.ox + 0.5, cy + 0.5, cx - lay.ox - 1, lay.oy - cy - 1);
  ctx.fillStyle = "#fff";
  ctx.strokeStyle = "#111";
  ctx.lineWidth = 1;
  ctx.fillRect(cx - HANDLE / 2, cy - HANDLE / 2, HANDLE, HANDLE);
  ctx.strokeRect(cx - HANDLE / 2 + 0.5, cy - HANDLE / 2 + 0.5, HANDLE - 1, HANDLE - 1);

  // the size line
  const sw = snap(w, p.step), sh = snap(h, p.step);
  const mp = (sw * sh) / 1e6;
  const at = mp >= p.max - 0.01;
  ctx.font = "12px sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillStyle = at ? "#f3c969" : "rgba(255,255,255,0.8)";
  const asp = W(node, "aspect")?.value;
  const img = node._lcSpImg;
  const tag = asp === "image" ? (img ? ` · image ${img.iw} × ${img.ih}` : " · image (none: drawn shape)")
    : asp && asp !== "free" ? ` · ${asp}` : "";
  ctx.fillText(`${sw} × ${sh} · ${mp.toFixed(2)} / ${p.max} MP${tag}`, cw / 2, lay.ch + 12);

  // "Max megapixels reached" while a drag is held at the limit, fading out after release
  const tip = node._lcSpTip;
  if (tip && (performance.now() < tip.until || node._lcSpDrag)) {
    const text = "Max megapixels reached";
    ctx.font = "bold 11px sans-serif";
    const tw = ctx.measureText(text).width + 14, th = 20;
    const x = cw - tw - 8, y = 8;
    ctx.fillStyle = "rgba(20,22,26,0.92)";
    ctx.strokeStyle = "#f3c969";
    ctx.beginPath();
    ctx.roundRect ? ctx.roundRect(x, y, tw, th, 5) : ctx.rect(x, y, tw, th);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = "#f3c969";
    ctx.fillText(text, x + tw / 2, y + th / 2 + 0.5);
  }
}

// ---------------------------------------------------------------- dragging: the corner goes where the pointer is
function dragTo(d, px, py) {
  const { lay, r, p } = d;
  let w = (px - lay.ox) / lay.scale, h = (lay.oy - py) / lay.scale;
  if (r) {
    // slide along the aspect line: the nearest point on it
    const k = (w * r + h) / (r * r + 1);
    w = k * r;
    h = k;
  }
  const lo = minSide(p);
  if (r) {
    const k = Math.max(1, lo / Math.max(1e-6, Math.min(w, h)));
    w *= k;
    h *= k;
  } else {
    w = Math.max(lo, w);
    h = Math.max(lo, h);
  }
  return { w, h };
}

function onMove(node, px, py) {
  const d = node._lcSpDrag;
  if (!d) return;
  let s = dragTo(d, px, py);
  const limit = d.p.max * 1e6;
  if (s.w * s.h > limit) {
    // stop on the limit, along the line from the corner (the shape you were dragging toward)
    const k = Math.sqrt(limit / (s.w * s.h));
    s = { w: s.w * k, h: s.h * k };
    node._lcSpTip = { until: performance.now() + 1200 };
    clearTimeout(node._lcSpTipT);
    node._lcSpTipT = setTimeout(() => draw(node), 1250);
  } else if (node._lcSpTip) node._lcSpTip = null;
  node._lcSpLive = s;
  // the widgets follow the snapped size while dragging, so the numbers move with the frame
  let sw = snap(s.w, d.p.step), sh = snap(s.h, d.p.step);
  while (sw * sh > limit + 1 && sw > d.p.step && sh > d.p.step) {
    if (sw / sh > s.w / s.h) sw -= d.p.step;
    else sh -= d.p.step;
  }
  setSize(node, sw, sh);
}

function endDrag(node) {
  if (!node?._lcSpDrag) return;
  node._lcSpDrag = null;
  node._lcSpLive = null;
  node.setDirtyCanvas?.(true, true);
  draw(node);
}

// ---------------------------------------------------------------- the widget
function attach(node) {
  if (node._lcSp) return;
  const wrap = document.createElement("div");
  // a fixed height: a canvas sized "100%" of a box that grows with it would redraw itself forever
  wrap.style.cssText = `width:100%;height:${PAD_H}px;box-sizing:border-box;padding:2px 0;overflow:hidden;`;
  const cv = document.createElement("canvas");
  cv.style.cssText = `width:100%;height:${PAD_H - 4}px;display:block;touch-action:none;cursor:default;`;
  wrap.appendChild(cv);
  node._lcSp = { wrap, cv };
  const pos = (e) => {
    const r = cv.getBoundingClientRect();
    // the canvas may be scaled by the graph zoom: work in its own CSS pixels
    return [((e.clientX - r.left) * cv.clientWidth) / r.width, ((e.clientY - r.top) * cv.clientHeight) / r.height];
  };
  cv.addEventListener("pointerdown", (e) => {
    if (e.button !== 0) return;
    const [x, y] = pos(e);
    const lay = layout(node);
    if (y > lay.ch) return; // the size line under the pad
    e.preventDefault();
    e.stopPropagation();
    cv.setPointerCapture?.(e.pointerId);
    node._lcSpDrag = { r: ratioNode(node), p: preset(node), lay };
    onMove(node, x, y); // a click puts the corner right there
  });
  cv.addEventListener("pointermove", (e) => {
    const [x, y] = pos(e);
    if (node._lcSpDrag) {
      e.preventDefault();
      e.stopPropagation();
      onMove(node, x, y);
      return;
    }
    cv.style.cursor = y <= layout(node).ch ? "crosshair" : "default";
  });
  const up = (e) => {
    if (!node._lcSpDrag) return;
    e?.stopPropagation?.();
    endDrag(node);
  };
  cv.addEventListener("pointerup", up);
  cv.addEventListener("pointercancel", up);
  cv.addEventListener("lostpointercapture", up);
  new ResizeObserver(() => draw(node)).observe(cv);

  const dw = node.addDOMWidget("size_pad", "LC_SIZE_PAD", wrap, { getMinHeight: () => PAD_H, getHeight: () => PAD_H, serialize: false });
  if (dw) dw.serialize = false;
  // the right side Parameters panel writes its own column width onto widgets it lists: always follow the node
  if (dw) Object.defineProperty(dw, "width", { get: () => undefined, set: () => {}, configurable: true });

  // settings
  const hook = (name, fn) => {
    const w = W(node, name);
    if (!w) return;
    const prev = w.callback;
    w.callback = function (v, ...rest) {
      const out = prev?.apply(this, [v, ...rest]);
      fn(v);
      return out;
    };
  };
  hook("model", () => {
    const p = preset(node);
    const { w, h } = size(node);
    const s = sizeFor(p.mp, ratioNode(node) || w / h, p);
    setSize(node, s.w, s.h);
  });
  hook("aspect", () => {
    const r = ratioNode(node);
    if (!r) return draw(node);
    const p = preset(node);
    const { w, h } = size(node);
    // near the model's own size: use exactly that, so 16:9 on H3 is its native 1344 x 768
    const mp = Math.abs((w * h) / 1e6 - p.mp) < 0.1 ? p.mp : (w * h) / 1e6;
    const s = sizeFor(mp, r, p);
    setSize(node, s.w, s.h);
  });
  hook("megapixels", (v) => {
    const p = preset(node);
    const { w, h } = size(node);
    const s = sizeFor(Number(v) || p.mp, w / h, p);
    setSize(node, s.w, s.h);
  });
  hook("width", () => draw(node));
  hook("height", () => draw(node));
  node.addWidget("button", "⇄ portrait / landscape", null, () => {
    const a = W(node, "aspect");
    if (a?.value === "image" && node._lcSpImg) return; // the picture decides the shape
    if (a && FLIP[a.value]) a.value = FLIP[a.value];
    const { w, h } = size(node);
    setSize(node, h, w);
  });
  requestAnimationFrame(() => draw(node));
}

app.registerExtension({
  name: "LC123.SizePad",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData?.name !== TYPE) return;
    const created = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const r = created?.apply(this, arguments);
      attach(this);
      // a fresh node starts at the preset's own size
      setTimeout(() => {
        if (this._lcSpConfigured) return;
        // something already set a size (a swap, a script): keep it
        const cur = size(this);
        if (cur.w !== 1024 || cur.h !== 1024) return draw(this);
        const p = preset(this);
        const s = sizeFor(p.mp, 1, p);
        setSize(this, s.w, s.h);
        const min = this.computeSize?.() || this.size;
        this.setSize?.([Math.max(320, this.size[0]), Math.max(min[1], this.size[1])]);
      }, 0);
      return r;
    };
    const configure = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function () {
      this._lcSpConfigured = true;
      const r = configure?.apply(this, arguments);
      requestAnimationFrame(() => draw(this));
      return r;
    };
    // after a run: the picture's shape (aspect = image), so the pad shows and locks to the size that went out
    const executed = nodeType.prototype.onExecuted;
    nodeType.prototype.onExecuted = function (msg) {
      const r = executed?.apply(this, arguments);
      const s = msg?.lc_size_pad?.[0];
      if (s) {
        this._lcSpImg = s.iw > 0 && s.ih > 0 ? { iw: s.iw, ih: s.ih } : null;
        if (this._lcSpImg && W(this, "aspect")?.value === "image") setSize(this, s.w, s.h);
        else draw(this);
      }
      return r;
    };
    const conn = nodeType.prototype.onConnectionsChange;
    nodeType.prototype.onConnectionsChange = function (type, slot, connected) {
      const r = conn?.apply(this, arguments);
      if (!connected && this.inputs?.[slot]?.name === "image") {
        this._lcSpImg = null; // unplugged: back to the drawn frame
        draw(this);
      }
      return r;
    };
    const removed = nodeType.prototype.onRemoved;
    nodeType.prototype.onRemoved = function () {
      endDrag(this);
      return removed?.apply(this, arguments);
    };
  },
});
