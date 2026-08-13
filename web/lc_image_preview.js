/**
 * Shared on-node preview for LC image nodes.
 * Most nodes: hover wipe (A=after, B=before; default full after).
 * LCTextOverlay: no wipe; live text/size/color/position on the base image.
 */

import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const NODE_CLASSES = new Set([
  "LCImageAdjust",
  "LCAutoWhiteBalance",
  "LCClarity",
  "LCLensFX",
  "LCLiftGammaGain",
  "LCImageRGB",
  "LCFilmGrain",
  "LCApplyLUT",
  "LCVibrance",
  "LCVignette",
  "LCBloom",
  "LCImageDenoise",
  "LCColorMatch",
  "LCFilmStockBW",
  "LCFilmStockColor",
  "LCImageDesaturate",
  "LCLensProfile",
  "LCChromaticAberration",
]);

// Text overlay handled separately (live overlay, no wipe)
const TEXT_OVERLAY = "LCTextOverlay";
const WATERMARK = "LCWatermark";

const DEFAULT_W = 300;
const MIN_W = 260;
const PAD = 16;
const TITLE = 34;

/** Display name → CSS font-family for live canvas preview */
const LC_FONT_CSS = {
  "Arial": "Arial, Helvetica, sans-serif",
  "Arial Bold": "Arial, Helvetica, sans-serif",
  "Arial Italic": "Arial, Helvetica, sans-serif",
  "Times New Roman": "\"Times New Roman\", Times, serif",
  "Times New Roman Bold": "\"Times New Roman\", Times, serif",
  "Georgia": "Georgia, serif",
  "Georgia Bold": "Georgia, serif",
  "Verdana": "Verdana, Geneva, sans-serif",
  "Verdana Bold": "Verdana, Geneva, sans-serif",
  "Tahoma": "Tahoma, sans-serif",
  "Trebuchet MS": "\"Trebuchet MS\", sans-serif",
  "Comic Sans MS": "\"Comic Sans MS\", cursive",
  "Impact": "Impact, Haettenschweiler, sans-serif",
  "Courier New": "\"Courier New\", Courier, monospace",
  "Consolas": "Consolas, monospace",
  "Segoe UI": "\"Segoe UI\", sans-serif",
  "Segoe UI Bold": "\"Segoe UI\", sans-serif",
  "Calibri": "Calibri, sans-serif",
  "Calibri Bold": "Calibri, sans-serif",
  "DejaVu Sans": "\"DejaVu Sans\", sans-serif",
  "DejaVu Serif": "\"DejaVu Serif\", serif",
  "DejaVu Sans Mono": "\"DejaVu Sans Mono\", monospace",
  "Liberation Sans": "\"Liberation Sans\", Arial, sans-serif",
  "Liberation Serif": "\"Liberation Serif\", Times, serif",
};

function imageDataToUrl(data) {
  if (!data) return null;
  const rand =
    typeof app.getRandParam === "function" ? app.getRandParam() : "";
  const fmt =
    typeof app.getPreviewFormatParam === "function"
      ? app.getPreviewFormatParam()
      : "";
  return api.apiURL(
    `/view?filename=${encodeURIComponent(data.filename)}` +
      `&type=${data.type || "temp"}` +
      `&subfolder=${encodeURIComponent(data.subfolder || "")}` +
      `${fmt}${rand}`
  );
}

function widgetsHeight(node) {
  let y = TITLE;
  for (const w of node.widgets || []) {
    if (!w || w.type === "hidden" || w._lcHidden) continue;
    const h =
      typeof w.computeSize === "function"
        ? w.computeSize(node.size[0])?.[1] ?? 22
        : 22;
    y += Math.max(20, h);
  }
  return y;
}

function defaultHeight(node) {
  const innerW = DEFAULT_W - PAD * 2;
  const imgH = Math.round(innerW * (5 / 4));
  return widgetsHeight(node) + PAD + imgH + PAD;
}

function contentTop(node) {
  return widgetsHeight(node) + PAD;
}

function wval(node, name, fallback) {
  const w = (node.widgets || []).find((x) => x.name === name);
  return w != null ? w.value : fallback;
}

function setWval(node, name, value) {
  const w = (node.widgets || []).find((x) => x.name === name);
  if (!w) return;
  w.value = value;
  if (typeof w.callback === "function") {
    try {
      w.callback(value, app.canvas, node, null, null);
    } catch (_) {}
  }
}

/**
 * Hover wipe compare (LC Image Compare style).
 */
class LCPreviewCompare {
  constructor(node) {
    this.node = node;
    this.imgA = null;
    this.imgB = null;
    this.pointerOver = false;
    this.pointerPos = [0, 0];
    this._bind(node);
  }

  _bind(node) {
    const self = this;

    // Persist preview meta across undo/configure (imgs are runtime-only otherwise)
    const origConfigure = node.onConfigure;
    node.onConfigure = function (data) {
      const r = origConfigure ? origConfigure.apply(this, arguments) : undefined;
      // Defer restore so size/widgets settle after undo
      queueMicrotask(() => self._restoreFromProps());
      return r;
    };
    // Also try restore when node is first created from graph
    queueMicrotask(() => self._restoreFromProps());

    const origDrawFG = node.onDrawForeground;
    node.onDrawForeground = function (ctx) {
      if (origDrawFG) origDrawFG.apply(this, arguments);
      self.draw(ctx);
    };

    const origMouseMove = node.onMouseMove;
    node.onMouseMove = function (e, pos, canvas) {
      self.pointerPos = pos;
      if (self.pointerOver && self.imgA && self.imgB) {
        app.canvas?.setDirty?.(true, true);
      }
      return origMouseMove ? origMouseMove.apply(this, arguments) : false;
    };

    const origMouseEnter = node.onMouseEnter;
    node.onMouseEnter = function (e) {
      self.pointerOver = true;
      app.canvas?.setDirty?.(true, true);
      if (origMouseEnter) origMouseEnter.apply(this, arguments);
    };

    const origMouseLeave = node.onMouseLeave;
    node.onMouseLeave = function (e) {
      self.pointerOver = false;
      app.canvas?.setDirty?.(true, true);
      if (origMouseLeave) origMouseLeave.apply(this, arguments);
    };

    const origExecuted = node.onExecuted;
    node.onExecuted = function (message) {
      if (origExecuted) origExecuted.apply(this, arguments);
      self.onExecuted(message);
    };

    const origResize = node.onResize;
    node.onResize = function (size) {
      if (size[0] < MIN_W) size[0] = MIN_W;
      if (origResize) origResize.apply(this, arguments);
    };
  }

  _loadMeta(meta, which) {
    if (!meta?.length) {
      if (which === "A") this.imgA = null;
      if (which === "B") this.imgB = null;
      return;
    }
    const self = this;
    const url = imageDataToUrl(meta[0]);
    if (!url) return;
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => {
      if (which === "A") self.imgA = img;
      else self.imgB = img;
      app.canvas?.setDirty?.(true, true);
    };
    img.src = url;
  }

  _restoreFromProps() {
    const props = this.node.properties || {};
    if (props.lc_preview_meta) this._loadMeta(props.lc_preview_meta, "A");
    if (props.lc_before_meta) this._loadMeta(props.lc_before_meta, "B");
    else if (!props.lc_preview_meta) {
      // nothing stored
    }
  }

  onExecuted(message) {
    if (!message) return;
    const afterMeta = message.lc_preview || message.images;
    const beforeMeta = message.lc_before;
    // Persist lightweight meta so Ctrl+Z / onConfigure can restore previews
    if (!this.node.properties) this.node.properties = {};
    if (afterMeta?.length) {
      this.node.properties.lc_preview_meta = afterMeta;
      this._loadMeta(afterMeta, "A");
    }
    if (beforeMeta?.length) {
      this.node.properties.lc_before_meta = beforeMeta;
      this._loadMeta(beforeMeta, "B");
    } else {
      this.node.properties.lc_before_meta = null;
      this.imgB = null;
    }
    this.node._lcBypass = !!(
      message.lc_bypass &&
      (message.lc_bypass[0] === "1" || message.lc_bypass[0] === 1)
    );
  }

  draw(ctx) {
    const node = this.node;
    const imgA = this.imgA;
    const imgB = this.imgB;
    if (!imgA && !imgB) return;

    const top = contentTop(node);
    const x = PAD;
    const y = top;
    const w = Math.max(1, node.size[0] - PAD * 2);
    const h = Math.max(1, node.size[1] - top - PAD);
    if (h < 16) return;

    const drawCover = (img) => {
      if (!img) return;
      const scale = Math.min(w / img.naturalWidth, h / img.naturalHeight);
      const sw = img.naturalWidth * scale;
      const sh = img.naturalHeight * scale;
      const ox = x + (w - sw) / 2;
      const oy = y + (h - sh) / 2;
      ctx.drawImage(img, ox, oy, sw, sh);
    };

    if (imgB) drawCover(imgB);
    else drawCover(imgA);

    if (imgA && imgB) {
      let splitX = w;
      if (this.pointerOver) {
        splitX = Math.max(0, Math.min(w, this.pointerPos[0] - x));
      }
      ctx.save();
      ctx.beginPath();
      ctx.rect(x, y, splitX, h);
      ctx.clip();
      drawCover(imgA);
      ctx.restore();
      if (this.pointerOver) {
        ctx.strokeStyle = "rgba(255,255,255,0.9)";
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(x + splitX, y);
        ctx.lineTo(x + splitX, y + h);
        ctx.stroke();
      }
    } else if (imgA) {
      drawCover(imgA);
    }

    if (node._lcBypass) {
      ctx.save();
      ctx.font = "bold 13px sans-serif";
      ctx.fillStyle = "#e53935";
      ctx.textAlign = "center";
      ctx.textBaseline = "top";
      ctx.fillText("bypass", node.size[0] / 2, 34);
      ctx.restore();
    }
  }
}

/**
 * Text Overlay: base image + live canvas text (no wipe).
 * Size / color / x / y / text update immediately when widgets change.
 */

/**
 * Text Overlay: base image + live canvas text (no wipe).
 * x/y = top-center of text block. Word-wrap with side margins.
 * Size / color / position update when widgets change.
 */

/**
 * Text Overlay: base image + live canvas text (no wipe).
 * Drag ONLY while primary button is held (global pointer capture).
 * x/y = top-center; text block clamped inside the image.
 */
class LCTextOverlayPreview {
  constructor(node) {
    this.node = node;
    this.baseImg = null;
    this._dragging = false;
    this._bind(node);
    this._installGlobals();
    node.lcTextOverlayPreview = this;
    const origConfigure = node.onConfigure;
    node.onConfigure = function (data) {
      const r = origConfigure ? origConfigure.apply(this, arguments) : undefined;
      queueMicrotask(() => self_restore(this));
      return r;
    };
    const self_restore = (n) => n.lcTextOverlayPreview?._restoreFromProps?.();
    queueMicrotask(() => this._restoreFromProps());
  }

  _installGlobals() {
    if (window.__lcTextOverlayPtr) return;
    window.__lcTextOverlayPtr = true;
    window.addEventListener(
      "pointerup",
      () => {
        const n = window.__lcTextDragNode;
        if (n?.lcTextOverlayPreview) {
          n.lcTextOverlayPreview._dragging = false;
        }
        window.__lcTextDragNode = null;
      },
      true
    );
    window.addEventListener(
      "pointercancel",
      () => {
        const n = window.__lcTextDragNode;
        if (n?.lcTextOverlayPreview) {
          n.lcTextOverlayPreview._dragging = false;
        }
        window.__lcTextDragNode = null;
      },
      true
    );
  }

  _bind(node) {
    const self = this;

    for (const w of node.widgets || []) {
      if (!w) continue;
      const orig = w.callback;
      w.callback = function () {
        const r = orig?.apply(this, arguments);
        app.canvas?.setDirty?.(true, true);
        return r;
      };
    }

    const origDrawFG = node.onDrawForeground;
    node.onDrawForeground = function (ctx) {
      if (origDrawFG) origDrawFG.apply(this, arguments);
      self.draw(ctx);
    };

    const origExecuted = node.onExecuted;
    node.onExecuted = function (message) {
      if (origExecuted) origExecuted.apply(this, arguments);
      self.onExecuted(message);
    };

    const origDown = node.onMouseDown;
    node.onMouseDown = function (e, pos, canvas) {
      // Only primary button
      if (e && e.button != null && e.button !== 0) {
        return origDown ? origDown.apply(this, arguments) : false;
      }
      const box = self._box();
      if (
        pos[0] >= box.x &&
        pos[0] <= box.x + box.w &&
        pos[1] >= box.y &&
        pos[1] <= box.y + box.h
      ) {
        self._dragging = true;
        window.__lcTextDragNode = this;
        self._setPosFromLocal(pos[0], pos[1], box);
        app.canvas?.setDirty?.(true, true);
        return true;
      }
      return origDown ? origDown.apply(this, arguments) : false;
    };

    const origMove = node.onMouseMove;
    node.onMouseMove = function (e, pos, canvas) {
      // Require active drag AND primary button still down when event provides buttons
      if (!self._dragging) {
        return origMove ? origMove.apply(this, arguments) : false;
      }
      if (e && typeof e.buttons === "number" && (e.buttons & 1) === 0) {
        self._dragging = false;
        window.__lcTextDragNode = null;
        return false;
      }
      self._setPosFromLocal(pos[0], pos[1], self._box());
      app.canvas?.setDirty?.(true, true);
      return true;
    };

    const origUp = node.onMouseUp;
    node.onMouseUp = function (e, pos, canvas) {
      if (self._dragging) {
        self._dragging = false;
        window.__lcTextDragNode = null;
        return true;
      }
      return origUp ? origUp.apply(this, arguments) : false;
    };

    const origLeave = node.onMouseLeave;
    node.onMouseLeave = function (e) {
      // Do NOT cancel drag on leave — pointer may still be down outside node.
      // Global pointerup handles release.
      if (origLeave) origLeave.apply(this, arguments);
    };

    const origResize = node.onResize;
    node.onResize = function (size) {
      if (size[0] < MIN_W) size[0] = MIN_W;
      if (origResize) origResize.apply(this, arguments);
    };
  }

  _box() {
    const node = this.node;
    const top = contentTop(node);
    return {
      x: PAD,
      y: top,
      w: Math.max(1, node.size[0] - PAD * 2),
      h: Math.max(1, node.size[1] - top - PAD),
    };
  }

  _setPosFromLocal(lx, ly, box) {
    const xp = Math.max(0, Math.min(100, ((lx - box.x) / box.w) * 100));
    const yp = Math.max(0, Math.min(100, ((ly - box.y) / box.h) * 100));
    setWval(this.node, "x_percent", Math.round(xp * 10) / 10);
    setWval(this.node, "y_percent", Math.round(yp * 10) / 10);
  }

  _restoreFromProps() {
    const props = this.node.properties || {};
    const meta = props.lc_preview_meta || props.lc_before_meta;
    if (!meta?.length) return;
    const self = this;
    const url = imageDataToUrl(meta[0]);
    if (!url) return;
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => {
      self.baseImg = img;
      app.canvas?.setDirty?.(true, true);
    };
    img.src = url;
  }

  onExecuted(message) {
    if (!message) return;
    const self = this;
    const meta = message.lc_before || message.lc_preview || message.images;
    if (meta?.length) {
      if (!this.node.properties) this.node.properties = {};
      this.node.properties.lc_preview_meta = meta;
      const url = imageDataToUrl(meta[0]);
      if (url) {
        const img = new Image();
        img.crossOrigin = "anonymous";
        img.onload = () => {
          self.baseImg = img;
          app.canvas?.setDirty?.(true, true);
        };
        img.src = url;
      }
    }
  }

  _wrap(ctx, text, maxW) {
    const paras = String(text).split(/\r?\n/);
    const lines = [];
    for (const para of paras) {
      if (!para) {
        lines.push("");
        continue;
      }
      if (ctx.measureText(para).width <= maxW) {
        lines.push(para);
        continue;
      }
      const words = para.split(" ");
      let cur = "";
      for (const word of words) {
        const trial = cur ? cur + " " + word : word;
        if (ctx.measureText(trial).width <= maxW) {
          cur = trial;
        } else {
          if (cur) lines.push(cur);
          if (ctx.measureText(word).width > maxW) {
            let chunk = "";
            for (const ch of word) {
              const t2 = chunk + ch;
              if (ctx.measureText(t2).width <= maxW) chunk = t2;
              else {
                if (chunk) lines.push(chunk);
                chunk = ch;
              }
            }
            cur = chunk;
          } else {
            cur = word;
          }
        }
      }
      if (cur) lines.push(cur);
    }
    return lines.length ? lines : [""];
  }

  draw(ctx) {
    const node = this.node;
    const img = this.baseImg;
    if (!img) return;

    const box = this._box();
    const { x, y, w, h } = box;
    if (h < 16) return;

    const scale = Math.min(w / img.naturalWidth, h / img.naturalHeight);
    const sw = img.naturalWidth * scale;
    const sh = img.naturalHeight * scale;
    const ox = x + (w - sw) / 2;
    const oy = y + (h - sh) / 2;

    ctx.drawImage(img, ox, oy, sw, sh);

    const text = String(wval(node, "text", "") ?? "");
    if (!text) return;

    const fontSize = Number(wval(node, "font_size", 64)) || 64;
    const fontKey = String(wval(node, "font", "Arial") || "Arial");
    const fontCss = LC_FONT_CSS[fontKey] || `"${fontKey}", sans-serif`;
    const r = Number(wval(node, "color_r", 255)) | 0;
    const g = Number(wval(node, "color_g", 255)) | 0;
    const b = Number(wval(node, "color_b", 255)) | 0;
    let xp = Number(wval(node, "x_percent", 50));
    let yp = Number(wval(node, "y_percent", 90));
    const anchor = String(wval(node, "anchor", "center-top"));
    const [ah, av] = anchor.split("-");

    const dispSize = Math.max(8, fontSize * scale);
    const margin = Math.max(4, 6 * scale);
    const maxW = Math.max(8, sw - 2 * margin);

    const weight = /bold/i.test(fontKey) ? "bold " : "";
    const italic = /italic/i.test(fontKey) ? "italic " : "";
    ctx.save();
    ctx.font = `${italic}${weight}${dispSize}px ${fontCss}`;
    ctx.fillStyle = `rgb(${r},${g},${b})`;
    ctx.textBaseline = "top";
    ctx.textAlign = "left";

    const lines = this._wrap(ctx, text, maxW);
    const lineH = dispSize * 1.2;
    const blockH = Math.max(lineH, lines.length * lineH);

    // Desired top of block from percent
    let topY = oy + (yp / 100) * sh;
    if (av === "bottom") topY -= blockH;
    else if (av === "center") topY -= blockH / 2;

    // Hard clamp inside drawn image
    const minY = oy + margin;
    const maxY = oy + sh - margin - blockH;
    if (maxY < minY) topY = minY;
    else topY = Math.max(minY, Math.min(maxY, topY));

    const cx = ox + (xp / 100) * sw;

    lines.forEach((line, i) => {
      const tw = ctx.measureText(line).width;
      let lx;
      if (ah === "left") lx = cx;
      else if (ah === "right") lx = cx - tw;
      else lx = cx - tw / 2;
      lx = Math.max(ox + margin, Math.min(ox + sw - margin - tw, lx));
      ctx.fillText(line, lx, topY + i * lineH);
    });
    ctx.restore();
  }
}



/**
 * LC Watermark — live composite (no wipe). Drag to place; size/opacity from widgets.
 */
class LCWatermarkPreview {
  constructor(node) {
    this.node = node;
    this.baseImg = null;
    this.wmImg = null;
    this._dragging = false;
    this._bind(node);
    this._installGlobals();
    node.lcWatermarkPreview = this;
    const origConfigure = node.onConfigure;
    node.onConfigure = function (data) {
      const r = origConfigure ? origConfigure.apply(this, arguments) : undefined;
      queueMicrotask(() => self_restore(this));
      return r;
    };
    const self_restore = (n) => n.lcWatermarkPreview?._restoreFromProps?.();
    queueMicrotask(() => this._restoreFromProps());
  }

  _installGlobals() {
    if (window.__lcWmPtr) return;
    window.__lcWmPtr = true;
    const clear = () => {
      const n = window.__lcWmDragNode;
      if (n?.lcWatermarkPreview) n.lcWatermarkPreview._dragging = false;
      window.__lcWmDragNode = null;
    };
    window.addEventListener("pointerup", clear, true);
    window.addEventListener("pointercancel", clear, true);
  }

  _bind(node) {
    const self = this;

    const origDrawFG = node.onDrawForeground;
    node.onDrawForeground = function (ctx) {
      if (origDrawFG) origDrawFG.apply(this, arguments);
      self.draw(ctx);
    };

    // Live redraw when size/opacity/position widgets change
    for (const w of node.widgets || []) {
      if (!w || w._lcWmHooked) continue;
      if (!["size_percent", "opacity", "x_percent", "y_percent", "margin_percent"].includes(w.name))
        continue;
      w._lcWmHooked = true;
      const prev = w.callback;
      w.callback = function (v, ...args) {
        const out = prev?.apply(this, [v, ...args]);
        app.canvas?.setDirty?.(true, true);
        return out;
      };
    }

    const origDown = node.onMouseDown;
    node.onMouseDown = function (e, pos, canvas) {
      const { ox, oy, sw, sh } = self._imageRect();
      if (
        pos[0] >= ox &&
        pos[0] <= ox + sw &&
        pos[1] >= oy &&
        pos[1] <= oy + sh
      ) {
        self._dragging = true;
        window.__lcWmDragNode = this;
        self._setPosFromLocal(pos[0], pos[1], self._box());
        app.canvas?.setDirty?.(true, true);
        return true;
      }
      return origDown ? origDown.apply(this, arguments) : false;
    };

    const origMove = node.onMouseMove;
    node.onMouseMove = function (e, pos, canvas) {
      if (self._dragging) {
        self._setPosFromLocal(pos[0], pos[1], self._box());
        app.canvas?.setDirty?.(true, true);
        return true;
      }
      return origMove ? origMove.apply(this, arguments) : false;
    };

    const origUp = node.onMouseUp;
    node.onMouseUp = function (e, pos, canvas) {
      if (self._dragging) {
        self._dragging = false;
        window.__lcWmDragNode = null;
        return true;
      }
      return origUp ? origUp.apply(this, arguments) : false;
    };

    const origExecuted = node.onExecuted;
    node.onExecuted = function (message) {
      if (origExecuted) origExecuted.apply(this, arguments);
      self.onExecuted(message);
    };

    const origResize = node.onResize;
    node.onResize = function (size) {
      if (size[0] < MIN_W) size[0] = MIN_W;
      if (origResize) origResize.apply(this, arguments);
    };
  }

  _box() {
    const node = this.node;
    const top = contentTop(node);
    return {
      x: PAD,
      y: top,
      w: Math.max(1, node.size[0] - PAD * 2),
      h: Math.max(1, node.size[1] - top - PAD),
    };
  }

  /** Same coordinate space as draw(): letterboxed image rect inside the node. */
  _imageRect() {
    const base = this.baseImg;
    const box = this._box();
    if (!base || !base.naturalWidth) {
      return { ox: box.x, oy: box.y, sw: box.w, sh: box.h };
    }
    const scale = Math.min(box.w / base.naturalWidth, box.h / base.naturalHeight);
    const sw = base.naturalWidth * scale;
    const sh = base.naturalHeight * scale;
    const ox = box.x + (box.w - sw) / 2;
    const oy = box.y + (box.h - sh) / 2;
    return { ox, oy, sw, sh };
  }

  _setPosFromLocal(lx, ly, box) {
    // Map mouse into the drawn image (letterbox), not the full node pad area
    const { ox, oy, sw, sh } = this._imageRect();
    if (sw < 1 || sh < 1) return;
    // Account for margin so 0/100 sit on the padded usable region
    const marginPct = Number(wval(this.node, "margin_percent", 0.5)) || 0;
    const mx = (marginPct / 100) * sw;
    const my = (marginPct / 100) * sh;
    const usableW = Math.max(1, sw - 2 * mx);
    const usableH = Math.max(1, sh - 2 * my);
    let xp = ((lx - ox - mx) / usableW) * 100;
    let yp = ((ly - oy - my) / usableH) * 100;
    xp = Math.max(0, Math.min(100, xp));
    yp = Math.max(0, Math.min(100, yp));
    // One decimal — stable, matches widget step
    setWval(this.node, "x_percent", Math.round(xp * 10) / 10);
    setWval(this.node, "y_percent", Math.round(yp * 10) / 10);
  }

  _loadMeta(meta, which) {
    if (!meta?.length) return;
    const self = this;
    const url = imageDataToUrl(meta[0]);
    if (!url) return;
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => {
      if (which === "base") self.baseImg = img;
      else self.wmImg = img;
      app.canvas?.setDirty?.(true, true);
    };
    img.src = url;
  }

  _restoreFromProps() {
    const props = this.node.properties || {};
    if (props.lc_before_meta) this._loadMeta(props.lc_before_meta, "base");
    if (props.lc_wm_meta) this._loadMeta(props.lc_wm_meta, "wm");
  }

  onExecuted(message) {
    if (!message) return;
    if (!this.node.properties) this.node.properties = {};
    const before = message.lc_before;
    const wm = message.lc_watermark;
    // Prefer base image for live composite (not the baked result)
    if (before?.length) {
      this.node.properties.lc_before_meta = before;
      this._loadMeta(before, "base");
    } else if (message.lc_preview?.length) {
      this.node.properties.lc_before_meta = message.lc_preview;
      this._loadMeta(message.lc_preview, "base");
    }
    if (wm?.length) {
      this.node.properties.lc_wm_meta = wm;
      this._loadMeta(wm, "wm");
    }
  }

  draw(ctx) {
    const node = this.node;
    const base = this.baseImg;
    if (!base) return;

    const box = this._box();
    const { x, y, w, h } = box;
    if (h < 16) return;

    const scale = Math.min(w / base.naturalWidth, h / base.naturalHeight);
    const sw = base.naturalWidth * scale;
    const sh = base.naturalHeight * scale;
    const ox = x + (w - sw) / 2;
    const oy = y + (h - sh) / 2;

    ctx.drawImage(base, ox, oy, sw, sh);

    const wm = this.wmImg;
    if (!wm) return;

    const sizePct = Number(wval(node, "size_percent", 20)) || 10;
    const opacity = Math.max(0, Math.min(1, Number(wval(node, "opacity", 0.85)) || 0));
    const xp = Number(wval(node, "x_percent", 90));
    const yp = Number(wval(node, "y_percent", 90));
    const marginPct = Number(wval(node, "margin_percent", 0.5)) || 0;

    const targetW = Math.max(1, (sizePct / 100) * sw);
    const aspect = wm.naturalHeight / Math.max(1, wm.naturalWidth);
    const targetH = Math.max(1, targetW * aspect);

    const mx = (marginPct / 100) * sw;
    const my = (marginPct / 100) * sh;
    const usableW = Math.max(1, sw - 2 * mx);
    const usableH = Math.max(1, sh - 2 * my);

    let cx = ox + mx + (xp / 100) * usableW;
    let cy = oy + my + (yp / 100) * usableH;
    let dx = cx - targetW / 2;
    let dy = cy - targetH / 2;
    dx = Math.max(ox, Math.min(ox + sw - targetW, dx));
    dy = Math.max(oy, Math.min(oy + sh - targetH, dy));

    ctx.save();
    ctx.globalAlpha = opacity;
    ctx.drawImage(wm, dx, dy, targetW, targetH);
    ctx.restore();
  }
}

app.registerExtension({
  name: "LC123.ImagePreview",

  async beforeRegisterNodeDef(nodeType, nodeData) {
    const name = nodeData?.name || "";
    const isText = name === TEXT_OVERLAY;
    const isWm = name === WATERMARK;
    if (!NODE_CLASSES.has(name) && !isText && !isWm) return;

    const onCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      if (onCreated) onCreated.apply(this, arguments);
      this.color = "#324B4B";
      this.bgcolor = "#324B4B";
      this._lcBypass = false;
      this.comfyClass = name;

      if (isText) {
        const tw = (this.widgets || []).find((w) => w.name === "text");
        if (tw) {
          tw.computeSize = function (width) {
            return [width, 54];
          };
        }
      }

      this.size = [DEFAULT_W, defaultHeight(this)];
      setTimeout(() => {
        try {
          this.size = [
            Math.max(this.size[0], DEFAULT_W),
            Math.max(this.size[1], defaultHeight(this)),
          ];
          this.setDirtyCanvas?.(true, true);
        } catch (_) {}
      }, 0);

      if (isText) {
        this.lcTextOverlayPreview = new LCTextOverlayPreview(this);
      } else if (isWm) {
        this.lcWatermarkPreview = new LCWatermarkPreview(this);
      } else {
        this.lcPreviewCompare = new LCPreviewCompare(this);
      }
    };
  },
});

console.log("[LC123.ImagePreview] wipe + live text + watermark");
