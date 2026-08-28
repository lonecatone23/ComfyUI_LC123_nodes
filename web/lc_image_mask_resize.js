/**
 * LC Image-Mask Resize — chrome matches 📐 Aspect Ratio Simplifier
 * (#324B4B, launch width 280). upscale_by shows multiplier or megapixels.
 */

import { app } from "../../scripts/app.js";

const TYPE = "LCImageMaskResize";
const COLOR = "#324B4B";
const DEFAULT_W = 280; // same as Aspect Ratio Simplifier in LC Node examples

function widgetByName(node, name) {
  return (node.widgets || []).find((w) => w.name === name);
}

function paint(node) {
  try {
    node.color = COLOR;
    node.bgcolor = COLOR;
  } catch (_) {}
}

function sizeLaunch(node) {
  if (node._lcUserSized || node.properties?.lc_w) {
    const w = node.properties?.lc_w;
    const h = node.properties?.lc_h;
    if (w && h) {
      node.size = [w, h];
      node._lcUserSized = true;
    }
    return;
  }
  const h = node.size?.[1] || 200;
  if (!node.size || (node.size[0] || 0) < 40) {
    node.setSize?.([DEFAULT_W, h]);
  } else if ((node.size[0] || 0) < DEFAULT_W) {
    node.size[0] = DEFAULT_W;
  }
}

function rememberSize(node) {
  if (!node.properties) node.properties = {};
  if (node.size) {
    node.properties.lc_w = node.size[0];
    node.properties.lc_h = node.size[1];
  }
  node._lcUserSized = true;
}

function hideWidget(w) {
  if (!w) return;
  if (w._lcOrigType == null) w._lcOrigType = w.type;
  w.hidden = true;
  w.disabled = true;
  w.type = "hidden";
  w.computeSize = () => [0, 0];
}

function showWidget(w, enabled) {
  if (!w) return;
  w.hidden = false;
  w.disabled = !enabled;
  w.type = w._lcOrigType || "number";
  delete w.computeSize;
  w.options = w.options || {};
  w.options.precision = 2;
  if (w.inputEl) w.inputEl.disabled = !enabled;
}

function applyUpscaleBy(node) {
  const modeW = widgetByName(node, "upscale_by");
  const mulW = widgetByName(node, "multiplier");
  const mpW = widgetByName(node, "megapixels");
  if (mulW) {
    mulW.options = mulW.options || {};
    mulW.options.precision = 2;
  }
  if (mpW) {
    mpW.options = mpW.options || {};
    mpW.options.precision = 2;
    if (mpW.value == null || mpW.value === "") mpW.value = 1.0;
  }
  if (!modeW) return;

  const mode = modeW.value;
  if (mode === "multiplier") {
    showWidget(mulW, true);
    hideWidget(mpW);
  } else if (mode === "megapixels") {
    hideWidget(mulW);
    showWidget(mpW, true);
  } else {
    showWidget(mulW, false);
    hideWidget(mpW);
  }

  if (typeof node.computeSize === "function") {
    const sz = node.computeSize();
    if (Array.isArray(sz) && sz.length >= 2) {
      const w = node._lcUserSized
        ? node.size?.[0] || DEFAULT_W
        : Math.max(DEFAULT_W, node.size?.[0] || DEFAULT_W);
      node.setSize?.([w, sz[1]]);
    }
  }
  node.setDirtyCanvas?.(true, true);
}

function hook(node) {
  if (node._lcImgMaskResizeHooked) return;
  node._lcImgMaskResizeHooked = true;
  paint(node);
  sizeLaunch(node);
  const modeW = widgetByName(node, "upscale_by");
  if (modeW) {
    const prev = modeW.callback;
    modeW.callback = function (value, ...rest) {
      applyUpscaleBy(node);
      if (typeof prev === "function") return prev.apply(this, [value, ...rest]);
    };
  }
  const prevResize = node.onResize;
  node.onResize = function (size) {
    rememberSize(this);
    if (typeof prevResize === "function") return prevResize.apply(this, arguments);
  };
  applyUpscaleBy(node);
}

app.registerExtension({
  name: "LC123.ImageMaskResize",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData?.name !== TYPE) return;
    const onNodeCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const r = onNodeCreated?.apply(this, arguments);
      paint(this);
      sizeLaunch(this);
      return r;
    };
  },
  nodeCreated(node) {
    if (node.comfyClass !== TYPE && node.type !== TYPE) return;
    hook(node);
  },
  loadedGraphNode(node) {
    if (node.comfyClass !== TYPE && node.type !== TYPE) return;
    hook(node);
    paint(node);
    applyUpscaleBy(node);
  },
});
