// System & Model Optimization Report: what this machine has and what actually works on it (small live GPU tests), in the same window
// style as the Comfy Optimization Report. The server saves the result as user/LC123/system_profile.json, which the
// LC Optimizer node reads to pick the best settings per model. Nothing is changed.
import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { addCsvButton } from "./lc_report_csv.js";

const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[ch]);
const ICON = { 3: "⚠️", 2: "✅", 1: "💡", 0: "ℹ️", "-1": "➖" };
const KINDS = [
  ["gpu", "Graphics card", "#60a5fa"],
  ["memory", "Memory and storage", "#c4b5fd"],
  ["speed", "Speed-ups (tested live on this machine)", "#86efac"],
  ["packs", "Optimizer packs", "#fbbf24"],
  ["setup", "ComfyUI setup", "#9aa3ad"],
];

// ---------------------------------------------------------------- last run (one run kept, in this browser)
const LAST_KEY = "lc123.syscheck.lastRun";
function loadLast() {
  try {
    return JSON.parse(localStorage.getItem(LAST_KEY) || "null");
  } catch (_) {
    return null;
  }
}
function saveLast(v) {
  try {
    localStorage.setItem(LAST_KEY, JSON.stringify(v));
  } catch (_) {}
}

// the numbers worth comparing between runs
function snapshot(p) {
  const g = p.gpus?.[0] || {};
  const t = p.tests || {};
  return {
    nums: {
      "RAM to GPU (GB/s)": t.transfer?.to_gpu_gbs,
      "GPU to RAM (GB/s)": t.transfer?.to_ram_gbs,
      "Attention, standard (ms)": t.attention_sdpa?.ms,
      "Attention, Sage (ms)": t.sageattention?.ms,
      "fp16 math (TFLOPS)": t.matmul_fp16?.tflops,
      "fp8 math (TFLOPS)": t.matmul_fp8?.tflops,
    },
    facts: {
      GPU: g.name,
      Driver: g.driver,
      PCIe: g.pcie_gen ? `Gen${g.pcie_gen} x${g.pcie_width}` : "",
      "System RAM": p.machine?.ram_total_gb ? p.machine.ram_total_gb + " GB" : "",
      "Page file": p.machine?.swap_managed ? "managed by Windows" : p.machine?.swap_total_gb != null ? p.machine.swap_total_gb + " GB" : "", // a managed one changes size on its own
      PyTorch: p.software?.torch,
      SageAttention: p.software?.sageattention || "",
      ComfyUI: p.comfy?.version || "",
    },
    open: (p.findings || []).filter((f) => f.level === 3 || f.level === 1).map((f) => ({ title: f.title, level: f.level })),
  };
}
const LOWER_BETTER = /\(ms\)/;

function sinceLast(prev, now, h, lines) {
  h.push(`<div style="font-weight:600;font-size:14px;margin:6px 0">Since the last run <span style="font-weight:400;color:#9aa3ad;font-size:12px">(${esc(prev.when)})</span></div>`);
  lines.push("", `Since the last run (${prev.when}):`);
  h.push(`<div style="color:#9aa3ad;font-size:12px;margin-bottom:4px">Grey = under 10%, which is normal run-to-run noise. Green = better, red = worse.</div>`);
  h.push(`<table style="width:100%;border-collapse:collapse;margin-bottom:8px;font-size:12px"><tr style="color:#9aa3ad;text-align:left"><th>Measured</th><th>Last run → this run</th></tr>`);
  const bigDrop = [];
  for (const [k, b] of Object.entries(now.nums)) {
    const a = prev.snap.nums?.[k];
    if (a == null || b == null) continue;
    const pct = a ? Math.round(((b - a) / a) * 100) : 0;
    const good = LOWER_BETTER.test(k) ? b < a : b > a;
    const col = Math.abs(pct) < 10 ? "#9aa3ad" : good ? "#86efac" : "#f87171";
    h.push(`<tr><td>${esc(k)}</td><td style="color:${col}">${a} → ${b} (${pct > 0 ? "+" : ""}${pct}%)</td></tr>`);
    lines.push(`${k}: ${a} → ${b} (${pct > 0 ? "+" : ""}${pct}%)`);
    if (!good && Math.abs(pct) >= 40) bigDrop.push(k);
  }
  h.push(`</table>`);
  // a drop this big is almost never the card: something else was using the GPU while the tests ran
  if (bigDrop.length) {
    const msg = `⚠️ ${bigDrop.join(", ")} dropped 40% or more. That usually means something else was using the graphics card during the test (a generation, a game, a browser video). Run the report again with ComfyUI idle before trusting these numbers.`;
    h.push(`<div style="margin:2px 0 6px 10px;color:#fbbf24">${esc(msg)}</div>`);
    lines.push(msg);
  }
  const changed = Object.entries(now.facts).filter(([k, v]) => (prev.snap.facts?.[k] ?? "") !== (v ?? ""));
  for (const [k, v] of changed) {
    h.push(`<div style="margin:2px 0 2px 10px;color:#fbbf24">Changed: <b>${esc(k)}</b>: ${esc(prev.snap.facts?.[k] || "none")} → ${esc(v || "none")}</div>`);
    lines.push(`Changed: ${k}: ${prev.snap.facts?.[k] || "none"} → ${v || "none"}`);
  }
  const nowT = new Set(now.open.map((f) => f.title));
  const prevT = new Set((prev.snap.open || []).map((f) => f.title));
  const fixed = (prev.snap.open || []).filter((f) => !nowT.has(f.title));
  const fresh = now.open.filter((f) => !prevT.has(f.title));
  for (const f of fixed) h.push(`<div style="margin:2px 0 2px 10px;color:#86efac">✔ done: ${esc(f.title)}</div>`);
  for (const f of fresh) h.push(`<div style="margin:2px 0 2px 10px;color:#fbbf24">${ICON[f.level]} new: ${esc(f.title)}</div>`);
  if (fixed.length) lines.push(`Fixed: ${fixed.map((f) => f.title).join(" | ")}`);
  if (fresh.length) lines.push(`New: ${fresh.map((f) => f.title).join(" | ")}`);
  if (!changed.length && !fixed.length && !fresh.length) h.push(`<div style="color:#9aa3ad;margin:4px 0">Same machine and same open items as last time.</div>`);
}

// Qwen3-VL picks for LC Vision: exact arithmetic from file sizes and this card's VRAM, not a benchmark
const TIER_TIP = {
  Quality: "the best answers this card can hold",
  Optimal: "the best balance of answer quality, speed and room to spare",
  Fast: "quicker answers, a little less detail",
};
function lcVision(v, h, lines) {
  if (!v || v.error || !v.tiers) return;
  h.push(`<div style="font-weight:600;font-size:14px;margin:6px 0">LC Vision model suggestion</div>`);
  lines.push("", "LC Vision model suggestion:");
  h.push(`<table style="width:100%;border-collapse:collapse;margin-bottom:4px;font-size:12px"><tr style="color:#9aa3ad;text-align:left"><th></th><th>Model</th><th>Context (n_ctx)</th><th>VRAM it takes</th><th>On this machine</th></tr>`);
  for (const tier of ["Quality", "Optimal", "Fast"]) {
    const t = v.tiers[tier];
    if (!t) continue;
    const name = `Qwen3-VL-${t.size} ${t.quant}`;
    const col = tier === "Optimal" ? "#86efac" : "#dfe3e8";
    h.push(
      `<tr style="border-top:1px solid #2d333b"><td style="color:${col};font-weight:600;padding:3px 10px 3px 0" title="${esc(TIER_TIP[tier])}">${tier}</td>` +
        `<td style="color:${col}">${esc(name)}${t.cpu ? " (partly on the CPU)" : ""}</td><td>${t.ctx}</td><td>~${t.need_gb} GB</td>` +
        `<td>${t.on_disk ? "✅ you have it" : `<span style="color:#9aa3ad">not downloaded</span>`}</td></tr>`
    );
    lines.push(`${tier}: ${name}, context ${t.ctx}, ~${t.need_gb} GB VRAM${t.cpu ? " (partly on the CPU)" : ""}${t.on_disk ? " (you have it)" : ""}`);
  }
  h.push(`</table>`);
  if (v.chat) {
    const c = v.chat;
    const text = c.lite || c.cpu ? c.note
      : `Vision Assistant chat: Qwen3-VL-${c.size} ${c.quant} at ${c.ctx} context, ~${c.need_gb} GB, only while you chat (it unloads a minute after the last answer, or when you queue).${c.tours ? " It can build guided tours." : " Building guided tours needs a 20 GB+ card; saved tours still play."} Auto picks this.`;
    h.push(`<div style="font-size:12px;margin:6px 0 2px"><b>💬 ${esc(text)}</b></div>`);
    lines.push(text);
  }
  const notes = [v.note, "Set the Loader's n_ctx to the context shown: LC Vision's default (32768) reserves about 4.5 GB on its own.", v.assumes].filter(Boolean);
  for (const n of notes) h.push(`<div style="color:#9aa3ad;font-size:12px;margin:2px 0">${esc(n)}</div>`);
  lines.push(...notes);
  h.push(`<div style="margin-bottom:12px"></div>`);
}

// Shopping guide: model independent, for picking custom models (finetunes, merges) that no profile covers
function shopping(sg, h, lines) {
  if (!sg || sg.error) return;
  h.push(`<div style="font-weight:600;font-size:14px;margin:6px 0">When picking a model (includes custom models)</div>`);
  h.push(`<div style="color:#9aa3ad;font-size:12px;margin-bottom:6px">For this machine: ${esc(sg.machine)}. Based on 9 models measured on an RTX 5090 and an 8 GB RTX 5060 Laptop.</div>`);
  lines.push("", `When picking a model, includes custom models (${sg.machine}):`);
  const block = (title, col, items, icon) => {
    h.push(`<div style="margin:8px 0 4px;color:${col};font-weight:600">${title}</div>`);
    lines.push(title + ":");
    for (const x of items) {
      h.push(`<div style="margin:3px 0;padding:5px 10px;background:#252a31;border-left:3px solid ${col};border-radius:4px">${icon} <b>${esc(x.what)}</b>: ${esc(x.why)}</div>`);
      lines.push(`${icon} ${x.what}: ${x.why}`);
    }
  };
  // what to pick for each goal on this machine, best first
  const GOAL_COL = { Quality: "#c4b5fd", Optimal: "#86efac", Fast: "#fbbf24" };
  h.push(`<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:6px 0">`);
  for (const goal of ["Quality", "Optimal", "Fast"]) {
    const items = (sg.by_goal || {})[goal] || [];
    h.push(`<div style="padding:6px 10px;background:#252a31;border-top:3px solid ${GOAL_COL[goal]};border-radius:4px"><div style="color:${GOAL_COL[goal]};font-weight:600;margin-bottom:3px">${goal}</div>` +
      items.map((x, i) => `<div style="margin:2px 0">${i + 1}. <b>${esc(x.what)}</b> <span style="color:#9aa3ad">${esc(x.why)}</span></div>`).join("") + `</div>`);
    lines.push(`${goal}: ` + items.map((x, i) => `${i + 1}. ${x.what} (${x.why})`).join("  "));
  }
  h.push(`</div>`);
  if (sg.tip) {
    h.push(`<div style="color:#9aa3ad;font-size:12px;margin:2px 0 4px">💡 ${esc(sg.tip)}</div>`);
    lines.push(`💡 ${sg.tip}`);
  }
  h.push(`<div style="margin:8px 0 4px;color:#60a5fa;font-weight:600">Size guide (the model file)</div>`);
  lines.push("Size guide:");
  for (const t of sg.size?.text || []) {
    h.push(`<div style="margin:2px 0 2px 10px">📏 ${esc(t)}</div>`);
    lines.push(`📏 ${t}`);
  }
  block("Avoid", "#f87171", sg.avoid, "🚫");
  h.push(`<div style="margin-bottom:14px"></div>`);
}

// Model recommendations: pick a model, a goal and a size; the server combines the saved check with the model's
// measured profile (lc_model_calc.recommend). Recommends only: nothing in the workflow is changed.
const REC_KEY = "lc123.syscheck.rec";
const QUALITY_WORDS = (q) => (q <= 0.005 ? "identical" : q <= 0.05 ? "near identical" : q <= 0.1 ? "small differences" : q <= 0.2 ? "visible differences" : "different picture");
function recShell() {
  return `<div class="lc-sys-rec" style="margin:4px 0 14px">
    <div style="font-weight:600;font-size:14px;margin:6px 0">Model recommendations</div>
    <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:6px">
      <select class="lc-rec-model p-inputtext" style="padding:3px 6px;background:#252a31;color:#dfe3e8;border:1px solid #3a4048;border-radius:4px"></select>
      <span class="lc-rec-goals" style="display:inline-flex;gap:4px">${["Quality", "Optimal", "Fast"].map((g) => `<button type="button" data-goal="${g}" class="p-button p-button-sm p-button-secondary">${g}</button>`).join("")}</span>
      <select class="lc-rec-size" style="padding:3px 6px;background:#252a31;color:#dfe3e8;border:1px solid #3a4048;border-radius:4px"></select>
    </div>
    <div class="lc-rec-out" style="font-size:12px;color:#9aa3ad">Loading…</div>
    <div class="lc-rec-glance"></div></div>`;
}
async function initRec(root, lines) {
  const el = root.querySelector(".lc-sys-rec");
  if (!el) return;
  let models = [];
  try {
    models = await (await api.fetchApi("/lc123/syscheck/models")).json();
  } catch (_) {}
  if (!models.length) {
    el.querySelector(".lc-rec-out").textContent = "No model profiles found.";
    return;
  }
  let st = {};
  try {
    st = JSON.parse(localStorage.getItem(REC_KEY) || "{}");
  } catch (_) {}
  const selM = el.querySelector(".lc-rec-model");
  const selS = el.querySelector(".lc-rec-size");
  selM.innerHTML = models.map((m) => `<option value="${esc(m.id)}">${esc(m.name)}</option>`).join("");
  if (models.some((m) => m.id === st.model)) selM.value = st.model;
  let goal = st.goal || "Optimal";
  const sizes = () => {
    const m = models.find((x) => x.id === selM.value);
    selS.innerHTML = (m?.sizes || []).map((s) => `<option value="${s}">${s} MP</option>`).join("");
    if ((m?.sizes || []).map(String).includes(String(st.mp))) selS.value = String(st.mp);
  };
  const paintGoals = () =>
    el.querySelectorAll("[data-goal]").forEach((b) => {
      const on = b.dataset.goal === goal;
      b.style.background = on ? "#2563eb" : "";
      b.style.color = on ? "#fff" : "";
      b.style.fontWeight = on ? "600" : "";
    });
  const run = async () => {
    st = { model: selM.value, goal, mp: selS.value };
    try {
      localStorage.setItem(REC_KEY, JSON.stringify(st));
    } catch (_) {}
    const out = el.querySelector(".lc-rec-out");
    out.textContent = "…";
    const seq = (el._lcRecSeq = (el._lcRecSeq || 0) + 1); // the newest pick wins over an older, slower answer
    let r;
    try {
      r = await (await api.fetchApi(`/lc123/syscheck/recommend?model=${encodeURIComponent(st.model)}&goal=${goal}&mp=${st.mp}`)).json();
    } catch (e) {
      if (seq !== el._lcRecSeq) return;
      out.textContent = String(e);
      return;
    }
    if (seq !== el._lcRecSeq) return;
    if (r.error) {
      out.textContent = r.error;
      return;
    }
    out.innerHTML = recTable(r);
    const txt = recText(r);
    lines.rec = txt; // the Copy report button picks it up
  };
  selM.onchange = () => {
    sizes();
    run();
  };
  selS.onchange = run;
  el.querySelectorAll("[data-goal]").forEach((b) => (b.onclick = () => {
    goal = b.dataset.goal;
    paintGoals();
    run();
    glance(el, goal);
  }));
  glance(el, goal);
  sizes();
  paintGoals();
  run();
}
// At a glance: every profiled base model, one row each, for the selected goal
async function glance(root, goal) {
  const out = root.querySelector(".lc-rec-glance");
  if (!out) return;
  out.innerHTML = `<div style="color:#9aa3ad">Loading all models…</div>`;
  const seq = (out._lcSeq = (out._lcSeq || 0) + 1); // a newer goal's table wins over an older, slower one
  let models = [];
  try {
    models = await (await api.fetchApi("/lc123/syscheck/models")).json();
  } catch (_) {}
  const rows = await Promise.all(
    models.map(async (m) => {
      try {
        return await (await api.fetchApi(`/lc123/syscheck/recommend?model=${encodeURIComponent(m.id)}&goal=${goal}&mp=${m.sizes[0] ?? ""}`)).json();
      } catch (_) {
        return null;
      }
    })
  );
  if (seq !== out._lcSeq) return;
  const h = [`<div style="font-weight:600;margin:10px 0 4px">All base models at a glance <span style="font-weight:400;color:#9aa3ad;font-size:12px">(${esc(goal)})</span></div>`,
    `<table style="width:100%;border-collapse:collapse;font-size:12px;color:#dfe3e8"><tr style="color:#9aa3ad;text-align:left"><th>Model</th><th>Model file</th><th>Size</th><th>vs bf16</th><th>Time per image / clip</th><th>Text encoder</th></tr>`];
  rows.forEach((r, i) => {
    if (!r || r.error) return;
    const d = r.picks.find((p) => p.role === "diffusion");
    const te = r.picks.find((p) => p.role === "text_encoder");
    if (!d) return;
    const link = (p) => (p.repo ? `<a href="https://huggingface.co/${esc(p.repo)}" target="_blank" rel="noopener" style="color:#60a5fa">${esc(p.display || p.file)}</a>` : esc(p.file)) + (p.on_disk ? " ✅" : "");
    const q = d.lpips_measured === "reference" ? (d.format && d.format !== "bf16" ? `reference (${esc(d.format.split("_")[0])})` : "bf16") : d.lpips === 0 && d.lpips_measured === true ? "bf16" : `${d.lpips}`;
    const tm = d.total_s != null ? `~${d.total_s} s <span style="color:#9aa3ad">(${d.steps} steps, ${d.at_mp} MP)</span>` : `<span style="color:#9aa3ad">not measured</span>`;
    h.push(`<tr style="border-top:1px solid #2d333b;vertical-align:top"><td style="padding:4px 8px 4px 0">${esc(r.name)}</td><td>${link(d)}</td><td>${d.gb} GB</td><td>${q}</td><td>${tm}</td><td>${te ? link(te) : ""}</td></tr>`);
  });
  h.push(`</table><div style="color:#9aa3ad;font-size:12px;margin-top:4px">✅ = already on this machine. Links open the file's Hugging Face page.</div>`);
  out.innerHTML = h.join("");
}

function recTable(r) {
  const h = [`<table style="width:100%;border-collapse:collapse;font-size:12px;color:#dfe3e8"><tr style="color:#9aa3ad;text-align:left"><th>Part</th><th>File</th><th>Size</th><th>Quality vs bf16</th><th>Speed on this machine</th><th>Fits</th></tr>`];
  for (const p of r.picks) {
    const link = p.repo ? `<a href="https://huggingface.co/${esc(p.repo)}" target="_blank" rel="noopener" style="color:#60a5fa">${esc(p.display || p.file)}</a>` : esc(p.file);
    const have = p.on_disk ? ` <span style="color:#86efac">✅ you have it</span>` : "";
    let q = "";
    if (p.role !== "fixed") {
      q = p.lpips_measured === "reference" || (p.lpips === 0 && p.lpips_measured === true) ? "full quality (bf16)" : `${p.lpips} · ${QUALITY_WORDS(p.lpips)}${p.lpips_measured === true ? "" : ` <span style="color:#9aa3ad">(${p.lpips_measured === "same format" ? "from the same format" : "estimated"})</span>`}`;
    }
    let sp = "";
    if (p.step_s) {
      const conf = p.borrowed ? "estimated from similar files" : p.confidence;
      sp = `${p.step_s} s/step${p.total_s ? ` · ~${p.total_s} s for ${p.steps} steps` : ""} <span style="color:#9aa3ad">(${esc(conf)}, ${p.at_mp} MP)</span>`;
    } else if (p.role === "diffusion") sp = `<span style="color:#9aa3ad">not measured</span>`;
    const fits = p.role === "fixed" ? "" : `${p.fits === "vram" ? "on the card" : "streams from RAM"}${p.ram === "pagefile" ? ` <span style="color:#fbbf24">· page file</span>` : ""}`;
    const warn = (p.warnings || []).map((w) => `<div style="color:#fbbf24">⚠️ ${esc(w)}</div>`).join("") + (p.info || []).map((w) => `<div style="color:#9aa3ad">💡 ${esc(w)}</div>`).join("");
    h.push(`<tr style="border-top:1px solid #2d333b;vertical-align:top"><td style="color:#9aa3ad;padding:4px 8px 4px 0">${esc(p.component)}</td><td>${link}${have}${warn}</td><td>${p.gb} GB</td><td>${q}</td><td>${sp}</td><td>${fits}</td></tr>`);
  }
  h.push(`</table>`);
  h.push(`<div style="color:#9aa3ad;margin-top:4px">RAM for these files: ~${r.ram_need_gb} GB of ${r.ram_gb} GB. Quality = difference from bf16 after one step (0 = identical, under 0.05 hard to see).</div>`);
  for (const w of r.warnings || []) h.push(`<div style="color:#fbbf24;margin-top:2px">⚠️ ${esc(w)}</div>`);
  for (const n of r.notes || []) h.push(`<div style="color:#9aa3ad;margin-top:2px">💡 ${esc(n)}</div>`);
  return h.join("");
}
function recText(r) {
  const l = ["", `Model recommendation: ${r.name}, ${r.goal}`];
  for (const p of r.picks) l.push(`${p.component}: ${p.file} (${p.gb} GB)${p.step_s ? `, ${p.step_s} s/step` : ""}${p.role !== "fixed" && p.lpips_measured !== "reference" ? `, quality ${p.lpips}` : ""}${p.on_disk ? ", you have it" : ""}${p.repo ? `, https://huggingface.co/${p.repo}` : ""}`);
  return l.join("\n");
}

// "Recommended to install": links to other people's projects, matched to this card. Nothing is installed from here.
function installSection(p, h, lines) {
  const ins = p.install;
  if (!ins?.items?.length) return;
  const link = (u, t) => `<a href="${esc(u)}" target="_blank" rel="noopener" style="color:#60a5fa">${esc(t)}</a>`;
  h.push(`<div style="font-weight:600;font-size:14px;margin:14px 0 4px">Recommended to install</div>`);
  h.push(`<div style="color:#9aa3ad;font-size:12px;margin-bottom:6px">For this machine: ${esc(ins.detected)}</div>`);
  lines.push("", "Recommended to install:", `For this machine: ${ins.detected}`);
  for (const it of ins.items) {
    const tag = it.status === "failed" ? "⚠️" : it.status === "info" ? "ℹ️" : "💡";
    const more = (it.more || []).map(([t, u]) => " · " + link(u, t)).join("");
    h.push(`<div style="margin:6px 0;padding:8px 10px;background:#252a31;border-left:3px solid #60a5fa;border-radius:4px">${tag} <b>${esc(it.name)}</b>${it.link ? ` · ${link(it.link, "Get it here")}` : ""}${more}<div style="margin-top:3px">${esc(it.why)}</div>`);
    for (const n of it.notes || []) {
      const cmd = n.startsWith("Command: ");
      h.push(`<div style="margin-top:3px;color:#b8c2d0">${cmd ? `<code style="background:#161a1f;padding:1px 6px;border-radius:3px;user-select:all">${esc(n.slice(9))}</code>` : "• " + esc(n)}</div>`);
    }
    h.push(`</div>`);
    lines.push(`${tag} ${it.name}${it.link ? `: ${it.link}` : ""}`, `   ${it.why}`, ...(it.notes || []).map((n) => `   ${n}`));
  }
  h.push(`<div style="color:#9aa3ad;font-size:11px;margin:4px 0 12px">${esc(ins.fine_print)}</div>`);
}

let running = false;

// opts.saved: show the saved report when there is one (no new test), run a new one otherwise
function openWindow(opts = {}) {
  const open = document.querySelector(".lc-sys-overlay");
  if (open && running) return;
  open?.remove();
  const ov = document.createElement("div");
  ov.className = "lc-sys-overlay";
  ov.style.cssText = "position:fixed;inset:0;z-index:10000;background:rgba(0,0,0,0.55);display:flex;align-items:center;justify-content:center;";
  const box = document.createElement("div");
  box.style.cssText =
    "width:min(920px,94vw);max-height:88vh;overflow:auto;background:#1e2227;color:#dfe3e8;border:1px solid #3a4048;border-radius:10px;padding:18px 22px;font:13px/1.45 system-ui,sans-serif;";
  box.innerHTML = `<div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">
      <div style="font-size:17px;font-weight:600;flex:1">System &amp; Model Optimization Report</div>
      <button class="lc-sys-last p-button p-button-sm p-button-secondary" type="button" style="display:none">Show last run</button>
      <button class="lc-sys-copy p-button p-button-sm" type="button" disabled>Copy report</button>
      <button class="lc-sys-again p-button p-button-sm" type="button" disabled>Run again</button>
      <button class="lc-sys-close p-button p-button-sm p-button-secondary" type="button">Close</button></div>
    <div class="lc-sys-body">Starting…</div>`;
  ov.appendChild(box);
  document.body.appendChild(ov);
  const body = box.querySelector(".lc-sys-body");
  const close = () => !running && ov.remove();
  box.querySelector(".lc-sys-close").onclick = close;
  ov.addEventListener("pointerdown", (e) => e.target === ov && close());
  let text = "";
  let current = "";
  let showingLast = false;
  const lastBtn = box.querySelector(".lc-sys-last");
  const paintLast = () => {
    const last = loadLast();
    lastBtn.style.display = last?.html ? "" : "none";
    lastBtn.textContent = showingLast ? "Back to this run" : "Show last run";
  };
  lastBtn.onclick = () => {
    const last = loadLast();
    if (!last?.html) return;
    showingLast = !showingLast;
    body.innerHTML = showingLast ? `<div style="color:#fbbf24;margin-bottom:8px">Last run: ${esc(last.when)}</div>` + last.html : current;
    paintLast();
    initRec(body, recState); // the restored HTML is static: wire the model recommendation controls again
  };
  const recState = {};
  box.querySelector(".lc-sys-copy").onclick = () => navigator.clipboard?.writeText(text + (recState.rec || ""));
  box.querySelector(".lc-sys-again").onclick = () => go();
  addCsvButton(box, ".lc-sys-copy", ".lc-sys-body", "System and Model Optimization Report");

  async function go() {
    if (running) return;
    running = true;
    showingLast = false;
    paintLast();
    for (const c of [".lc-sys-again", ".lc-sys-copy", ".lc-sys-close"]) box.querySelector(c).disabled = true;
    lastBtn.disabled = true;
    body.innerHTML = `<div style="padding:30px 0;text-align:center">Testing this machine… <b>about 10 seconds</b>. The GPU runs a few small tests.</div>`;
    let prof = null;
    let failed = null;
    try {
      const r = await api.fetchApi("/lc123/syscheck/run", { method: "POST" });
      prof = await r.json();
      if (prof?.error) failed = prof.error;
    } catch (e) {
      failed = e?.message || String(e);
    }
    running = false;
    for (const c of [".lc-sys-again", ".lc-sys-copy", ".lc-sys-close"]) box.querySelector(c).disabled = false;
    lastBtn.disabled = false;
    if (failed) {
      body.innerHTML = `<div style="padding:30px 0;text-align:center;color:#f87171">${esc(failed)}</div>`;
      return;
    }
    try {
      render(prof);
    } catch (e) {
      body.innerHTML = `<div style="padding:30px 0;text-align:center;color:#f87171">The report could not be built: ${esc(e?.message || e)}</div>`;
      console.warn("[LC123] System check", e);
    }
  }

  function render(p, saved = false) {
    const lines = [];
    const h = [];
    const prev = loadLast();
    const g = p.gpus?.[0] || {};
    const m = p.machine || {};
    const t = p.tests || {};
    h.push(`<div style="color:#fbbf24;font-weight:700;margin-bottom:6px">Tests this machine, then suggests the model files that suit it. Nothing is changed.</div>`);
    lines.push("System & Model Optimization Report", `${p.when} (${p.seconds} s)`);
    const rows = [
      ["Graphics card", g.name ? `${g.name}, ${g.vram_gb} GB${g.arch ? ` (${g.arch})` : ""}` : "none found"],
      ["Driver / PCIe", [g.driver && `driver ${g.driver}`, g.pcie_gen && `PCIe Gen${g.pcie_gen} x${g.pcie_width}`].filter(Boolean).join(", ")],
      ["System RAM / page file", `${m.ram_total_gb ?? "?"} GB / ${m.swap_total_gb ?? "?"} GB${m.swap_managed ? " now (managed by Windows, grows when needed)" : ""}`],
      ["CPU", m.cpu],
      ["Models drive", (p.disks || []).map((d) => `${d.drive} ${d.kind || ""}${d.free_gb != null ? `, ${d.free_gb} GB free` : ""}`).join(" · ")],
      ["RAM ↔ GPU", t.transfer?.ok ? `${t.transfer.to_gpu_gbs} GB/s to the GPU, ${t.transfer.to_ram_gbs} GB/s back` : t.transfer?.detail],
      ["Attention (one call)", [t.attention_sdpa?.ms != null && `standard ${t.attention_sdpa.ms} ms`, t.sageattention?.ms != null && `Sage ${t.sageattention.ms} ms`].filter(Boolean).join(", ")],
      ["Software", [p.comfy?.version && `ComfyUI ${p.comfy.version}`, p.software?.torch && `PyTorch ${p.software.torch}`, p.software?.cuda && `CUDA ${p.software.cuda}`, p.software?.hip && `ROCm ${p.software.hip}`].filter(Boolean).join(", ")],
    ];
    h.push(`<table style="width:100%;border-collapse:collapse;margin-bottom:14px">`);
    for (const [k, v] of rows) {
      if (!v) continue;
      h.push(`<tr style="border-top:1px solid #2d333b"><td style="color:#9aa3ad;padding:3px 10px 3px 0;white-space:nowrap">${esc(k)}</td><td>${esc(v)}</td></tr>`);
      lines.push(`${k}: ${v}`);
    }
    h.push(`</table>`);

    lcVision(p.lc_vision, h, lines);
    shopping(p.shopping, h, lines);
    h.push(recShell());

    const snap = snapshot(p);
    if (prev?.snap) sinceLast(prev, snap, h, lines);

    installSection(p, h, lines);
    h.push(`<div style="font-weight:600;font-size:14px;margin:6px 0">Findings</div>`);
    h.push(`<div style="color:#9aa3ad;font-size:12px;margin-bottom:4px">⚠️ problem · 💡 worth changing · ✅ works · ℹ️ info · ➖ not installed / does not apply</div>`);
    lines.push("", "Findings (⚠️ problem, 💡 worth changing, ✅ works, ℹ️ info, ➖ not installed):");
    const order = { 3: 0, 1: 1, 2: 2, 0: 3, "-1": 4 };
    for (const [kind, title, col] of KINDS) {
      const list = (p.findings || []).filter((f) => f.kind === kind).sort((a, b) => order[a.level] - order[b.level]);
      if (!list.length) continue;
      h.push(`<div style="margin:10px 0 4px;color:${col};font-weight:600">${esc(title)}</div>`);
      lines.push("", title + ":");
      for (const f of list) {
        const dim = f.level === -1 ? "opacity:0.6;" : "";
        h.push(`<div style="margin:4px 0;padding:6px 10px;background:#252a31;border-left:3px solid ${col};border-radius:4px;${dim}">${ICON[f.level] || ""} <b>${esc(f.title)}</b>: ${esc(f.text)}</div>`);
        lines.push(`${ICON[f.level] || ""} ${f.title}: ${f.text}`);
      }
    }
    h.push(`<div style="color:#9aa3ad;margin-top:10px;font-size:12px">Saved on this machine${p.saved_to ? `: ${esc(p.saved_to)}` : ""}, so Show last run and the recommendations work without re-testing. The speed tests are tiny, so treat small differences between runs as noise.</div>`);
    current = h.join("");
    body.innerHTML = current;
    text = lines.join("\n");
    initRec(body, recState); // live controls: filled after the report is on screen
    if (saved) body.insertAdjacentHTML("afterbegin", `<div style="color:#9aa3ad;margin-bottom:8px">Saved report from ${esc(p.when || "the last run")}. <b>Run again</b> for a new test.</div>`);
    else saveLast({ when: new Date().toLocaleString(), html: current, snap }); // only the last run is kept (a saved report is not a new run)
    paintLast();
  }

  async function showSaved() {
    try {
      const r = await api.fetchApi("/lc123/syscheck/profile");
      const prof = r.ok ? await r.json() : null;
      if (prof && !prof.error) {
        for (const c of [".lc-sys-again", ".lc-sys-copy", ".lc-sys-close"]) box.querySelector(c).disabled = false;
        render(prof, true);
        return;
      }
    } catch (_) {}
    go();
  }
  if (opts.saved) showSaved();
  else go();
}

app.registerExtension({
  name: "LC123.SystemCheck",
  settings: [
    {
      id: "LC123.Optimization.SystemCheck",
      name: "System & Model Optimization Report",
      sortOrder: 10, // under the Comfy Optimization Report
      category: ["LC Settings ⚙️", "Optimization", "System & Model Optimization Report"],
      defaultValue: "",
      tooltip:
        "Tests this machine (graphics card, memory, drive, and which speed-ups really work here: small live GPU tests, about 10 seconds), then tells you which model files suit it: what to look for, what to avoid, and exact picks with download links for the tested base models. Missing Sage, Triton or Comfy Kitchen? It links to builds that match your card. Nothing is changed or installed.",
      type: () => {
        const b = document.createElement("button");
        b.type = "button";
        b.textContent = "Run the System & Model Optimization Report";
        b.className = "p-button p-component p-button-sm";
        b.onclick = (e) => {
          e.preventDefault();
          e.stopPropagation();
          document.querySelector('.p-dialog-mask .p-dialog-close-button, .p-dialog .p-dialog-header-close, [role="dialog"] button[aria-label="Close dialog"]')?.click(); // old and new settings dialog
          setTimeout(openWindow, 250);
        };
        return b;
      },
    },
  ],
  getCanvasMenuItems() {
    return [{ content: "System & Model Optimization Report", callback: () => openWindow() }];
  },
});

window.LC123SystemCheck = { open: openWindow };
