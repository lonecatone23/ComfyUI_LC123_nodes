/**
 * LC preview tooltip: resting the pointer on an LC on-node preview picture shows how to use it, after the same delay
 * and with the same look as ComfyUI's own tooltips (LiteGraph.Node.TooltipDelay, off with Comfy.EnableTooltips).
 * Classic: a node opts in with node._lcPreviewHit(localPos) -> true over its picture. Nodes 2.0: an LC node's picture
 * that has a before image. Shipped in LC123 and MaskMaker; the first one loaded does the work.
 */
import { app } from "../../scripts/app.js";

const TEXT = "Click an area to enlarge and compare. Double-click to close.";

if (!window.__lcPreviewTip) {
  window.__lcPreviewTip = true;
  const setting = (id, d) => {
    try {
      const v = app.extensionManager?.setting?.get?.(id);
      return v === undefined || v === null ? d : v;
    } catch (_) {
      return d;
    }
  };
  let tip = null;
  let timer = 0;
  const hide = () => {
    clearTimeout(timer);
    if (tip) tip.style.display = "none";
  };
  const show = (x, y) => {
    if (!tip) {
      tip = document.createElement("div");
      // the core tooltip's look (its own class is scoped to the frontend's component)
      tip.style.cssText =
        "position:fixed;pointer-events:none;background:var(--comfy-input-bg);color:var(--input-text);white-space:pre-wrap;" +
        "z-index:99999;border-radius:5px;max-width:30vw;padding:4px 8px;transform:translate(5px,calc(-100% - 5px));" +
        "box-shadow:0 0 5px #0006;font-size:14px;";
      tip.textContent = TEXT;
      document.body.appendChild(tip);
    }
    // below and right of the pointer so it doesn't cover what you point at (LC Settings > Tooltips), above near the bottom
    const below = setting("LC123.Tooltips.Below", true) !== false;
    tip.style.transform = below ? "translate(16px,26px)" : "translate(5px,calc(-100% - 5px))";
    tip.style.left = `${x}px`;
    tip.style.top = `${y}px`;
    tip.style.display = "block";
    const r = tip.getBoundingClientRect();
    if (r.right > window.innerWidth) tip.style.left = `${x - r.width - 10}px`;
    if (below && r.bottom > window.innerHeight - 4) tip.style.transform = "translate(16px,calc(-100% - 12px))";
    if (!below && r.top < 0) tip.style.top = `${y + r.height + 10}px`;
  };
  const vue = () => setting("Comfy.VueNodes.Enabled", false) === true;

  const overClassic = () => {
    const c = app.canvas;
    const node = c?.node_over;
    if (!node || node.flags?.collapsed || typeof node._lcPreviewHit !== "function") return false;
    const [gx, gy] = c.graph_mouse;
    return node._lcPreviewHit([gx - node.pos[0], gy - node.pos[1]]);
  };
  const overVue = (e) => {
    const nodeEl = e.target?.closest?.("[data-node-id]");
    if (!nodeEl || nodeEl.querySelector("canvas[style*='crosshair']")) return false; // zoomed: its label says it
    const key = nodeEl.getAttribute("data-node-id");
    if (!(key in (window.LC123VueBefore || {}))) return false;
    const node = app.graph?.getNodeById?.(Number(key)) || app.graph?.getNodeById?.(key);
    if (!/^LC/.test(String(node?.comfyClass || node?.type || ""))) return false;
    return [...nodeEl.querySelectorAll("img")].some((i) => {
      const r = i.getBoundingClientRect();
      return i.naturalWidth && e.clientX >= r.left && e.clientX <= r.right && e.clientY >= r.top && e.clientY <= r.bottom;
    });
  };

  window.addEventListener("mousemove", (e) => {
    hide();
    if (setting("Comfy.EnableTooltips", true) === false) return;
    const x = e.clientX, y = e.clientY;
    timer = window.setTimeout(() => {
      try {
        if (vue() ? overVue(e) : e.target?.nodeName === "CANVAS" && overClassic()) show(x, y);
      } catch (_) {}
    }, Number(setting("LiteGraph.Node.TooltipDelay", 500)) || 500);
  });
  window.addEventListener("click", hide, true);
  window.addEventListener("wheel", hide, true);
}
