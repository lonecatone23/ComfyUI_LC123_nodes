/**
 * LC Sampler Configure family — hide layout spacer widgets (_gap1, _gap2)
 * and keep a thin vertical gap without showing empty STRING fields.
 */
import { app } from "../../scripts/app.js";

const TYPES = new Set([
  "LCSamplerConfigure",
  "LCSamplerConfigurePipeOut",
  "LCSamplerConfigurePipe",
  "LCSamplerConfigureSimple",
  "LCSamplerConfigureSimplePipeOut",
]);

const GAP_PX = 6;

function hideGaps(node) {
  if (!node?.widgets) return;
  for (const w of node.widgets) {
    const n = (w.name || "").toString();
    if (!n.startsWith("_gap")) continue;
    w.type = "converted-widget"; // not drawn as text field
    w.computeSize = () => [0, GAP_PX];
    w.draw = function () {};
    w.serializeValue = () => "";
    try {
      w.hidden = true;
    } catch (_) {}
  }
  // Force layout refresh
  try {
    node.setDirtyCanvas?.(true, true);
  } catch (_) {}
}

app.registerExtension({
  name: "LC123.SamplerConfigureGaps",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (!TYPES.has(nodeData?.name)) return;
    const onCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const r = onCreated?.apply(this, arguments);
      hideGaps(this);
      requestAnimationFrame(() => hideGaps(this));
      return r;
    };
  },
  nodeCreated(node) {
    const t = node.comfyClass || node.type;
    if (TYPES.has(t)) hideGaps(node);
  },
});
