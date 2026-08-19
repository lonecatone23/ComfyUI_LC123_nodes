/**
 * LC Image Split 🖼️
 * Live A|B wipe on the node, driven ONLY by the split_position widget.
 * Dragging on the image does not change the wipe (avoids accidental moves).
 */
import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const TYPE = "LCImageSplit";
const COLOR = "#324B4B";
const DEFAULT_W = 300; // same as other LC image nodes
const MIN_W = 300;
const PAD = 16;
const TITLE = 34;

function widgetsHeight(node) {
  let h = TITLE;
  for (const w of node.widgets || []) {
    if (!w || w.type === "hidden") continue;
    try {
      const sz = w.computeSize?.(node.size?.[0] || DEFAULT_W) || [0, LiteGraph?.NODE_WIDGET_HEIGHT || 20];
      h += (sz[1] || 20) + 4;
    } catch (_) {
      h += 24;
    }
  }
  return h;
}

/** Match LC image FX nodes: ~4:5 image area under widgets */
function defaultSize(node) {
  const innerW = DEFAULT_W - PAD * 2;
  const imgH = Math.round(innerW * (5 / 4));
  return [DEFAULT_W, widgetsHeight(node) + PAD + imgH + PAD];
}

function imageUrl(img) {
  if (!img) return null;
  if (img.filename) {
    const params = new URLSearchParams();
    params.set("filename", img.filename);
    params.set("type", img.type || "temp");
    params.set("subfolder", img.subfolder || "");
    return api.apiURL(`/view?${params.toString()}`);
  }
  return null;
}

function loadImg(meta) {
  return new Promise((resolve) => {
    const url = imageUrl(meta);
    if (!url) {
      resolve(null);
      return;
    }
    const im = new Image();
    im.crossOrigin = "anonymous";
    im.onload = () => resolve(im);
    im.onerror = () => resolve(null);
    im.src = url;
  });
}

function widgetVal(node, name, fallback) {
  const w = (node.widgets || []).find((x) => x.name === name);
  return w != null ? w.value : fallback;
}

class LCImageSplitPreview {
  constructor(node) {
    this.node = node;
    this.imgA = null;
    this.imgB = null;
    this._bound = false;
    node.lcImageSplitPreview = this;
    this._bind();
  }

  _bind() {
    if (this._bound) return;
    this._bound = true;
    const node = this.node;

    // Widget → live redraw only (no image drag)
    for (const w of node.widgets || []) {
      if (!w) continue;
      const prev = w.callback;
      w.callback = (...args) => {
        const r = typeof prev === "function" ? prev.apply(w, args) : undefined;
        app.canvas?.setDirty?.(true, true);
        return r;
      };
    }

    const origDraw = node.onDrawForeground;
    node.onDrawForeground = function (ctx) {
      origDraw?.apply(this, arguments);
      this.lcImageSplitPreview?.draw(ctx);
    };

    const origExec = node.onExecuted;
    node.onExecuted = function (message) {
      origExec?.apply(this, arguments);
      this.lcImageSplitPreview?.onExecuted(message);
    };

    // Explicitly do NOT attach pointer handlers that write split_position
  }

  async onExecuted(message) {
    if (!message) return;
    const aMeta = message.a_images?.[0];
    const bMeta = message.b_images?.[0];
    const [a, b] = await Promise.all([loadImg(aMeta), loadImg(bMeta)]);
    if (a) this.imgA = a;
    if (b) this.imgB = b;
    app.canvas?.setDirty?.(true, true);
  }

  _box() {
    const node = this.node;
    const w = Math.max(MIN_W - PAD * 2, (node.size?.[0] || DEFAULT_W) - PAD * 2);
    const widgetsBottom = this._widgetsBottom();
    const top = Math.max(TITLE + 8, widgetsBottom + 10);
    const h = Math.max(80, (node.size?.[1] || 320) - top - 12);
    return { x: PAD / 2, y: top, w, h };
  }

  _widgetsBottom() {
    const node = this.node;
    let y = TITLE;
    try {
      for (const w of node.widgets || []) {
        if (!w || w.type === "converted-widget") continue;
        const sz = w.computeSize?.(node.size[0]) || [0, LiteGraph?.NODE_WIDGET_HEIGHT || 20];
        y += (sz[1] || 20) + 4;
      }
    } catch (_) {
      y = TITLE + 80;
    }
    return y;
  }

  draw(ctx) {
    const node = this.node;
    const box = this._box();
    const { x, y, w, h } = box;

    ctx.save();
    ctx.beginPath();
    ctx.rect(x, y, w, h);
    ctx.clip();
    ctx.fillStyle = "#111";
    ctx.fillRect(x, y, w, h);

    const a = this.imgA;
    const b = this.imgB;
    if (!a && !b) {
      ctx.fillStyle = "#666";
      ctx.font = "12px sans-serif";
      ctx.fillText("Queue once for preview", x + 8, y + 20);
      ctx.restore();
      return;
    }

    const src = a || b;
    const scale = Math.min(w / src.naturalWidth, h / src.naturalHeight);
    const dw = src.naturalWidth * scale;
    const dh = src.naturalHeight * scale;
    const ox = x + (w - dw) / 2;
    const oy = y + (h - dh) / 2;

    // Position from widget only (0–1)
    let pos = parseFloat(widgetVal(node, "split_position", 0.5));
    if (!Number.isFinite(pos)) pos = 0.5;
    pos = Math.max(0, Math.min(1, pos));
    const cut = ox + dw * pos;

    // B full
    if (b) {
      ctx.drawImage(b, ox, oy, dw, dh);
    } else {
      ctx.fillStyle = "#222";
      ctx.fillRect(ox, oy, dw, dh);
    }

    // A left of cut
    if (a) {
      ctx.save();
      ctx.beginPath();
      ctx.rect(ox, oy, Math.max(0, cut - ox), dh);
      ctx.clip();
      ctx.drawImage(a, ox, oy, dw, dh);
      ctx.restore();
    }

    // Divider line (visual only)
    ctx.strokeStyle = "rgba(255,255,255,0.85)";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(cut, oy);
    ctx.lineTo(cut, oy + dh);
    ctx.stroke();

    ctx.restore();
  }
}

app.registerExtension({
  name: "LC123.ImageSplit",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData?.name !== TYPE) return;

    const onNodeCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const r = onNodeCreated?.apply(this, arguments);
      try {
        this.color = COLOR;
        this.bgcolor = COLOR;
        // Always launch at standard image-node size (widgets + 4:5 preview)
        this.size = defaultSize(this);
      } catch (_) {
        try {
          this.size = [DEFAULT_W, 400];
        } catch (__) {}
      }
      if (!this.lcImageSplitPreview) {
        new LCImageSplitPreview(this);
      }
      return r;
    };

    const onConfigure = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function (data) {
      const r = onConfigure?.apply(this, arguments);
      if (!this.lcImageSplitPreview) {
        new LCImageSplitPreview(this);
      }
      return r;
    };
  },
  nodeCreated(node) {
    if (node.comfyClass !== TYPE && node.type !== TYPE) return;
    try {
      node.color = COLOR;
      node.bgcolor = COLOR;
      if (!node.size || node.size[0] < MIN_W || (node.size[1] || 0) < 200) {
        node.size = defaultSize(node);
      }
    } catch (_) {}
    if (!node.lcImageSplitPreview) {
      new LCImageSplitPreview(node);
    }
  },
});
