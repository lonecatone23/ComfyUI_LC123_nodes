/** Resize the library without recentering it or moving its top-left corner. */
export function makeLibraryResizable(dialog) {
  let resize = null;
  const pin = () => {
    const rect = dialog.getBoundingClientRect();
    dialog.style.margin = "0";
    dialog.style.left = rect.left + "px";
    dialog.style.top = rect.top + "px";
    return rect;
  };
  const apply = (width, height, rect) => {
    const maxWidth = Math.min(window.innerWidth * .94, window.innerWidth - rect.left - 8);
    const maxHeight = Math.min(window.innerHeight * .94, window.innerHeight - rect.top - 8);
    dialog.style.width = Math.max(Math.min(640, maxWidth), Math.min(width, maxWidth)) + "px";
    dialog.style.height = Math.max(Math.min(420, maxHeight), Math.min(height, maxHeight)) + "px";
  };
  for (const edge of ["se"]) {
    const handle = document.createElement("div");
    handle.className = `lc-library-resize lc-library-resize-${edge}`;
    if (edge === "se") {
      handle.tabIndex = 0;
      handle.setAttribute("role", "button");
      handle.setAttribute("aria-label", "Resize library");
      handle.addEventListener("keydown", (event) => {
        if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key)) return;
        event.preventDefault(); event.stopPropagation();
        const rect = pin(), step = event.shiftKey ? 50 : 10;
        apply(rect.width + (event.key === "ArrowRight" ? step : event.key === "ArrowLeft" ? -step : 0),
          rect.height + (event.key === "ArrowDown" ? step : event.key === "ArrowUp" ? -step : 0), rect);
      });
    }
    handle.addEventListener("pointerdown", (event) => {
      if (event.button !== 0) return;
      event.preventDefault(); event.stopPropagation();
      resize = { rect: pin(), x: event.clientX, y: event.clientY };
      handle.setPointerCapture(event.pointerId);
    });
    handle.addEventListener("pointermove", (event) => {
      if (!resize) return;
      const { rect, x, y } = resize;
      apply(rect.width + (edge.includes("e") ? event.clientX - x : 0),
        rect.height + (edge.includes("s") ? event.clientY - y : 0), rect);
    });
    for (const type of ["pointerup", "pointercancel", "lostpointercapture"]) handle.addEventListener(type, () => { resize = null; });
    dialog.append(handle);
  }
}
