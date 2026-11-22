/**
 * Launch color for LC nodes: apply pack default only if the node still has
 * Comfy stock / empty color. Never overwrite a user-chosen or workflow-saved color.
 *
 * Comfy's own palette colors (green #232, blue #223, black #222/#000) look like "stock" to the
 * check below, and several nodes repaint after the saved workflow has been applied. So every node
 * that arrives with a saved color (load, paste, undo) is marked, and marked nodes are never repainted.
 *
 * "No color" clears the color, which a workflow would not save, so the pack default came back on
 * reload. An LC node with no color now keeps a lc_no_color property, which loads back as no color.
 *
 * The same file ships in every LC pack; the hooks install once however many packs are loaded.
 */
const NO_COLOR = "lc_no_color";
const isLC = (node) => /ComfyUI_LC/i.test(String(node?.constructor?.nodeData?.python_module || ""));

(function installHooks() {
  const LGN = globalThis.LiteGraph?.LGraphNode || globalThis.LGraphNode;
  if (!LGN || LGN.prototype.__lcColorHooks) return;
  LGN.prototype.__lcColorHooks = true;

  const configure = LGN.prototype.configure;
  LGN.prototype.configure = function (info) {
    let none = false;
    try {
      none = !!info?.properties?.[NO_COLOR] && !info.color && !info.bgcolor;
      if (info && (info.color || info.bgcolor || none)) this._lcSavedColor = true;
    } catch (_) {}
    const r = configure.apply(this, arguments);
    try {
      if (none) {
        this.color = undefined;
        this.bgcolor = undefined;
      } else if (this.properties && NO_COLOR in this.properties) {
        delete this.properties[NO_COLOR];
      }
    } catch (_) {}
    return r;
  };

  // a workflow never saves a missing color, so "No color" on an LC node is kept as a property
  const setColorOption = LGN.prototype.setColorOption;
  if (setColorOption) {
    LGN.prototype.setColorOption = function (option) {
      const r = setColorOption.apply(this, arguments);
      try {
        if (!this.properties) this.properties = {};
        if (!option && isLC(this)) this.properties[NO_COLOR] = true;
        else delete this.properties[NO_COLOR];
      } catch (_) {}
      return r;
    };
  }
})();

export function lcHasSavedColor(node) {
  return !!node && !!node._lcSavedColor;
}

const STOCK = new Set([
  "",
  "#333",
  "#333333",
  "#353535",
  "#232",
  "#223",
  "#222",
  "#222222",
  "#2a2a2a",
  "#1a1a1a",
  "#444",
  "#444444",
  "#3d3d3d",
  "#0f0f0f",
  "#111",
  "#111111",
  "#000",
  "#000000",
]);

function norm(c) {
  return String(c ?? "").trim().toLowerCase();
}

export function lcColorIsStock(c) {
  const n = norm(c);
  if (!n || n === "undefined" || n === "null") return true;
  return STOCK.has(n);
}

export function lcApplyLaunchColor(node, color, bgcolor) {
  if (!node) return;
  if (lcHasSavedColor(node)) return;
  if (!lcColorIsStock(node.color)) return;
  try {
    node.color = color;
    node.bgcolor = bgcolor || color;
  } catch (_) {}
}

export function lcRestoreSerializedColor(node, data) {
  if (!node || !data) return false;
  if ("color" in data || "bgcolor" in data) {
    try {
      node.color = data.color;
      node.bgcolor = data.bgcolor ?? data.color;
    } catch (_) {}
    return true;
  }
  return false;
}
