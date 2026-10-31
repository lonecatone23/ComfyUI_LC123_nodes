/**
 * LC Continue: carry on a run that a hold stopped (LC Stop, LC Weighted Prompt on Block: always), with the seeds
 * it used.
 *
 * ComfyUI moves every randomize / increment seed on each queue, so the run after a stop used to start over: a new
 * seed is a changed input, and everything below it ran again. A Continue run sends the last run's values for every
 * seed a control moved (anything you changed yourself goes through), and marks the run so randomizing LC Seeds hand
 * back their last number (lc_seed.py). The server then takes everything above the hold from its cache.
 *
 * A hold reports itself with ui `lc_hold` (a fresh stamp per stop; a cached replay of the same stamp is ignored).
 * After one, the next queue is a Continue: Run, or LC Stop's play button. One Continue, then runs are normal again.
 */
import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const CONTROLS = new Set(["control_after_generate", "control_before_generate"]);

let last = null; // the last queued prompt (API format)
let pending = false; // a hold stopped the last run
let force = false;
const seen = new Set(); // hold stamps already counted

// A plain copy of a prompt. Not structuredClone: other packs and some frontends leave proxies or class objects in the
// prompt, structuredClone throws on those ("could not be cloned"), and that stopped every queue (issue #19).
function copy(o) {
  try {
    return JSON.parse(JSON.stringify(o));
  } catch (_) {
    return null;
  }
}

/** The widget's own randomize / increment control (or a Primitive node's, when one feeds the input), not on fixed. */
function moved(node, name) {
  const ws = node?.widgets || [];
  const i = ws.findIndex((w) => w.name === name);
  const w = ws[i];
  const ctl = w ? (w.linkedWidgets || []).find((x) => CONTROLS.has(x.name)) || (CONTROLS.has(ws[i + 1]?.name) ? ws[i + 1] : null) : null;
  if (ctl) return ctl.value !== "fixed";
  const link = node?.inputs?.find((x) => x.name === name)?.link;
  const src = link != null ? node.graph?.getNodeById(node.graph.links?.[link]?.origin_id) : null;
  if (src?.type === "PrimitiveNode" && src !== node) return moved(src, src.widgets?.[0]?.name);
  return false;
}

function continued(output) {
  const out = copy(output);
  if (!out || !last) return out || output;
  for (const [id, n] of Object.entries(out)) {
    const prev = last[id];
    if (!prev || prev.class_type !== n.class_type) continue;
    const node = app.graph?.getNodeById(Number(id)) ?? app.graph?.getNodeById(id);
    if (!node) continue;
    for (const [k, v] of Object.entries(n.inputs || {})) {
      if (Array.isArray(v) || !(k in (prev.inputs || {})) || prev.inputs[k] === v) continue;
      if (moved(node, k)) n.inputs[k] = prev.inputs[k];
    }
  }
  return out;
}

/** Continue the stopped run now (LC Stop's play button). */
export function lcContinue() {
  force = true;
  return app.queuePrompt(0);
}

app.registerExtension({
  name: "LC123.Continue",
  setup() {
    if (api.__lcContinue) return;
    api.__lcContinue = true;
    const queuePrompt = api.queuePrompt;
    api.queuePrompt = async function (number, data, ...rest) {
      // Continue never blocks a queue: if anything here fails, the prompt goes through as it came
      try {
        if ((pending || force) && data?.output) {
          const wf = data.workflow;
          data = {
            ...data,
            output: continued(data.output),
            workflow: wf ? { ...wf, extra: { ...(wf.extra || {}), lc_continue: true } } : wf,
          };
          console.log("[LC Continue] continuing the stopped run with its seeds");
        }
        if (data?.output) last = copy(data.output);
      } catch (e) {
        console.warn("[LC Continue] skipped:", e);
      }
      pending = false;
      force = false;
      return queuePrompt.call(this, number, data, ...rest);
    };
    api.addEventListener("executed", (e) => {
      const stamp = e.detail?.output?.lc_hold?.[0];
      if (stamp == null || seen.has(stamp)) return;
      seen.add(stamp);
      pending = true;
    });
  },
});
