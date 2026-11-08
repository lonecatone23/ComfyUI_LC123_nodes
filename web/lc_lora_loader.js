/**
 * LC LoRA Loader — a multi-row LoRA loader modeled on rgthree's Power Lora Loader, rebuilt to fix three things
 * in that node:
 *   1. It does not render in Nodes 2.0 -- rgthree draws each row with its own canvas-widget `draw()` method,
 *      which the Vue node renderer never calls. Every row here is real HTML in one addDOMWidget, the same
 *      approach already proven for LC Slider / LC Preview / LC Label in this pack.
 *   2. It re-centres on a cross-page paste -- rgthree's own `configure()` skips calling the normal position/size
 *      restoration whenever the incoming node's `id` is null, which is exactly what a paste into a different
 *      graph looks like. This node never overrides `configure()` and never touches `node.pos` at all; the
 *      default LiteGraph restore path runs untouched, and only the row list and size are our own doing.
 *   3. Its "Info" menu item never populated anything (it depends on rgthree's own civitai-info cache). Info here
 *      reads the LoRA file's own safetensors header for trigger words -- a local file read, no network call --
 *      and whether the button shows up at all is one global toggle in Settings -> LC123 -> Performance, not a
 *      per-node menu item.
 *
 * Row state lives in the hidden `lora_rows` STRING widget as JSON: [{on, lora, strength}, ...]. That widget is
 * what gets serialized and sent to Python; everything drawn here is just a face on top of it, same pattern as
 * LC Slider's hidden value/min/max/step/decimals widgets.
 *
 * This same face also drives LC LoRA Loader Stack (lc_lora_stack.py), modeled on Comfyroll's CR LoRA Stack:
 * identical rows, identical dropdown, identical Info button, just with no model/clip sockets -- it outputs a
 * LORA_STACK instead, for LC Apply LoRA Stack to apply to one or more model/clip pairs. NODES below lists
 * every node type this file drives; both get the exact same treatment.
 */
import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { lcApplyLaunchColor } from "./lc_color.js";

// LC LoRA Loader Stack (lc_lora_stack.py) shares this exact face -- same rows, same subfolder-grouped
// dropdown, same Info button -- it just has no model/clip sockets. Both node types are driven from here.
const NODES = new Set(["LCLoraLoader", "LCLoraLoaderStack", "LCLoraLoaderSingle"]);
// LC LoRA Loader (single): the same row, always exactly one, without the header, add, drag handle and remove
const isSingle = (node) => (node?.comfyClass || node?.type) === "LCLoraLoaderSingle";
const ROW_H = 28;
const HEADER_H = 24;
const FOOTER_H = 28;
const PAD = 8;
const MIN_W = 280;

// ---- the available LoRA list (fetched once, shared by every node instance) ----
let loraListPromise = null;
function getLoraList() {
  if (!loraListPromise) {
    const p = api
      .fetchApi("/object_info/LoraLoader")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((info) => {
        const spec = info?.LoraLoader?.input?.required?.lora_name;
        const list = Array.isArray(spec?.[0]) ? spec[0] : spec?.[0] === "COMBO" ? spec[1]?.options : null;
        return Array.isArray(list) ? list : [];
      })
      .catch(() => [])
      .then((list) => {
        // a failed or empty answer is not remembered: the next open asks the server again
        if (!list.length && loraListPromise === p) loraListPromise = null;
        return list;
      });
    loraListPromise = p;
  }
  return loraListPromise;
}

// ComfyUI "Refresh Node Definitions" (R): forget the cached list and folder tree so new LoRA files show up
function resetLoraCache() {
  loraListPromise = null;
  loraTreeCache = null;
}

// A folder can nest arbitrarily deep ("Qwen/Lightning & Model loras/image lightning loRa"), which a plain
// <select><optgroup> can't represent (no nested optgroups) -- built once into a real tree so the picker
// popover below can drill down through it the way rgthree's own lora chooser does.
let loraTreeCache = null;
// Remembered across rows and across nodes for this page session, so picking several LoRAs out of the
// same project folder doesn't mean re-drilling from the root every time.
let lastLoraPath = [];
function buildLoraTree(list) {
  if (loraTreeCache) return loraTreeCache;
  const root = { files: [], folders: new Map() };
  for (const name of list) {
    const parts = name.replace(/\\/g, "/").split("/");
    let node = root;
    for (let i = 0; i < parts.length - 1; i++) {
      const seg = parts[i];
      if (!node.folders.has(seg)) node.folders.set(seg, { files: [], folders: new Map() });
      node = node.folders.get(seg);
    }
    node.files.push(name);
  }
  if (list.length) loraTreeCache = root; // an empty (failed) list is not cached
  return root;
}

// A new row starts in the folder last opened in the picker (or, after a reload, the folder of this node's last
// LoRA), not on the alphabetically first file of the whole list. Falls back to a file further down that folder,
// then to the first LoRA overall.
function defaultLoraFor(node, list) {
  let folder = lastLoraPath;
  if (!folder.length) {
    const prev = [...getRows(node)].reverse().find((r) => r.lora && r.lora !== "None");
    if (prev) folder = prev.lora.replace(/\\/g, "/").split("/").slice(0, -1);
  }
  if (folder.length) {
    let level = buildLoraTree(list);
    for (const seg of folder) level = level?.folders.get(seg);
    if (level) {
      const here = [...level.files].sort((a, b) => a.localeCompare(b));
      if (here.length) return here[0];
      const prefix = folder.join("/") + "/";
      const below = list.filter((n) => n.replace(/\\/g, "/").startsWith(prefix)).sort((a, b) => a.localeCompare(b));
      if (below.length) return below[0];
    }
  }
  return list[0] || "None";
}

// ---- strength control: rgthree Power Lora Loader's <arrow number arrow>, ported to DOM/pointer events
// (rgthree draws it on canvas with its own hit-area framework, which this file doesn't have -- same visual
// layout and the same two interactions: click an arrow to step by 0.05, or click-drag the number itself
// left/right to scrub it continuously. A plain click with no movement opens it for typing an exact value.
const STRENGTH_STEP = 0.05;
const STRENGTH_DRAG_RATE = 0.05; // value change per pixel of horizontal drag, matches rgthree's own rate

function ensureStrengthStyle() {
  if (document.getElementById("lc123-lora-strength-style")) return;
  const st = document.createElement("style");
  st.id = "lc123-lora-strength-style";
  st.textContent = `
.lc-lora-strength{display:flex;align-items:center;flex:0 0 auto;gap:0;background:#1e1e1e;border:1px solid #444;border-radius:4px;overflow:hidden;}
.lc-lora-str-arrow{width:16px;height:22px;line-height:22px;padding:0;background:#2a2a2a;color:#9cf;border:none;cursor:pointer;font-size:9px;flex:0 0 16px;}
.lc-lora-str-arrow:hover{background:#3a3a3a;}
.lc-lora-str-value{width:46px;flex:0 0 46px;text-align:center;cursor:ew-resize;user-select:none;font:12px Arial,sans-serif;color:#ddd;line-height:22px;}
.lc-lora-str-edit{width:46px;flex:0 0 46px;text-align:center;font:12px Arial,sans-serif;color:#fff;background:#111;border:none;padding:0;}
`;
  document.head.appendChild(st);
}

function makeStrengthControl(node, index) {
  return makeStrength(
    () => Number(getRows(node)[index]?.strength ?? 1),
    (v) => {
      const rs = getRows(node);
      if (!rs[index]) return;
      rs[index].strength = v;
      setRows(node, rs, { rerender: false });
    }
  );
}

/** The <◀ value ▶> strength control on its own: get() reads the value, set(v) stores it (shared with other LC
 * packs through window.LC123LoraUI, e.g. LC AV Showrunner's shot LoRAs). */
function makeStrength(get, set) {
  ensureStrengthStyle();
  const wrap = document.createElement("div");
  wrap.className = "lc-lora-strength";

  const dec = document.createElement("button");
  dec.type = "button";
  dec.className = "lc-lora-str-arrow";
  dec.textContent = "◀";
  dec.title = `-${STRENGTH_STEP} (drag the number to scrub, click it to type an exact value)`;

  const valueEl = document.createElement("div");
  valueEl.className = "lc-lora-str-value";

  const inc = document.createElement("button");
  inc.type = "button";
  inc.className = "lc-lora-str-arrow";
  inc.textContent = "▶";
  inc.title = `+${STRENGTH_STEP} (drag the number to scrub, click it to type an exact value)`;

  wrap.append(dec, valueEl, inc);

  const getValue = () => Number(get() ?? 1);
  const commit = (v) => set(Math.round(v * 100) / 100);
  const render = () => {
    valueEl.textContent = getValue().toFixed(2);
  };
  render();

  dec.addEventListener("click", (e) => {
    e.stopPropagation();
    commit(getValue() - STRENGTH_STEP);
    render();
  });
  inc.addEventListener("click", (e) => {
    e.stopPropagation();
    commit(getValue() + STRENGTH_STEP);
    render();
  });

  let dragging = false;
  let moved = false;
  let dragValue = 0;

  const onMove = (e) => {
    if (!dragging) return;
    if (e.movementX) {
      moved = true;
      dragValue += e.movementX * STRENGTH_DRAG_RATE;
      valueEl.textContent = dragValue.toFixed(2);
    }
  };
  const onUp = () => {
    window.removeEventListener("pointermove", onMove);
    window.removeEventListener("pointerup", onUp);
    window.removeEventListener("pointercancel", onUp);
    dragging = false;
    if (moved) {
      commit(dragValue);
      render();
    }
  };
  valueEl.addEventListener("pointerdown", (e) => {
    e.preventDefault();
    e.stopPropagation();
    dragging = true;
    moved = false;
    dragValue = getValue();
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    window.addEventListener("pointercancel", onUp); // a cancelled press (touch, alt-tab) ends the scrub too
  });
  valueEl.addEventListener("click", (e) => {
    e.stopPropagation();
    if (moved) return; // that pointerdown->up was a drag, not a click -- don't also open the editor
    startEditValue();
  });

  function startEditValue() {
    const input = document.createElement("input");
    input.type = "number";
    input.step = String(STRENGTH_STEP);
    input.className = "lc-lora-str-edit";
    input.value = getValue().toFixed(2);
    valueEl.replaceWith(input);
    input.focus();
    input.select();
    const done = (apply) => {
      input.replaceWith(valueEl);
      if (apply) {
        const v = parseFloat(input.value);
        if (Number.isFinite(v)) commit(v);
      }
      render();
    };
    input.addEventListener("keydown", (e) => {
      e.stopPropagation();
      if (e.key === "Enter") done(true);
      else if (e.key === "Escape") done(false);
    });
    input.addEventListener("blur", () => done(true));
  }

  return { wrap, render };
}

// ---- trigger-word chip styling (hover + copied state need a real stylesheet, not inline styles) ----
function ensureChipStyle() {
  if (document.getElementById("lc123-lora-chip-style")) return;
  const st = document.createElement("style");
  st.id = "lc123-lora-chip-style";
  st.textContent = `
.lc-lora-chip{background:#2a2a2a;border:1px solid #444;border-radius:10px;padding:2px 8px;cursor:pointer;
  transition:background .12s ease,border-color .12s ease,transform .08s ease;}
.lc-lora-chip:hover{background:#3a2f26;border-color:#6e5032;}
.lc-lora-chip:active{transform:scale(0.94);}
.lc-lora-chip.lc-copied{background:#6e5032;border-color:#8a6a45;color:#fff;}
`;
  document.head.appendChild(st);
}

// ---- the Info popover reads the file's own header; cache per lora name for the session ----
const infoCache = new Map();
function fetchLoraInfo(name) {
  if (infoCache.has(name)) return Promise.resolve(infoCache.get(name));
  return api
    .fetchApi(`/lc123/lora_loader/info?lora=${encodeURIComponent(name)}`)
    .then((r) => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    })
    .then((data) => {
      if (data && !data.error) infoCache.set(name, data); // errors are retried on the next open
      return data || { error: "empty response" };
    })
    .catch((e) => ({ error: String(e) }));
}

function infoEnabled() {
  try {
    return window.LC123Perf?.get?.(window.LC123Perf.ID?.loraInfo, true) !== false;
  } catch (_) {
    return true;
  }
}

function widget(node, name) {
  return (node.widgets || []).find((w) => w && w.name === name);
}

function getRows(node) {
  const w = widget(node, "lora_rows");
  try {
    const v = JSON.parse(w?.value || "[]");
    return Array.isArray(v) ? v : [];
  } catch (_) {
    return [];
  }
}

function setRows(node, rows, { rerender = true } = {}) {
  const w = widget(node, "lora_rows");
  if (w) w.value = JSON.stringify(rows);
  if (rerender) renderRows(node);
  growToFit(node);
  try {
    app.extensionManager?.workflow?.activeWorkflow?.changeTracker?.checkState?.();
  } catch (_) {}
}

function hideRowsWidget(node) {
  const w = widget(node, "lora_rows");
  if (!w || w._lcHidden) return;
  w._lcHidden = true;
  w.type = "hidden";
  w.computeSize = () => [0, -4];
  try {
    w.hidden = true;
  } catch (_) {}
  if (w.options) w.options.hidden = true;
}

function desiredHeight(node) {
  if (isSingle(node)) return ROW_H + PAD * 2;
  const rows = getRows(node);
  return HEADER_H + Math.max(rows.length, 0) * ROW_H + FOOTER_H + PAD * 2;
}

function growToFit(node) {
  if (!node.__lcFace) return;
  node.__lcFace.wrap.style.height = desiredHeight(node) + "px";
  const min = node.computeSize();
  if (node.size[1] < min[1] - 0.5) node.setSize([node.size[0], min[1]]);
  node.setDirtyCanvas?.(true, true);
}

// ---- the Info popover ----
let openPopover = null;
function closePopover() {
  if (openPopover) {
    openPopover.remove();
    openPopover = null;
  }
}
function showInfoPopover(anchorEl, name) {
  closePopover();
  const pop = document.createElement("div");
  pop.style.cssText =
    "position:fixed;z-index:10001;background:#1a1a1a;border:1px solid #555;border-radius:8px;padding:12px 14px;" +
    "color:#eee;font:12px Arial,sans-serif;max-width:340px;box-shadow:0 8px 24px rgba(0,0,0,.6);";
  pop.textContent = "Loading…";
  document.body.appendChild(pop);
  openPopover = pop;

  const r = anchorEl.getBoundingClientRect();
  const place = () => {
    let x = r.left;
    let y = r.bottom + 6;
    if (x + pop.offsetWidth > window.innerWidth - 10) x = window.innerWidth - pop.offsetWidth - 10;
    if (y + pop.offsetHeight > window.innerHeight - 10) y = r.top - pop.offsetHeight - 6;
    pop.style.left = Math.max(10, x) + "px";
    pop.style.top = Math.max(10, y) + "px";
  };
  place();

  const onDocDown = (e) => {
    if (!pop.contains(e.target) && e.target !== anchorEl) {
      closePopover();
      document.removeEventListener("pointerdown", onDocDown, true);
    }
  };
  document.addEventListener("pointerdown", onDocDown, true);

  fetchLoraInfo(name).then((data) => {
    if (openPopover !== pop) return; // closed while loading
    pop.innerHTML = "";
    const title = document.createElement("div");
    title.textContent = name;
    title.style.cssText = "font-weight:bold;margin-bottom:8px;word-break:break-all;color:#fff;";
    pop.appendChild(title);

    if (data.error) {
      const p = document.createElement("div");
      p.textContent = data.error;
      p.style.color = "#e88";
      pop.appendChild(p);
    } else {
      if (data.base_model) {
        const p = document.createElement("div");
        const b = document.createElement("b");
        b.textContent = "Base model:";
        p.append(b, document.createTextNode(` ${data.base_model}`));
        p.style.marginBottom = "6px";
        pop.appendChild(p);
      }
      const words = data.trigger_words || [];
      const label = document.createElement("div");
      label.textContent = "Trigger words:";
      label.style.cssText = "color:#9a9;margin-bottom:4px;";
      pop.appendChild(label);
      if (words.length) {
        ensureChipStyle();
        const list = document.createElement("div");
        list.style.cssText = "display:flex;flex-wrap:wrap;gap:4px;";
        for (const w of words) {
          const chip = document.createElement("span");
          chip.className = "lc-lora-chip";
          chip.textContent = w;
          chip.title = "Click to copy";
          let resetTimer = null;
          chip.addEventListener("click", () => {
            navigator.clipboard?.writeText(w).catch(() => {});
            clearTimeout(resetTimer);
            chip.classList.add("lc-copied");
            chip.textContent = "✓ copied";
            resetTimer = setTimeout(() => {
              chip.classList.remove("lc-copied");
              chip.textContent = w;
            }, 650);
          });
          list.appendChild(chip);
        }
        pop.appendChild(list);
      } else {
        const p = document.createElement("div");
        p.textContent = data.has_metadata
          ? "This file has no trigger words recorded in its own metadata."
          : "This file carries no metadata at all.";
        p.style.color = "#999";
        pop.appendChild(p);
      }
    }
    place();
  });
}

// ---- the LoRA picker: a folder-drill-down popup (rgthree's chooser), not a native <select> ----
let openLoraPicker = null;
function closeLoraPicker() {
  if (openLoraPicker) {
    openLoraPicker.panel.remove();
    document.removeEventListener("pointerdown", openLoraPicker.onDocDown, true);
    document.removeEventListener("keydown", openLoraPicker.onKey, true);
    openLoraPicker = null;
  }
}

function showLoraPickerPopover(anchorEl, node, index) {
  pickLora(anchorEl, () => getRows(node)[index]?.lora, (fullName) => {
    const rs = getRows(node);
    rs[index].lora = fullName;
    setRows(node, rs);
  });
}

/** The folder drill-down LoRA picker on its own: current() names the selected file, onSelect(fullName) takes the
 * pick (shared with other LC packs through window.LC123LoraUI). */
function pickLora(anchorEl, current, onSelect) {
  closeLoraPicker();
  closePopover();

  const panel = document.createElement("div");
  panel.style.cssText =
    "position:fixed;z-index:10002;background:#1a1a1a;border:1px solid #555;border-radius:8px;" +
    "box-shadow:0 12px 32px rgba(0,0,0,.6);width:360px;max-width:92vw;display:flex;flex-direction:column;" +
    "font:12px Arial,sans-serif;color:#ddd;overflow:hidden;";

  const header = document.createElement("div");
  header.style.cssText = "padding:8px 10px;border-bottom:1px solid #333;display:flex;flex-direction:column;gap:6px;";
  const titleRow = document.createElement("div");
  titleRow.style.cssText = "display:flex;align-items:center;justify-content:space-between;";
  const title = document.createElement("div");
  title.textContent = "Choose a LoRA";
  title.style.cssText = "font-weight:bold;color:#fff;";
  const closeBtn = document.createElement("button");
  closeBtn.textContent = "✕";
  closeBtn.style.cssText = "background:none;border:none;color:#999;cursor:pointer;font-size:13px;padding:0 2px;";
  closeBtn.addEventListener("click", closeLoraPicker);
  titleRow.append(title, closeBtn);

  const search = document.createElement("input");
  search.type = "text";
  search.placeholder = "Search…";
  search.style.cssText =
    "width:100%;box-sizing:border-box;background:#111;color:#eee;border:1px solid #444;border-radius:5px;padding:5px 7px;";
  header.append(titleRow, search);

  const crumbBar = document.createElement("div");
  crumbBar.style.cssText =
    "padding:4px 10px;border-bottom:1px solid #2a2a2a;display:flex;flex-wrap:wrap;align-items:center;gap:4px;font-size:11px;min-height:16px;";

  const listEl = document.createElement("div");
  listEl.style.cssText = "max-height:320px;overflow-y:auto;padding:4px 0;";

  panel.append(header, crumbBar, listEl);
  document.body.appendChild(panel);

  const place = () => {
    const r = anchorEl.getBoundingClientRect();
    let x = r.left;
    let y = r.bottom + 4;
    const pw = panel.offsetWidth || 360;
    const ph = panel.offsetHeight || 200;
    if (x + pw > window.innerWidth - 10) x = window.innerWidth - pw - 10;
    if (y + ph > window.innerHeight - 10) y = Math.max(10, r.top - ph - 4);
    panel.style.left = Math.max(10, x) + "px";
    panel.style.top = Math.max(10, y) + "px";
  };

  let path = [...lastLoraPath]; // start where the last picker (any row, any node) left off

  const currentLora = () => current();

  const select = (fullName) => {
    closeLoraPicker();
    onSelect(fullName);
  };

  const makeRowEl = () => {
    const r = document.createElement("div");
    r.style.cssText =
      "display:flex;align-items:center;gap:6px;padding:6px 10px;cursor:pointer;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;";
    r.addEventListener("mouseenter", () => (r.style.background = "#2a2a2a"));
    r.addEventListener("mouseleave", () => (r.style.background = ""));
    return r;
  };

  const emptyRow = (text) => {
    const e = document.createElement("div");
    e.textContent = text;
    e.style.cssText = "padding:10px;color:#999;";
    return e;
  };

  function renderCrumbs() {
    crumbBar.innerHTML = "";
    const crumb = (label, onClick, isLast) => {
      const b = document.createElement("span");
      b.textContent = label;
      b.style.cssText = isLast ? "color:#ddd;" : "color:#7ab;cursor:pointer;text-decoration:underline;";
      if (!isLast) b.addEventListener("click", onClick);
      return b;
    };
    const sep = () => {
      const s = document.createElement("span");
      s.textContent = "/";
      s.style.color = "#555";
      return s;
    };
    crumbBar.appendChild(
      crumb(
        "All",
        () => {
          path = [];
          renderList();
        },
        path.length === 0
      )
    );
    path.forEach((seg, i) => {
      crumbBar.appendChild(sep());
      crumbBar.appendChild(
        crumb(
          seg,
          () => {
            path = path.slice(0, i + 1);
            renderList();
          },
          i === path.length - 1
        )
      );
    });
  }

  function renderList() {
    lastLoraPath = path;
    renderCrumbs();
    listEl.innerHTML = "";
    getLoraList().then((list) => {
      if (!list.length) {
        listEl.appendChild(emptyRow("No LoRAs found."));
        place();
        return;
      }
      const tree = buildLoraTree(list);
      let level = tree;
      for (const seg of path) level = level.folders.get(seg) || { files: [], folders: new Map() };
      const folderNames = [...level.folders.keys()].sort((a, b) => a.localeCompare(b));
      for (const fname of folderNames) {
        const r = makeRowEl();
        const icon = document.createElement("span");
        icon.textContent = "📁";
        icon.style.opacity = "0.85";
        const label = document.createElement("span");
        label.textContent = fname;
        label.title = fname;
        label.style.cssText = "flex:1 1 auto;overflow:hidden;text-overflow:ellipsis;";
        const chevron = document.createElement("span");
        chevron.textContent = "›";
        chevron.style.color = "#777";
        r.append(icon, label, chevron);
        r.addEventListener("click", () => {
          path = [...path, fname];
          renderList();
        });
        listEl.appendChild(r);
      }
      const files = [...level.files].sort((a, b) => a.localeCompare(b));
      const cur = currentLora();
      for (const full of files) {
        const base = full.replace(/\\/g, "/").split("/").pop();
        const r = makeRowEl();
        r.textContent = base;
        r.title = base;
        if (full === cur) {
          r.style.color = "#fff";
          r.style.fontWeight = "bold";
        }
        r.addEventListener("click", () => select(full));
        listEl.appendChild(r);
      }
      if (!folderNames.length && !files.length) listEl.appendChild(emptyRow("Empty folder."));
      place();
    });
  }

  function renderSearch(q) {
    crumbBar.innerHTML = "";
    const label = document.createElement("span");
    label.textContent = `Search results for "${q}"`;
    label.style.color = "#9ab";
    crumbBar.appendChild(label);
    listEl.innerHTML = "";
    getLoraList().then((list) => {
      const ql = q.toLowerCase();
      const matches = list.filter((n) => n.toLowerCase().includes(ql)).sort((a, b) => a.localeCompare(b));
      if (!matches.length) {
        listEl.appendChild(emptyRow("No matches."));
        place();
        return;
      }
      const cur = currentLora();
      for (const full of matches.slice(0, 200)) {
        const r = makeRowEl();
        r.textContent = full.replace(/\\/g, "/");
        if (full === cur) {
          r.style.color = "#fff";
          r.style.fontWeight = "bold";
        }
        r.title = r.textContent;
        r.addEventListener("click", () => select(full));
        listEl.appendChild(r);
      }
      place();
    });
  }

  search.addEventListener("input", () => {
    const q = search.value.trim();
    if (q) renderSearch(q);
    else renderList();
  });

  const onDocDown = (e) => {
    if (!panel.contains(e.target) && e.target !== anchorEl) closeLoraPicker();
  };
  const onKey = (e) => {
    if (e.key === "Escape") closeLoraPicker();
  };
  document.addEventListener("pointerdown", onDocDown, true);
  document.addEventListener("keydown", onKey, true);
  openLoraPicker = { panel, onDocDown, onKey };

  renderList();
  requestAnimationFrame(() => {
    place();
    search.focus();
  });
}

// Shared with the other LC packs (LC AV Showrunner's 🎛 shot LoRAs): the same folder picker, strength control and
// Info popover as this node, so a LoRA is picked the same way everywhere.
window.LC123LoraUI = { pickLora, makeStrength, showInfoPopover, infoEnabled, getLoraList };

// ---- rows ----
function ensureFace(node) {
  if (node.__lcFace) return node.__lcFace;

  const wrap = document.createElement("div");
  wrap.style.cssText = `width:100%;box-sizing:border-box;display:flex;flex-direction:column;font:12px Arial,sans-serif;color:#ddd;`;

  const header = document.createElement("div");
  header.style.cssText = `height:${HEADER_H}px;flex:0 0 ${HEADER_H}px;display:flex;align-items:center;gap:6px;padding:0 ${PAD}px;`;
  const toggleAll = document.createElement("input");
  toggleAll.type = "checkbox";
  toggleAll.title = "Toggle all";
  const headerLabel = document.createElement("div");
  headerLabel.style.cssText = "flex:1;color:#9a9;user-select:none;";
  header.append(toggleAll, headerLabel);
  wrap.appendChild(header);

  const rowsHost = document.createElement("div");
  rowsHost.style.cssText = "flex:1 1 auto;display:flex;flex-direction:column;overflow:visible;";
  wrap.appendChild(rowsHost);

  const footer = document.createElement("div");
  footer.style.cssText = `height:${FOOTER_H}px;flex:0 0 ${FOOTER_H}px;padding:2px ${PAD}px;`;
  const addBtn = document.createElement("button");
  addBtn.textContent = "➕ Add LoRA";
  addBtn.style.cssText =
    "width:100%;height:100%;background:#2a2a2a;color:#ddd;border:1px solid #444;border-radius:5px;cursor:pointer;font:12px Arial,sans-serif;";
  addBtn.addEventListener("click", async () => {
    const list = await getLoraList();
    const rows = getRows(node);
    rows.push({ on: true, lora: defaultLoraFor(node, list), strength: 1.0 });
    setRows(node, rows);
  });
  footer.appendChild(addBtn);
  wrap.appendChild(footer);

  toggleAll.addEventListener("change", () => {
    const rows = getRows(node).map((r) => ({ ...r, on: toggleAll.checked }));
    setRows(node, rows);
  });

  const dom = node.addDOMWidget("lc_lora_face", "LC_LORA_FACE", wrap, {
    getMinHeight: () => desiredHeight(node),
    serialize: false,
  });
  dom.serializeValue = () => undefined;
  // the right side Parameters panel writes its own column width onto widgets it lists: always follow the node
  Object.defineProperty(dom, "width", { get: () => undefined, set: () => {}, configurable: true });

  if (isSingle(node)) {
    header.style.display = "none";
    footer.style.display = "none";
    rowsHost.style.padding = `${PAD}px 0`;
  }
  node.__lcFace = { wrap, header, headerLabel, toggleAll, rowsHost, addBtn };
  return node.__lcFace;
}

function makeRow(node, row, index, rows, dragState) {
  const el = document.createElement("div");
  el.style.cssText = `height:${ROW_H}px;flex:0 0 ${ROW_H}px;display:flex;align-items:center;gap:4px;padding:0 ${PAD}px;box-sizing:border-box;`;
  el.dataset.index = String(index);

  const handle = document.createElement("div");
  handle.textContent = "⋮⋮";
  handle.title = "Drag to reorder";
  handle.style.cssText = "cursor:grab;color:#777;width:12px;flex:0 0 12px;text-align:center;user-select:none;font-size:11px;line-height:1;";

  const on = document.createElement("input");
  on.type = "checkbox";
  on.checked = !!row.on;
  on.style.flex = "0 0 auto";
  on.addEventListener("change", () => {
    const rs = getRows(node);
    rs[index].on = on.checked;
    setRows(node, rs);
  });

  // A folder-drill-down popup (showLoraPickerPopover), not a native <select> -- rgthree's own lora
  // chooser works this way, and a plain <select><optgroup> can't represent nested subfolders anyway.
  const picker = document.createElement("div");
  picker.style.cssText =
    "flex:1 1 auto;min-width:0;background:#1e1e1e;color:#ddd;border:1px solid #444;border-radius:4px;" +
    "padding:2px 6px;cursor:pointer;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;user-select:none;";
  const refreshPickerLabel = () => {
    const name = getRows(node)[index]?.lora || row.lora;
    getLoraList().then((list) => {
      picker.textContent = name ? name : "(none)";
      if (name && list.length && !list.includes(name)) picker.textContent += "  [missing]";
      picker.title = picker.textContent; // the full name on hover when the box is too narrow to show it
    });
  };
  refreshPickerLabel();
  picker.addEventListener("click", (e) => {
    e.stopPropagation();
    showLoraPickerPopover(picker, node, index);
  });

  const strength = makeStrengthControl(node, index);

  el.append(...(isSingle(node) ? [] : [handle]), on, picker, strength.wrap);

  if (infoEnabled()) {
    const info = document.createElement("button");
    info.textContent = "ℹ";
    info.title = "Trigger words (from the file's own metadata)";
    info.style.cssText = "flex:0 0 20px;width:20px;height:20px;line-height:18px;padding:0;background:#2a2a2a;color:#9cf;border:1px solid #444;border-radius:4px;cursor:pointer;";
    info.addEventListener("click", (e) => {
      e.stopPropagation();
      showInfoPopover(info, getRows(node)[index]?.lora || row.lora);
    });
    el.appendChild(info);
  }

  const del = document.createElement("button");
  del.textContent = "✕";
  del.title = "Remove this LoRA";
  del.style.cssText = "flex:0 0 20px;width:20px;height:20px;line-height:18px;padding:0;background:#2a2a2a;color:#e88;border:1px solid #444;border-radius:4px;cursor:pointer;";
  del.addEventListener("click", () => {
    const rs = getRows(node);
    rs.splice(index, 1);
    setRows(node, rs);
  });
  if (!isSingle(node)) el.appendChild(del);

  // drag to reorder: a plain vertical list reorder among the sibling row elements, window-level pointer
  // listeners so a fast drag never loses the pointer even if it briefly leaves the row
  handle.addEventListener("pointerdown", (e) => {
    e.preventDefault();
    e.stopPropagation(); // the canvas must not start dragging the node as well
    const host = node.__lcFace.rowsHost;
    const rowEls = () => Array.from(host.children);
    handle.style.cursor = "grabbing";
    el.style.opacity = "0.5";
    const move = (ev) => {
      const siblings = rowEls();
      const myPos = siblings.indexOf(el);
      for (let i = 0; i < siblings.length; i++) {
        if (siblings[i] === el) continue;
        const r = siblings[i].getBoundingClientRect();
        if (ev.clientY > r.top && ev.clientY < r.bottom) {
          const target = Number(siblings[i].dataset.index);
          const from = Number(el.dataset.index);
          if (i < myPos) host.insertBefore(el, siblings[i]);
          else host.insertBefore(el, siblings[i].nextSibling);
          // renumber dataset.index to match the new visual order, then commit that order on release
          void target;
          void from;
          break;
        }
      }
    };
    const up = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      window.removeEventListener("pointercancel", up);
      handle.style.cursor = "grab";
      el.style.opacity = "1";
      // read the final DOM order back into the row array and commit it
      const order = rowEls();
      const rs = getRows(node);
      const newRows = order.map((rowEl) => rs[Number(rowEl.dataset.index)]);
      setRows(node, newRows);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
    window.addEventListener("pointercancel", up);
  });

  return el;
}

function renderRows(node) {
  const face = ensureFace(node);
  if (isSingle(node) && getRows(node).length !== 1) {
    // always exactly one row: a new node gets one (the usual default LoRA), extra rows are dropped
    const rs = getRows(node).slice(0, 1);
    if (rs.length) setRows(node, rs, { rerender: false });
    else {
      getLoraList().then((list) => {
        if (getRows(node).length === 0) setRows(node, [{ on: true, lora: defaultLoraFor(node, list), strength: 1.0 }]);
      });
    }
  }
  const rows = getRows(node);
  face.rowsHost.innerHTML = "";
  for (let i = 0; i < rows.length; i++) {
    face.rowsHost.appendChild(makeRow(node, rows[i], i, rows));
  }
  const enabled = rows.filter((r) => r.on).length;
  face.headerLabel.textContent = rows.length ? `${enabled}/${rows.length} active` : "No LoRAs yet";
  face.toggleAll.indeterminate = enabled > 0 && enabled < rows.length;
  face.toggleAll.checked = rows.length > 0 && enabled === rows.length;
  face.wrap.style.height = desiredHeight(node) + "px";
}

app.registerExtension({
  name: "LC123.LoraLoader",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (!NODES.has(nodeData?.name)) return;

    const onNodeCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const r = onNodeCreated?.apply(this, arguments);
      lcApplyLaunchColor(this, "#6e5032");
      hideRowsWidget(this);
      ensureFace(this);
      renderRows(this);
      if (!this.size || this.size[0] < MIN_W) this.setSize([MIN_W, this.computeSize()[1]]);
      if (isSingle(this)) this.setSize([Math.max(this.size[0], 360), this.computeSize()[1]]); // just the one row tall
      return r;
    };

    // never override configure() itself and never touch node.pos here -- the default LiteGraph restore path
    // (position, size, and the hidden lora_rows widget's saved value) must run completely untouched, which is
    // exactly the step rgthree's own configure() skips on a cross-page paste
    const onConfigure = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function () {
      const r = onConfigure?.apply(this, arguments);
      hideRowsWidget(this);
      ensureFace(this);
      renderRows(this);
      return r;
    };

    const getExtra = nodeType.prototype.getExtraMenuOptions;
    nodeType.prototype.getExtraMenuOptions = function (canvas, options) {
      getExtra?.apply(this, arguments);
      const node = this;
      if (isSingle(node)) return;
      options.push(
        { content: "Select all LoRAs", callback: () => setRows(node, getRows(node).map((r) => ({ ...r, on: true }))) },
        { content: "Deselect all LoRAs", callback: () => setRows(node, getRows(node).map((r) => ({ ...r, on: false }))) },
        { content: "Remove all LoRAs", callback: () => setRows(node, []) }
      );
    };
  },

  async nodeCreated(node) {
    if (!NODES.has(node.comfyClass || node.type)) return;
    ensureFace(node);
    renderRows(node);
  },

  async refreshComboInNodes() {
    resetLoraCache();
  },

  async setup() {
    // the Performance-settings toggle for the Info button applies live, to every open LC LoRA Loader /
    // LC LoRA Loader Stack node
    window.addEventListener("lc123-perf-changed", () => {
      try {
        const root = app.rootGraph || app.graph;
        for (const g of [root, ...(root?.subgraphs?.values?.() || [])]) { // loaders inside subgraphs too
          for (const n of g?._nodes || []) {
            if (NODES.has(n.comfyClass || n.type)) renderRows(n);
          }
        }
      } catch (_) {}
    });
  },
});
