/**
 * LC tooltips below the cursor: ComfyUI draws a widget's tooltip just above and right of the pointer, so it covers the
 * widget row you are on and grows upward over it. This moves it below and right of the pointer, clear of that row, so
 * it can grow downward; near the bottom of the window it flips above. Classic canvas tooltips (.node-tooltip) and the
 * LC preview tooltip. Setting: LC Settings ⚙️ > Tooltips > Below the cursor (on by default).
 */
import { app } from "../../scripts/app.js";

const ID = "LC123.Tooltips.Below";
const DX = 16; // right of the pointer
const DY = 26; // below the pointer: one widget row (20 px) plus a gap
const CSS = `
body.lc-tip-below .node-tooltip { transform: translate(${DX}px, ${DY}px) !important; }
body.lc-tip-below .node-tooltip.lc-tip-flip { transform: translate(${DX}px, calc(-100% - 12px)) !important; }
`;

function setting(id, d) {
  try {
    const v = app.extensionManager?.setting?.get?.(id);
    return v === undefined || v === null ? d : v;
  } catch (_) {
    return d;
  }
}

function apply(on) {
  document.body.classList.toggle("lc-tip-below", !!on);
  window.LCTooltipBelow = !!on;
}

// flip above when the tooltip would run off the bottom of the window
function watch() {
  let el = null;
  const check = () => {
    if (!el || !document.body.classList.contains("lc-tip-below")) return;
    el.classList.remove("lc-tip-flip");
    const r = el.getBoundingClientRect();
    if (r.height && r.bottom > window.innerHeight - 4) el.classList.add("lc-tip-flip");
  };
  const obs = new MutationObserver(() => requestAnimationFrame(check));
  const find = () => {
    const t = document.querySelector(".node-tooltip");
    if (t && t !== el) {
      obs.disconnect();
      el = t;
      obs.observe(el, { attributes: true, attributeFilter: ["style"], childList: true, characterData: true, subtree: true });
      check();
    }
    return !!t;
  };
  if (!find()) {
    const wait = new MutationObserver(() => find() && wait.disconnect());
    wait.observe(document.body, { childList: true, subtree: true });
  }
}

// shipped in every LC pack (LC123, MaskMaker, AV, Vision, ModelBuilder): the first one loaded does the work
if (!window.__lcTooltipBelow) {
  window.__lcTooltipBelow = true;
  const s = document.createElement("style");
  s.id = "lc-tooltip-below-css";
  s.textContent = CSS;
  document.head.appendChild(s);
  app.registerExtension({
    name: "LC123.TooltipBelow",
  settings: [
    {
      id: ID,
      category: ["LC Settings ⚙️", "Tooltips", "Below the cursor"],
      name: "Show tooltips below the cursor",
      tooltip: "Tooltips open below and right of the pointer, so they don't cover the widget you're adjusting. Off = ComfyUI's own placement (above the pointer).",
      type: "boolean",
      defaultValue: true,
      onChange: (v) => apply(v !== false),
    },
  ],
    setup() {
      apply(setting(ID, true) !== false);
      watch();
    },
  });
}
