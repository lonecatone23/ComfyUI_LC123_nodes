/**
 * LC Dual Model Optimizer node face: an on/off switch and a model + text encoder picker per model, the shared VAE /
 * audio VAE / latent upscaler pickers, and the status panel (files, speed-ups, the Wan 2.2 pair check, hints).
 * The real values live in the node's own (hidden) widgets, so saving and queueing work like any node. Everything is
 * one DOM widget, so it works in the classic canvas and in Nodes 2.0. The pair check also draws a line under the node.
 */
import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { lcApplyLaunchColor } from "./lc_color.js";

const CLASS = "LCOptimizerDual";
const COLOR = "#2E4A3B";
const DEFAULT_W = 360;
const REC = "★ Recommended", DL = "⬇ Download: ", CKPT = "From checkpoint", NONE = "None", AUTHOR = "★ Author: ";
const isPick = (v) => typeof v === "string" && v.startsWith("★ ") && v !== REC;
const SLOTS = [
  { on: "model_1_on", model: "model_file_1", te: "text_encoder_1", slot: 1 },
  { on: "model_2_on", model: "model_file_2", te: "text_encoder_2", slot: 2 },
];
const SHARED = [["vae", "vae", "VAE"], ["audio_vae", "audio_vae", "Audio VAE"], ["latent_upscaler", "upscaler", "Latent upscaler"]];
const HIDDEN = ["model_1_on", "model_file_1", "text_encoder_1", "model_2_on", "model_file_2", "text_encoder_2", "vae", "audio_vae", "latent_upscaler"];
const MANUAL = ["attention", "fp16_accumulation", "step_cache", "torch_compile", "qwen21_cache", "spectrum", "veda"];
const LEGEND = {
  picker: "★ recommended for this machine · ⬇ downloads on the first run · 📦 from the checkpoint",
  file: "✅ on disk · ⬇️ downloads on the first run (you picked it) · ★⬇ not on disk: pick it to download · 📦 from the checkpoint · ⚠️ not found",
  speed: "✅ on (will apply, then applied) · ➖ off or not available here",
  hint: "⚠️ check this (it still loads) · 💡 tip · ℹ️ info",
};
const ICON = { disk: "✅", download: "⬇️", pick: "★⬇", ckpt: "📦", missing: "⚠️", on: "✅", off: "➖", na: "➖", unsupported: "➖" };
const PAIR_COLOR = { ok: "#6fd3a0", warn: "#f3c969", note: "#b8c2d0" };
const STATUS_COLORS = { warn: "#f0b040", info: "#9aa4b2", ok: "#6fd3a0" };
const CUSTOM = "Custom";

const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const tip = (detail, legend) => esc(detail ? `${detail}\n\n${legend}` : legend);
const wByName = (node, n) => (node.widgets || []).find((w) => w.name === n);
const baseName = (p) => String(p).replace(/\\/g, "/").split("/").pop();

function hideWidget(w) {
  if (!w || w._lcHidden) return;
  w._lcOrigType = w._lcOrigType ?? w.type;
  w._lcOrigCompute = w.computeSize;
  w.type = "hidden";
  w.hidden = true;
  w.computeSize = () => [0, -4];
  w._lcHidden = true;
}
function showWidget(w) {
  if (!w || !w._lcHidden) return;
  w.type = w._lcOrigType;
  w.hidden = false;
  if (w._lcOrigCompute) w.computeSize = w._lcOrigCompute; else delete w.computeSize;
  w._lcHidden = false;
}

// ---------------------------------------------------------------- the picker popup (same as LC Model Optimizer's)
let openPop = null;
function closePop() {
  openPop?.remove();
  openPop = null;
  document.removeEventListener("pointerdown", outside, true);
  document.removeEventListener("keydown", escKey, true);
}
function outside(e) { if (openPop && !openPop.contains(e.target)) closePop(); }
function escKey(e) { if (e.key === "Escape") closePop(); }

function buildTree(list) {
  const root = { files: [], folders: new Map() };
  for (const name of list) {
    const parts = name.replace(/\\/g, "/").split("/");
    let n = root;
    for (const seg of parts.slice(0, -1)) {
      if (!n.folders.has(seg)) n.folders.set(seg, { files: [], folders: new Map() });
      n = n.folders.get(seg);
    }
    n.files.push(name);
  }
  return root;
}

async function showPicker(node, widget, role, slot, anchor) {
  closePop();
  const base = wByName(node, "base_model")?.value, goal = wByName(node, "goal")?.value;
  const pop = document.createElement("div");
  openPop = pop;
  pop.style.cssText = "position:fixed;z-index:10000;width:380px;max-height:460px;display:flex;flex-direction:column;background:#1b1f24;color:#e6e9ee;border:1px solid #3a4250;border-radius:8px;box-shadow:0 10px 30px #0009;font:13px sans-serif;overflow:hidden";
  const r = anchor.getBoundingClientRect();
  pop.style.left = Math.min(r.left, innerWidth - 390) + "px";
  pop.style.top = Math.min(r.bottom + 4, innerHeight - 470) + "px";
  pop.innerHTML = `<div style="padding:8px;border-bottom:1px solid #2c333d;display:flex;gap:6px;align-items:center"><button data-back style="display:none;background:#2a313b;color:#cfd6df;border:0;border-radius:4px;padding:3px 8px;cursor:pointer">‹</button><span data-crumb style="flex:1;color:#9aa6b8;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">Loading…</span></div><input data-q placeholder="Search" style="margin:6px 8px;padding:5px 8px;background:#12161b;color:#e6e9ee;border:1px solid #333b46;border-radius:4px;outline:none"><div data-list style="overflow:auto;flex:1;padding:0 4px 6px"></div>`;
  document.body.appendChild(pop);
  setTimeout(() => { document.addEventListener("pointerdown", outside, true); document.addEventListener("keydown", escKey, true); }, 0);

  let data;
  try {
    data = await (await api.fetchApi(`/lc123/optimizer_dual/choices?base=${encodeURIComponent(base)}&slot=${slot}&role=${role}&goal=${encodeURIComponent(goal)}`)).json();
  } catch (e) { data = { error: String(e) }; }
  if (openPop !== pop) return;
  const listEl = pop.querySelector("[data-list]"), crumb = pop.querySelector("[data-crumb]"), back = pop.querySelector("[data-back]"), q = pop.querySelector("[data-q]");
  const pick = (v) => { widget.value = v; widget.callback?.(v); closePop(); node._lcDualRefresh?.(); };
  const row = (html, onClick, opts = {}) => {
    const el = document.createElement("div");
    el.style.cssText = `padding:6px 8px;border-radius:4px;cursor:pointer;display:flex;gap:8px;align-items:center;${opts.current ? "background:#26303b;" : ""}`;
    el.innerHTML = html;
    el.onmouseenter = () => (el.style.background = "#2b3542");
    el.onmouseleave = () => (el.style.background = opts.current ? "#26303b" : "");
    el.onclick = onClick;
    listEl.appendChild(el);
  };
  const tree = buildTree(data.local || []);
  const known = new Set(data.known || []);
  const extras = role === "model" ? [] : [CKPT, NONE];
  let path = [];
  const open = new Set();

  const render = () => {
    listEl.innerHTML = "";
    const term = q.value.trim().toLowerCase();
    back.style.display = path.length ? "" : "none";
    if (term) {
      crumb.textContent = "Search";
      const all = [...(data.picks || []).map((p) => p.value), ...(data.downloads || []).map((d) => d.value), ...(data.local || [])].filter((v) => v.toLowerCase().includes(term));
      for (const v of all.slice(0, 200)) row(`<span>${isPick(v) ? "★" : v.startsWith(DL) ? "⬇️" : "📄"}</span><span style="word-break:break-all">${esc(isPick(v) ? v.slice(2) : v.startsWith(DL) ? baseName(v.slice(DL.length)) : v)}</span>`, () => pick(v), { current: v === widget.value });
      if (!all.length) listEl.innerHTML = `<div style="padding:10px;color:#8a95a5">No match.</div>`;
      return;
    }
    if (path[0] === "__dl") {
      crumb.textContent = "⬇ Download";
      for (const d of data.downloads || []) {
        const tag = d.featured ? ` · ${esc(d.featured)}` : d.gated ? " · gated" : d.community ? " · community" : "";
        row(`<span>⬇️</span><span style="flex:1;word-break:break-all">${esc(d.file)}</span><span style="color:#8a95a5;white-space:nowrap">${d.gb ?? "?"} GB${tag}</span>`, () => pick(d.value), { current: d.value === widget.value });
      }
      return;
    }
    if (path[0] === "__known") {
      crumb.textContent = `On disk for ${base}`;
      const local = data.local || [];
      const byBase = (file) => local.find((n) => baseName(n).toLowerCase() === String(file).toLowerCase());
      const pins = [];
      if (data.recommended?.on_disk) pins.push(["Recommended", byBase(data.recommended.file)]);
      for (const p of data.picks || []) if (p.on_disk) pins.push([p.label, byBase(p.file)]);
      for (const [label, f] of pins) if (f) row(`<span>★</span><span style="flex:1;word-break:break-all">${esc(baseName(f))}</span><span style="color:#8a95a5;white-space:nowrap">${esc(label)}</span>`, () => pick(f), { current: f === widget.value });
      const groups = data.groups || [];
      if (!groups.length && !pins.length) listEl.innerHTML = `<div style="padding:10px;color:#8a95a5">Nothing on disk for ${esc(base)} yet.</div>`;
      const fileRow = (f, indent) => row(`<span style="margin-left:${indent}px">${f === widget.value ? "●" : "✅"}</span><span style="word-break:break-all">${esc(baseName(f))}</span>`, () => pick(f), { current: f === widget.value });
      const toggle = (key, label, count, indent) => {
        const isOpen = open.has(key);
        row(`<span style="margin-left:${indent}px;width:10px;color:#8a95a5">${isOpen ? "▾" : "▸"}</span><span style="flex:1">${esc(label)}</span><span style="color:#8a95a5">${count}</span>`, () => { isOpen ? open.delete(key) : open.add(key); render(); });
        return isOpen;
      };
      for (const g of groups) {
        const files = g.versions.flatMap((v) => v.files);
        if (files.length === 1) { fileRow(files[0], 0); continue; }
        if (!toggle(g.family, g.family, files.length, 0)) continue;
        const flat = g.versions.length === 1;
        for (const v of g.versions) {
          if (flat) { for (const f of v.files) fileRow(f, 18); continue; }
          if (!toggle(`${g.family}|${v.version}`, v.version || "other", v.files.length, 18)) continue;
          for (const f of v.files) fileRow(f, 36);
        }
      }
      return;
    }
    let level = tree;
    for (const seg of path) level = level.folders.get(seg) || { files: [], folders: new Map() };
    crumb.textContent = path.length ? path.join(" / ") : `${base} · ${goal}`;
    if (!path.length) {
      const rec = data.recommended;
      const ckptPart = role !== "model" && node._lcDualPlan?.checkpoint;
      row(`<span>${rec && !rec.on_disk ? "★⬇" : "★"}</span><span style="flex:1"><b>Recommended</b><br><span style="color:#8a95a5">${rec ? esc(rec.file) + (rec.on_disk ? " · on disk" : ` · downloads ${rec.gb ?? "?"} GB`) + (rec.source === "default" ? " · Comfy default" : "") : (ckptPart ? "blank: the checkpoint's own" : data.unsupported ? "unsupported for Custom: pick a file" : "nothing for this part")}</span></span>`, () => pick(rec && !rec.on_disk ? DL + rec.file : REC), { current: widget.value === REC });
      for (const p of data.picks || []) row(`<span>${p.on_disk ? "★" : "★⬇"}</span><span style="flex:1"><b>${esc(p.label)}</b><br><span style="color:#8a95a5">${esc(p.file)}${p.on_disk ? " · on disk" : ` · downloads ${p.gb ?? "?"} GB`}</span></span>`, () => pick(p.on_disk ? p.value : DL + p.file), { current: widget.value === p.value });
      for (const x of extras) row(`<span>${x === CKPT ? "📦" : "∅"}</span><span>${x}</span>`, () => pick(x), { current: widget.value === x });
      if ((data.downloads || []).length) row(`<span>📁</span><span style="flex:1">⬇ Download</span><span style="color:#8a95a5">${data.downloads.length}</span>`, () => { path = ["__dl"]; render(); });
      const onDisk = (data.groups || []).reduce((k, g) => k + g.versions.reduce((j, v) => j + v.files.length, 0), 0) || known.size;
      if (onDisk) row(`<span>📁</span><span style="flex:1">On disk for ${esc(base)}</span><span style="color:#8a95a5">${onDisk}</span>`, () => { path = ["__known"]; render(); });
    }
    for (const [name, sub] of [...level.folders.entries()].sort((a, b) => a[0].localeCompare(b[0]))) {
      const count = (function c(n) { let k = n.files.length; for (const s of n.folders.values()) k += c(s); return k; })(sub);
      row(`<span>📁</span><span style="flex:1">${esc(name)}</span><span style="color:#8a95a5">${count}</span>`, () => { path = [...path, name]; render(); });
    }
    for (const f of level.files.sort((a, b) => baseName(a).localeCompare(baseName(b))))
      row(`<span>${known.has(f) ? "✅" : "📄"}</span><span style="word-break:break-all">${esc(baseName(f))}</span>`, () => pick(f), { current: f === widget.value });
  };
  back.onclick = () => { path = path.slice(0, -1); render(); };
  q.oninput = render;
  if (data.error) { listEl.innerHTML = `<div style="padding:10px;color:#f0a0a0">${esc(data.error)}</div>`; crumb.textContent = ""; return; }
  render();
  q.focus();
}

// ---------------------------------------------------------------- the face
function display(v, planFile) {
  if (v === REC && planFile?.state === "unsupported") return "unsupported: pick a file";
  if (v === REC && planFile?.state === "ckpt") return "";
  const star = planFile?.state === "pick" ? "★⬇" : "★";
  if (v === REC) return `${star} ${planFile?.label ? baseName(planFile.label) : "Recommended"}`;
  if (isPick(v)) return `${star} ${planFile?.label ? baseName(planFile.label) : v.startsWith(AUTHOR) ? v.slice(AUTHOR.length).split(" | ")[0] : v.slice(2)}`;
  if (typeof v === "string" && v.startsWith(DL)) return `⬇ ${baseName(planFile?.label || v.slice(DL.length))}`;
  if (v === CKPT) return "📦 From checkpoint";
  return baseName(v ?? "");
}

const BTN = "flex:1;min-width:0;text-align:left;background:#20262e;color:#e6e9ee;border:1px solid #333b46;border-radius:5px;padding:4px 8px;cursor:pointer;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font:12px sans-serif";

function pickerButton(node, w, role, slot, planFile, opts = {}) {
  const btn = document.createElement("button");
  btn.style.cssText = BTN;
  if (opts.unused) {
    btn.textContent = opts.unused;
    btn.style.opacity = "0.45";
    btn.style.cursor = "default";
  } else {
    btn.textContent = display(w.value, planFile) + "  ▾";
    btn.title = `${w.value}\n\n${LEGEND.picker}`;
    if (opts.off) btn.style.opacity = "0.45";
    btn.onclick = (e) => { e.stopPropagation(); showPicker(node, w, role, slot, btn); };
  }
  return btn;
}

// a small on / off switch like rgthree's Power Lora Loader toggles
function toggleSwitch(node, w) {
  const on = w.value !== false;
  const t = document.createElement("button");
  t.title = on ? "On: loads this model. Click to turn it off." : "Off: model and clip outputs are None. Click to turn it on.";
  t.setAttribute("role", "switch");
  t.setAttribute("aria-checked", String(on));
  t.dataset.lcDualToggle = w.name;
  t.style.cssText = `flex:none;width:30px;height:16px;border-radius:8px;border:0;padding:0;position:relative;cursor:pointer;background:${on ? "#3f9d63" : "#4a525e"}`;
  t.innerHTML = `<span style="position:absolute;top:2px;${on ? "right:2px" : "left:2px"};width:12px;height:12px;border-radius:50%;background:#f2f4f7"></span>`;
  t.onclick = (e) => {
    e.stopPropagation();
    w.value = !on;
    w.callback?.(w.value);
    renderFace(node);
    node._lcDualRefresh?.();
  };
  return t;
}

function renderFace(node) {
  const f = node._lcDualFace;
  if (!f) return;
  const pl = node._lcDualPlan;
  const labels = pl?.labels || ["Model 1", "Model 2"];
  f.pickers.innerHTML = "";
  for (const s of SLOTS) {
    const onW = wByName(node, s.on), mW = wByName(node, s.model), tW = wByName(node, s.te);
    if (!onW || !mW || !tW) continue;
    const off = onW.value === false;
    const sp = pl?.slots?.[s.slot - 1];
    const files = Object.fromEntries((sp?.files || []).map((x) => [x.role, x]));
    const r1 = document.createElement("div");
    r1.style.cssText = "display:flex;align-items:center;gap:6px;margin:0 0 3px";
    r1.appendChild(toggleSwitch(node, onW));
    const lab = document.createElement("span");
    lab.style.cssText = `width:70px;flex:none;color:${off ? "#6b7480" : "#cfd6df"};font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis`;
    lab.textContent = labels[s.slot - 1];
    lab.title = `Model ${s.slot}: ${labels[s.slot - 1]}`;
    r1.appendChild(lab);
    r1.appendChild(pickerButton(node, mW, "model", s.slot, files.model, { off }));
    const r2 = document.createElement("div");
    r2.style.cssText = "display:flex;align-items:center;gap:6px;margin:0 0 7px";
    r2.innerHTML = `<span style="width:106px;flex:none;color:${off ? "#6b7480" : "#9aa6b8"};text-align:right;padding-right:0">Text encoder</span>`;
    r2.appendChild(pickerButton(node, tW, "clip", s.slot, files.clip, { off }));
    f.pickers.append(r1, r2);
  }
  const shared = Object.fromEntries((pl?.files || []).map((x) => [x.role, x]));
  for (const [wn, role, label] of SHARED) {
    const w = wByName(node, wn);
    if (!w) continue;
    const r = document.createElement("div");
    r.style.cssText = "display:flex;align-items:center;gap:6px;margin:0 0 4px";
    r.innerHTML = `<span style="width:106px;flex:none;color:#9aa6b8;text-align:right">${label}</span>`;
    const unused = pl?.roles && !pl.roles.includes(role) ? `not used by ${pl.base}` : null;
    r.appendChild(pickerButton(node, w, role, (pl?.anchor ?? 0) + 1, shared[role], { unused }));
    f.pickers.appendChild(r);
  }
  if (!pl) { f.status.innerHTML = `<div style="color:#8a95a5">Checking…</div>`; f.foot.textContent = ""; return; }
  const lines = [];
  if (pl.error) lines.push(`<div style="color:#f0a0a0">${esc(pl.error)}</div>`);
  if (pl.slots && !pl.report) {
    lines.push(`<div style="margin-bottom:6px;padding:6px 8px;border:1px solid #f3c969;border-radius:6px;background:rgba(243,201,105,0.12);color:#f3c969">
      <div style="font-weight:700;font-size:14px">💡⚠️ Run the System &amp; Model Optimization Report first</div>
      <div style="color:#dfe5ec;margin-top:2px">Without it, you get Comfy's default files and speed-ups that aren't matched to your card. Click <b>Run or Open Report</b> below (about 10 seconds).</div></div>`);
  }
  const fileLine = (x, prefix) => {
    const what = x.state === "download" ? `downloads ${x.gb ?? "?"} GB` : x.state === "pick" ? `not on disk · pick ⬇ (${x.gb ?? "?"} GB)` : x.state === "disk" ? "on disk" : x.state === "ckpt" || x.state === "unsupported" ? "" : "not found";
    return `<div style="display:flex;gap:6px" title="${tip(baseName(x.label), LEGEND.file)}"><span>${ICON[x.state] || "•"}</span><span style="color:#8a95a5;flex:none">${esc(prefix)}</span><span style="flex:1;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${esc(baseName(x.label))}</span><span style="color:#8a95a5;white-space:nowrap">${what}</span></div>`;
  };
  (pl.slots || []).forEach((sp, i) => {
    if (!sp.on) { lines.push(`<div style="display:flex;gap:6px;color:#6b7480"><span>➖</span><span>${i + 1} ${esc(sp.label)}: off</span></div>`); return; }
    for (const x of sp.files || []) lines.push(fileLine(x, `${i + 1}${x.role === "clip" ? " te" : ""}`));
  });
  for (const x of pl.files || []) lines.push(fileLine(x, ""));
  const applied = pl.applied;
  for (const s of pl.speedups || []) {
    if (s.key === "kitchen" && s.state === "on") {
      lines.push(`<div style="display:flex;gap:6px" title="${tip(s.why, LEGEND.speed)}"><span>${ICON[s.state]}</span><span style="flex:1">${esc(s.label)}</span><span style="color:#8a95a5;white-space:nowrap">used by ComfyUI</span></div>`);
      continue;
    }
    const ok = !applied || applied.includes(s.label);
    lines.push(`<div style="display:flex;gap:6px" title="${tip(s.why, LEGEND.speed)}"><span>${ICON[s.state]}</span><span style="flex:1">${esc(s.label)}</span><span style="color:#8a95a5;white-space:nowrap;max-width:48%;overflow:hidden;text-overflow:ellipsis">${s.state === "on" ? (applied ? (ok ? "applied" : "failed") : "will apply") : esc(s.why)}</span></div>`);
  }
  if (pl.pair) lines.push(`<div style="display:flex;gap:6px;color:${PAIR_COLOR[pl.pair.level] || "#b8c2d0"};font-weight:600" title="${esc((pl.pair.files || []).map((x) => `${x.file}: ${x.noise || "?"} noise${x.noise_src ? ` (${x.noise_src})` : ""}, ${x.label || "release unknown"}`).join("\n"))}"><span style="flex:1">${esc(pl.pair.text)}</span></div>`);
  for (const [icon, text] of pl.hints || []) {
    if (!pl.report && String(text).startsWith("No report yet")) continue;
    lines.push(`<div style="display:flex;gap:6px;color:${icon === "⚠️" ? "#f3c969" : "#b8c2d0"}" title="${tip("", LEGEND.hint)}"><span>${icon}</span><span style="flex:1">${esc(text)}</span></div>`);
  }
  f.status.innerHTML = lines.join("");
  requestAnimationFrame(() => faceHeight(node));
  const rep = pl.report;
  f.foot.innerHTML = `<span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(rep ? `Report: ${rep.when?.slice(0, 10)} · ${rep.gpu}` : "No report yet")}</span>`;
  const b = document.createElement("button");
  b.textContent = "Run or Open Report";
  b.title = "Run the optimization report or view the saved one";
  b.style.cssText = rep
    ? "background:#2a313b;color:#dfe5ec;border:1px solid #3a4250;border-radius:4px;padding:2px 8px;cursor:pointer;font:12px sans-serif"
    : "background:#f3c969;color:#1e2227;border:1px solid #f3c969;border-radius:4px;padding:3px 10px;cursor:pointer;font:bold 13px sans-serif";
  b.onclick = (ev) => { ev.stopPropagation(); window.LC123SystemCheck?.open?.({ saved: true }); };
  f.foot.appendChild(b);
  fit(node);
}

function faceHeight(node) {
  const f = node._lcDualFace;
  if (!f) return 0;
  if (!f.foot.offsetHeight) {
    clearTimeout(node._lcDualMeasure);
    node._lcDualMeasure = setTimeout(() => faceHeight(node), 250);
    return node._lcDualFaceH || 420;
  }
  const h = f.foot.offsetTop + f.foot.offsetHeight + 10 + 20;
  if (Math.abs(h - (node._lcDualFaceH || 0)) > 1) {
    node._lcDualFaceH = h;
    fit(node);
  }
  return node._lcDualFaceH;
}

function fit(node) {
  requestAnimationFrame(() => {
    const need = node.computeSize?.()?.[1];
    if (need && Math.abs(node.size[1] - need) > 1) node.setSize([Math.max(node.size[0], DEFAULT_W), need]);
    node.setDirtyCanvas?.(true, true);
  });
}

async function refreshPlan(node) {
  const picks = {};
  for (const n of HIDDEN) { const w = wByName(node, n); if (w && !n.endsWith("_on")) picks[n] = w.value; }
  const body = {
    base: wByName(node, "base_model")?.value, goal: wByName(node, "goal")?.value, speed_ups: wByName(node, "speed_ups")?.value,
    picks, on: SLOTS.map((s) => wByName(node, s.on)?.value !== false),
    manual: Object.fromEntries(MANUAL.map((k) => [k, wByName(node, k)?.value])),
  };
  const seq = (node._lcDualSeq = (node._lcDualSeq || 0) + 1);
  try {
    const res = await api.fetchApi("/lc123/optimizer_dual/plan", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    if (seq !== node._lcDualSeq) return;
    const pl = await res.json();
    // the last run's pair check (it reads the files) stays until the files change
    if (!pl.pair && node._lcDualRunPair && node._lcDualRunPair.key === pairKey(node)) pl.pair = node._lcDualRunPair.pair;
    node._lcDualPlan = pl;
  } catch (e) {
    node._lcDualPlan = { hints: [["⚠️", "Could not reach ComfyUI to check the files."]] };
  }
  renderFace(node);
}

const pairKey = (node) => ["base_model", "model_file_1", "model_file_2", "model_1_on", "model_2_on"].map((n) => String(wByName(node, n)?.value)).join("|");

// a click on the family fills both slots with its recommended files (never on load: saved picks stay)
async function fillDefaults(node) {
  const base = wByName(node, "base_model")?.value, goal = wByName(node, "goal")?.value;
  try {
    const d = await (await api.fetchApi(`/lc123/optimizer_dual/defaults?base=${encodeURIComponent(base)}&goal=${encodeURIComponent(goal)}`)).json();
    if (d.error) return;
    for (const [wn, v] of Object.entries(d)) { const w = wByName(node, wn); if (w) w.value = v; }
  } catch (_) {}
  node._lcDualRefresh?.();
}

function applyManual(node) {
  const manual = wByName(node, "speed_ups")?.value === "Manual";
  for (const k of MANUAL) (manual ? showWidget : hideWidget)(wByName(node, k));
  const base = String(wByName(node, "base_model")?.value || "");
  if (base.startsWith("MiniMax H3") && !base.includes("Image")) {
    showWidget(wByName(node, "spectrum"));
    showWidget(wByName(node, "veda"));
  }
  if (base.startsWith("MOSS Image") || base.startsWith("Krea 2")) showWidget(wByName(node, "spectrum"));
  if (!base.startsWith("Qwen-Image 2.1") && !manual) hideWidget(wByName(node, "qwen21_cache"));
  (base === CUSTOM ? showWidget : hideWidget)(wByName(node, "clip_type"));
  fit(node);
}

function setup(node) {
  if (node._lcDualFace) return;
  lcApplyLaunchColor?.(node, COLOR);
  for (const n of HIDDEN) hideWidget(wByName(node, n));
  const wrap = document.createElement("div");
  wrap.style.cssText = "display:flex;flex-direction:column;gap:6px;padding:4px 2px;font:12px sans-serif;color:#e6e9ee;box-sizing:border-box;width:100%;max-width:100%;min-width:0;overflow:hidden;position:relative";
  const pickers = document.createElement("div");
  const status = document.createElement("div");
  status.style.cssText = "display:grid;grid-template-columns:minmax(0,1fr);gap:4px;border:1px solid #333b46;border-radius:6px;padding:6px 8px;background:#161a1f";
  const foot = document.createElement("div");
  foot.style.cssText = "display:flex;gap:6px;align-items:center;color:#8a95a5";
  for (const el of [pickers, status, foot]) el.style.flex = "none";
  wrap.append(pickers, status, foot);
  for (const ev of ["pointerdown", "mousedown", "wheel"]) wrap.addEventListener(ev, (e) => e.stopPropagation());
  const dom = node.addDOMWidget("lc_dual_optimizer_face", "LC_DUAL_OPTIMIZER_FACE", wrap, { serialize: false, getMinHeight: () => faceHeight(node), getMaxHeight: () => faceHeight(node) });
  dom.serializeValue = () => undefined;
  Object.defineProperty(dom, "width", { get: () => undefined, set: () => {}, configurable: true });
  node._lcDualFace = { wrap, pickers, status, foot };

  let timer = 0;
  node._lcDualRefresh = () => { clearTimeout(timer); timer = setTimeout(() => refreshPlan(node), 150); };
  for (const n of ["base_model", "goal", "speed_ups", "clip_type", ...MANUAL]) {
    const w = wByName(node, n);
    if (!w) continue;
    const prev = w.callback;
    w.callback = function (...a) {
      const r = prev?.apply(this, a);
      if (n === "speed_ups" || n === "base_model") applyManual(node);
      if (n === "base_model") fillDefaults(node); // a user click on the family: fill both slots
      else node._lcDualRefresh();
      return r;
    };
  }
  const prevExec = node.onExecuted;
  node.onExecuted = function (msg) {
    prevExec?.apply(this, arguments);
    let swapped = false;
    try {
      const swap = JSON.parse(msg?.lc_optimizer_dual_swap?.[0] || "{}");
      swapped = Object.keys(swap).length > 0;
      for (const [wn, v] of Object.entries(swap)) { const w = wByName(this, wn); if (w) w.value = v; }
      if (msg?.lc_optimizer_dual?.[0]) {
        this._lcDualPlan = JSON.parse(msg.lc_optimizer_dual[0]);
        if (this._lcDualPlan.pair) this._lcDualRunPair = { key: pairKey(this), pair: this._lcDualPlan.pair };
      }
    } catch (e) { /* keep the last plan */ }
    renderFace(this);
    if (swapped) this._lcDualRefresh();
  };
  if (!node.size || node.size[0] < DEFAULT_W) node.setSize([DEFAULT_W, node.size?.[1] || 420]);
  applyManual(node);
  renderFace(node);
  node._lcDualRefresh();
}

// ---------------------------------------------------------------- download safeguard (like LC Model Optimizer's)
function pendingDownloads() {
  const out = [];
  const root = app.rootGraph || app.graph;
  const graphs = [root, ...(root?.subgraphs?.values?.() || [])];
  for (const n of graphs.flatMap((g) => g?._nodes || [])) {
    if (n.comfyClass !== CLASS || n.mode === 2 || n.mode === 4) continue;
    const pl = n._lcDualPlan;
    const rows = [...(pl?.files || []), ...(pl?.slots || []).filter((s) => s.on).flatMap((s) => s.files || [])];
    for (const f of rows) if (f.state === "download") out.push({ file: baseName(f.label), gb: f.gb });
  }
  return out;
}

function guardQueue() {
  if (app._lcDualGuard) return;
  app._lcDualGuard = true;
  const orig = app.queuePrompt;
  app.queuePrompt = async function (...args) {
    const list = pendingDownloads();
    if (list.length) {
      const total = list.reduce((t, x) => t + (Number(x.gb) || 0), 0);
      const msg = `This run downloads ${list.length === 1 ? "a file" : `${list.length} files`} you don't have yet (${total.toFixed(1)} GB) from Hugging Face:\n\n`
        + list.map((x) => `• ${x.file} (${x.gb ?? "?"} GB)`).join("\n")
        + "\n\nOnce it starts, cancel the run to stop it (the partial file is deleted). To skip the download, pick a file you already have in the LC Dual Model Optimizer node.";
      const dlg = app.extensionManager?.dialog;
      const ok = dlg?.confirm ? (await dlg.confirm({ title: "Download and run?", message: msg })) === true : window.confirm(msg);
      if (!ok) {
        try { app.extensionManager.toast.add({ severity: "info", summary: "LC Dual Model Optimizer", detail: "Run cancelled. Nothing was downloaded.", life: 3500 }); } catch (_) {}
        return false;
      }
    }
    return orig.apply(this, args);
  };
}

// ---------------------------------------------------------------- the pair check line under the node
function findNode(id) {
  const key = String(id).split(":").pop();
  const root = app.rootGraph || app.graph;
  const graphs = [root, ...(root?.subgraphs?.values?.() || [])];
  for (const g of graphs) {
    const n = g?.getNodeById?.(key) ?? g?.getNodeById?.(Number(key));
    if (n && (n.comfyClass || n.type) === CLASS) return n;
  }
  return null;
}

function wrapText(ctx, text, width) {
  const words = text.split(" ");
  const lines = [];
  let cur = "";
  for (const w of words) {
    const t = cur ? cur + " " + w : w;
    if (ctx.measureText(t).width > width && cur) { lines.push(cur); cur = w; } else cur = t;
  }
  if (cur) lines.push(cur);
  return lines.slice(0, 4);
}

api.addEventListener("lc_dual_optimizer_status", (e) => {
  const d = e.detail || {};
  const n = findNode(d.node);
  if (n) {
    n._lcDualStatus = { text: d.text, level: d.level };
    n.setDirtyCanvas?.(true, true);
  }
  if (d.level === "warn") {
    try { app.extensionManager?.toast?.add({ severity: "warn", summary: "LC Dual Model Optimizer", detail: d.text, life: 9000 }); } catch (_e) {}
  }
});

api.addEventListener("execution_start", () => {
  const root = app.rootGraph || app.graph;
  for (const n of root?._nodes || []) {
    if (n._lcDualStatus) { n._lcDualStatus = null; n.setDirtyCanvas?.(true, true); }
  }
});

app.registerExtension({
  name: "LC123.DualOptimizerNode",
  setup() { guardQueue(); },
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== CLASS) return;
    const draw = nodeType.prototype.onDrawForeground;
    nodeType.prototype.onDrawForeground = function (ctx) {
      const r = draw?.apply(this, arguments);
      const st = this._lcDualStatus;
      if (!st || this.flags?.collapsed) return r;
      ctx.save();
      ctx.font = "12px sans-serif";
      ctx.fillStyle = STATUS_COLORS[st.level] || STATUS_COLORS.info;
      ctx.textAlign = "left";
      wrapText(ctx, st.text, Math.max(160, this.size[0] - 8)).forEach((ln, i) => ctx.fillText(ln, 4, this.size[1] + 16 + i * 15));
      ctx.restore();
      return r;
    };
  },
  nodeCreated(node) { if (node.comfyClass === CLASS) setup(node); },
  loadedGraphNode(node) {
    if (node.comfyClass !== CLASS) return;
    setup(node);
    applyManual(node);
    node._lcDualRefresh?.();
  },
});
