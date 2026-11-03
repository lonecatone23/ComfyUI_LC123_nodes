/**
 * LC Weighted Prompt: the prompt as clickable words and one slider.
 *
 * Click a word (shift-click a second word for the whole phrase between them) and the slider under the words edits
 * it: from -1 to 2, the number can be dragged or double-clicked to type. Click another word and the slider moves to
 * that one. A weighted word reads "cat:1.5": bold green above 1, red below. ✕ (or back to 1) clears it.
 *
 * The weights live in the hidden `weights` STRING widget as JSON [{text, w}], matched to the prompt by words, so
 * a new prompt keeps the weight of every phrase still in it and drops the rest. 📋 copies the prompt, ✎ edits it.
 * The words come from the text box (or, when a link feeds
 * the box, from what it got on the last run: Python sends back `lc_prompt`).
 */
import { app } from "../../scripts/app.js";
import { lcApplyLaunchColor } from "./lc_color.js";

const NODE = "LCWeightedPrompt";
const ROW_H = 28;
const PAD = 8;
const MIN_W = 340;
const BOX_MAX = 170; // about 8 lines of words, then the box scrolls
const MIN_V = -1;
const MAX_V = 2;
const STEP = 0.05;
const GREEN = "#5fd35f";
const RED = "#ff6b6b";

const widget = (node, name) => node.widgets?.find((w) => w.name === name);
const norm = (s) => String(s || "").toLowerCase().replace(/\s+/g, " ").trim();
const fmt = (v) => (Math.round(v * 100) / 100).toFixed(2);
const short = (v) => String(Math.round(v * 100) / 100); // "1.5", "-0.5", "1.25": the inline "cat:1.5"

function getWeights(node) {
  try {
    const v = JSON.parse(widget(node, "weights")?.value || "[]");
    return Array.isArray(v) ? v.filter((r) => r && r.text) : [];
  } catch (_) {
    return [];
  }
}

function setWeights(node, rows) {
  const w = widget(node, "weights");
  if (w) w.value = JSON.stringify(rows.map((r) => ({ text: r.text, w: Math.round(r.w * 100) / 100 })));
  render(node);
  try {
    app.extensionManager?.workflow?.activeWorkflow?.changeTracker?.checkState?.();
  } catch (_) {}
}

const linked = (node, name) => node.inputs?.find((i) => i.name === name)?.link != null;
/** The box is fed from outside: the prompt socket, or (older wiring) a link into the box itself. */
const textLinked = (node) => linked(node, "prompt") || linked(node, "text");
/** The box can't be edited: a link straight into it. (Block on never: ✎ switches Block to on change first.) */
const locked = (node) => linked(node, "text");
const passThrough = (node) => linked(node, "prompt") && widget(node, "block")?.value === "never";

/**
 * Weights for phrases no longer in the prompt are dropped when the prompt changes: kept, they came back days later on
 * a new prompt that happened to use the word (2026-11-02, test words lit up on a new picture).
 */
function pruneTo(node, text) {
  const face = node.__lcPW;
  const t = String(text || "");
  if (!t.trim() || (face && face.seen === t)) return;
  if (face) face.seen = t;
  const rows = getWeights(node);
  const hit = new Set(wordRows(tokens(t), rows));
  const keep = rows.filter((r, k) => hit.has(k));
  if (keep.length !== rows.length) {
    const w = widget(node, "weights");
    if (w) w.value = JSON.stringify(keep.map((r) => ({ text: r.text, w: Math.round(r.w * 100) / 100 })));
  }
}

/** Copy text to the clipboard (the canvas eats Ctrl+C on the node). */
async function copyText(s) {
  try {
    await navigator.clipboard.writeText(s);
    return true;
  } catch (_) {
    const ta = Object.assign(document.createElement("textarea"), { value: s });
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand("copy");
    ta.remove();
    return ok;
  }
}

/**
 * The text box stays linkable but takes no room, and reports the word box's height as its own: its link socket is
 * placed by that, so a link lands beside the words. Hidden outright it had no row and its socket sat on top of clip.
 * The widget order stays as Python declares it (text, strength, weights): saved values follow that order.
 */
function tuckText(node) {
  const w = widget(node, "text");
  if (!w || w._lcTucked) return;
  w._lcTucked = true;
  w.computeSize = () => [0, 0];
  w.computeLayoutSize = () => ({ minHeight: 0, maxHeight: 0, minWidth: 0 });
  const el = w.element || w.inputEl;
  if (el?.style) el.style.display = "none";
  // the frontend's wrapper around the hidden box keeps a full-height, clickable frame that covers whatever sits
  // below the node (a note there could not be selected or dragged): let clicks pass through it
  el?.classList?.add("lc-wp-tucked");
  if (!document.getElementById("lc-wp-tucked-style")) {
    const st = document.createElement("style");
    st.id = "lc-wp-tucked-style";
    st.textContent = ".dom-widget:has(.lc-wp-tucked){pointer-events:none!important}";
    document.head.appendChild(st);
  }
  Object.defineProperty(w, "y", {
    // below the slider and hint rows, at the top of the word box
    get: () => (widget(node, "lc_weighted_prompt_face")?.y ?? 0) + ROW_H + (node.__lcPW?.hintRow.offsetHeight || 22) + 6,
    set: () => {},
    configurable: true,
  });
}

/** Saved values back onto their widgets by what they are: a number is strength, a [...] list the weights. */
function restoreValues(node, values) {
  if (!Array.isArray(values)) return;
  const vals = values.slice(0, 3);
  const isList = (v) => typeof v === "string" && /^\s*\[/.test(v);
  const strength = vals.find((v) => typeof v === "number" && isFinite(v));
  const weights = vals.find(isList);
  const text = vals.find((v) => typeof v === "string" && !isList(v));
  const set = (name, v) => {
    const w = widget(node, name);
    if (w && v !== undefined) w.value = v;
  };
  set("strength", strength ?? 1);
  set("weights", weights ?? "[]");
  set("text", text ?? "");
  const block = widget(node, "block");
  const ok = block?.options?.values?.includes(values[3]);
  set("block", ok ? values[3] : "on change");
  set("last_in", ok && typeof values[4] === "string" ? values[4] : "");
}

function hideWidget(w) {
  if (!w || w._lcHidden) return;
  w._lcHidden = true;
  w.type = "hidden";
  w.computeSize = () => [0, -4];
  try {
    w.hidden = true;
  } catch (_) {}
  if (w.options) w.options.hidden = true;
  const el = w.element || w.inputEl; // a multiline text box is a real element: hide it too
  if (el?.style) el.style.display = "none";
}

/** The prompt shown as words: the text box. */
function promptText(node) {
  const v = widget(node, "text")?.value;
  return typeof v === "string" && v ? v : node.__lcRunPrompt ?? v ?? "";
}

/** Words and the gaps between them: [{t: "word", word: true}, {t: ", ", word: false}, ...] */
function tokens(text) {
  const out = [];
  const re = /[\p{L}\p{N}][\p{L}\p{N}'’\-]*/gu;
  let pos = 0;
  for (const m of text.matchAll(re)) {
    if (m.index > pos) out.push({ t: text.slice(pos, m.index), word: false });
    out.push({ t: m[0], word: true });
    pos = m.index + m[0].length;
  }
  if (pos < text.length) out.push({ t: text.slice(pos), word: false });
  return out;
}

/** For every word token: the weight row it belongs to (longest phrase match wins), or -1. */
function wordRows(toks, rows) {
  const words = toks.map((t, i) => ({ i, w: norm(t.t), word: t.word })).filter((x) => x.word);
  const hit = new Array(toks.length).fill(-1);
  const order = rows.map((r, k) => ({ k, parts: norm(r.text).split(" ") })).sort((a, b) => b.parts.length - a.parts.length);
  for (const { k, parts } of order) {
    for (let s = 0; s + parts.length <= words.length; s++) {
      if (parts.every((p, j) => words[s + j].w === p) && words.slice(s, s + parts.length).every((x) => hit[x.i] === -1)) {
        for (let j = 0; j < parts.length; j++) hit[words[s + j].i] = k;
      }
    }
  }
  return hit;
}

function colorFor(v) {
  if (v > 1.0001) return GREEN;
  if (v < 0.9999) return RED;
  return "#ddd";
}

function ensureFace(node) {
  if (node.__lcPW) return node.__lcPW;
  const wrap = document.createElement("div");
  wrap.style.cssText = "width:100%;height:100%;box-sizing:border-box;display:flex;flex-direction:column;" +
    "font:12px Arial,sans-serif;color:#ddd;";
  const words = document.createElement("div");
  words.style.cssText = `padding:6px ${PAD}px;line-height:1.75;user-select:none;word-break:break-word;white-space:pre-wrap;` +
    "background:#1e1e1e;border:1px solid #444;border-radius:5px;margin:0 4px 4px;min-height:22px;" +
    "flex:1 1 auto;overflow-y:auto;box-sizing:border-box;"; // fills the node: stretch the node, the box grows
  // the same box turns into a text editor (double-click, or ✎): one box to type in and to weight in
  const editor = document.createElement("textarea");
  editor.style.cssText = `display:none;padding:6px ${PAD}px;line-height:1.75;font:12px Arial,sans-serif;color:#fff;resize:none;` +
    "background:#141414;border:1px solid #6a8;border-radius:5px;margin:0 4px 4px;min-height:22px;box-sizing:border-box;" +
    "width:calc(100% - 8px);flex:1 1 auto;overflow-y:auto;";
  editor.spellcheck = false;
  // the wheel scrolls a long prompt inside the box instead of zooming the canvas
  for (const el of [words, editor]) {
    el.addEventListener("wheel", (e) => {
      if (el.scrollHeight > el.clientHeight + 1) e.stopPropagation();
    }, { passive: true });
  }
  const hintRow = document.createElement("div");
  hintRow.style.cssText = `display:flex;align-items:center;gap:6px;padding:0 ${PAD}px 4px;`;
  const hint = document.createElement("div");
  hint.style.cssText = "flex:1;color:#888;font-size:11px;user-select:none;";
  const editBtn = document.createElement("button");
  editBtn.textContent = "✎";
  editBtn.title = "Edit the prompt (or double-click it)";
  editBtn.style.cssText = "flex:0 0 22px;width:22px;height:20px;line-height:18px;padding:0;background:#2a2a2a;color:#9cf;border:1px solid #444;border-radius:4px;cursor:pointer;";
  const copyBtn = document.createElement("button");
  copyBtn.textContent = "📋";
  copyBtn.title = "Copy the prompt";
  copyBtn.style.cssText = "flex:0 0 22px;width:22px;height:20px;line-height:18px;padding:0;background:#2a2a2a;border:1px solid #444;border-radius:4px;cursor:pointer;font-size:11px;";
  // Block always stopped the run on a new incoming prompt: this puts that prompt in the box
  const useBtn = document.createElement("button");
  useBtn.textContent = "Use new";
  useBtn.title = "Put the new incoming prompt in the box (your weights stay on the words still in it)";
  useBtn.style.cssText = "display:none;flex:0 0 auto;height:20px;line-height:18px;padding:0 6px;background:#2a2a2a;color:#fc6;border:1px solid #444;border-radius:4px;cursor:pointer;font-size:11px;";
  hintRow.append(hint, useBtn, copyBtn, editBtn);
  const rowsHost = document.createElement("div");
  rowsHost.style.cssText = "display:flex;flex-direction:column;";
  wrap.append(rowsHost, hintRow, words, editor);
  const dom = node.addDOMWidget("lc_weighted_prompt_face", "LC_WEIGHTED_PROMPT_FACE", wrap, {
    getMinHeight: () => node.__lcPW?.height || 60,
    serialize: false,
  });
  dom.serializeValue = () => undefined;
  Object.defineProperty(dom, "width", { get: () => undefined, set: () => {}, configurable: true });
  node.__lcPW = { wrap, words, editor, hintRow, hint, editBtn, copyBtn, useBtn, rowsHost, height: 60, anchor: null, sel: "", editing: false };
  useBtn.addEventListener("pointerdown", (e) => e.stopPropagation());
  copyBtn.addEventListener("pointerdown", (e) => e.stopPropagation());
  copyBtn.addEventListener("click", async (e) => {
    e.stopPropagation();
    const face = node.__lcPW;
    const s = face.editing ? face.editor.value : promptText(node);
    const ok = await copyText(s);
    copyBtn.textContent = ok ? "✓" : "✕";
    setTimeout(() => (copyBtn.textContent = "📋"), 900);
  });
  useBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    const t = widget(node, "text");
    if (t && node.__lcHoldIn != null) {
      t.value = node.__lcHoldIn;
      t.callback?.(t.value);
    }
    node.__lcHoldIn = undefined;
    node.__lcPW.sel = "";
    render(node);
    try {
      app.extensionManager?.workflow?.activeWorkflow?.changeTracker?.checkState?.();
    } catch (_) {}
  });
  editBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    if (node.__lcPW.editing) finishEdit(node, true);
    else startEdit(node);
  });
  words.addEventListener("dblclick", (e) => {
    e.stopPropagation();
    clearTimeout(node.__lcPW.clickTimer);
    startEdit(node);
  });
  words.addEventListener("click", () => {
    if (!promptText(node).trim()) startEdit(node); // an empty box: one click starts typing
  });
  words.addEventListener("pointerdown", (e) => e.stopPropagation());
  const grow = () => fit(node); // the edit box fills the same room as the words
  editor.addEventListener("input", grow);
  editor.addEventListener("pointerdown", (e) => e.stopPropagation());
  editor.addEventListener("keydown", (e) => {
    e.stopPropagation(); // typing must not trigger ComfyUI's shortcuts
    if (e.key === "Escape") finishEdit(node, false);
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) finishEdit(node, true);
  });
  editor.addEventListener("blur", () => finishEdit(node, true));
  editor.__grow = grow;
  // off screen the box measures 0 (a big workflow loads with the node out of view): size it again once it shows
  if (typeof ResizeObserver !== "undefined") {
    const ro = new ResizeObserver(() => fit(node));
    ro.observe(words);
    ro.observe(editor);
  }
  return node.__lcPW;
}

function startEdit(node) {
  const face = node.__lcPW;
  if (!face || face.editing || locked(node)) return; // fed straight into the box: edited where it comes from
  if (passThrough(node)) {
    // Block: never puts every incoming prompt over the box, so an edit would be gone on the next run. Editing
    // means keeping it: on change holds the edit until a different prompt comes in
    const b = widget(node, "block");
    b.value = "on change";
    b.callback?.(b.value);
  }
  face.editing = true;
  face.editor.value = promptText(node);
  face.words.style.display = "none";
  face.editor.style.display = "block";
  face.editBtn.textContent = "✓";
  face.editBtn.title = "Done (Ctrl+Enter). Escape cancels.";
  face.hint.textContent = "Type the prompt. Ctrl+Enter or click outside when done, Escape cancels.";
  face.editor.__grow();
  // a click anywhere outside the box finishes the edit (blur alone needs the box to have had focus)
  face.outside = (ev) => {
    if (ev.target !== face.editor && ev.target !== face.editBtn) finishEdit(node, true);
  };
  setTimeout(() => window.addEventListener("pointerdown", face.outside, true), 0);
  face.editor.focus();
  face.editor.setSelectionRange(face.editor.value.length, face.editor.value.length);
}

function finishEdit(node, keep) {
  const face = node.__lcPW;
  if (!face || !face.editing) return;
  face.editing = false;
  window.removeEventListener("pointerdown", face.outside, true);
  face.anchor = null; // the words moved: a half-made phrase start no longer points at the same word
  face.sel = "";
  if (keep) {
    const t = widget(node, "text");
    if (t && t.value !== face.editor.value) {
      t.value = face.editor.value;
      t.callback?.(t.value);
      try {
        app.extensionManager?.workflow?.activeWorkflow?.changeTracker?.checkState?.();
      } catch (_) {}
    }
  }
  face.editor.style.display = "none";
  face.words.style.display = "";
  face.editBtn.textContent = "✎";
  face.editBtn.title = "Edit the prompt (or double-click it)";
  render(node);
}

/** A row's value control: the number, drag left / right to change it, double-click to type. */
function makeNumber(get, set) {
  const box = document.createElement("div");
  box.style.cssText = "width:46px;flex:0 0 46px;text-align:center;cursor:ew-resize;user-select:none;font:12px Arial,sans-serif;" +
    "line-height:22px;background:#1e1e1e;border:1px solid #444;border-radius:4px;";
  const show = () => {
    const v = get();
    box.textContent = fmt(v);
    box.style.color = colorFor(v);
    box.style.fontWeight = v > 1.0001 ? "bold" : "normal";
  };
  show();
  box.addEventListener("pointerdown", (e) => {
    e.preventDefault();
    e.stopPropagation();
    const x0 = e.clientX;
    const v0 = get();
    const move = (ev) => set(Math.max(MIN_V, Math.min(MAX_V, Math.round((v0 + (ev.clientX - x0) / 100) / STEP) * STEP)));
    const up = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  });
  box.addEventListener("dblclick", (e) => {
    e.stopPropagation();
    const inp = document.createElement("input");
    inp.value = fmt(get());
    inp.style.cssText = "width:42px;text-align:center;font:12px Arial,sans-serif;color:#fff;background:#111;border:none;padding:0;";
    box.textContent = "";
    box.appendChild(inp);
    inp.focus();
    inp.select();
    const done = () => {
      const v = parseFloat(inp.value);
      if (!isNaN(v)) set(Math.max(MIN_V, Math.min(MAX_V, v)));
      else show();
    };
    inp.addEventListener("keydown", (ev) => {
      ev.stopPropagation();
      if (ev.key === "Enter") inp.blur();
      if (ev.key === "Escape") {
        inp.value = "";
        inp.blur();
      }
    });
    inp.addEventListener("blur", done);
  });
  return { box, show };
}

/** Set the selected phrase's weight: 1 takes the weight away. live = while dragging (no rebuild). */
function setSelected(node, v, live) {
  const face = node.__lcPW;
  if (!face?.sel) return;
  const rows = getWeights(node);
  const k = rows.findIndex((r) => norm(r.text) === norm(face.sel));
  if (Math.abs(v - 1) < 0.0001) {
    if (k >= 0) rows.splice(k, 1);
  } else if (k >= 0) {
    rows[k].w = v;
  } else {
    rows.push({ text: face.sel, w: v });
  }
  if (live) {
    const w = widget(node, "weights");
    if (w) w.value = JSON.stringify(rows.map((r) => ({ text: r.text, w: Math.round(r.w * 100) / 100 })));
    // a weight that just appeared or went away changes which words belong to it: re-render the words only
    if (k < 0 || Math.abs(v - 1) < 0.0001) renderWords(node);
    paint(node);
  } else {
    setWeights(node, rows);
  }
}

function selectedWeight(node) {
  const face = node.__lcPW;
  const r = face?.sel ? getWeights(node).find((x) => norm(x.text) === norm(face.sel)) : null;
  return r ? r.w : 1;
}

/** The one slider row: the selected phrase, the slider, the number, clear. */
function makeControl(node) {
  const el = document.createElement("div");
  el.style.cssText = `height:${ROW_H}px;flex:0 0 ${ROW_H}px;display:flex;align-items:center;gap:6px;padding:0 ${PAD}px;box-sizing:border-box;`;
  const label = document.createElement("div");
  label.style.cssText = "flex:0 1 38%;min-width:40px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;";
  const slider = document.createElement("input");
  slider.type = "range";
  slider.min = String(MIN_V);
  slider.max = String(MAX_V);
  slider.step = String(STEP);
  slider.style.cssText = "flex:1 1 auto;min-width:60px;";
  const num = makeNumber(() => selectedWeight(node), (v) => {
    setSelected(node, v, true);
    slider.value = String(v);
  });
  slider.addEventListener("input", () => setSelected(node, parseFloat(slider.value), true));
  slider.addEventListener("change", () => setWeights(node, getWeights(node)));
  slider.addEventListener("pointerdown", (e) => e.stopPropagation());
  const del = document.createElement("button");
  del.textContent = "✕";
  del.title = "Clear this weight (back to 1)";
  del.style.cssText = "flex:0 0 20px;width:20px;height:20px;line-height:18px;padding:0;background:#2a2a2a;color:#e88;border:1px solid #444;border-radius:4px;cursor:pointer;";
  del.addEventListener("click", (e) => {
    e.stopPropagation();
    setSelected(node, 1, false);
  });
  el.append(label, slider, num.box, del);
  el.__paint = () => {
    const sel = node.__lcPW?.sel || "";
    const v = selectedWeight(node);
    label.textContent = sel || "click a word";
    label.title = sel;
    label.style.color = sel ? colorFor(v) : "#777";
    label.style.fontWeight = v > 1.0001 ? "bold" : "normal";
    slider.disabled = !sel;
    del.disabled = !sel;
    num.box.style.opacity = sel ? "1" : "0.4";
    num.box.style.pointerEvents = sel ? "" : "none";
    if (document.activeElement !== slider) slider.value = String(v);
    num.show();
  };
  return el;
}

/** Recolour the words and rows without rebuilding them (while a slider moves). */
function paint(node) {
  const face = node.__lcPW;
  if (!face) return;
  const rows = getWeights(node);
  for (const span of face.words.querySelectorAll("span[data-row]")) {
    const k = Number(span.dataset.row);
    const v = k >= 0 ? rows[k]?.w ?? 1 : 1;
    span.style.color = k >= 0 ? colorFor(v) : "#ddd";
    span.style.fontWeight = k >= 0 && v > 1.0001 ? "bold" : "normal";
    const tag = span.querySelector("span.lc-w");
    if (tag) tag.textContent = k >= 0 && span.dataset.last === "1" && Math.abs(v - 1) > 0.0001 ? ":" + short(v) : "";
    span.style.outline = k >= 0 && face.sel && norm(rows[k]?.text) === norm(face.sel) ? "1px solid #9cf" : "";
  }
  face.control?.__paint?.();
}

function render(node) {
  const face = ensureFace(node);
  renderWords(node);
  if (!face.control) {
    face.control = makeControl(node);
    face.rowsHost.appendChild(face.control);
  }
  paint(node);
  fit(node);
}

function renderWords(node) {
  const face = ensureFace(node);
  const text = promptText(node);
  pruneTo(node, text);
  const rows = getWeights(node);
  const toks = tokens(text);
  const hit = wordRows(toks, rows);
  face.words.innerHTML = "";
  const wordIdx = [];
  toks.forEach((t, i) => {
    if (!t.word) {
      face.words.appendChild(document.createTextNode(t.t));
      return;
    }
    const span = document.createElement("span");
    span.textContent = t.t;
    span.dataset.row = String(hit[i]);
    span.dataset.tok = String(i);
    const next = toks.slice(i + 1).find((x) => x.word);
    const nextIdx = next ? toks.indexOf(next) : -1;
    span.dataset.last = hit[i] >= 0 && (nextIdx < 0 || hit[nextIdx] !== hit[i]) ? "1" : "0";
    span.style.cssText = "cursor:pointer;border-radius:3px;padding:0 1px;";
    const tag = document.createElement("span");
    tag.className = "lc-w";
    span.appendChild(tag);
    span.addEventListener("mouseenter", () => (span.style.background = "#333"));
    span.addEventListener("mouseleave", () => (span.style.background = ""));
    span.addEventListener("pointerdown", (e) => e.stopPropagation());
    span.addEventListener("click", (e) => {
      e.stopPropagation();
      if (e.detail > 1) return; // the second click of a double-click: that one edits
      const shift = e.shiftKey;
      clearTimeout(face.clickTimer);
      face.clickTimer = setTimeout(() => clickWord(node, toks, i, shift), 220);
    });
    face.words.appendChild(span);
    wordIdx.push(i);
  });
  if (!text.trim()) {
    face.words.style.color = "#777";
    face.words.textContent = textLinked(node) ? "Linked: the words show after a run." : "Click here to type a prompt.";
  } else {
    face.words.style.color = "#ddd";
  }
  face.editBtn.style.display = locked(node) ? "none" : "";
  face.editBtn.title = passThrough(node) ? "Edit the prompt: sets Block to on change, so your edit holds until a new prompt comes in"
    : "Edit the prompt (or double-click it)";
  face.copyBtn.style.display = text.trim() ? "" : "none";
  const held = node.__lcHoldIn != null && !face.editing;
  face.useBtn.style.display = held ? "" : "none";
  face.hint.style.color = held ? "#fc6" : "#888";
  if (held) face.hint.textContent = "Stopped: a new prompt came in. Edit if you like, then Run.";
  else if (!face.editing)
    face.hint.textContent = text.trim()
      ? "Click a word, then move the slider. Shift-click a second word for a phrase." + (locked(node) ? "" : " Double-click to edit.")
      : "";
}

function clickWord(node, toks, i, shift) {
  const face = node.__lcPW;
  const rows = getWeights(node);
  const hit = wordRows(toks, rows);
  if (shift && face.anchor != null && face.anchor !== i) {
    const [a, b] = face.anchor < i ? [face.anchor, i] : [i, face.anchor];
    const phrase = toks.slice(a, b + 1).map((t) => t.t).join("").replace(/\s+/g, " ").trim();
    // the first word's weight, if it had one of its own, moves to the whole phrase
    const k0 = hit[face.anchor];
    if (k0 >= 0 && norm(rows[k0].text) === norm(toks[face.anchor].t)) {
      const w0 = rows[k0].w;
      rows.splice(k0, 1);
      if (!rows.some((r) => norm(r.text) === norm(phrase))) rows.push({ text: phrase, w: w0 });
    }
    face.sel = phrase;
    face.anchor = null;
    setWeights(node, rows);
    return;
  }
  // a weighted word selects its whole phrase; any other word selects itself (weighted once the slider moves)
  face.sel = hit[i] >= 0 ? rows[hit[i]].text : toks[i].t;
  face.anchor = i;
  render(node);
}

/** Height the words need (up to BOX_MAX, then the box scrolls), in node units whatever the canvas zoom. */
function wordsNeed(face) {
  const el = face.words;
  if (!el.offsetHeight || !el.firstChild) return 22;
  const zoom = el.getBoundingClientRect().height / el.offsetHeight || 1;
  const range = document.createRange();
  range.selectNodeContents(el);
  const content = range.getBoundingClientRect().height / zoom;
  return Math.min(BOX_MAX, Math.ceil(content) + 14); // padding + border
}

function fit(node) {
  const face = node.__lcPW;
  if (!face) return;
  requestAnimationFrame(() => {
    if (!face.wrap.offsetHeight && !face.words.offsetHeight) return; // not on screen: the observer sizes it when it shows
    if (!face.editing) face.need = wordsNeed(face);
    const h = ROW_H + face.hintRow.offsetHeight + (face.need || 22) + 16;
    face.height = Math.max(60, h);
    // the node grows to fit the words; a node you stretched taller keeps its size and the box fills it
    const min = node.computeSize();
    if (node.size[1] < min[1] - 0.5) node.setSize([Math.max(node.size[0], MIN_W), min[1]]);
    node.setDirtyCanvas?.(true, true);
  });
}

function hookBlock(node) {
  const b = widget(node, "block");
  if (!b || b._lcHooked) return;
  b._lcHooked = true;
  const cb = b.callback;
  b.callback = function () {
    const r = cb?.apply(this, arguments);
    render(node);
    return r;
  };
}

function hookText(node) {
  const t = widget(node, "text");
  if (!t || t._lcPWHooked) return;
  t._lcPWHooked = true;
  const cb = t.callback;
  t.callback = function () {
    const r = cb?.apply(this, arguments);
    render(node);
    return r;
  };
  // typing in the box (the callback only fires on blur in some renderers)
  const el = t.element || t.inputEl;
  el?.addEventListener?.("input", () => {
    clearTimeout(node.__lcPWTimer);
    node.__lcPWTimer = setTimeout(() => render(node), 250);
  });
}


app.registerExtension({
  name: "LC123.WeightedPrompt",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData?.name !== NODE) return;

    const onNodeCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const r = onNodeCreated?.apply(this, arguments);
      lcApplyLaunchColor(this, "#232", "#353"); // LiteGraph's stock green
      hideWidget(widget(this, "weights"));
      hideWidget(widget(this, "last_in"));
      hookBlock(this);
      ensureFace(this);
      tuckText(this);
      hookText(this);
      render(this);
      if (!this.size || this.size[0] < MIN_W) this.setSize([MIN_W, this.computeSize()[1]]);
      return r;
    };

    const onConfigure = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function (info) {
      const r = onConfigure?.apply(this, arguments);
      // by content, not position: a copy saved while the widgets were briefly reordered loads right too
      restoreValues(this, info?.widgets_values);
      hideWidget(widget(this, "weights"));
      hideWidget(widget(this, "last_in"));
      hookBlock(this);
      ensureFace(this);
      tuckText(this);
      hookText(this);
      render(this);
      return r;
    };

    const onExecuted = nodeType.prototype.onExecuted;
    nodeType.prototype.onExecuted = function (message) {
      const r = onExecuted?.apply(this, arguments);
      if (Array.isArray(message?.lc_in)) {
        const last = widget(this, "last_in");
        if (last) last.value = String(message.lc_in[0] ?? "");
        this.__lcHoldIn = message.lc_hold ? String(message.lc_in[0] ?? "") : undefined;
        const t = widget(this, "text");
        if (message.lc_take?.[0] && t && t.value !== String(message.lc_prompt?.[0] ?? "")) {
          t.value = String(message.lc_prompt?.[0] ?? "");
          this.__lcPW && (this.__lcPW.sel = "");
        }
        this.__lcRunPrompt = undefined;
        render(this);
        try {
          app.extensionManager?.workflow?.activeWorkflow?.changeTracker?.checkState?.();
        } catch (_) {}
        return r;
      }
      // a text box fed by a link: show the words it got on this run
      if (Array.isArray(message?.lc_prompt) && widget(this, "text")?.value !== String(message.lc_prompt[0] ?? "")) {
        this.__lcRunPrompt = String(message.lc_prompt[0] ?? "");
        render(this);
      }
      return r;
    };

    const onConnectionsChange = nodeType.prototype.onConnectionsChange;
    nodeType.prototype.onConnectionsChange = function () {
      const r = onConnectionsChange?.apply(this, arguments);
      render(this);
      return r;
    };
  },
});
