/**
 * Align LC Pipe (in/edit) input socket labels with LC Pipe Out output names.
 */
import { app } from "../../scripts/app.js";

const LABEL = {
  model_1: "Model 1",
  clip_1: "Clip 1",
  vae_1: "VAE 1",
  model_2: "Model 2",
  clip_2: "Clip 2",
  vae_2: "VAE 2",
  image: "Image",
  mask: "Mask",
  width: "Width",
  height: "Height",
  latent: "Latent",
  batch: "Batch",
  positive_prompt: "Positive prompt",
  positive: "Positive conditioning",
  negative_prompt: "Negative prompt",
  negative: "Negative conditioning",
  seed: "Seed",
  detailer_steps: "detailer_steps",
  total_steps: "total_steps",
  cfg_1: "cfg_1",
  denoise: "denoise",
  step_swap: "step_swap",
  cfg_2: "cfg_2",
  sampler_name: "sampler_name",
  scheduler: "scheduler",
  pipe: "pipe",
};

function applyLabels(node) {
  if (!node) return;
  for (const inp of node.inputs || []) {
    if (inp?.name && LABEL[inp.name]) {
      inp.label = LABEL[inp.name];
      inp.localized_name = LABEL[inp.name];
    }
  }
  for (const out of node.outputs || []) {
    if (out?.name && LABEL[out.name] && out.name.includes("_")) {
      // outputs already use pretty RETURN_NAMES; skip if already pretty
    }
  }
  node.setDirtyCanvas?.(true, true);
}

const NODES = new Set(["LCPipeEdit", "LCPipeOut", "LCDetailPipeOut", "LCPipeIn"]);

app.registerExtension({
  name: "LC123.PipeLabels",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (!NODES.has(nodeData?.name || "")) return;
    const onCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const r = onCreated?.apply(this, arguments);
      applyLabels(this);
      setTimeout(() => applyLabels(this), 0);
      return r;
    };
    const onConfigure = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function () {
      const r = onConfigure?.apply(this, arguments);
      setTimeout(() => applyLabels(this), 0);
      return r;
    };
  },
});
