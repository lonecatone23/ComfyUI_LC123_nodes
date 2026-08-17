/**
 * LC Image Split — live sticky wipe over A/B previews (does not snap back).
 * Output socket is baked by Python; preview stays interactive.
 */
import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const NODE_TYPE = "LCImageSplit";
const DEFAULT_W = 300;
const DEFAULT_H = 420;
const MIN_W = 280;
const MIN_H = 360;
const PAD = 14;
const SLOT_H = 22;

function imageDataToUrl(data) {
  if (!data) return null;
  const fmt =
    typeof app.getPreviewFormatParam === "function"
      ? app.getPreviewFormatParam()
      : "";
  const rand =
    typeof app.getRandParam === "function" ? app.getRandParam() : "";
  return api.apiURL(
    `/view?filename=${encodeURIComponent(data.filename)}` +
      `&type=${data.type || "temp"}` +
      `&subfolder=${encodeURIComponent(data.subfolder || "")}` +
      `${fmt}${rand}`
  );
}

function widgetByName(node, name) {
  return (node.widgets || []).find((w) => w.name === name);
}

function socketOffset(node) {
  const nIn = (node.inputs || []).filter((s) => s && s.type).length;
  const nOut = (node.outputs || []).filter((s) => s && s.type).length;
  return Math.max(nIn, nOut, 1) * SLOT_H + 6;
}

function widgetsBottom(node) {
  let y = socketOffset(node);
  for (const w of node.widgets || []) {
    if (!w || w.type === "hidden") continue;
    const h =
      typeof w.computeSize === "function"
        ? w.computeSize(node.size[0])?.[1] ?? 22
        : 22;
    y += Math.max(20, h);
  }
  return y + 6;
}

class LCImageSplitUI {
  constructor(node) {
    this.node = node;
    this.imagesA = [];
    this.imagesB = [];
    this.imgA = null;
    this.imgB = null;
    this.dragging = false;
    this._bind(node);
  }

  _bind(node) {
    if (!node.size || node.size[0] < MIN_W || node.size[1] < MIN_H) {
      node.size = [
        Math.max(node.size?.[0] || DEFAULT_W, DEFAULT_W),
        Math.max(node.size?.[1] || DEFAULT_H, DEFAULT_H),
      ];
    }

    const self = this;

    const onExecuted = node.onExecuted;
    node.onExecuted = function (message) {
      onExecuted?.apply(this, arguments);
      self.imagesA = message?.a_images || [];
      self.imagesB = message?.b_images || [];
      self._loadImages();
      this.setDirtyCanvas?.(true, true);
    };

    const onDrawFG = node.onDrawForeground;
    node.onDrawForeground = function (ctx) {
      if (this.flags?.collapsed) return;
      onDrawFG?.apply(this, arguments);
      self.draw(ctx);
    };

    const onMouseDown = node.onMouseDown;
    node.onMouseDown = function (e, pos, canvas) {
      if (this.flags?.collapsed) return onMouseDown?.apply(this, arguments);
      const area = self._imgArea();
      if (pos[1] >= area.y && pos[1] <= area.y + area.h) {
        self.dragging = true;
        self._setPosFromLocalX(pos[0], area);
        return true;
      }
      return onMouseDown?.apply(this, arguments);
    };

    const onMouseMove = node.onMouseMove;
    node.onMouseMove = function (e, pos, canvas) {
      if (self.dragging) {
        const area = self._imgArea();
        self._setPosFromLocalX(pos[0], area);
        return true;
      }
      return onMouseMove?.apply(this, arguments);
    };

    const onMouseUp = node.onMouseUp;
    node.onMouseUp = function (e, pos, canvas) {
      if (self.dragging) {
        self.dragging = false;
        const area = self._imgArea();
        self._setPosFromLocalX(pos[0], area);
        return true;
      }
      return onMouseUp?.apply(this, arguments);
    };

    const origResize = node.onResize;
    node.onResize = function (size) {
      if (size) {
        if (size[0] < MIN_W) size[0] = MIN_W;
        if (size[1] < MIN_H) size[1] = MIN_H;
      }
      const r = origResize?.apply(this, arguments);
      this.setDirtyCanvas?.(true, true);
      return r;
    };
  }

  _imgArea() {
    const node = this.node;
    const y = widgetsBottom(node);
    const w = Math.max(40, node.size[0] - PAD * 2);
    const h = Math.max(40, node.size[1] - y - PAD);
    return { x: PAD, y, w, h };
  }

  _setPosFromLocalX(localX, area) {
    const t = Math.max(0, Math.min(1, (localX - area.x) / Math.max(1, area.w)));
    const w = widgetByName(this.node, "split_position");
    if (!w) return;
    w.value = Math.round(t * 100) / 100;
    if (typeof w.callback === "function") {
      try {
        w.callback(w.value, this.node, app.canvas);
      } catch (_) {}
    }
    this.node.setDirtyCanvas?.(true, true);
  }

  _loadImages() {
    const a = this.imagesA[0];
    const b = this.imagesB[0];
    if (a) {
      const url = imageDataToUrl(a);
      if (!this.imgA || this.imgA._lcUrl !== url) {
        const im = new Image();
        im._lcUrl = url;
        im.src = url;
        this.imgA = im;
      }
    } else this.imgA = null;
    if (b) {
      const url = imageDataToUrl(b);
      if (!this.imgB || this.imgB._lcUrl !== url) {
        const im = new Image();
        im._lcUrl = url;
        im.src = url;
        this.imgB = im;
      }
    } else this.imgB = null;
  }

  draw(ctx) {
    const node = this.node;
    const area = this._imgArea();
    const { x, y, w, h } = area;

    ctx.save();
    ctx.beginPath();
    ctx.rect(x, y, w, h);
    ctx.clip();

    // Placeholder
    ctx.fillStyle = "#111";
    ctx.fillRect(x, y, w, h);

    const posW = widgetByName(node, "split_position");
    const t = posW ? Number(posW.value) : 0.5;
    const cut = x + t * w;

    // Contain: fit full image inside the preview window (letterbox if needed)
    const drawFit = (img) => {
      if (!img || !img.complete || !img.naturalWidth) return false;
      const ir = img.naturalWidth / img.naturalHeight;
      const ar = w / h;
      let dw, dh, dx, dy;
      if (ir > ar) {
        dw = w;
        dh = w / ir;
        dx = x;
        dy = y + (h - dh) / 2;
      } else {
        dh = h;
        dw = h * ir;
        dx = x + (w - dw) / 2;
        dy = y;
      }
      ctx.drawImage(img, dx, dy, dw, dh);
      return true;
    };

    // Full B, then clip A on the left of the wipe
    drawFit(this.imgB || this.imgA);

    if (this.imgA && this.imgA.complete) {
      ctx.save();
      ctx.beginPath();
      ctx.rect(x, y, Math.max(0, cut - x), h);
      ctx.clip();
      drawFit(this.imgA);
      ctx.restore();
    }

    // Wipe line
    ctx.strokeStyle = "rgba(255,255,255,0.9)";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(cut, y);
    ctx.lineTo(cut, y + h);
    ctx.stroke();
    ctx.strokeStyle = "rgba(0,0,0,0.5)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(cut + 1, y);
    ctx.lineTo(cut + 1, y + h);
    ctx.stroke();

    ctx.restore();

    // Soft border
    ctx.strokeStyle = "#333";
    ctx.strokeRect(x + 0.5, y + 0.5, w - 1, h - 1);
  }
}

app.registerExtension({
  name: "LC123.ImageSplit",
  nodeCreated(node) {
    if (node.comfyClass !== NODE_TYPE && node.type !== NODE_TYPE) return;
    node.color = "#324B4B";
    node.bgcolor = "#324B4B";
    if (!node.size || node.size[0] < MIN_W) {
      node.size = [DEFAULT_W, DEFAULT_H];
    }
    node._lcImageSplitUI = new LCImageSplitUI(node);
  },
});
