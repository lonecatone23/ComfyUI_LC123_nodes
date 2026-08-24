/**
 * LC Lighting Control — interactive light stage (DOMWidget, below all params).
 * White = light 1, red = light 2 (when enabled).
 * Drag = XY.  Shift+drag vertical (or wheel over handle) = Z depth.
 */
import { app } from "../../scripts/app.js";

const COLOR = "#324B4B";
const TYPE = "LCRelight";
/** Match LCSkinBeauty / image FX via lc_image_preview.js */
const IMAGE_W = 300;
const PAD = 16; // same PAD as lc_image_preview.js — equal inset all sides
/** Stage fills node content width minus PAD*2 (300 - 32 = 268) */
const STAGE_CSS = IMAGE_W - PAD * 2;
/** Grid inset inside the stage canvas — equal on all 4 sides */
const MARGIN = PAD;
const HANDLE_HIT = 14;

function wval(node, name, fallback) {
  const w = (node.widgets || []).find((x) => x.name === name);
  if (!w) return fallback;
  const v = w.value;
  if (v === undefined || v === null || v === "") return fallback;
  return v;
}

function setWval(node, name, value) {
  const w = (node.widgets || []).find((x) => x.name === name);
  if (!w) return;
  w.value = value;
  try {
    w.callback?.(value, undefined, node, undefined, undefined);
  } catch (_) {}
}

function clamp(v, a, b) {
  return Math.max(a, Math.min(b, v));
}

function radiusForZ(z, base) {
  const t = Math.max(0, Math.min(1, Number(z)));
  return base * (0.55 + 0.55 * t);
}

function installStage(node) {
  if (node.__lcLightStage) return;
  node.__lcLightStage = true;

  const wrap = document.createElement("div");
  wrap.style.cssText =
    "width:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:0;box-sizing:border-box;";

  const canvas = document.createElement("canvas");
  canvas.width = STAGE_CSS * 2; // retina
  canvas.height = STAGE_CSS * 2;
  canvas.style.cssText = `width:${STAGE_CSS}px;height:${STAGE_CSS}px;border-radius:6px;cursor:grab;touch-action:none;background:#1a1f1f;`;
  wrap.appendChild(canvas);

  const hint = document.createElement("div");
  hint.textContent = "adjust z for depth  ·  shift-drag or wheel";
  hint.style.cssText =
    "font-size:10px;color:rgba(255,255,255,0.4);margin-top:8px;margin-bottom:0;user-select:none;text-align:center;";
  wrap.appendChild(hint);

  const widget = node.addDOMWidget("lc_light_stage", "LC_LIGHT_STAGE", wrap, {
    getMinHeight: () => STAGE_CSS + PAD + 18, // stage + gap + hint
    hideOnZoom: false,
  });
  // Don’t serialize DOM chrome
  widget.serializeValue = () => undefined;

  let dragging = null; // "1" | "2" | null
  let lastY = 0;
  let shiftZ = false;

  function stageGeom() {
    // Drawing space in CSS pixels (canvas is 2x)
    return { size: STAGE_CSS, margin: MARGIN };
  }

  function lightToPx(x, y) {
    const { size, margin } = stageGeom();
    const usable = size - 2 * margin;
    const u = (Number(x) + 1) * 0.5;
    const v = (1 - Number(y)) * 0.5;
    return {
      px: margin + u * usable,
      py: margin + v * usable,
    };
  }

  function pxToLight(px, py) {
    const { size, margin } = stageGeom();
    const usable = Math.max(1, size - 2 * margin);
    const u = clamp((px - margin) / usable, 0, 1);
    const v = clamp((py - margin) / usable, 0, 1);
    return {
      x: Math.round((u * 2 - 1) * 20) / 20,
      y: Math.round((1 - v * 2) * 20) / 20,
    };
  }

  function eventToLocal(ev) {
    const rect = canvas.getBoundingClientRect();
    const scaleX = STAGE_CSS / Math.max(1, rect.width);
    const scaleY = STAGE_CSS / Math.max(1, rect.height);
    return {
      x: (ev.clientX - rect.left) * scaleX,
      y: (ev.clientY - rect.top) * scaleY,
    };
  }

  function hitTest(lx, ly) {
    const enable2 = !!wval(node, "enable_light_2", false);
    const items = [];
    const p1 = lightToPx(wval(node, "light1_x", 0), wval(node, "light1_y", -0.85));
    items.push({ id: "1", ...p1, r: radiusForZ(wval(node, "light1_z", 0.9), HANDLE_HIT) + 6 });
    if (enable2) {
      const p2 = lightToPx(wval(node, "light2_x", 0.55), wval(node, "light2_y", 0.15));
      items.push({ id: "2", ...p2, r: radiusForZ(wval(node, "light2_z", 0.45), HANDLE_HIT) + 6 });
    }
    let best = null;
    let bestD = Infinity;
    for (const c of items) {
      const d = Math.hypot(lx - c.px, ly - c.py);
      if (d <= c.r && d < bestD) {
        bestD = d;
        best = c.id;
      }
    }
    return best;
  }

  function setXY(which, lx, ly) {
    const { x, y } = pxToLight(lx, ly);
    if (which === "1") {
      setWval(node, "light1_x", x);
      setWval(node, "light1_y", y);
    } else {
      setWval(node, "light2_x", x);
      setWval(node, "light2_y", y);
    }
  }

  function setZ(which, z) {
    z = Math.round(clamp(z, 0, 1) * 20) / 20;
    setWval(node, which === "1" ? "light1_z" : "light2_z", z);
  }

  function getZ(which) {
    return Number(wval(node, which === "1" ? "light1_z" : "light2_z", 0.7));
  }

  function redraw() {
    const ctx = canvas.getContext("2d");
    const W = canvas.width;
    const H = canvas.height;
    const s = W / STAGE_CSS; // 2
    ctx.setTransform(s, 0, 0, s, 0, 0);
    const { size, margin } = stageGeom();

    ctx.clearRect(0, 0, size, size);
    ctx.fillStyle = "#1a1f1f";
    ctx.fillRect(0, 0, size, size);
    ctx.strokeStyle = "#3a4545";
    ctx.lineWidth = 1;
    ctx.strokeRect(0.5, 0.5, size - 1, size - 1);

    // crosshair
    ctx.strokeStyle = "rgba(255,255,255,0.12)";
    ctx.beginPath();
    ctx.moveTo(margin, size / 2);
    ctx.lineTo(size - margin, size / 2);
    ctx.moveTo(size / 2, margin);
    ctx.lineTo(size / 2, size - margin);
    ctx.stroke();
    ctx.strokeStyle = "rgba(255,255,255,0.06)";
    ctx.strokeRect(margin, margin, size - 2 * margin, size - 2 * margin);

    const drawHandle = (x, y, z, color, label) => {
      const { px, py } = lightToPx(x, y);
      const r = radiusForZ(z, 10);
      ctx.beginPath();
      ctx.arc(px, py, r + 3, 0, Math.PI * 2);
      ctx.fillStyle = color + "33";
      ctx.fill();
      ctx.beginPath();
      ctx.arc(px, py, r, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.fill();
      ctx.strokeStyle = "rgba(0,0,0,0.45)";
      ctx.lineWidth = 1.5;
      ctx.stroke();
      ctx.fillStyle = "rgba(0,0,0,0.75)";
      ctx.font = "bold 9px sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(label, px, py);
    };

    drawHandle(
      wval(node, "light1_x", 0),
      wval(node, "light1_y", -0.85),
      wval(node, "light1_z", 0.9),
      "#F5F5F5",
      "1"
    );
    if (wval(node, "enable_light_2", false)) {
      drawHandle(
        wval(node, "light2_x", 0.55),
        wval(node, "light2_y", 0.15),
        wval(node, "light2_z", 0.45),
        "#E74C3C",
        "2"
      );
    }
  }

  // Pointer: normal drag = XY, Shift+drag vertical = Z
  canvas.addEventListener("pointerdown", (ev) => {
    const loc = eventToLocal(ev);
    const hit = hitTest(loc.x, loc.y);
    if (!hit) return;
    dragging = hit;
    lastY = loc.y;
    shiftZ = !!ev.shiftKey;
    canvas.setPointerCapture?.(ev.pointerId);
    canvas.style.cursor = shiftZ ? "ns-resize" : "grabbing";
    ev.preventDefault();
    ev.stopPropagation();
  });

  canvas.addEventListener("pointermove", (ev) => {
    if (!dragging) return;
    const loc = eventToLocal(ev);
    if (ev.shiftKey || shiftZ) {
      // Vertical drag → Z (up = toward camera / +Z)
      const dy = lastY - loc.y;
      lastY = loc.y;
      const z = getZ(dragging) + dy * 0.02;
      setZ(dragging, z);
    } else {
      setXY(dragging, loc.x, loc.y);
    }
    redraw();
    app.canvas?.setDirty?.(true, true);
    ev.preventDefault();
    ev.stopPropagation();
  });

  const endDrag = (ev) => {
    if (!dragging) return;
    dragging = null;
    shiftZ = false;
    canvas.style.cursor = "grab";
    try {
      canvas.releasePointerCapture?.(ev.pointerId);
    } catch (_) {}
  };
  canvas.addEventListener("pointerup", endDrag);
  canvas.addEventListener("pointercancel", endDrag);

  // Wheel over handle → Z (does not zoom graph when over a handle)
  canvas.addEventListener(
    "wheel",
    (ev) => {
      const loc = eventToLocal(ev);
      const hit = hitTest(loc.x, loc.y);
      if (!hit) return; // let event bubble if not on a handle
      const z = getZ(hit) - Math.sign(ev.deltaY) * 0.05;
      setZ(hit, z);
      redraw();
      app.canvas?.setDirty?.(true, true);
      ev.preventDefault();
      ev.stopPropagation();
    },
    { passive: false }
  );

  // Live redraw when XYZ / enable widgets change
  const hookNames = [
    "light1_x", "light1_y", "light1_z",
    "light2_x", "light2_y", "light2_z",
    "enable_light_2",
  ];
  for (const w of node.widgets || []) {
    if (!w || w._lcLightHooked) continue;
    if (!hookNames.includes(w.name)) continue;
    w._lcLightHooked = true;
    const prev = w.callback;
    w.callback = function (v, ...args) {
      const out = prev?.apply(this, [v, ...args]);
      redraw();
      return out;
    };
  }

  // Initial paint after layout
  requestAnimationFrame(redraw);
  setTimeout(redraw, 50);
  setTimeout(redraw, 200);

  return widget;
}


function sizeImageNode(node) {
  if (node._lcUserSized || node.properties?.lc_w) {
    const w = node.properties?.lc_w;
    const h = node.properties?.lc_h;
    if (w && h && node.size) {
      node.size[0] = w;
      node.size[1] = h;
    }
    return;
  }
  if (!node.size) node.size = [IMAGE_W, 400];
  node.size[0] = IMAGE_W;
  try {
    node.setSize?.([IMAGE_W, Math.max(node.size[1] || 400, 200)]);
  } catch (_) {}
  const enforce = () => {
    if (node._lcUserSized) return;
    if (!node.size) node.size = [IMAGE_W, 400];
    if ((node.size[0] || 0) !== IMAGE_W) {
      node.size[0] = IMAGE_W;
      try {
        node.setSize?.([IMAGE_W, node.size[1]]);
      } catch (_) {}
      node.setDirtyCanvas?.(true, true);
    }
  };
  setTimeout(enforce, 0);
  setTimeout(enforce, 50);
  setTimeout(enforce, 250);
}

function hookSizeRetention(node) {
  if (node._lcRelightSizeHooked) return;
  node._lcRelightSizeHooked = true;
  const prev = node.onResize;
  node.onResize = function () {
    const r = prev?.apply(this, arguments);
    if (!this.properties) this.properties = {};
    if (this.size) {
      this.properties.lc_w = this.size[0];
      this.properties.lc_h = this.size[1];
    }
    this._lcUserSized = true;
    return r;
  };
  const prevCfg = node.onConfigure;
  node.onConfigure = function (data) {
    const r = prevCfg?.apply(this, arguments);
    if (data?.size) {
      if (!this.properties) this.properties = {};
      this.properties.lc_w = data.size[0];
      this.properties.lc_h = data.size[1];
      this._lcUserSized = true;
    }
    return r;
  };
}

app.registerExtension({
  name: "LC123.RelightChrome",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData?.name !== TYPE) return;

    // Lock minimum width to IMAGE_W (same as lc_image_preview Skin Beauty family)
    const origCompute = nodeType.prototype.computeSize;
    nodeType.prototype.computeSize = function (out) {
      const size = origCompute?.apply(this, arguments) || [IMAGE_W, 200];
      if (!this._lcUserSized) {
        size[0] = Math.max(IMAGE_W, size[0] || IMAGE_W);
      } else if (this.properties?.lc_w) {
        size[0] = this.properties.lc_w;
        if (this.properties.lc_h) size[1] = this.properties.lc_h;
      }
      if (out) {
        out[0] = size[0];
        out[1] = size[1];
        return out;
      }
      return size;
    };

    const onCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const r = onCreated?.apply(this, arguments);
      try {
        this.color = COLOR;
        this.bgcolor = COLOR;
      } catch (_) {}
      hookSizeRetention(this);
      sizeImageNode(this);
      queueMicrotask(() => {
        installStage(this);
        sizeImageNode(this);
      });
      return r;
    };
  },
  nodeCreated(node) {
    if ((node.comfyClass || node.type) !== TYPE) return;
    try {
      node.color = COLOR;
      node.bgcolor = COLOR;
    } catch (_) {}
    hookSizeRetention(node);
    sizeImageNode(node);
    queueMicrotask(() => {
      installStage(node);
      sizeImageNode(node);
    });
  },
});
