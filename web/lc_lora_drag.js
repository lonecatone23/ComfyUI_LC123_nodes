/** One delegated drag controller per node; no row mutation or layout reads on pointer hover. */
export function installLoraDrag(host, onDrop) {
  let drag = null, frame = 0, sample = null, geometryDirty = true, previousKey = "";
  const rects = new Map();
  const line = document.createElement("div");
  line.className = "lc-group-lora-insert-line";
  line.hidden = true;
  let press = null;

  const hide = () => { line.hidden = true; previousKey = ""; };
  const invalidate = () => { geometryDirty = true; };
  function measure() {
    if (!geometryDirty) return;
    rects.clear();
    for (const el of host.querySelectorAll(".lc-group-lora-row,.lc-group-lora-group,.lc-group-lora-group-header,.lc-group-lora-group-body")) rects.set(el, el.getBoundingClientRect());
    geometryDirty = false;
    previousKey = "";
  }
  function destination(point) {
    if (!drag || !point || !host.contains(point.target)) return null;
    measure();
    const section = point.target.closest(".lc-group-lora-group");
    if (!section) return null;
    const groupId = section.dataset.groupId;
    const header = section.querySelector(".lc-group-lora-group-header");
    const headerRect = rects.get(header) || rects.get(section);
    if (drag.kind === "group") {
      if (drag.id === groupId) return null;
      const before = !groupId || point.y < headerRect.top + headerRect.height / 2;
      const rect = rects.get(section);
      return { kind: "group", id: drag.id, groupId, before, rect, y: before ? rect.top : rect.bottom, key: `${groupId}:${before}` };
    }
    const row = point.target.closest(".lc-group-lora-row");
    if (row) {
      if (row.dataset.rowId === drag.id) return null;
      const rect = rects.get(row);
      const before = point.y < rect.top + rect.height / 2;
      let next = before ? row : row.nextElementSibling;
      if (next?.dataset.rowId === drag.id) next = next.nextElementSibling;
      const beforeId = next?.dataset.rowId || null;
      return { kind: "row", id: drag.id, groupId, beforeId, rect, y: before ? rect.top : rect.bottom, key: `${groupId}:${beforeId}` };
    }
    const body = section.querySelector(".lc-group-lora-group-body");
    const rect = body ? rects.get(body) : headerRect;
    return { kind: "row", id: drag.id, groupId, beforeId: null, rect, y: rect.bottom, key: `${groupId}:null` };
  }
  function paint() {
    frame = 0;
    const target = destination(sample && {target:document.elementFromPoint(sample.x,sample.y),y:sample.y});
    if (!target) { hide(); return; }
    const key = `${target.key}:${target.y}`;
    if (key === previousKey) return;
    previousKey = key;
    line.style.transform = `translate3d(${target.rect.left + 5}px,${target.y - 1}px,0)`;
    line.style.width = Math.max(0, target.rect.width - 10) + "px";
    line.hidden = false;
  }
  function cleanup() {
    if (frame) cancelAnimationFrame(frame);
    frame = 0; sample = null;
    drag = null; press = null; rects.clear(); hide(); line.remove();
    document.documentElement.classList.remove("lc-group-lora-pointer-drag");
    document.removeEventListener("pointermove", move, true);
    document.removeEventListener("pointerup", end, true);
    document.removeEventListener("pointercancel", cleanup, true);
    document.removeEventListener("keydown", key, true);
    window.removeEventListener("blur", cleanup);
    window.removeEventListener("scroll", invalidate, true);
    window.removeEventListener("resize", invalidate);
  }
  function key(event) { if (event.key === "Escape") {event.preventDefault();event.stopPropagation();cleanup();} }
  function start(event) {
    const handle = event.target.closest("[data-drag-kind]");
    if (event.button !== 0 || !handle || !host.contains(handle)) return;
    cleanup(); event.preventDefault(); event.stopPropagation();
    const kind = handle.dataset.dragKind;
    const source = handle.closest(kind === "row" ? ".lc-group-lora-row" : ".lc-group-lora-group");
    press = { x:event.clientX, y:event.clientY, kind, source, id:kind === "row" ? source.dataset.rowId : source.dataset.groupId };
    document.addEventListener("pointermove", move, true);
    document.addEventListener("pointerup", end, true);
    document.addEventListener("pointercancel", cleanup, true);
    document.addEventListener("keydown", key, true);
    window.addEventListener("blur", cleanup);
    window.addEventListener("scroll", invalidate, true);
    window.addEventListener("resize", invalidate);
  }
  function move(event) {
    if (!press) return;
    event.preventDefault(); event.stopPropagation();
    if (!drag) {
      if (Math.hypot(event.clientX-press.x,event.clientY-press.y)<4) return;
      drag = press; document.body.append(line);
      document.documentElement.classList.add("lc-group-lora-pointer-drag");
      invalidate(); measure();
    }
    sample = { x:event.clientX, y:event.clientY };
    if (!frame) frame = requestAnimationFrame(paint);
  }
  function end(event) {
    if (!press) return;
    event.preventDefault(); event.stopPropagation();
    const target = drag && destination({target:document.elementFromPoint(event.clientX,event.clientY), y:event.clientY});
    cleanup();
    if (target) onDrop(target);
  }
  host.addEventListener("pointerdown", start, true);
  return {cancel:cleanup,destroy() {cleanup();host.removeEventListener("pointerdown",start,true);}};
}
