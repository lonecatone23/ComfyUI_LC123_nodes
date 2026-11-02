/**
 * LC first-use downloads: a gentle warning toast when a node starts fetching its model. Every LC pack ships this file;
 * the first one loaded listens, the others step aside, so a download shows one toast.
 */
import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

if (!window.__lcFirstDownload) {
  window.__lcFirstDownload = true;
  api.addEventListener("lc.download", (e) => {
    const d = e.detail || {};
    const size = d.size ? ` (${d.size})` : "";
    try {
      app.extensionManager?.toast?.add({
        severity: "warn",
        summary: "LC",
        detail: `Downloading ${d.label || "a model"}${size} for first use. This may take several minutes. Press Stop to cancel.`,
        life: 10000,
      });
    } catch (_e) {}
  });
}
