/**
 * Shared on-node preview for LC image nodes.
 * Most nodes: the result fitted; click = 100% zoom with a before | after wipe, double-click = back.
 * LCTextOverlay: no wipe; live text/size/color/position on the base image.
 */

import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { lcApplyLaunchColor } from "./lc_color.js";
import { loadBundledFonts } from "./lc_fonts.js";
// one listener for every Text Overlay node (a per-node closure would keep deleted nodes alive)
const redrawOnFontLoad = () => app.canvas?.setDirty?.(true, true);

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
  "LCNaturalLook",
  "LCVignette",
  "LCBloom",
  "LCDepthFX",
  "LCImageDenoise",
  "LCColorMatch",
  "LCToneMatch",
  "LCFilmStockBW",
  "LCFilmStockColor",
  "LCImageDesaturate",
  "LCLensProfile",
  "LCChromaticAberration",
  "LCSkinBeauty",
  "LCSkinUpscale",
  "LCSkinTexture",
  "LCSkinMaster",
  "LCPhoneLook",
  "LCPhoneFilters",
  "LegendEffects",
  "LCDirectionalBlur",
]);

window.LC123FXClasses = NODE_CLASSES; // read by the Optimization report

// Text overlay handled separately (live overlay, no wipe)
const TEXT_OVERLAY = "LCTextOverlay";
const WATERMARK = "LCWatermark";

const DEFAULT_W = 300;
const MIN_W = 260;
const PAD = 16;
const TITLE = 34;

function lcPerfPolicy(node) {
  const cls = node.comfyClass || node.type || "";
  if (window.LC123Perf && typeof window.LC123Perf.policyFor === "function") {
    return window.LC123Perf.policyFor(cls);
  }
  return {
    hide: false,
    halfRes: false,
    clampEdge: false,
    maxEdge: 0,
    skipCollapsed: true,
    skinFull: false,
  };
}

function drawCoverScaled(ctx, img, x, y, w, h, maxEdge) {
  if (!img || !img.complete || !img.naturalWidth) return;
  let src = img;
  const nw = img.naturalWidth;
  const nh = img.naturalHeight;
  if (maxEdge > 0 && Math.max(nw, nh) > maxEdge) {
    const scale = maxEdge / Math.max(nw, nh);
    const cw = Math.max(1, Math.round(nw * scale));
    const ch = Math.max(1, Math.round(nh * scale));
    const key = cw + "x" + ch;
    if (!img._lcScaled) img._lcScaled = {};
    if (!img._lcScaled[key]) {
      const c = document.createElement("canvas");
      c.width = cw;
      c.height = ch;
      c.getContext("2d").drawImage(img, 0, 0, cw, ch);
      img._lcScaled[key] = c;
    }
    src = img._lcScaled[key];
  }
  const iw = src.naturalWidth || src.width;
  const ih = src.naturalHeight || src.height;
  const scale = Math.min(w / iw, h / ih);
  const sw = iw * scale;
  const sh = ih * scale;
  const ox = x + (w - sw) / 2;
  const oy = y + (h - sh) / 2;
  if (window.LC123Perf?.skipImage?.(ctx, ox, oy, sw, sh)) return;
  ctx.drawImage(src, ox, oy, sw, sh);
}


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
  const params = new URLSearchParams({
    filename: data.filename ?? "",
    type: data.type || "temp",
    subfolder: data.subfolder || "",
  });
  return api.apiURL(`/view?${params}${fmt}${rand}`);
}

/** Stable identity of an output image (no rand param): used to spot a repeated restore of the same file. */
function imageDataKey(data) {
  return data ? `${data.type || "temp"}|${data.subfolder || ""}|${data.filename}` : "";
}

/**
 * Load a preview image where only the newest request per (owner, slot) may land: an older, slower
 * response never replaces a newer image. `restore` requests are skipped while the same file is still
 * loading for that slot (onConfigure and node creation both ask for it).
 */
function loadLatest(owner, slot, data, onload, restore = false) {
  const url = imageDataToUrl(data);
  if (!url) return;
  const key = imageDataKey(data);
  const pend = (owner._lcPending ||= {});
  if (restore && pend[slot] === key) return;
  const tokens = (owner._lcLoadToken ||= {});
  const token = (tokens[slot] = (tokens[slot] || 0) + 1);
  pend[slot] = key;
  const img = new Image();
  img.crossOrigin = "anonymous";
  const done = () => {
    if (tokens[slot] === token) pend[slot] = null;
  };
  img.onload = () => {
    done();
    if (tokens[slot] !== token) return;
    onload(img);
    app.canvas?.setDirty?.(true, true);
  };
  img.onerror = done;
  img.src = url;
}

/** Cancel any in-flight load for a slot (its result must not land any more). */
function cancelLoad(owner, slot) {
  const tokens = (owner._lcLoadToken ||= {});
  tokens[slot] = (tokens[slot] || 0) + 1;
  if (owner._lcPending) owner._lcPending[slot] = null;
}

// measured text changes once a web font finishes loading: wrapped-line caches key on this counter
let fontEpoch = 0;
try {
  document.fonts?.addEventListener?.("loadingdone", () => {
    fontEpoch++;
  });
} catch (_) {}

function widgetsHeight(node) {
  // the real layout first: the frontend places every widget (y), and its row spacing has grown over versions,
  // so a fixed per-row estimate drifts on nodes with many widgets and the preview slid under the last rows
  let bottom = 0;
  for (const w of node.widgets || []) {
    if (!w || w.type === "hidden" || w._lcHidden) continue;
    const wy = typeof w.y === "number" && w.y > 0 ? w.y : w.last_y;
    if (typeof wy !== "number" || wy <= 0) continue;
    const h = typeof w.computeSize === "function" ? w.computeSize(node.size[0])?.[1] ?? 20 : 20;
    bottom = Math.max(bottom, wy + h);
  }
  if (bottom > 0) return bottom;
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

function slotsHeight(node) {
  // a widget's own input socket (new frontends give every widget one) sits on the widget's row, not a row of its own
  const n = (node.inputs || []).filter((i) => i && i.type !== "hidden" && !i.widget).length;
  return TITLE + n * 22;
}

function defaultHeight(node) {
  const innerW = DEFAULT_W - PAD * 2;
  const imgH = Math.round(innerW * (5 / 4));
  const top = Math.max(widgetsHeight(node), slotsHeight(node));
  return top + PAD + imgH + PAD;
}

function contentTop(node) {
  return Math.max(widgetsHeight(node), slotsHeight(node)) + PAD;
}

// Nodes with a tall widget column get the preview beside it instead of under it: the widgets keep a 300-wide column,
// the preview runs from below the input / output rows to the last widget, 4:5 portrait
const SIDE_CLASSES = new Set(["LCSkinMaster"]);
const SIDE_COL = DEFAULT_W; // the widget column
const SIDE_ASPECT = 4 / 5;
function isSide(node) {
  return SIDE_CLASSES.has(node.comfyClass || node.type || "");
}
function sideTop(node) {
  // socket rows only: in the new frontend every widget also has an input entry (i.widget), drawn on its widget row
  const rows = Math.max((node.inputs || []).filter((i) => i && !i.widget && i.type !== "hidden").length, (node.outputs || []).length);
  return rows * 22 + 6;
}
function widgetsLaidOut(node) {
  return (node.widgets || []).some((w) => typeof w.y === "number" && w.y > 0);
}
function sideSize(node) {
  for (const w of node.widgets || []) w.width = SIDE_COL; // measure the widgets at their column width
  const bottom = widgetsHeight(node);
  const h = Math.max(200, bottom - sideTop(node));
  return [SIDE_COL + Math.round(h * SIDE_ASPECT) + PAD, bottom + PAD];
}

/**
 * Resolve STRING for live text overlay preview.
 * - Unlinked: use local widget
 * - Linked to a *primitive* string source (value/text widget only): use that
 * - Linked to a *computed* node (Join Strings, etc.): return null → do not
 *   redraw client text (would pick up delimiter/widgets). Show server image only.
 */
function isPrimitiveStringNode(origin) {
  if (!origin) return false;
  const t = String(origin.type || origin.comfyClass || "");
  // Common primitive / constant string nodes
  if (/Primitive|StringLiteral|TextBox|ConstantString|StringConstant/i.test(t)) return true;
  if (t === "String" || t === "Text") return true;
  // Single "value" string widget, no delimiter/inputcount → treat as primitive-like
  const widgets = origin.widgets || [];
  const names = widgets.map((w) => w?.name).filter(Boolean);
  if (names.length === 1 && (names[0] === "value" || names[0] === "string" || names[0] === "text")) {
    return true;
  }
  // Explicitly NOT join / concatenate style nodes
  if (/Join|Concat|Replace|Combine|StringFunction/i.test(t)) return false;
  if (names.includes("delimiter") || names.includes("inputcount")) return false;
  return false;
}

function inputOrWidgetValue(node, name, fallback) {
  try {
    const graph = node.graph ?? app.graph;
    const idx = (node.inputs || []).findIndex((i) => i.name === name);
    const inp = idx >= 0 ? node.inputs[idx] : null;
    const linked =
      inp && (typeof node.isInputConnected === "function" ? node.isInputConnected(idx) : inp.link != null);
    if (linked && graph?.links) {
      const link =
        typeof node.getInputLink === "function" ? node.getInputLink(idx) : graph.links[inp.link];
      if (link) {
        const origin = graph.getNodeById(link.origin_id);
        if (origin) {
          if (!isPrimitiveStringNode(origin)) {
            // Computed STRING — live text unknown; signal caller to skip overlay
            return null;
          }
          const prefer = ["value", "string", "text", "STRING"];
          for (const pn of prefer) {
            const w = (origin.widgets || []).find((x) => x.name === pn);
            if (w && w.value != null) return w.value;
          }
          for (const w of origin.widgets || []) {
            if (w && typeof w.value === "string") return w.value;
          }
        }
      }
      // Linked but unresolved — don't fall back to stale local widget text
      return null;
    }
  } catch (_) {}
  return wval(node, name, fallback);
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

const ZOOM_RESET_SCALE = 0.5; // fallback when LC Performance settings are not loaded: canvas zoom below this ends the 100% view

// previews in their 100% view; while there is one, a slow check ends it once its node is off screen
const ZOOMED = new Set();
const ZOOM_OUT_RESET = 0.7; // canvas zoomed out to 70% of its zoom at the click = back to the fitted picture
let zoomTimer = null;
function watchZoomed() {
  if (zoomTimer || !ZOOMED.size) return;
  zoomTimer = setInterval(() => {
    const va = app.canvas?.visible_area; // [x, y, w, h] of the canvas in graph units
    for (const c of ZOOMED) {
      const n = c.node;
      if (!c.zoom || !app.graph?.getNodeById?.(n.id)) ZOOMED.delete(c);
      else if (va && va[2] > 0 && va[3] > 0 &&
               (n.pos[0] > va[0] + va[2] || n.pos[0] + n.size[0] < va[0] || n.pos[1] > va[1] + va[3] || n.pos[1] + n.size[1] < va[1])) {
        c.unzoom();
      }
    }
    if (!ZOOMED.size) {
      clearInterval(zoomTimer);
      zoomTimer = null;
    }
  }, 500);
}

// the wheel over a zoomed preview magnifies it instead of zooming the canvas
let wheelHooked = false;
function hookWheel() {
  if (wheelHooked) return;
  wheelHooked = true;
  window.addEventListener("wheel", (e) => {
    if (!ZOOMED.size || !app.canvas) return;
    const g = app.canvas.convertEventToCanvasOffset?.(e);
    if (!g) return;
    for (const c of ZOOMED) {
      const n = c.node;
      if (c.wheel([g[0] - n.pos[0], g[1] - n.pos[1]], e.deltaY)) {
        e.preventDefault();
        e.stopImmediatePropagation();
        return;
      }
    }
  }, { capture: true, passive: false });
}

/** Where an image sits when fitted (contain) into a box. */
function fitRect(img, x, y, w, h) {
  const iw = img.naturalWidth || img.width;
  const ih = img.naturalHeight || img.height;
  const s = Math.min(w / iw, h / ih);
  return { x: x + (w - iw * s) / 2, y: y + (h - ih * s) / 2, w: iw * s, h: ih * s };
}

/**
 * The result fitted to the node. Click a spot: the preview zooms to 100% (one picture pixel per screen pixel) there and
 * the cursor wipes between before and after. Double-click: back to the fitted result. The before picture is only loaded
 * once you zoom.
 */
class LCPreviewCompare {
  constructor(node) {
    this.node = node;
    this.imgA = null;
    this.imgB = null;
    this.metaB = null; // the before picture, loaded on the first zoom
    this.zoom = null; // {u, v}: the zoom centre as a fraction of the picture
    this.pointerOver = false;
    this.pointerPos = [0, 0];
    node._lcPreview = this;
    this._bind(node);
  }

  _box() {
    const node = this.node;
    if (isSide(node)) {
      const top = sideTop(node);
      return { x: SIDE_COL, y: top, w: Math.max(1, node.size[0] - SIDE_COL - PAD), h: Math.max(1, node.size[1] - top - PAD) };
    }
    const top = contentTop(node);
    return { x: PAD, y: top, w: Math.max(1, node.size[0] - PAD * 2), h: Math.max(1, node.size[1] - top - PAD) };
  }

  /** The zoomed view: the picture rectangle shown (u0, v0 fractions, sw x sh picture pixels) and where it is drawn. */
  _view() {
    const b = this._box();
    const img = this.imgA;
    const ds = app.canvas?.ds?.scale || 1;
    const mag = this.zoom.mag || 1;
    const iw = img.naturalWidth, ih = img.naturalHeight;
    const sw = Math.min(iw, (b.w * ds) / mag), sh = Math.min(ih, (b.h * ds) / mag);
    const dw = (sw * mag) / ds, dh = (sh * mag) / ds;
    const dx = b.x + (b.w - dw) / 2, dy = b.y + (b.h - dh) / 2;
    const u0 = Math.max(0, Math.min(iw - sw, this.zoom.u * iw - sw / 2)) / iw;
    const v0 = Math.max(0, Math.min(ih - sh, this.zoom.v * ih - sh / 2)) / ih;
    return { iw, ih, sw, sh, dw, dh, dx, dy, u0, v0 };
  }

  /** The wheel over the zoomed preview: magnify in or out around the cursor; out past the whole picture = fitted again. */
  wheel(pos, delta) {
    if (!this.zoom || !this.imgA) return false;
    const v = this._view();
    if (pos[0] < v.dx || pos[0] > v.dx + v.dw || pos[1] < v.dy || pos[1] > v.dy + v.dh) return false;
    const fx = (pos[0] - v.dx) / v.dw, fy = (pos[1] - v.dy) / v.dh;
    const pu = v.u0 + (fx * v.sw) / v.iw, pv = v.v0 + (fy * v.sh) / v.ih; // the picture point under the cursor
    const old = this.zoom.mag || 1;
    const step = Math.pow(1.25, Math.max(1, Math.min(4, Math.abs(delta) / 100))); // a harder flick steps further
    const mag = Math.min(16, old * (delta > 0 ? 1 / step : step));
    const b = this._box();
    const fitMag = (app.canvas?.ds?.scale || 1) * Math.min(b.w / v.iw, b.h / v.ih); // the fitted picture's size
    if (delta > 0 && mag <= fitMag * 1.05) {
      this.unzoom(); // out past the whole picture: the fitted view again
      return true;
    }
    const k = old / mag; // the shown area grows by this
    const vw = (v.sw * k) / v.iw, vh = (v.sh * k) / v.ih;
    this.zoom = { u: pu - fx * vw + vw / 2, v: pv - fy * vh + vh / 2, mag, ds0: this.zoom.ds0 };
    app.canvas?.setDirty?.(true, true);
    return true;
  }

  /** Back to the fitted picture, and let go of the before picture until the next zoom. */
  unzoom() {
    this.zoom = null;
    ZOOMED.delete(this);
    cancelLoad(this, "B");
    this.imgB = null;
    app.canvas?.setDirty?.(true, true);
  }

  _setBefore(meta, restore = false) {
    this.metaB = meta?.length ? meta : null;
    cancelLoad(this, "B");
    this.imgB = null;
    if (this.metaB && this.zoom) this._loadMeta(this.metaB, "B", restore);
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
      if (this.flags?.collapsed) return;
      if (isSide(this)) {
        for (const w of this.widgets || []) if (w.width !== SIDE_COL) w.width = SIDE_COL; // keep the column
        // size it once the widgets are laid out (a new node, or one saved with the old preview-below layout)
        if (!this._lcSideSized && widgetsLaidOut(this)) {
          this._lcSideSized = true;
          if (!this._lcPvConfigured || this.size[0] < SIDE_COL + 200) {
            this.size = sideSize(this);
            this.setDirtyCanvas?.(true, true);
          }
        }
      }
      self.draw(ctx);
    };

    const origMouseMove = node.onMouseMove;
    node.onMouseMove = function (e, pos, canvas) {
      self.pointerPos = pos;
      const pol = lcPerfPolicy(this);
      if (self.zoom && !pol.hide && self.pointerOver && self.imgA && self.imgB) {
        app.canvas?.setDirty?.(true, false); // the wipe is drawn in the foreground only
      }
      return origMouseMove ? origMouseMove.apply(this, arguments) : false;
    };

    // the usage tooltip (lc_preview_tip.js) shows over the fitted picture
    node._lcPreviewHit = (pos) => {
      const img = self.imgA;
      if (!img || self.zoom || lcPerfPolicy(node).hide) return false;
      const b = self._box();
      const r = fitRect(img, b.x, b.y, b.w, b.h);
      return pos[0] >= r.x && pos[0] <= r.x + r.w && pos[1] >= r.y && pos[1] <= r.y + r.h;
    };
    // click on the picture: zoom to 100% there (or stay at the on-screen size when the canvas already shows it bigger);
    // double-click: back to the fitted picture
    const origMouseDown = node.onMouseDown;
    node.onMouseDown = function (e, pos, canvas) {
      const img = self.imgA;
      if (img && !self.zoom && (e.button === 0 || e.button === undefined) && !lcPerfPolicy(this).hide) {
        const b = self._box();
        const r = fitRect(img, b.x, b.y, b.w, b.h);
        if (pos[0] >= r.x && pos[0] <= r.x + r.w && pos[1] >= r.y && pos[1] <= r.y + r.h) {
          const fit = ((app.canvas?.ds?.scale || 1) * r.w) / img.naturalWidth; // screen pixels per picture pixel now
          self.zoom = { u: (pos[0] - r.x) / r.w, v: (pos[1] - r.y) / r.h, mag: Math.max(1, fit), ds0: app.canvas?.ds?.scale || 1 };
          ZOOMED.add(self);
          watchZoomed();
          hookWheel();
          if (self.metaB && !self.imgB) self._loadMeta(self.metaB, "B");
          app.canvas?.setDirty?.(true, true);
          return true;
        }
      }
      return origMouseDown ? origMouseDown.apply(this, arguments) : false;
    };

    const origDblClick = node.onDblClick;
    node.onDblClick = function (e, pos, canvas) {
      if (self.zoom) {
        self.unzoom();
        return true;
      }
      return origDblClick ? origDblClick.apply(this, arguments) : false;
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

  _loadMeta(meta, which, restore = false) {
    if (!meta?.length) {
      cancelLoad(this, which);
      if (which === "A") this.imgA = null;
      if (which === "B") this.imgB = null;
      return;
    }
    const self = this;
    loadLatest(
      this,
      which,
      meta[0],
      (img) => {
        if (which === "A") self.imgA = img;
        else self.imgB = img;
      },
      restore
    );
  }

  _restoreFromProps() {
    const props = this.node.properties || {};
    if (props.lc_preview_meta) this._loadMeta(props.lc_preview_meta, "A", true);
    if (props.lc_before_meta && imageDataKey(props.lc_before_meta[0]) !== imageDataKey(this.metaB?.[0])) {
      this._setBefore(props.lc_before_meta, true);
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
    this.node.properties.lc_before_meta = beforeMeta?.length ? beforeMeta : null;
    this._setBefore(beforeMeta);
    this.node._lcBypass = !!(
      message.lc_bypass &&
      (message.lc_bypass[0] === "1" || message.lc_bypass[0] === 1)
    );
  }

  draw(ctx) {
    const node = this.node;
    const pol = lcPerfPolicy(node);
    if (pol.skipCollapsed && node.flags?.collapsed) return;
    if (pol.hide) return;

    const imgA = this.imgA;
    const { x, y, w, h } = this._box();
    if (isSide(node) && h >= 16) {
      // the side panel stays visible before the first run, so the node keeps its shape
      ctx.save();
      ctx.fillStyle = "rgba(0,0,0,0.22)";
      ctx.beginPath();
      ctx.roundRect ? ctx.roundRect(x, y, w, h, 6) : ctx.rect(x, y, w, h);
      ctx.fill();
      if (!imgA) {
        ctx.fillStyle = "rgba(255,255,255,0.35)";
        ctx.font = "12px sans-serif";
        ctx.textAlign = "center";
        ctx.fillText("preview after the first run", x + w / 2, y + h / 2);
      }
      ctx.restore();
    }
    if (!imgA && !this.imgB) return;
    if (h < 16) return;

    const maxEdge = pol.maxEdge || 0;

    const drawCover = (img) => {
      if (!img) return;
      let dw = w, dh = h, dx = x, dy = y;
      if (pol.halfRes) {
        dw = w * 0.5;
        dh = h * 0.5;
        dx = x + (w - dw) / 2;
        dy = y + (h - dh) / 2;
      }
      drawCoverScaled(ctx, img, dx, dy, dw, dh, maxEdge);
    };

    const ds = app.canvas?.ds?.scale || 1;
    const lost = window.LC123Perf?.tooSmall ? window.LC123Perf.tooSmall(w, h) : ds < ZOOM_RESET_SCALE;
    // canvas zoomed out to where the preview is no longer drawn, or well out from where it was clicked (big previews)
    if (this.zoom && (lost || ds < (this.zoom.ds0 || ds) * ZOOM_OUT_RESET)) this.unzoom();
    if (this.zoom && imgA) {
      // 100% (one picture pixel per screen pixel) times the wheel's magnification, centred on the clicked spot
      const { iw, ih, sw, sh, dw, dh, dx, dy, u0, v0 } = this._view();
      const crop = (img, cx, cy, cw, ch) => {
        const nw = img.naturalWidth, nh = img.naturalHeight;
        ctx.drawImage(img, u0 * nw, v0 * nh, (sw / iw) * nw, (sh / ih) * nh, cx, cy, cw, ch);
      };
      ctx.save();
      ctx.imageSmoothingEnabled = false;
      const wipe = !!this.imgB;
      crop(imgA, dx, dy, dw, dh); // after underneath, before left of the pointer
      const splitX = wipe && this.pointerOver ? Math.max(0, Math.min(dw, this.pointerPos[0] - dx)) : 0;
      if (splitX > 0) {
        ctx.beginPath();
        ctx.rect(dx, dy, splitX, dh);
        ctx.clip();
        crop(this.imgB, dx, dy, dw, dh);
      }
      ctx.restore();
      if (wipe && this.pointerOver) {
        ctx.strokeStyle = "rgba(255,255,255,0.9)";
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(dx + splitX, dy);
        ctx.lineTo(dx + splitX, dy + dh);
        ctx.stroke();
      }
      ctx.save();
      ctx.font = "11px sans-serif";
      ctx.textAlign = "right";
      ctx.textBaseline = "bottom";
      ctx.fillStyle = "rgba(0,0,0,0.55)";
      const pct = `${Math.round((this.zoom.mag || 1) * 100)}%`;
      const label = wipe ? `${pct} · before | after · double-click: back` : `${pct} · double-click: back`;
      const tw = ctx.measureText(label).width;
      ctx.fillRect(dx + dw - tw - 10, dy + dh - 18, tw + 10, 18);
      ctx.fillStyle = "#fff";
      ctx.fillText(label, dx + dw - 5, dy + dh - 4);
      ctx.restore();
    } else if (imgA) {
      drawCover(imgA);
    } else if (this.imgB) {
      drawCover(this.imgB);
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


    const origConn = node.onConnectionsChange;
    node.onConnectionsChange = function () {
      const r = origConn?.apply(this, arguments);
      app.canvas?.setDirty?.(true, true);
      return r;
    };

    const origDrawFG = node.onDrawForeground;
    node.onDrawForeground = function (ctx) {
      if (origDrawFG) origDrawFG.apply(this, arguments);
      if (this.flags?.collapsed) return;
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

    // Alignment → default X (user can still drag/override after)
    const alignW = (node.widgets || []).find((w) => w.name === "alignment")
      || (node.widgets || []).find((w) => w.name === "anchor");
    if (alignW && !alignW._lcAlignHook) {
      alignW._lcAlignHook = true;
      const prevA = alignW.callback;
      alignW.callback = function (v, ...rest) {
        let key = String(v || "").toLowerCase();
        if (key.includes("-")) key = key.split("-")[0];
        const map = { left: 8, center: 50, right: 92 };
        // Only snap X when user picks a simple left/center/right (not on every legacy load)
        if (v === "left" || v === "center" || v === "right") {
          const xw = (node.widgets || []).find((w) => w.name === "x_percent");
          if (xw) {
            xw.value = map[key];
            if (typeof xw.callback === "function") {
              try { xw.callback(xw.value); } catch (_) {}
            }
          }
        }
        if (typeof prevA === "function") return prevA.apply(this, [v, ...rest]);
      };
    }
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

  /**
   * Map pointer to % of the *letterboxed image*, not the full node box
   * (matches output: % of full image width/height).
   * IMAGE_MARGIN_PX = 6 — same as Python MARGIN_PX.
   */
  _imageRect(box) {
    const img = this.baseImg;
    if (!img || !img.naturalWidth) {
      return { ox: box.x, oy: box.y, sw: box.w, sh: box.h, scale: 1 };
    }
    const scale = Math.min(box.w / img.naturalWidth, box.h / img.naturalHeight);
    const sw = img.naturalWidth * scale;
    const sh = img.naturalHeight * scale;
    const ox = box.x + (box.w - sw) / 2;
    const oy = box.y + (box.h - sh) / 2;
    return { ox, oy, sw, sh, scale };
  }

  _setPosFromLocal(lx, ly, box) {
    const { ox, oy, sw, sh } = this._imageRect(box);
    if (sw < 1 || sh < 1) return;
    const xp = Math.max(0, Math.min(100, ((lx - ox) / sw) * 100));
    const yp = Math.max(0, Math.min(100, ((ly - oy) / sh) * 100));
    setWval(this.node, "x_percent", Math.round(xp * 10) / 10);
    setWval(this.node, "y_percent", Math.round(yp * 10) / 10);
  }

  _restoreFromProps() {
    const props = this.node.properties || {};
    if (props.lc_overlay_text != null) {
      this._linkedText = String(props.lc_overlay_text);
    }
    const meta = props.lc_preview_meta || props.lc_before_meta;
    if (!meta?.length) return;
    const self = this;
    loadLatest(this, "base", meta[0], (img) => (self.baseImg = img), true);
  }

  onExecuted(message) {
    if (!message) return;
    const self = this;
    // Text actually drawn this run (works with Join Strings after first queue)
    if (message.lc_overlay_text != null) {
      const raw = message.lc_overlay_text;
      const s = Array.isArray(raw) ? raw.join("") : String(raw);
      this._linkedText = s;
      if (!this.node.properties) this.node.properties = {};
      this.node.properties.lc_overlay_text = s;
    }
    const meta = message.lc_before || message.lc_preview || message.images;
    if (meta?.length) {
      if (!this.node.properties) this.node.properties = {};
      this.node.properties.lc_preview_meta = meta;
      loadLatest(this, "base", meta[0], (img) => (self.baseImg = img));
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
    if (box.h < 16) return;

    const { ox, oy, sw, sh, scale } = this._imageRect(box);
    if (!window.LC123Perf?.skipImage?.(ctx, ox, oy, sw, sh)) ctx.drawImage(img, ox, oy, sw, sh);

    let rawText = inputOrWidgetValue(node, "text", "");
    // Linked computed (Join Strings, etc.): use text from last successful run
    if (rawText === null) {
      rawText =
        this._linkedText ??
        node.properties?.lc_overlay_text ??
        null;
      if (rawText === null || rawText === "") {
        // First run: image from server may already include text after queue;
        // skip client redraw so we don't paint delimiter/wrong text on top.
        return;
      }
    }
    const text = String(rawText ?? "");
    if (!text) return;

    const fontSize = Number(wval(node, "font_size", 64)) || 64;
    const fontKey = String(wval(node, "font", "Arial") || "Arial");
    const fontCss = LC_FONT_CSS[fontKey] || `"${fontKey}", sans-serif`;
    const r = Number(wval(node, "color_r", 255)) | 0;
    const g = Number(wval(node, "color_g", 255)) | 0;
    const b = Number(wval(node, "color_b", 255)) | 0;
    let xp = Number(wval(node, "x_percent", 50));
    let yp = Number(wval(node, "y_percent", 92));
    // alignment preferred; fall back to legacy "anchor" widget if present
    let ah = String(wval(node, "alignment", "") || wval(node, "anchor", "center") || "center").toLowerCase();
    if (ah.includes("-")) ah = ah.split("-")[0];
    if (ah !== "left" && ah !== "right" && ah !== "center") ah = "center";

    // Same as Python MARGIN_PX = 6 (in *image* pixels), converted to display space
    const IMAGE_MARGIN_PX = 6;
    const dispSize = Math.max(8, fontSize * scale);
    const margin = IMAGE_MARGIN_PX * scale;
    const maxW = Math.max(8, sw - 2 * margin);

    const weight = /bold/i.test(fontKey) ? "bold " : "";
    const italic = /italic/i.test(fontKey) ? "italic " : "";
    ctx.save();
    const font = `${italic}${weight}${dispSize}px ${fontCss}`;
    ctx.font = font;
    ctx.fillStyle = `rgb(${r},${g},${b})`;
    ctx.textBaseline = "top";
    ctx.textAlign = "left";

    // wrapping measures every word: only redo it when text, font, size, width or loaded fonts change
    const wrapKey = `${fontEpoch}\n${font}\n${maxW}\n${text}`;
    if (!this._wrapCache || this._wrapCache.key !== wrapKey) {
      const wrapped = this._wrap(ctx, text, maxW);
      this._wrapCache = { key: wrapKey, lines: wrapped, widths: wrapped.map((l) => ctx.measureText(l).width) };
    }
    const lines = this._wrapCache.lines;
    const widths = this._wrapCache.widths;
    const lineH = dispSize * 1.2;
    const blockH = Math.max(lineH, lines.length * lineH);

    // y_percent = top of text block (no vertical anchor). Default ~92 = near bottom.
    let topY = oy + (yp / 100) * sh;

    // Hard clamp inside drawn image
    const minY = oy + margin;
    const maxY = oy + sh - margin - blockH;
    if (maxY < minY) topY = minY;
    else topY = Math.max(minY, Math.min(maxY, topY));

    const cx = ox + (xp / 100) * sw;

    lines.forEach((line, i) => {
      const tw = widths[i];
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
      if (this.flags?.collapsed) return;
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
      // Only primary button
      if (e && e.button != null && e.button !== 0) {
        return origDown ? origDown.apply(this, arguments) : false;
      }
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

  _loadMeta(meta, which, restore = false) {
    if (!meta?.length) return;
    const self = this;
    loadLatest(
      this,
      which,
      meta[0],
      (img) => {
        if (which === "base") self.baseImg = img;
        else self.wmImg = img;
      },
      restore
    );
  }

  _restoreFromProps() {
    const props = this.node.properties || {};
    if (props.lc_before_meta) this._loadMeta(props.lc_before_meta, "base", true);
    if (props.lc_wm_meta) this._loadMeta(props.lc_wm_meta, "wm", true);
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

    if (window.LC123Perf?.skipImage?.(ctx, ox, oy, sw, sh)) return;
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

    const onConfigure = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function () {
      this._lcPvConfigured = true;
      return onConfigure?.apply(this, arguments);
    };

    const onCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      if (onCreated) onCreated.apply(this, arguments);
      lcApplyLaunchColor(this, "#324B4B");
      this._lcBypass = false;
      this.comfyClass = name;

      if (isText) {
        loadBundledFonts(redrawOnFontLoad);
        const tw = (this.widgets || []).find((w) => w.name === "text");
        if (tw) {
          tw.computeSize = function (width) {
            return [width, 54];
          };
        }
      }

      const side = SIDE_CLASSES.has(name);
      this.size = side ? sideSize(this) : [DEFAULT_W, defaultHeight(this)];
      setTimeout(() => {
        if (this._lcPvConfigured) return; // restored from a workflow (load, undo, paste): keep its saved size
        try {
          const want = side ? sideSize(this) : [DEFAULT_W, defaultHeight(this)];
          this.size = [
            Math.max(this.size[0], want[0]),
            Math.max(this.size[1], want[1]),
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
