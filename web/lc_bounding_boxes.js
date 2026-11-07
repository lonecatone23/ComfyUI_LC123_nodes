// LC Bounding Boxes 🔲: draw boxes on a picture for FLUX 3 (or anything that takes boxes). Drag on empty space for a new
// box, drag a box to move it, a corner to resize it. The box under the editor gets a name, what happens to it (new,
// change, move, remove) and a description. A move box has a second, dashed box: where it goes. The canvas and the editor
// are DOM widgets with fixed heights, so the node works the same in the classic canvas and in Nodes 2.0.
import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const TYPE = "LCBoundingBoxes";
const CANVAS_H = 330;
const EDITOR_H = 150;
const HANDLE = 8;
const KINDS = ["new", "change", "move", "remove"];
const COLORS = { new: "#5ac878", change: "#5aa0f0", move: "#f0b43c", remove: "#e65050" };

const W = (node, name) => (node.widgets || []).find((w) => w.name === name);

function hideWidget(widget) {
  if (!widget) return;
  widget.hidden = true;
  widget.computeSize = () => [0, -4];
  widget.serialize = true;
}

function load(node) {
  try {
    const v = JSON.parse(W(node, "boxes")?.value || "[]");
    return Array.isArray(v) ? v : [];
  } catch {
    return [];
  }
}

function save(node) {
  const w = W(node, "boxes");
  if (w) w.value = JSON.stringify(node._lcBb.boxes);
  node.setDirtyCanvas?.(true, true);
  // the next canvases in a chain show these boxes: redraw them too
  for (const n of bbNodes()) if (n !== node && n._lcBb) draw(n);
}

/** BFL ids as the Python side numbers them: name + index per name, text blocks En_Text_N. */
function ids(boxes) {
  const count = {};
  return boxes.map((b) => {
    const stem = b.type === "text" ? "En_Text" : (String(b.name || "object").toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "") || "object");
    count[stem] = (count[stem] || 0) + 1;
    return `${stem}_${count[stem]}`;
  });
}

function gridSize(node) {
  const custom = { w: Number(W(node, "width")?.value) || 1024, h: Number(W(node, "height")?.value) || 1024 };
  if (W(node, "size")?.value === "custom") return custom; // width / height win; the picture is stretched to fit
  return node._lcBb.size || custom;
}

// ---------------------------------------------------------------- background picture
function viewUrl(meta) {
  const q = new URLSearchParams();
  q.set("filename", meta.filename || "");
  q.set("subfolder", meta.subfolder ?? "");
  q.set("type", meta.type || "temp");
  return api.apiURL(`/view?${q.toString()}`);
}

function setBackground(node, url) {
  if (!url || node._lcBb.bgUrl === url) return;
  node._lcBb.bgUrl = url;
  const img = new Image();
  img.onload = () => {
    node._lcBb.bg = img;
    node._lcBb.size = { w: img.naturalWidth, h: img.naturalHeight };
    draw(node);
  };
  img.src = url;
}

const inactive = (n) => !n || n.mode === 2 || n.mode === 4;

/** The node that really feeds an input: through Reroutes and Get / Set nodes (KJ and rgthree style). */
function realSource(node, inputName, depth = 0) {
  const slot = node.inputs?.findIndex((i) => i.name === inputName || i.type === inputName);
  if (slot == null || slot < 0 || node.inputs[slot].link == null || depth > 20) return null;
  let src = node.getInputNode?.(slot);
  for (let hop = 0; src && hop < 20; hop++) {
    const t = src.type || "";
    if (/Reroute/i.test(t)) {
      const nxt = src.inputs?.[0]?.link != null ? src.getInputNode?.(0) : null;
      if (!nxt) return null;
      src = nxt;
    } else if (/GetNode/i.test(t)) {
      const key = src.widgets?.[0]?.value;
      const setter = (node.graph?._nodes || []).find((n) => /SetNode/i.test(n.type || "") && n.widgets?.[0]?.value === key);
      const nxt = setter?.inputs?.[0]?.link != null ? setter.getInputNode?.(0) : null;
      if (!nxt) return null;
      src = nxt;
    } else break;
  }
  return src || null;
}

/** Boxes from further up a chain of LC Bounding Boxes, read live from their canvases (no run needed). Other sources
 * (Create Bounding Boxes, a JSON) show what they sent on the last run. */
function upstreamBoxes(node, seen = new Set()) {
  if (seen.has(node.id)) return [];
  seen.add(node.id);
  const src = realSource(node, "bboxes");
  if (!src || inactive(src)) return [];
  if (src.type === TYPE || src.comfyClass === TYPE) {
    const own = src._lcBb ? src._lcBb.boxes : load(src);
    return [...upstreamBoxes(src, seen), ...(own || [])];
  }
  return node._lcBb?.runIncoming || [];
}

function clearBackground(node) {
  const st = node._lcBb;
  if (!st) return;
  st.bg = null;
  st.bgUrl = null;
  st.size = null;
}

/** The first picture up the chain from `src`: a node that has shown one, or a Load Image's file. Walks through nodes
 * that pass a picture on (crop, aspect ratio, bypassed ones) and through pipes (Pipe Out -> the image put in the pipe,
 * with Get / Set in between), so pipe workflows show their picture before a run. A muted node stops the walk. */
function findPicture(src, depth = 0, seen = new Set()) {
  if (!src || src.mode === 2 || depth > 16 || seen.has(src.id)) return null;
  seen.add(src.id);
  const shown = src.imgs?.[0]?.src;
  if (shown) return { url: shown };
  if (/LoadImage/i.test(src.type || "")) {
    const v = (src.widgets || []).find((w) => w.name === "image")?.value;
    return typeof v === "string" && v ? { file: v } : null;
  }
  const img = src.inputs?.find((i) => i.link != null && (i.type === "IMAGE" || i.name === "image" || i.name === "images"));
  if (img) {
    const got = findPicture(realSource(src, img.name), depth + 1, seen);
    if (got) return got;
  }
  return src.inputs?.some((i) => i.name === "pipe" && i.link != null) ? findPicture(realSource(src, "pipe"), depth + 1, seen) : null;
}

/** The picture upstream, shown before a run: a Load Image's file right away; any other node once it has shown a
 * picture, through pipes and pass-through nodes (findPicture). A bypassed or muted source means no picture. */
function upstreamPicture(node) {
  const slot = node.inputs?.findIndex((i) => i.name === "image");
  if (slot == null || slot < 0 || node.inputs[slot].link == null) return;
  const src = realSource(node, "image");
  if (inactive(src)) {
    clearBackground(node);
    return;
  }
  const found = findPicture(src);
  if (found?.url) setBackground(node, found.url);
  const name = found?.file;
  if (!name) return;
  const m = /^(.*?)[\\/]([^\\/]+)$/.exec(name.replace(/ \[(input|output|temp)\]$/, ""));
  setBackground(node, viewUrl({ filename: m ? m[2] : name.replace(/ \[(input|output|temp)\]$/, ""), subfolder: m ? m[1] : "", type: "input" }));
}

// ---------------------------------------------------------------- geometry
function layout(node) {
  const cv = node._lcBb.cv;
  const cw = cv.clientWidth, ch = cv.clientHeight;
  const { w, h } = gridSize(node);
  const s = Math.min((cw - 16) / w, (ch - 16) / h);
  const dw = w * s, dh = h * s;
  return { x: (cw - dw) / 2, y: (ch - dh) / 2, w: dw, h: dh };
}

const toPx = (L, r) => ({ x: L.x + Math.min(r.x, r.x + r.w) * L.w, y: L.y + Math.min(r.y, r.y + r.h) * L.h, w: Math.abs(r.w) * L.w, h: Math.abs(r.h) * L.h });

/** What is under the pointer: a corner, a box or a move box's target, front (last drawn) first. */
function hit(node, x, y) {
  const L = layout(node);
  const boxes = node._lcBb.boxes;
  const order = boxes.map((_, i) => i).reverse();
  const sel = node._lcBb.sel;
  if (sel != null && boxes[sel]) order.unshift(sel);
  for (const i of order) {
    const b = boxes[i];
    for (const part of b.kind === "move" && b.to ? ["to", "box"] : ["box"]) {
      const r = toPx(L, part === "to" ? b.to : b);
      const corners = [[r.x, r.y, "tl"], [r.x + r.w, r.y, "tr"], [r.x, r.y + r.h, "bl"], [r.x + r.w, r.y + r.h, "br"]];
      for (const [cx, cy, c] of corners) if (Math.abs(x - cx) <= HANDLE && Math.abs(y - cy) <= HANDLE) return { i, part, corner: c };
      if (x >= r.x && x <= r.x + r.w && y >= r.y && y <= r.y + r.h) return { i, part, corner: null };
    }
  }
  return null;
}

// ---------------------------------------------------------------- drawing
function draw(node) {
  const st = node._lcBb;
  const cv = st?.cv;
  if (!cv?.isConnected) return;
  const dpr = window.devicePixelRatio || 1;
  const cw = cv.clientWidth, ch = cv.clientHeight;
  if (cv.width !== Math.round(cw * dpr) || cv.height !== Math.round(ch * dpr)) {
    cv.width = Math.round(cw * dpr);
    cv.height = Math.round(ch * dpr);
  }
  const ctx = cv.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, cw, ch);
  ctx.fillStyle = "#1b1b1b";
  ctx.fillRect(0, 0, cw, ch);
  const L = layout(node);
  if (st.bg) {
    ctx.drawImage(st.bg, L.x, L.y, L.w, L.h);
    ctx.fillStyle = "rgba(0,0,0,0.25)";
    ctx.fillRect(L.x, L.y, L.w, L.h);
  } else {
    ctx.fillStyle = "#2a2a2a";
    ctx.fillRect(L.x, L.y, L.w, L.h);
    ctx.fillStyle = "#777";
    ctx.font = "12px sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("Connect a picture (or run once) to draw on it", cw / 2, ch / 2);
    ctx.textAlign = "left";
  }
  const up = upstreamBoxes(node);
  const upNames = ids(up);
  up.forEach((b, i) => {
    const r = toPx(L, b);
    ctx.globalAlpha = 0.55;
    ctx.strokeStyle = "#bbb";
    ctx.lineWidth = 1.5;
    ctx.setLineDash([5, 4]);
    ctx.strokeRect(r.x, r.y, r.w, r.h);
    ctx.setLineDash([]);
    const label = `${i + 1} ${upNames[i]} ↑`;
    ctx.font = "bold 11px sans-serif";
    const tw = ctx.measureText(label).width;
    const ly = r.y - (r.y - L.y > 15 ? 15 : 0);
    ctx.fillStyle = "#bbb";
    ctx.fillRect(r.x, ly, tw + 8, 15);
    ctx.fillStyle = "#000";
    ctx.fillText(label, r.x + 4, ly + 11);
    ctx.globalAlpha = 1;
  });
  const names = ids(st.boxes);
  const offset = up.length;
  st.boxes.forEach((b, i) => {
    const c = boxColor(b);
    const r = toPx(L, b);
    const selected = i === st.sel;
    ctx.strokeStyle = c;
    ctx.lineWidth = selected ? 3 : 2;
    ctx.setLineDash([]);
    ctx.strokeRect(r.x, r.y, r.w, r.h);
    if (b.kind === "remove") {
      ctx.beginPath();
      ctx.moveTo(r.x, r.y);
      ctx.lineTo(r.x + r.w, r.y + r.h);
      ctx.moveTo(r.x + r.w, r.y);
      ctx.lineTo(r.x, r.y + r.h);
      ctx.stroke();
    }
    if (b.kind === "move" && b.to) {
      const t = toPx(L, b.to);
      ctx.setLineDash([6, 4]);
      ctx.strokeRect(t.x, t.y, t.w, t.h);
      ctx.beginPath();
      ctx.moveTo(r.x + r.w / 2, r.y + r.h / 2);
      ctx.lineTo(t.x + t.w / 2, t.y + t.h / 2);
      ctx.stroke();
      ctx.setLineDash([]);
      if (selected) for (const [hx, hy] of [[t.x, t.y], [t.x + t.w, t.y], [t.x, t.y + t.h], [t.x + t.w, t.y + t.h]]) {
        ctx.fillStyle = c;
        ctx.fillRect(hx - 3, hy - 3, 6, 6);
      }
    }
    const label = `${i + 1 + offset} ${names[i]}`;
    ctx.font = "bold 11px sans-serif";
    const tw = ctx.measureText(label).width;
    ctx.fillStyle = c;
    ctx.fillRect(r.x, r.y - (r.y - L.y > 15 ? 15 : 0), tw + 8, 15);
    ctx.fillStyle = inkOn(c);
    ctx.fillText(label, r.x + 4, r.y - (r.y - L.y > 15 ? 15 : 0) + 11);
    if (selected) for (const [hx, hy] of [[r.x, r.y], [r.x + r.w, r.y], [r.x, r.y + r.h], [r.x + r.w, r.y + r.h]]) {
      ctx.fillStyle = c;
      ctx.fillRect(hx - 4, hy - 4, 8, 8);
    }
  });
  if (st.draft) {
    const r = toPx(L, st.draft);
    ctx.strokeStyle = "#fff";
    ctx.setLineDash([4, 3]);
    ctx.lineWidth = 1;
    ctx.strokeRect(r.x, r.y, r.w, r.h);
    ctx.setLineDash([]);
  }
  const { w, h } = gridSize(node);
  ctx.fillStyle = "#999";
  ctx.font = "11px sans-serif";
  ctx.fillText(`${w} x ${h}   ${st.boxes.length} box${st.boxes.length === 1 ? "" : "es"}`, 6, ch - 5);
  renderEditor(node);
}

// ---------------------------------------------------------------- editor (the selected box)
function el(tag, css, props = {}) {
  const e = document.createElement(tag);
  if (css) e.style.cssText = css;
  Object.assign(e, props);
  return e;
}

const FIELD = "background:#222;color:#ddd;border:1px solid #444;border-radius:4px;padding:2px 4px;font:12px sans-serif;box-sizing:border-box;";

// ---------------------------------------------------------------- ✨ write boxes (needs LC Vision)
const WRITER_H = 28;

function toast(severity, summary, detail) {
  const t = app.extensionManager?.toast;
  if (t?.add) t.add({ severity, summary, detail, life: severity === "error" ? 8000 : 5000 });
  else if (severity === "error") alert(`${summary}\n${detail || ""}`);
}

/** The picture on the canvas as a JPEG data URL (longest side 1024), or "" with no picture. */
function pictureData(node) {
  const img = node._lcBb.bg;
  if (!img?.naturalWidth) return "";
  const s = Math.min(1, 1024 / Math.max(img.naturalWidth, img.naturalHeight));
  const c = document.createElement("canvas");
  c.width = Math.round(img.naturalWidth * s);
  c.height = Math.round(img.naturalHeight * s);
  c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
  try {
    return c.toDataURL("image/jpeg", 0.9);
  } catch {
    return "";
  }
}

/** LC MOSS Layout Prompt fed by this node's elements (through Reroutes): where the scene caption goes. */
function layoutPromptBelow(node) {
  const out = node.outputs?.find((o) => o.name === "elements");
  const seen = new Set();
  const walk = (links) => {
    for (const id of links || []) {
      const l = node.graph?.links?.[id] ?? node.graph?.links?.get?.(id);
      const t = l && node.graph.getNodeById(l.target_id);
      if (!t || seen.has(t.id)) continue;
      seen.add(t.id);
      if ((t.comfyClass || t.type) === "LCMOSSLayoutPrompt") return t;
      if (/Reroute/i.test(t.type || "")) {
        const hit = walk(t.outputs?.[0]?.links);
        if (hit) return hit;
      }
    }
    return null;
  };
  return walk(out?.links);
}

function putScene(node, scene) {
  if (!scene) return;
  const lp = layoutPromptBelow(node);
  const w = lp && W(lp, "prompt");
  const wired = lp?.inputs?.find((i) => i.name === "prompt")?.link != null;
  if (w && !wired && (!String(w.value || "").trim() || confirm("Replace the prompt in LC MOSS Layout Prompt with the scene?"))) {
    w.value = scene;
    lp.setDirtyCanvas?.(true, true);
    return;
  }
  navigator.clipboard?.writeText(scene).catch(() => {});
  toast("info", "Scene copied", scene);
}

async function writeBoxes(node) {
  const st = node._lcBb;
  const wr = st.writer;
  const idea = wr.idea.value.trim();
  const picture = pictureData(node);
  if (!picture && !idea) return toast("warn", "Write boxes", "Write an idea first, or connect a picture.");
  if (st.boxes.length && !confirm(`Replace the ${st.boxes.length} box${st.boxes.length === 1 ? "" : "es"}?`)) return;
  const { w, h } = gridSize(node);
  wr.go.disabled = true;
  wr.go.textContent = "⏳";
  try {
    const r = await api.fetchApi("/lc_vision/boxes/write", {
      method: "POST",
      body: JSON.stringify({ model: wr.model.value, idea, picture, width: w, height: h }),
    });
    const res = await r.json();
    if (!r.ok || res.error) throw new Error(res.error || r.statusText);
    st.boxes = res.boxes || [];
    st.sel = st.boxes.length ? 0 : null;
    save(node);
    draw(node);
    putScene(node, res.scene);
    if (res.notes?.length) toast("warn", "Boxes written, some left out", res.notes.join("; "));
  } catch (e) {
    toast("error", "Write boxes", String(e.message || e));
  } finally {
    wr.go.disabled = false;
    wr.go.textContent = "✨ boxes";
  }
}

function buildWriter(node) {
  const st = node._lcBb;
  const row = el("div", "display:none;gap:4px;align-items:center;");
  const idea = el("input", `${FIELD}flex:1;min-width:0;`, {
    placeholder: "✨ idea: three women on a beach (with a picture: what to box)",
    title: "With a picture: LC Vision finds the subjects and boxes them (this note says what to box or change). Without one: it plans the boxes from the idea.",
    value: node.properties?.lcBoxIdea || "",
  });
  const model = el("select", `${FIELD}flex:none;max-width:120px;`, { title: "The LC Vision model that writes the boxes (a vision model sees the picture)" });
  const go = el("button", `${FIELD}cursor:pointer;flex:none;`, { textContent: "✨ boxes", title: "Write the boxes, names, descriptions and palettes. The scene goes to LC MOSS Layout Prompt." });
  idea.addEventListener("keydown", (ev) => ev.stopPropagation());
  idea.oninput = () => { node.properties = { ...(node.properties || {}), lcBoxIdea: idea.value }; };
  model.onchange = () => { node.properties = { ...(node.properties || {}), lcBoxModel: model.value }; };
  go.onclick = () => writeBoxes(node);
  row.append(idea, model, go);
  st.writer = { row, idea, model, go, on: false };
  api.fetchApi("/lc_vision/boxes/models").then((r) => (r.ok ? r.json() : null)).then((res) => {
    if (!res?.models?.length) return;  // no LC Vision, or no model on disk: the row stays hidden
    const want = node.properties?.lcBoxModel;
    for (const m of res.models) model.append(el("option", "", { value: m, textContent: m }));
    model.value = res.models.includes(want) ? want : res.default;
    row.style.display = "flex";
    st.writer.on = true;
    st.ed.root.style.height = `${EDITOR_H - 6 + WRITER_H}px`;
    node.setSize?.([node.size[0], Math.max(node.size[1], node.computeSize?.()[1] || 0)]);
    node.setDirtyCanvas?.(true, true);
  }).catch(() => {});
  return row;
}

function buildEditor(node) {
  const st = node._lcBb;
  const ed = el("div", `height:${EDITOR_H - 6}px;display:flex;flex-direction:column;gap:4px;padding:4px 2px;box-sizing:border-box;font:12px sans-serif;color:#ccc;`);
  ed.append(buildWriter(node));
  const row1 = el("div", "display:flex;gap:4px;align-items:center;");
  const chips = el("div", "display:flex;gap:3px;flex-wrap:nowrap;overflow-x:auto;flex:1;min-height:20px;");
  const del = el("button", `${FIELD}cursor:pointer;flex:none;`, { textContent: "✕ delete", title: "Delete the selected box (or press Delete)" });
  del.onclick = () => removeSel(node);
  row1.append(chips, del);
  const row2 = el("div", "display:flex;gap:4px;");
  const name = el("input", `${FIELD}flex:1;min-width:0;`, { placeholder: "name (person, cup, hat)", title: "A plain noun: the box id becomes name_1" });
  const kind = el("select", `${FIELD}flex:none;`, { title: "new = add it here; change = edit it in place; move = take it to the dashed box; remove = take it out" });
  for (const k of KINDS) kind.append(el("option", "", { value: k, textContent: k }));
  const type = el("select", `${FIELD}flex:none;`, { title: "object, character (a person or creature: MOSS Image keeps them apart), or a block of text to write" });
  for (const [v, t] of [["obj", "object"], ["character", "character"], ["text", "text"]]) type.append(el("option", "", { value: v, textContent: t }));
  const palette = el("input", `${FIELD}flex:1;min-width:0;`, { placeholder: "palette (MOSS): olive green, #f2e6d0", title: "MOSS Image: the box's colours, comma separated (#1a1a1a, warm beige). Leave empty for none." });
  row2.append(name, kind, type);
  const text = el("input", `${FIELD}flex:1;min-width:0;`, { placeholder: "the exact text to write in this box" });
  const row3 = el("div", "display:flex;gap:4px;");
  // 🎨 the system colour picker: each pick is added to the palette as a hex code (typed names still work)
  const pick = el("input", "position:absolute;width:0;height:0;opacity:0;pointer-events:none;", { type: "color" });
  const swatch = el("button", `${FIELD}cursor:pointer;flex:none;width:30px;padding:0;`, { textContent: "🎨", title: "Pick a colour: it is added to this box's palette (up to 6)" });
  swatch.onclick = () => {
    const last = (palette.value.match(/#[0-9a-f]{6}/gi) || []).pop();
    if (last) pick.value = last;
    pick.click();
  };
  pick.onchange = () => {
    const parts = palette.value.split(",").map((x) => x.trim()).filter(Boolean);
    if (!parts.some((x) => x.toLowerCase() === pick.value.toLowerCase())) parts.push(pick.value);
    palette.value = parts.slice(-6).join(", ");
    edit("palette", palette.value);
    paletteCheck(palette);
  };
  row3.append(text, palette, swatch, pick);
  const desc = el("textarea", `${FIELD}width:100%;flex:1;resize:none;`, { placeholder: "what it looks like (the result): \"a black pirate tricorn hat in worn leather\"" });
  ed.append(row1, row2, row3, desc);
  for (const e of [name, text, desc, palette]) e.addEventListener("keydown", (ev) => ev.stopPropagation());
  const edit = (field, value) => {
    const b = st.boxes[st.sel];
    if (!b) return;
    b[field] = value;
    if (field === "kind" && value === "move" && !b.to) b.to = { x: Math.min(0.98 - Math.abs(b.w), b.x + 0.1), y: b.y, w: b.w, h: b.h };
    if (field === "kind" && value !== "move") b.to = null;
    st.lastKind = field === "kind" ? value : st.lastKind;
    save(node);
    draw(node);
  };
  name.oninput = () => edit("name", name.value);
  kind.onchange = () => edit("kind", kind.value);
  type.onchange = () => edit("type", type.value);
  text.oninput = () => edit("text", text.value);
  desc.oninput = () => edit("desc", desc.value);
  palette.oninput = () => {
    edit("palette", palette.value);
    paletteCheck(palette);
  };
  st.ed = { root: ed, chips, name, kind, type, text, desc, palette, swatch, del };
  return ed;
}

/** A box draws in its palette's first hex colour; without one, in its kind's colour (new / change / move / remove). */
function boxColor(b) {
  const m = /#([0-9a-f]{6}|[0-9a-f]{3})\b/i.exec(String(b?.palette || ""));
  if (!m) return COLORS[b?.kind] || COLORS.new;
  const h = m[1].length === 3 ? [...m[1]].map((x) => x + x).join("") : m[1];
  return `#${h.toLowerCase()}`;
}

/** Black or white label text, whichever reads on the box colour. */
function inkOn(hex) {
  const h = String(hex).replace("#", "");
  if (h.length !== 6) return "#000";
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16));
  return 0.299 * r + 0.587 * g + 0.114 * b > 140 ? "#000" : "#fff";
}

const PAL_OK = (c) => /^#?([0-9a-f]{3}|[0-9a-f]{6})$/i.test(c) || /^[a-z][a-z '-]{1,39}$/i.test(c);
const PAL_TIP = "MOSS Image: the box's colours, comma separated (#1a1a1a, warm beige), or pick them with 🎨. Leave empty for none.";

/** Bad palette entries (not a hex code or a colour name) are left out by the node: show which, in red. */
function paletteCheck(inp) {
  const bad = inp.value.split(/[,;\n]/).map((x) => x.trim()).filter((x) => x && !PAL_OK(x));
  inp.style.borderColor = bad.length ? "#e65050" : "#444";
  inp.title = bad.length ? `Left out (not a colour): ${bad.join(", ")}. Use a hex code (#1a1a1a) or a colour name (warm beige).` : PAL_TIP;
}

const EMPTY_TIP = "Drag on the picture to draw a box first, or click a box to select it. Then fill this in.";

function renderEditor(node) {
  const st = node._lcBb;
  const ed = st.ed;
  if (!ed) return;
  const names = ids(st.boxes);
  const key = st.boxes.map((b, i) => `${i}:${names[i]}:${b.kind}`).join("|") + `#${st.sel}`;
  if (ed.key !== key) {
    ed.key = key;
    ed.chips.replaceChildren(...st.boxes.map((b, i) => {
      const c = el("span", `cursor:pointer;padding:1px 6px;border-radius:9px;white-space:nowrap;font:bold 11px sans-serif;color:${inkOn(boxColor(b))};background:${boxColor(b)};${i === st.sel ? "outline:2px solid #fff;" : "opacity:0.75;"}`,
        { textContent: `${i + 1} ${names[i]}`, title: "Select this box" });
      c.onclick = () => {
        st.sel = i;
        draw(node);
      };
      return c;
    }));
    if (!st.boxes.length) ed.chips.append(el("span", "color:#777;", { textContent: "Drag on the picture to draw a box" }));
  }
  const b = st.boxes[st.sel];
  const on = !!b;
  for (const k of ["name", "kind", "type", "text", "desc", "palette", "swatch", "del"]) {
    const e = ed[k];
    e.disabled = !on;
    if (e.dataset.tip == null) e.dataset.tip = e.title || "";
    e.title = on ? e.dataset.tip : EMPTY_TIP;
  }
  ed.root.title = on ? "" : EMPTY_TIP;
  if (st.cv) st.cv.title = st.boxes.length ? "" : "Empty: drag here to draw a box. Then drag a box to move it, a corner to resize it.";
  ed.text.style.display = on && b.type === "text" ? "" : "none";
  if (!on) return;
  const set = (inp, v) => {
    if (document.activeElement !== inp && inp.value !== v) inp.value = v;
  };
  set(ed.name, b.name || "");
  set(ed.kind, b.kind || "new");
  set(ed.type, b.type || "obj");
  set(ed.text, b.text || "");
  set(ed.desc, b.desc || "");
  set(ed.palette, b.palette || "");
  ed.palette.dataset.tip = PAL_TIP;
  paletteCheck(ed.palette);
  ed.text.style.display = b.type === "text" ? "" : "none";
}

function removeSel(node) {
  const st = node._lcBb;
  if (st.sel == null || !st.boxes[st.sel]) return;
  st.boxes.splice(st.sel, 1);
  st.sel = st.boxes.length ? Math.min(st.sel, st.boxes.length - 1) : null;
  save(node);
  draw(node);
}

// ---------------------------------------------------------------- pointer
function attach(node) {
  if (node._lcBb) return;
  hideWidget(W(node, "boxes"));
  const wrap = el("div", "width:100%;display:flex;flex-direction:column;");
  const cv = el("canvas", `width:100%;height:${CANVAS_H - 4}px;display:block;touch-action:none;outline:none;`, { tabIndex: 0 });
  wrap.appendChild(cv);
  node._lcBb = { cv, boxes: load(node), sel: null, lastKind: "new" };
  const st = node._lcBb;
  wrap.appendChild(buildEditor(node));

  const pos = (e) => {
    const r = cv.getBoundingClientRect();
    return [((e.clientX - r.left) * cv.clientWidth) / r.width, ((e.clientY - r.top) * cv.clientHeight) / r.height];
  };
  const clamp01 = (v) => Math.max(0, Math.min(1, v));
  const frac = (x, y) => {
    const L = layout(node);
    return [clamp01((x - L.x) / L.w), clamp01((y - L.y) / L.h)];
  };
  cv.addEventListener("pointerdown", (e) => {
    if (e.button !== 0) return;
    e.preventDefault();
    e.stopPropagation();
    cv.focus();
    cv.setPointerCapture?.(e.pointerId);
    const [x, y] = pos(e);
    const [fx, fy] = frac(x, y);
    const h = hit(node, x, y);
    if (h) {
      st.sel = h.i;
      const b = st.boxes[h.i];
      const r = h.part === "to" ? b.to : b;
      st.drag = { ...h, fx, fy, start: { ...r } };
    } else {
      st.drag = { draw: true, fx, fy };
      st.draft = { x: fx, y: fy, w: 0, h: 0 };
    }
    draw(node);
  });
  cv.addEventListener("pointermove", (e) => {
    const [x, y] = pos(e);
    const d = st.drag;
    if (!d) {
      const h = hit(node, x, y);
      cv.style.cursor = h?.corner ? (h.corner === "tl" || h.corner === "br" ? "nwse-resize" : "nesw-resize") : h ? "move" : "crosshair";
      return;
    }
    e.preventDefault();
    e.stopPropagation();
    const [fx, fy] = frac(x, y);
    if (d.draw) {
      st.draft = { x: d.fx, y: d.fy, w: fx - d.fx, h: fy - d.fy };
    } else {
      const b = st.boxes[d.i];
      const r = d.part === "to" ? b.to : b;
      const s = d.start;
      if (!d.corner) {
        r.x = Math.max(0, Math.min(1 - Math.abs(s.w), s.x + fx - d.fx));
        r.y = Math.max(0, Math.min(1 - Math.abs(s.h), s.y + fy - d.fy));
      } else {
        let x0 = Math.min(s.x, s.x + s.w), y0 = Math.min(s.y, s.y + s.h), x1 = Math.max(s.x, s.x + s.w), y1 = Math.max(s.y, s.y + s.h);
        if (d.corner.includes("l")) x0 = fx; else x1 = fx;
        if (d.corner.includes("t")) y0 = fy; else y1 = fy;
        Object.assign(r, { x: Math.min(x0, x1), y: Math.min(y0, y1), w: Math.abs(x1 - x0), h: Math.abs(y1 - y0) });
      }
    }
    draw(node);
  });
  const up = (e) => {
    const d = st.drag;
    if (!d) return;
    e?.stopPropagation?.();
    st.drag = null;
    if (d.draw && st.draft) {
      const r = st.draft;
      st.draft = null;
      const L = layout(node);
      if (Math.abs(r.w) * L.w > 6 && Math.abs(r.h) * L.h > 6) {
        const kind = st.lastKind === "move" ? "new" : st.lastKind;
        st.boxes.push({ x: Math.min(r.x, r.x + r.w), y: Math.min(r.y, r.y + r.h), w: Math.abs(r.w), h: Math.abs(r.h), name: "object", kind, type: "obj", desc: "", text: "", to: null });
        st.sel = st.boxes.length - 1;
        setTimeout(() => st.ed?.name?.select?.(), 0);
      } else {
        st.sel = null;
      }
    }
    save(node);
    draw(node);
  };
  cv.addEventListener("pointerup", up);
  cv.addEventListener("pointercancel", up);
  cv.addEventListener("keydown", (e) => {
    if (e.key === "Delete" || e.key === "Backspace") {
      e.preventDefault();
      e.stopPropagation();
      removeSel(node);
    }
  });
  new ResizeObserver(() => draw(node)).observe(cv);
  const total = () => CANVAS_H + EDITOR_H + (st.writer?.on ? WRITER_H : 0);
  const dw = node.addDOMWidget("box_canvas", "LC_BOUNDING_BOXES", wrap, { getMinHeight: total, getHeight: total, serialize: false });
  if (dw) dw.serialize = false;
  // the right side Parameters panel writes its own column width onto widgets it lists: always follow the node
  if (dw) Object.defineProperty(dw, "width", { get: () => undefined, set: () => {}, configurable: true });
  for (const name of ["width", "height"]) {
    const w = W(node, name);
    if (!w) continue;
    const prev = w.callback;
    w.callback = function (...a) {
      const out = prev?.apply(this, a);
      draw(node);
      return out;
    };
  }
  requestAnimationFrame(() => {
    upstreamPicture(node);
    draw(node);
  });
}

// reset_after_run: the boxes clear once the whole run has finished (like LC Outpaint's snap back)
function bbNodes() {
  return (app.graph?._nodes || []).filter((n) => n?.comfyClass === TYPE || n?.type === TYPE);
}
api.addEventListener("execution_success", () => {
  for (const n of bbNodes()) {
    if (n._lcBbResetAfter && n._lcBb) {
      n._lcBb.boxes = [];
      n._lcBb.sel = null;
      save(n);
      draw(n);
    }
    n._lcBbResetAfter = false;
  }
});
for (const ev of ["execution_error", "execution_interrupted"]) api.addEventListener(ev, () => { for (const n of bbNodes()) n._lcBbResetAfter = false; });

app.registerExtension({
  name: "LC123.BoundingBoxes",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData?.name !== TYPE) return;
    const created = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const r = created?.apply(this, arguments);
      attach(this);
      for (const name of ["size", "width", "height"]) {
        const w = W(this, name);
        if (!w) continue;
        const cb = w.callback;
        w.callback = (...args) => {
          const out = cb?.apply(w, args);
          if (this._lcBb) draw(this);
          return out;
        };
      }
      setTimeout(() => {
        if (this._lcBbConfigured) return;
        const min = this.computeSize?.() || this.size;
        this.setSize?.([Math.max(380, this.size[0]), Math.max(min[1], this.size[1])]);
      }, 0);
      return r;
    };
    const configure = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function () {
      this._lcBbConfigured = true;
      const r = configure?.apply(this, arguments);
      if (this._lcBb) this._lcBb.boxes = load(this);
      requestAnimationFrame(() => {
        upstreamPicture(this);
        draw(this);
      });
      return r;
    };
    const connChange = nodeType.prototype.onConnectionsChange;
    nodeType.prototype.onConnectionsChange = function () {
      const r = connChange?.apply(this, arguments);
      if (this._lcBb) {
        if (!this.inputs?.find((i) => i.name === "image")?.link) {
          this._lcBb.bg = null;
          this._lcBb.bgUrl = null;
          this._lcBb.size = null;
        }
        requestAnimationFrame(() => {
          upstreamPicture(this);
          draw(this);
        });
      }
      return r;
    };
    // the picture's source switched on / off (LC Bypasser, Ctrl+B): show or drop its picture without a run
    const fg = nodeType.prototype.onDrawForeground;
    nodeType.prototype.onDrawForeground = function () {
      const r = fg?.apply(this, arguments);
      const slot = this.inputs?.findIndex((i) => i.name === "image");
      const src = slot != null && slot >= 0 && this.inputs[slot].link != null ? this.getInputNode?.(slot) : null;
      const key = src ? `${src.id}:${src.mode}` : "";
      if (this._lcBb && key !== this._lcBbSrcKey) {
        this._lcBbSrcKey = key;
        if (src && inactive(src)) {
          clearBackground(this);
          draw(this);
        } else if (src) {
          upstreamPicture(this);
        }
      }
      return r;
    };
    const executed = nodeType.prototype.onExecuted;
    nodeType.prototype.onExecuted = function (msg) {
      const r = executed?.apply(this, arguments);
      const st = this._lcBb;
      if (!st) return r;
      const sz = msg?.lc_size?.[0];
      if (sz) st.size = { w: sz.width, h: sz.height };
      const bg = msg?.lc_background?.[0];
      if (bg) setBackground(this, viewUrl(bg));
      else {
        // no picture arrived (nothing wired, or the source is bypassed / muted): a plain canvas
        st.bg = null;
        st.bgUrl = null;
      }
      this._lcBbResetAfter = !!msg?.lc_reset_after?.[0];
      // boxes from upstream are shown dimmed (and merged by the node), not copied in
      try {
        st.runIncoming = msg?.lc_incoming?.[0] ? JSON.parse(msg.lc_incoming[0]) : [];
      } catch {
        st.runIncoming = [];
      }
      draw(this);
      return r;
    };
  },
});
