/**
 * RTX support: when nvidia-vfx (NVIDIA's VFX SDK, about 800 MB) is missing, LC RTX Super Resolution shows a button with
 * the install command, and picking nvidia_rtx_vsr in an LC resize node offers the same. Nothing installs from inside
 * ComfyUI (the Comfy Registry does not allow runtime pip installs): the command is copied for a terminal, then a restart.
 */
import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const SIZE = "about 800 MB";
let status = null;

async function getStatus(fresh = false) {
  if (status && !fresh) return status;
  try {
    status = await (await api.fetchApi("/lc123/rtx/status")).json();
  } catch (_) {
    status = { installed: false, works: false, command: "python -m pip install nvidia-vfx" };
  }
  return status;
}

const toast = (severity, detail, life = 6000) => app.extensionManager?.toast?.add?.({ severity, summary: "RTX support", detail, life });

async function showInstall() {
  const st = await getStatus(true);
  if (st.works) return true;
  if (st.installed) {
    toast("warn", `nvidia-vfx ${st.version} is installed but didn't load. Restart ComfyUI; it also needs an NVIDIA RTX card.`, 9000);
    return false;
  }
  let copied = false;
  try {
    await navigator.clipboard.writeText(st.command);
    copied = true;
  } catch (_) {}
  const msg = `RTX Video Super Resolution needs NVIDIA's nvidia-vfx package (${SIZE}). Run this in a terminal, then restart ComfyUI:`
    + `\n\n${st.command}` + (copied ? "\n\n(Copied to your clipboard.)" : "");
  if (app.extensionManager?.dialog?.confirm) await app.extensionManager.dialog.confirm({ title: "Install RTX support", message: msg });
  else window.alert(msg);
  return false;
}

app.registerExtension({
  name: "LC123.RTXSupport",
  async nodeCreated(node) {
    // any LC node with an nvidia_rtx_vsr choice: show the install command when it's picked and RTX can't run
    for (const w of node.widgets || []) {
      if (!Array.isArray(w.options?.values) || !w.options.values.includes("nvidia_rtx_vsr")) continue;
      const prev = w.callback;
      w.callback = function (v, ...rest) {
        const r = prev?.apply(this, [v, ...rest]);
        if (v === "nvidia_rtx_vsr") getStatus().then((s) => { if (!s.works) showInstall(); });
        return r;
      };
    }
    if ((node.comfyClass || node.constructor?.comfyClass) !== "LCRTXSuperResolution") return;
    const s = await getStatus();
    if (s.works || node._lcRtxBtn) return;
    node._lcRtxBtn = node.addWidget("button", "", null, () => showInstall());
    node._lcRtxBtn.serialize = false;
    node._lcRtxBtn.name = node._lcRtxBtn.label = s.installed ? "⚠️ RTX support didn't load: restart ComfyUI"
      : `📋 RTX support: copy the install command (nvidia-vfx, ${SIZE})`;
    node.setSize?.([Math.max(node.size[0], 320), node.computeSize()[1]]);
  },
});
