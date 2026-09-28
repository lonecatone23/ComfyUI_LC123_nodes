/** LC Group LoRA Loader: persistent groups, a visual library, and .civitai.info panels. */
import { app } from "../../scripts/app.js";
import { lcApplyLaunchColor } from "./lc_color.js";
import { iconButton, installLibraryStyles, getLoraInfo, subscribeInfo, showLoraLibrary, showLoraInfo } from "./lc_lora_library.js";
import { installLoraDrag } from "./lc_lora_drag.js";
import { migrateGroupLoaders, normalizeRows, orderRows, moveRow, groupState, toggleGroup, removeGroup } from "./lc_lora_state.js";

const NODES = new Set(["LCGroupLoraLoader", "LCGroupLoraLoaderStack"]);
const MIN_W = 330;
const STRENGTH_MODE = "Show Strengths";
const SINGLE = "Single Strength";
const SEPARATE = "Separate Model & Clip";

const STRENGTH_STEP = 0.05;
const STRENGTH_DRAG_RATE = 0.05; // value change per pixel of horizontal drag, matches rgthree's own rate

function ensureStrengthStyle() {
  if (document.getElementById("lc123-group-lora-strength-style")) return;
  const st = document.createElement("style");
  st.id = "lc123-group-lora-strength-style";
  st.textContent = `
.lc-group-lora-strength{display:flex;align-items:center;flex:0 0 auto;gap:0;background:#1e1e1e;border:1px solid #444;border-radius:4px;overflow:hidden;}
.lc-group-lora-str-arrow{width:16px;height:22px;line-height:22px;padding:0;background:#2a2a2a;color:#dfb87e;border:none;cursor:pointer;font-size:9px;flex:0 0 16px;}
.lc-group-lora-str-arrow:hover{background:#3a3a3a;}
.lc-group-lora-str-value{width:46px;flex:0 0 46px;text-align:center;cursor:ew-resize;user-select:none;font:12px Arial,sans-serif;color:#ddd;line-height:22px;}
.lc-group-lora-str-edit{width:46px;flex:0 0 46px;text-align:center;font:12px Arial,sans-serif;color:#fff;background:#111;border:none;padding:0;}
`;
  document.head.appendChild(st);
}

function makeStrengthControl(node, rowId, field = "strength", label = "Strength") {
  ensureStrengthStyle();
  const wrap = document.createElement("div");
  wrap.className = "lc-group-lora-strength";
  wrap.dataset.strengthField = field;
  wrap.title = `${label} strength`;

  const dec = document.createElement("button");
  dec.type = "button";
  dec.className = "lc-group-lora-str-arrow";
  dec.textContent = "◀";
  dec.title = `-${STRENGTH_STEP} (drag the number to scrub, click it to type an exact value)`;

  const valueEl = document.createElement("div");
  valueEl.className = "lc-group-lora-str-value";

  const inc = document.createElement("button");
  inc.type = "button";
  inc.className = "lc-group-lora-str-arrow";
  inc.textContent = "▶";
  inc.title = `+${STRENGTH_STEP} (drag the number to scrub, click it to type an exact value)`;

  valueEl.setAttribute("aria-label", `${label} strength`);
  valueEl.title = `${label} strength`;
  wrap.append(dec, valueEl, inc);

  const getValue = () => {
    const row = getRows(node).find((row) => row.id === rowId);
    return Number(row?.[field] ?? row?.strength ?? 1);
  };
  const commit = (v) => {
    const rs = getRows(node);
    const index = rs.findIndex((row) => row.id === rowId);
    if (index < 0) return;
    rs[index][field] = Math.round(v * 100) / 100;
    setRows(node, rs, { rerender: false });
  };
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
  });
  valueEl.addEventListener("click", (e) => {
    e.stopPropagation();
    if (moved) return; // that pointerdown->up was a drag, not a click -- don't also open the editor
    startEditValue();
  });

  function startEditValue() {
    const input = document.createElement("input");
    input.type = "number";
    input.setAttribute("aria-label", `${label} strength`);
    input.step = String(STRENGTH_STEP);
    input.className = "lc-group-lora-str-edit";
    input.value = getValue().toFixed(2);
    valueEl.replaceWith(input);
    input.focus();
    input.select();
    let finished = false;
    const done = (apply) => {
      if (finished) return;
      finished = true;
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


function widget(node, name) {
  return (node.widgets || []).find((w) => w && w.name === name);
}

function getGroups(node) {
  node.properties ||= {};
  if (!Array.isArray(node.properties.lc_lora_groups)) node.properties.lc_lora_groups = [];
  return node.properties.lc_lora_groups;
}

function getRows(node) {
  const w = widget(node, "lora_rows");
  let rows;
  try { rows = JSON.parse(w?.value || "[]"); } catch { rows = []; }
  const clean = normalizeRows(Array.isArray(rows) ? rows : [], getGroups(node));
  if (w && JSON.stringify(clean) !== w.value) w.value = JSON.stringify(clean);
  return clean;
}

function changed(node) {
  node.setDirtyCanvas?.(true, true);
  app.extensionManager?.workflow?.activeWorkflow?.changeTracker?.checkState?.();
}

function setRows(node, rows, { rerender = true } = {}) {
  const w = widget(node, "lora_rows");
  if (w) w.value = JSON.stringify(orderRows(normalizeRows(rows, getGroups(node)), getGroups(node)));
  if (rerender) renderRows(node);
  growToFit(node);
  changed(node);
}

function hideRowsWidget(node) {
  const w = widget(node, "lora_rows");
  if (!w || w._lcHidden) return;
  w._lcHidden = true;
  w.type = "hidden";
  w.computeSize = () => [0, -4];
  w.hidden = true;
  if (w.options) w.options.hidden = true;
}

function desiredHeight(node) {
  const groups = getGroups(node);
  const rows = getRows(node);
  let height = 80 + (groups.length && rows.some((row) => !row.group) ? 9 : 0);
  for (const group of [{ id: "", collapsed: false }, ...groups]) {
    const count = rows.filter((row) => row.group === group.id).length;
    height += group.id ? 35 + (group.collapsed ? 0 : Math.max(count * 32, 29)) : Math.max(count * 32, 12);
  }
  return height;
}

function growToFit(node) {
  if (!node.__lcFace) return;
  node.__lcFace.wrap.style.height = desiredHeight(node) + "px";
  const min = node.computeSize();
  const width = Math.max(node.size[0], separateStrengths(node) ? 440 : MIN_W);
  if (node.size[1] < min[1] - 0.5 || width > node.size[0]) node.setSize([width, Math.max(node.size[1], min[1])]);
  node.setDirtyCanvas?.(true, true);
}

function openLibrary(node, rowId = null, groupId = "") {
  node.__lcCloseDialog?.();
  const row = getRows(node).find((item) => item.id === rowId);
  const group = getGroups(node).find((item) => item.id === groupId);
  node.__lcCloseDialog = showLoraLibrary({
    mode: rowId ? "replace" : "add", current: row?.lora || "", groupName: group?.name || "",
    onSelectBatch(names) {
      const rows = getRows(node);
      const targetGroup = getGroups(node).some((item) => item.id === groupId) ? groupId : "";
      rows.push(...names.map((name) => ({
        id: crypto.randomUUID(), on: true, lora: name, strength: 1,
        ...(separateStrengths(node) ? { strengthTwo: 1 } : {}), group: targetGroup,
      })));
      setRows(node, rows);
      return true;
    },
    onSelect(name) {
      const rows = getRows(node);
      if (rowId) {
        const target = rows.find((item) => item.id === rowId);
        if (!target) return false;
        target.lora = name;
      } else {
        const targetGroup = getGroups(node).some((item) => item.id === groupId) ? groupId : "";
        rows.push({ id: crypto.randomUUID(), on: true, lora: name, strength: 1, ...(separateStrengths(node) ? { strengthTwo: 1 } : {}), group: targetGroup });
      }
      setRows(node, rows);
      return true;
    },
  });
}

function editGroup(node, group = null) {
  if (!group) {
    group = { id: crypto.randomUUID(), name: "new group", collapsed: false };
    getGroups(node).push(group);
    changed(node);
  }
  node.__lcEditingGroup = group.id;
  renderRows(node); growToFit(node);
  const input = node.__lcFace.rowsHost.querySelector(".lc-group-lora-group-edit");
  input?.focus(); input?.select();
}

function separateStrengths(node) {
  return node.properties?.[STRENGTH_MODE] === SEPARATE;
}

function setStrengthMode(node, value) {
  node.properties ||= {};
  node.properties[STRENGTH_MODE] = value === SEPARATE ? SEPARATE : SINGLE;
  const rows = getRows(node).map((row) => {
    if (separateStrengths(node)) return { ...row, strengthTwo: row.strengthTwo ?? row.strength ?? 1 };
    const { strengthTwo, ...single } = row;
    return single;
  });
  setRows(node, rows);
}

function checkbox(title) {
  const input = document.createElement("input");
  input.type = "checkbox"; input.title = title; input.setAttribute("aria-label", title);
  return input;
}

function ensureFace(node) {
  if (node.__lcFace) return node.__lcFace;
  installLibraryStyles();
  const wrap = document.createElement("div"); wrap.className = "lc-group-lora-face";
  const header = document.createElement("div"); header.className = "lc-group-lora-header";
  const toggleAll = checkbox("Toggle all LoRAs");
  const headerLabel = document.createElement("div"); headerLabel.className = "lc-group-lora-active";
  const mode = document.createElement("select"); mode.className = "lc-group-lora-strength-mode";
  mode.setAttribute("aria-label", STRENGTH_MODE);
  for (const value of [SINGLE, SEPARATE]) {
    const option = document.createElement("option"); option.value = value; option.textContent = value;
    mode.append(option);
  }
  mode.addEventListener("change", () => setStrengthMode(node, mode.value));
  const addGroup = iconButton("plus", "Add Group", () => editGroup(node));
  addGroup.classList.add("lc-group-lora-add-group");
  header.append(toggleAll, headerLabel, addGroup, mode);
  const rowsHost = document.createElement("div"); rowsHost.className = "lc-group-lora-host";
  const footer = document.createElement("div"); footer.className = "lc-group-lora-footer";
  const addBtn = document.createElement("button");
  addBtn.type = "button"; addBtn.className = "lc-group-lora-add"; addBtn.textContent = "➕ Add LoRA";
  addBtn.setAttribute("aria-label", "Add LoRA");
  addBtn.addEventListener("click", () => openLibrary(node));
  footer.append(addBtn); wrap.append(header, rowsHost, footer);
  toggleAll.addEventListener("change", () => setRows(node, getRows(node).map((row) => ({ ...row, on: toggleAll.checked }))));
  // Keep node drag / graph shortcuts away from the embedded controls.
  for (const type of ["pointerdown", "dblclick", "keydown"]) wrap.addEventListener(type, (event) => event.stopPropagation());
  const dom = node.addDOMWidget("lc_group_lora_face", "LC_LORA_FACE", wrap, {
    getMinHeight: () => desiredHeight(node), serialize: false,
  });
  dom.serializeValue = () => undefined;
  node.__lcFace = { wrap, headerLabel, toggleAll, rowsHost, addBtn, mode };
  node.__lcFace.drag = installLoraDrag(rowsHost, (target) => {
    if (target.kind === "row") {
      setRows(node, moveRow(getRows(node), target.id, target.groupId, target.beforeId));
    } else {
      const groups = getGroups(node), moving = groups.find((group) => group.id === target.id);
      if (!moving) return;
      const rest = groups.filter((group) => group.id !== target.id);
      const index = target.groupId ? rest.findIndex((group) => group.id === target.groupId) + (target.before ? 0 : 1) : rest.length;
      rest.splice(index, 0, moving);
      node.properties.lc_lora_groups = rest;
      setRows(node, getRows(node));
    }
  });
  node.__lcInfoUnsubscribe = subscribeInfo((name, info) => {
    for (const button of wrap.querySelectorAll("[data-info-name]")) {
      if (button.dataset.infoName === name) updateInfoButton(button, info);
    }
  });
  return node.__lcFace;
}

function updateInfoButton(button, data) {
  button.classList.toggle("is-active", !!data.has_info);
  button.classList.toggle("is-empty", !data.has_info);
  button.title = data.has_info ? "LoRA information" : "No cached info · View details";
}

function makeRow(node, row) {
  const el = document.createElement("div"); el.className = "lc-group-lora-row";
  el.classList.toggle("is-disabled", !row.on); el.dataset.rowId = row.id;
  const handle = iconButton("grip", "Drag to move LoRA"); handle.className += " lc-group-lora-grip"; handle.draggable = false;
  handle.dataset.dragKind = "row";
  const on = checkbox(`Enable ${row.lora || "LoRA"}`); on.checked = !!row.on;
  on.addEventListener("change", () => setRows(node, getRows(node).map((item) => item.id === row.id ? { ...item, on: on.checked } : item)));
  const picker = document.createElement("button"); picker.type = "button"; picker.className = "lc-group-lora-file";
  picker.textContent = (row.lora || "Choose a LoRA").replaceAll("\\", "/").split("/").at(-1);
  picker.title = row.lora || "Choose a LoRA";
  picker.addEventListener("click", () => openLibrary(node, row.id));
  const strength = makeStrengthControl(node, row.id, "strength", separateStrengths(node) ? "Model" : "Strength");
  el.append(handle, on, picker);
  if (window.LC123Perf?.get?.(window.LC123Perf.ID?.loraInfo, true) !== false) {
    const info = iconButton("info", "LoRA information", () => {
      node.__lcCloseDialog?.(); node.__lcCloseDialog = showLoraInfo(row.lora);
    });
    info.classList.add("is-empty"); info.dataset.infoName = row.lora || "";
    if (row.lora && row.lora !== "None") getLoraInfo(row.lora).then((data) => updateInfoButton(info, data)).catch(() => {});
    else info.disabled = true;
    el.append(info);
  }
  el.append(strength.wrap);
  if (separateStrengths(node)) el.append(makeStrengthControl(node, row.id, "strengthTwo", "CLIP").wrap);
  el.append(iconButton("close", "Remove LoRA", () => setRows(node, getRows(node).filter((item) => item.id !== row.id))));
  return el;
}

function makeGroup(node, group) {
  const section = document.createElement("div"); section.className = "lc-group-lora-group"; section.dataset.groupId = group.id;
  if (!group.id) {
    section.classList.add("lc-group-lora-root");
    const body = document.createElement("div"); body.className = "lc-group-lora-group-body";
    for (const row of getRows(node).filter((row) => !row.group)) body.append(makeRow(node, row));
    section.append(body);
    return section;
  }
  const header = document.createElement("div"); header.className = "lc-group-lora-group-header";
  const collapse = iconButton("chevron", group.collapsed ? "Expand group" : "Collapse group", () => {
    if (!group.id) return;
    group.collapsed = !group.collapsed;
    renderRows(node); growToFit(node); changed(node);
  });
  collapse.classList.toggle("is-open", !group.collapsed); collapse.setAttribute("aria-expanded", String(!group.collapsed));
  if (!group.id) collapse.disabled = true;
  const state = groupState(getRows(node), group.id);
  const toggle = checkbox(`Toggle ${group.name}`);
  toggle.checked = state.checked; toggle.indeterminate = state.mixed; toggle.disabled = !state.total;
  toggle.addEventListener("change", () => setRows(node, toggleGroup(getRows(node), group.id, toggle.checked)));
  const name = document.createElement("span"); name.className = "lc-group-lora-group-name"; name.textContent = group.name; name.title = group.name;
  if (group.id) {
    name.title = `${group.name} · Double-click to rename`;
    name.addEventListener("dblclick", (event) => {
      event.preventDefault(); event.stopPropagation(); editGroup(node, group);
    });
  }
  const count = document.createElement("span"); count.className = "lc-group-lora-group-count"; count.textContent = `${state.active}/${state.total}`;
  if (group.id) header.append(collapse);
  header.append(toggle, name, count);
  if (group.id && node.__lcEditingGroup === group.id) {
    const input = document.createElement("input"); input.className = "lc-group-lora-group-edit";
    input.value = group.name; input.maxLength = 80; input.setAttribute("aria-label", "Group name");
    name.replaceWith(input);
    let finished = false;
    const finish = (save) => {
      if (finished) return; finished = true;
      if (save) group.name = input.value.trim() || "new group";
      node.__lcEditingGroup = null;
      renderRows(node); growToFit(node); changed(node);
    };
    input.addEventListener("keydown", (event) => {
      event.stopPropagation();
      if (event.key === "Enter") { event.preventDefault(); finish(true); }
      if (event.key === "Escape") { event.preventDefault(); finish(false); }
    });
    input.addEventListener("blur", () => finish(true));
  }
  header.append(iconButton("plus", "Add LoRA to group", () => openLibrary(node, null, group.id)));
  if (group.id) header.append(
    iconButton("edit", "Edit group", () => editGroup(node, group)),
    iconButton("trash", "Remove group · keep LoRAs in Ungrouped", () => {
      const rows = removeGroup(getRows(node), group.id);
      node.properties.lc_lora_groups = getGroups(node).filter((item) => item.id !== group.id);
      setRows(node, rows);
    }),
  );
  if (group.id) {
    const handle = iconButton("grip", "Drag to move group");
    handle.classList.add("lc-group-lora-grip"); handle.draggable = false; handle.dataset.dragKind = "group";
    header.prepend(handle);
  }
  section.append(header);
  if (!group.collapsed) {
    const body = document.createElement("div"); body.className = "lc-group-lora-group-body";
    const rows = getRows(node).filter((row) => row.group === group.id);
    for (const row of rows) body.append(makeRow(node, row));
    if (!rows.length) {
      const hint = document.createElement("div"); hint.className = "lc-group-lora-drop-hint"; hint.textContent = "Drop LoRAs here";
      body.append(hint);
    }
    section.append(body);
  }
  return section;
}

function syncNodeColors(node) {
  const face = node.__lcFace;
  if (!face) return;
  const background = node.bgcolor || LiteGraph.NODE_DEFAULT_BGCOLOR || "#353535";
  if (face.background === background) return;
  face.background = background;
  face.wrap.style.setProperty("--lc-node-bg", background);
}

function renderRows(node) {
  const face = ensureFace(node), groups = getGroups(node), rows = getRows(node);
  syncNodeColors(node);
  face.drag.cancel();
  face.rowsHost.replaceChildren();
  for (const group of [...groups, { id: "", name: "Ungrouped", collapsed: false }]) face.rowsHost.append(makeGroup(node, group));
  face.mode.value = separateStrengths(node) ? SEPARATE : SINGLE;
  const active = rows.filter((row) => row.on).length;
  face.headerLabel.textContent = `${active}/${rows.length} active`;
  face.toggleAll.indeterminate = active > 0 && active < rows.length;
  face.toggleAll.checked = rows.length > 0 && active === rows.length;
  face.wrap.style.height = desiredHeight(node) + "px";
}

app.registerExtension({
  name: "LC123.GroupLoraLoader",
  beforeConfigureGraph(graphData) { migrateGroupLoaders(graphData); },
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (!NODES.has(nodeData?.name)) return;
    nodeType["@" + STRENGTH_MODE] = { type: "combo", values: [SINGLE, SEPARATE] };
    const propertyChanged = nodeType.prototype.onPropertyChanged;
    nodeType.prototype.onPropertyChanged = function (name, value) {
      const result = propertyChanged?.apply(this, arguments);
      if (name === STRENGTH_MODE && this.__lcFace) setStrengthMode(this, value);
      return result;
    };
    const draw = nodeType.prototype.onDrawForeground;
    nodeType.prototype.onDrawForeground = function () {
      syncNodeColors(this);
      return draw?.apply(this, arguments);
    };
    const created = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const result = created?.apply(this, arguments);
      this.properties ||= {};
      this.properties[STRENGTH_MODE] ||= SINGLE;
      lcApplyLaunchColor(this, "#332922", "#593930");
      hideRowsWidget(this); ensureFace(this); renderRows(this);
      if (!this.size || this.size[0] < MIN_W) this.setSize([MIN_W, this.computeSize()[1]]);
      return result;
    };
    const configure = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function () {
      const result = configure?.apply(this, arguments);
      hideRowsWidget(this); ensureFace(this); renderRows(this); growToFit(this);
      return result;
    };
    const removed = nodeType.prototype.onRemoved;
    nodeType.prototype.onRemoved = function () {
      this.__lcCloseDialog?.(); this.__lcInfoUnsubscribe?.(); this.__lcFace?.drag.destroy();
      return removed?.apply(this, arguments);
    };
    const getExtra = nodeType.prototype.getExtraMenuOptions;
    nodeType.prototype.getExtraMenuOptions = function (canvas, options) {
      getExtra?.apply(this, arguments);
      options.push(
        { content: "Add LoRA group", callback: () => editGroup(this) },
        { content: "Select all LoRAs", callback: () => setRows(this, getRows(this).map((row) => ({ ...row, on: true }))) },
        { content: "Deselect all LoRAs", callback: () => setRows(this, getRows(this).map((row) => ({ ...row, on: false }))) },
        { content: "Remove all LoRAs", callback: () => setRows(this, []) },
      );
    };
  },
  async nodeCreated(node) {
    if (!NODES.has(node.comfyClass || node.type)) return;
    ensureFace(node); renderRows(node);
  },
  async setup() {
    window.addEventListener("lc123-perf-changed", () => {
      for (const node of app.graph?._nodes || []) if (NODES.has(node.comfyClass || node.type)) renderRows(node);
    });
  },
});
