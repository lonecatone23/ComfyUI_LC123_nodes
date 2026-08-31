/**
 * LC Notify 🔊 — play pack sounds/ files on execute + on-node ▶ preview
 */

import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { lcApplyLaunchColor } from "./lc_color.js";

const NODE_CLASS = "LCNotify";

function soundUrl(filename) {
  let file = (filename || "").trim() || "notify.mp3";
  file = file.replace(/\\/g, "/").split("/").pop();
  return api.apiURL(`/lc123/sounds/${encodeURIComponent(file)}`);
}

function playFile(filename, volume) {
  const url = soundUrl(filename);
  const audio = new Audio(url);
  audio.volume = Math.max(0, Math.min(1, Number(volume) ?? 0.5));
  const p = audio.play();
  if (p && typeof p.catch === "function") {
    p.catch((e) => console.warn("[LC Notify] play failed", e, url));
  }
  return audio;
}

function widgetVal(node, name, fallback) {
  const w = (node.widgets || []).find((x) => x.name === name);
  return w != null ? w.value : fallback;
}

app.registerExtension({
  name: "LC123.Notify",

  async beforeRegisterNodeDef(nodeType, nodeData) {
    if ((nodeData?.name || "") !== NODE_CLASS) return;

    const origCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const r = origCreated?.apply(this, arguments);
      lcApplyLaunchColor(this, "#649632");

      if (!(this.widgets || []).some((w) => w.name === "▶ preview")) {
        this.addWidget("button", "▶ preview", null, () => {
          const file = widgetVal(this, "file", "notify.mp3");
          const volume = widgetVal(this, "volume", 0.5);
          playFile(file, volume);
        });
      }

      return r;
    };

    const origExecuted = nodeType.prototype.onExecuted;
    nodeType.prototype.onExecuted = async function (message) {
      origExecuted?.apply(this, arguments);

      const mode = message?.mode?.[0] ?? widgetVal(this, "mode", "always");
      const volume = message?.volume?.[0] ?? widgetVal(this, "volume", 0.5);
      const file = message?.file?.[0] ?? widgetVal(this, "file", "notify.mp3");

      if (mode === "never") return;

      if (mode === "on empty queue") {
        if (app.ui?.lastQueueSize !== 0) {
          await new Promise((r) => setTimeout(r, 500));
        }
        if (app.ui?.lastQueueSize !== 0) {
          return;
        }
      }

      playFile(file, volume);
    };
  },
});

console.log("[LC123.Notify] loaded");
