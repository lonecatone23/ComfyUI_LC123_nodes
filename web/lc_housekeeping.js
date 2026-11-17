import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

// LC Settings ⚙️ > Housekeeping > Delete nuisance folders: once the node list has loaded (the other packs have made
// their folders by then), the empty folders other packs make in output / input are removed. A toast says which ones and
// which pack made them. Folders with files in them, LC folders and ComfyUI's own are never touched.
const ID = "LC123.Housekeeping.NuisanceFolders";

async function clean() {
  try {
    const res = await api.fetchApi("/lc123/nuisance_folders", { method: "POST" });
    const r = await res.json();
    if (r.removed?.length) {
      app.extensionManager?.toast?.add({
        severity: "info",
        summary: "LC Housekeeping 🧹",
        detail: `Removed ${r.removed.length} empty folder${r.removed.length > 1 ? "s" : ""} other packs made: ${r.removed.join(", ")}`,
        life: 8000,
      });
    }
  } catch (e) {
    console.warn("[LC123] nuisance folders:", e);
  }
}

app.registerExtension({
  name: "LC123.Housekeeping",
  settings: [
    {
      id: ID,
      name: "Delete nuisance folders",
      type: "boolean",
      defaultValue: false,
      tooltip: "Deletes nuisance folders created at startup (if empty).",
      category: ["LC Settings ⚙️", "Housekeeping", "Delete nuisance folders"],
      onChange: (on, old) => {
        if (on && old === false) clean();
      },
    },
  ],
  async setup() {
    if (app.ui.settings.getSettingValue(ID, false)) clean();
  },
});
