import { api } from "../../scripts/api.js";
import { makeLibraryResizable } from "./lc_lora_resize.js";

const ROOT = "/lc123/group_lora_loader";
const infoCache = new Map();
const pending = new Map();
const listeners = new Set();
const infoReadQueue = [];
let activeInfoReads = 0;
let lastFolder = "";

const ICONS = {
  plus: '<path d="M12 5v14M5 12h14"/>',
  folder: '<path d="M3 7V5h6l2 2h10v12H3z"/>',
  edit: '<path d="m15 5 4 4M4 20l4-1L20 7a2.8 2.8 0 0 0-4-4L4 15z"/>',
  trash: '<path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7M14 10v7"/>',
  chevron: '<path d="m9 5 7 7-7 7"/>',
  close: '<path d="m6 6 12 12M18 6 6 18"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7v1"/>',
  grip: '<path d="M9 5h.01M15 5h.01M9 12h.01M15 12h.01M9 19h.01M15 19h.01" stroke-width="3"/>',
  image: '<rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="8" cy="8" r="1.5"/><path d="m3 17 5-5 4 4 4-6 5 7"/>',
  refresh: '<path d="M20 7v5h-5M4 17v-5h5M6 7a7 7 0 0 1 12-2l2 7M4 12l2 7a7 7 0 0 0 12-2"/>',
};

function icon(name) {
  const span = document.createElement("span");
  span.className = "lc-library-icon";
  span.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[name] || ICONS.info}</svg>`;
  return span;
}

export function iconButton(name, title, action) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "lc-library-icon-button";
  button.title = title;
  button.setAttribute("aria-label", title);
  button.append(icon(name));
  button.addEventListener("click", (event) => {
    event.stopPropagation();
    action?.(event);
  });
  return button;
}

function element(tag, className, text) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (text !== undefined) el.textContent = text;
  return el;
}

export function installLibraryStyles() {
  if (document.getElementById("lc-group-lora-library-style")) return;
  const style = element("style");
  style.id = "lc-group-lora-library-style";
  style.textContent = `
.lc-library-dialog,.lc-group-lora-face{--lc-accent:var(--p-primary-color,var(--input-text,#ddd));--lc-panel:var(--comfy-menu-bg,#353535);--lc-border:var(--border-color,#666);--lc-muted:var(--descrip-text,#999);color:var(--input-text,#ddd);font:13px system-ui,sans-serif;color-scheme:dark}
.lc-library-dialog *,.lc-group-lora-face *{box-sizing:border-box}
.lc-library-dialog{box-sizing:border-box;border:1px solid var(--border-color,#666);border-radius:16px;padding:0;background:var(--comfy-menu-bg,#353535);width:min(980px,94vw);height:min(740px,88vh);max-width:94vw;max-height:88vh;box-shadow:0 24px 80px #0009;overflow:hidden}
.lc-library-dialog::backdrop{background:#080a10aa;backdrop-filter:blur(5px)}
.lc-library-shell{display:flex;flex-direction:column;height:100%;min-height:0}
.lc-library-top{display:flex;align-items:center;gap:14px;padding:18px 22px;border-bottom:1px solid var(--lc-border);flex-shrink:0}
.lc-library-heading{flex:1;min-width:0}.lc-library-heading h2{font-size:18px;line-height:1.3;font-weight:650;margin:0;color:#f4f3f0}.lc-library-subtitle{font-size:12px;color:var(--lc-muted);margin:5px 0 0;overflow-wrap:anywhere}
.lc-library-icon{display:inline-flex;align-items:center;justify-content:center;width:16px;height:16px;flex-shrink:0}.lc-library-icon svg{width:100%;height:100%}
.lc-library-icon-button{background:transparent;color:#a7abb7;border:1px solid transparent;border-radius:6px;display:inline-flex;align-items:center;justify-content:center;flex:0 0 24px;width:24px;height:24px;padding:3px;cursor:pointer}
.lc-library-icon-button:hover{color:#fff;background:#ffffff10;border-color:#ffffff18}.lc-library-icon-button:focus-visible,.lc-library-card:focus-visible{outline:2px solid var(--lc-accent);outline-offset:2px}.lc-library-icon-button:disabled{opacity:.35;cursor:default}
.lc-library-icon-button.is-active{color:var(--lc-accent)}.lc-library-icon-button.is-empty{color:#626772}.lc-library-icon-button.is-open svg{transform:rotate(90deg)}
.lc-library-search{background:#29211c;color:#eee;border:1px solid var(--border-color,#666);border-radius:9px;padding:10px 12px;font:inherit;min-width:0;width:100%;outline:none}.lc-library-search:focus{border-color:var(--lc-accent)}
.lc-library-tools{padding:14px 22px;display:flex;align-items:center;gap:10px;border-bottom:1px solid var(--lc-border);flex-shrink:0}
.lc-library-body{display:flex;min-height:0;flex:1}.lc-library-folders{flex:0 0 205px;width:205px;overflow:auto;padding:14px 10px;border-right:1px solid var(--lc-border)}
.lc-library-folder{display:flex;align-items:center;gap:8px;width:100%;border:0;background:transparent;color:#b3b6c0;text-align:left;padding:8px;border-radius:6px;font:12px system-ui;cursor:pointer}.lc-library-folder:hover{background:#ffffff08}.lc-library-folder.is-selected{background:#dfb87e16;color:var(--lc-accent)}
.lc-library-folder-name{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.lc-library-count{font-size:11px;color:#777d8b;font-variant-numeric:tabular-nums}
.lc-library-results{flex:1;min-width:0;overflow:auto;scrollbar-gutter:stable;padding:18px 20px}.lc-library-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(146px,1fr));gap:14px;align-content:start}
.lc-library-card{background:var(--comfy-input-bg,#222);border:1px solid var(--border-color,#666);border-radius:10px;padding:0;overflow:hidden;cursor:pointer;text-align:left;color:#eee;position:relative;font:inherit;transition:border-color .15s,transform .15s}.lc-library-card:hover{border-color:var(--lc-accent);transform:translateY(-2px)}.lc-library-card.is-selected{border-color:var(--lc-accent)}
.lc-library-preview{width:100%;aspect-ratio:4/5;background:linear-gradient(145deg,var(--comfy-input-bg,#222),var(--comfy-menu-bg,#353535));display:flex;flex-direction:column;align-items:center;justify-content:center;color:#777e8d;position:relative;overflow:hidden;gap:9px;font-size:11px}.lc-library-preview>.lc-library-icon{width:30px;height:30px;opacity:.6}.lc-library-preview img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}
.lc-library-card-copy{padding:10px}.lc-library-card-name{font-size:12px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.lc-library-card-folder{font-size:10px;color:#969ba8;margin-top:5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.lc-library-card-badge{position:absolute;left:8px;top:8px;background:#14161de6;color:var(--lc-accent);border:1px solid #ffffff20;border-radius:5px;padding:3px 6px;font-size:10px;max-width:calc(100% - 48px);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.lc-library-status{padding:11px 22px;border-top:1px solid var(--lc-border);font-size:12px;color:var(--lc-muted);min-height:39px;flex-shrink:0}.lc-library-status.is-error{color:#e9a098}.lc-library-empty{color:var(--lc-muted);padding:45px 15px;text-align:center;line-height:1.7}
.lc-library-button{border:1px solid var(--border-color,#666);background:var(--comfy-input-bg,#222);color:#e5e6eb;padding:8px 13px;border-radius:7px;cursor:pointer;font:inherit}.lc-library-button:not(:disabled):hover{border-color:var(--lc-accent)}.lc-library-button.is-primary{background:#d7b17a;color:#231c13;border-color:#d7b17a;font-weight:600}.lc-library-button:disabled{opacity:.5;cursor:not-allowed}
.lc-library-info{height:min(700px,88vh);width:min(860px,94vw)}.lc-library-info-content{display:grid;grid-template-columns:minmax(220px,40%) 1fr;min-height:0;overflow:auto;flex:1}.lc-library-info-art{padding:20px;background:#2b221d}.lc-library-info-art .lc-library-preview{border-radius:10px}.lc-library-info-art img{object-fit:contain}.lc-library-info-details{padding:22px;min-width:0}.lc-library-info-details h3{font-size:12px;letter-spacing:.03em;color:#babeca;margin:22px 0 10px}.lc-library-info-details h3:first-child{margin-top:0}.lc-library-info-grid{display:grid;grid-template-columns:auto 1fr;gap:10px 14px;font-size:12px}.lc-library-info-grid dt{color:#8f96a6}.lc-library-info-grid dd{margin:0;overflow-wrap:anywhere;color:#e4e6ec}
.lc-library-chips{display:flex;flex-wrap:wrap;gap:6px}.lc-library-chip{border:1px solid #4b4437;background:#dfb87e0c;color:var(--input-text,#ddd);border-radius:6px;padding:6px 9px;font:12px system-ui;cursor:pointer}.lc-library-chip:hover{background:#dfb87e20}.lc-library-description{font-size:12px;line-height:1.7;color:#adb2be;white-space:pre-wrap;overflow-wrap:anywhere}.lc-library-link{color:var(--lc-accent);font-size:12px;text-decoration:none}.lc-library-raw{margin-top:20px;color:#9ba3b3;font-size:12px}.lc-library-raw summary{cursor:pointer}.lc-library-raw pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#29211c;padding:12px;border-radius:6px;max-height:230px;overflow:auto;font:11px ui-monospace,monospace}.lc-library-image-nav{display:flex;align-items:center;justify-content:center;gap:8px;margin-top:10px}
.lc-library-form{height:auto;width:min(400px,92vw)}.lc-library-form-body{padding:20px}.lc-library-form-actions{display:flex;justify-content:flex-end;gap:8px;padding:0 20px 20px}.lc-library-form-label{display:block;font-size:12px;color:var(--lc-muted);margin-bottom:9px}
.lc-group-lora-face{width:100%;display:flex;flex-direction:column;box-sizing:border-box;padding:4px 0}.lc-group-lora-header{height:30px;display:flex;align-items:center;gap:5px;padding:0 8px;flex-shrink:0}.lc-group-lora-active{font-size:11px;color:#a4b2a1;flex:1}.lc-group-lora-face input[type=checkbox]{accent-color:var(--lc-accent);width:13px;height:13px;margin:0 3px;cursor:pointer;flex-shrink:0}.lc-group-lora-host{display:flex;flex-direction:column;overflow:visible}.lc-group-lora-row{height:32px;display:flex;align-items:center;gap:3px;padding:0 7px;border-radius:5px;flex-shrink:0}.lc-group-lora-row:hover{background:#ffffff05}.lc-group-lora-row.is-disabled .lc-group-lora-file{opacity:.5}.lc-group-lora-file{flex:1;min-width:0;background:var(--comfy-menu-bg,#353535);color:#d5d8e0;border:1px solid var(--border-color,#666);border-radius:5px;padding:4px 6px;text-align:left;font:11px system-ui;cursor:pointer;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.lc-group-lora-file:hover{border-color:#77705f}.lc-group-lora-grip{color:#606774;cursor:grab;flex:0 0 12px;width:12px}.lc-group-lora-grip .lc-library-icon{width:12px}.lc-group-lora-row.is-dragging{opacity:.35}
.lc-group-lora-group{border-top:1px solid #ffffff0c;margin-top:3px}.lc-group-lora-group-header{display:flex;align-items:center;gap:3px;padding:3px 7px;height:32px;background:#ffffff04;border-radius:5px}.lc-group-lora-group-name{flex:1;min-width:0;color:#c4bdaf;font-size:11px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.lc-group-lora-group-count{font-size:10px;color:#727989;margin-right:2px}.lc-group-lora-group-body{min-height:8px}.lc-group-lora-drop-hint{color:#737b89;font-size:10px;padding:8px 15px;min-height:29px}
.lc-group-lora-footer{height:42px;padding:10px 8px 4px;flex-shrink:0}.lc-group-lora-add{display:flex;align-items:center;justify-content:center;gap:6px;border:1px solid #444;background:#2a2a2a;color:#ddd;width:100%;height:28px;border-radius:5px;font:12px Arial,sans-serif;cursor:pointer;transition:transform .08s ease,box-shadow .08s ease}
.lc-group-lora-add:active{transform:translateY(1px);background:#242424;box-shadow:inset 0 2px 4px #0005;border-color:#555}

.lc-library-top{cursor:move;touch-action:none;user-select:none}
.lc-library-status:empty{display:none}



.lc-group-lora-group-edit{flex:1;min-width:0;width:60px;font:11px system-ui;padding:3px 5px;color:#eee;background:var(--comfy-menu-bg,#353535);border:1px solid var(--lc-accent);border-radius:4px}
.lc-group-lora-group.is-dragging{opacity:.4}
.lc-group-lora-grip *{pointer-events:none}.lc-group-lora-host.is-dragging-list,.lc-group-lora-host.is-dragging-list *{cursor:grabbing!important}
.lc-group-lora-host.is-dragging-list .lc-group-lora-row:hover{background:transparent}
.lc-group-lora-insert-line{position:fixed;top:0;left:0;height:2px;background:#dfb87e;border:0;border-radius:0;pointer-events:none;z-index:2147483647;contain:strict}

.lc-group-lora-strength-mode{max-width:175px;min-height:26px;font:11px system-ui;color:var(--input-text,#ddd);background:color-mix(in srgb,var(--lc-node-bg,var(--comfy-menu-bg,#353535)) 90%,black);border:1px solid color-mix(in srgb,var(--lc-node-bg,var(--comfy-menu-bg,#353535)) 72%,var(--input-text,#ddd));border-radius:6px;padding:4px 8px;cursor:pointer;transition:background .12s,border-color .12s}
.lc-group-lora-strength-mode:hover{background:color-mix(in srgb,var(--lc-node-bg,var(--comfy-menu-bg,#353535)) 92%,var(--input-text,#ddd));border-color:color-mix(in srgb,var(--lc-node-bg,var(--comfy-menu-bg,#353535)) 55%,var(--input-text,#ddd))}
.lc-group-lora-strength-mode:focus,.lc-group-lora-strength-mode:focus-visible{outline:none!important;box-shadow:none!important}
.lc-group-lora-strength-mode option{background:color-mix(in srgb,var(--lc-node-bg,var(--comfy-menu-bg,#353535)) 90%,black);color:var(--input-text,#ddd)}
@supports (appearance:base-select){
  .lc-group-lora-strength-mode,.lc-group-lora-strength-mode::picker(select){appearance:base-select}
  .lc-group-lora-strength-mode{align-items:center;gap:10px}
  .lc-group-lora-strength-mode::picker-icon{opacity:.7;font-size:9px}
  .lc-group-lora-strength-mode::picker(select){background:color-mix(in srgb,var(--lc-node-bg,var(--comfy-menu-bg,#353535)) 90%,black);color:var(--input-text,#ddd);border:1px solid color-mix(in srgb,var(--lc-node-bg,var(--comfy-menu-bg,#353535)) 65%,var(--input-text,#ddd));border-radius:8px;padding:5px;margin-top:4px;box-shadow:0 6px 18px #0005;font:11px system-ui}
  .lc-group-lora-strength-mode option{border-radius:4px;padding:7px 10px;gap:9px;outline:none;background:transparent}
  .lc-group-lora-strength-mode option:hover{background:color-mix(in srgb,var(--lc-node-bg,var(--comfy-menu-bg,#353535)) 68%,var(--input-text,#ddd));color:var(--input-text,#ddd)}
  .lc-group-lora-strength-mode option:focus-visible{outline:1px solid color-mix(in srgb,var(--input-text,#ddd) 35%,transparent);outline-offset:-2px}
  .lc-group-lora-strength-mode option::checkmark{display:none}
}
.lc-library-picker{width:min(1100px,94vw);height:min(780px,88vh);max-height:94vh;min-width:min(640px,94vw);min-height:min(420px,88vh)}
.lc-library-tools>.lc-library-icon-button{width:38px;height:38px;flex-basis:38px;background:var(--comfy-input-bg,#222);border-color:var(--lc-border)}
.lc-library-search{flex:1}
.lc-library-resize{position:absolute;touch-action:none;z-index:3}
.lc-library-resize-se{right:3px;bottom:3px;width:25px;height:25px;cursor:nwse-resize;color:var(--lc-muted);border-radius:4px}
.lc-library-resize-se::after{content:"";position:absolute;width:3px;height:3px;border-radius:50%;background:currentColor;right:5px;bottom:5px;box-shadow:-5px 0 currentColor,-10px 0 currentColor,0 -5px currentColor,-5px -5px currentColor,0 -10px currentColor;pointer-events:none}
.lc-library-resize-se:focus-visible{outline:1px solid var(--lc-muted);outline-offset:-2px}
.lc-library-sentinel{height:1px;width:100%;pointer-events:none}
.lc-library-picker-footer{display:flex;align-items:center;gap:12px;min-height:60px;padding:8px 30px 8px 20px;border-top:1px solid var(--lc-border);flex-shrink:0}
.lc-library-picker-count{color:var(--lc-muted);font-size:12px;margin-right:auto}
.lc-library-selection-count{display:flex;align-items:center;justify-content:center;min-width:88px;min-height:40px;padding:8px 12px;border:1px solid var(--border-color,#666);border-radius:7px;background:var(--comfy-input-bg,#222);color:var(--lc-accent);font:12px system-ui;cursor:pointer}
.lc-library-selection-count.is-selected{background:#dfb87e24;border-color:var(--lc-accent)}
.lc-library-picker-notice{font-size:11px;color:var(--lc-muted);max-width:45%;overflow-wrap:anywhere}
.lc-library-picker-notice.is-error{color:#e9a098}
.lc-library-batch-confirm{min-width:100px;min-height:40px}
.lc-library-card.is-selected{box-shadow:inset 0 0 0 2px var(--lc-accent)}
.lc-library-card.is-selected .lc-library-card-copy{background:#dfb87e20}
.lc-library-card-check[hidden]{display:none}
.lc-library-card-check{position:absolute;right:8px;bottom:65px;width:25px;height:25px;border-radius:50%;background:var(--lc-accent);color:var(--comfy-menu-bg,#353535);display:flex;align-items:center;justify-content:center;font-size:16px;font-weight:700;box-shadow:0 1px 5px #0006;pointer-events:none}
.lc-group-lora-active{flex:0 0 auto}.lc-group-lora-strength-mode{margin-left:auto}
.lc-group-lora-root{border:0;margin:0}
.lc-group-lora-group + .lc-group-lora-root:has(.lc-group-lora-row){border-top:1px solid var(--border-color,#666);margin-top:4px;padding-top:4px}.lc-group-lora-root .lc-group-lora-group-body{min-height:12px}
.lc-library-card{content-visibility:auto;contain-intrinsic-size:auto 250px;transition:border-color .15s}
.lc-library-card:hover{transform:none}.lc-library-results{overscroll-behavior:contain;overflow-anchor:none}
html.lc-group-lora-pointer-drag,html.lc-group-lora-pointer-drag *{cursor:grabbing!important;user-select:none!important}
@media(max-width:640px){.lc-library-folders{flex-basis:145px;width:145px}.lc-library-grid{grid-template-columns:repeat(auto-fill,minmax(115px,1fr))}.lc-library-top{padding:14px}.lc-library-results{padding:12px}.lc-library-info-content{grid-template-columns:1fr}.lc-library-info-art .lc-library-preview{max-height:260px;aspect-ratio:auto;height:260px}}
`;
  document.head.append(style);
}

async function request(path, options) {
  const response = await api.fetchApi(ROOT + path, options);
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    if (data?.error) throw new Error(data.error);
    if (response.status === 404) throw new Error("Library unavailable. Restart ComfyUI to load the new endpoints.");
    throw new Error(`Request failed (${response.status}).`);
  }
  if (!data) throw new Error("The library returned an invalid response.");
  if (data.error) throw new Error(data.error);
  return data;
}

function publish(name, data) {
  infoCache.set(name, data);
  for (const listener of listeners) listener(name, data);
  return data;
}

export function subscribeInfo(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function pumpInfoReads() {
  while (activeInfoReads < 4 && infoReadQueue.length) {
    activeInfoReads++;
    infoReadQueue.shift()().finally(() => { activeInfoReads--; pumpInfoReads(); });
  }
}
export function getLoraInfo(name) {
  if (infoCache.has(name)) return Promise.resolve(infoCache.get(name));
  const key = `read:${name}`;
  if (!pending.has(key)) {
    pending.set(key, new Promise((resolve, reject) => {
      infoReadQueue.push(async () => {
        try { resolve(infoCache.get(name) || publish(name, await request(`/info?lora=${encodeURIComponent(name)}`))); }
        catch (error) { reject(error); }
        finally { pending.delete(key); }
      });
      pumpInfoReads();
    }));
  }
  return pending.get(key);
}

async function getLoraDetails(name) {
  return request(`/info?lora=${encodeURIComponent(name)}&details=1`);
}

export async function ensureLoraInfo(name, force = false) {
  const info = await getLoraInfo(name);
  if (info.has_info_file && !force) return info;
  const key = `fetch:${force}:${name}`;
  if (!pending.has(key)) {
    pending.set(key, request("/info", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ lora: name, force }),
    }).then((data) => publish(name, data)).finally(() => pending.delete(key)));
  }
  return pending.get(key);
}

function restoreLibraryBounds(dialog, session) {
  try {
    const saved = JSON.parse(sessionStorage.getItem("lc-group-library-bounds") || "null");
    if (saved?.session === session) {
      const width = Math.min(saved.width, innerWidth * .94), height = Math.min(saved.height, innerHeight * .94);
      Object.assign(dialog.style, {margin:"0", width:width+"px", height:height+"px",
        left:Math.max(0,Math.min(saved.left,innerWidth-width))+"px", top:Math.max(0,Math.min(saved.top,innerHeight-height))+"px"});
    }
  } catch {}
  if (!dialog.open) dialog.showModal();
  let bounds = dialog.getBoundingClientRect();
  const snapshot = () => { if (dialog.open) bounds = dialog.getBoundingClientRect(); };
  const observer = new ResizeObserver(snapshot); observer.observe(dialog);
  dialog.addEventListener("pointerup", snapshot, true);
  dialog.addEventListener("keyup", snapshot);
  dialog.addEventListener("close", () => {
    observer.disconnect();
    const {left,top,width,height} = bounds;
    try { sessionStorage.setItem("lc-group-library-bounds", JSON.stringify({session,left,top,width,height})); } catch {}
  }, {once:true});
}

function modal(title, subtitle, extraClass = "", deferred = false) {
  installLibraryStyles();
  const dialog = element("dialog", `lc-library-dialog ${extraClass}`);
  const shell = element("div", "lc-library-shell");
  const top = element("div", "lc-library-top");
  const heading = element("div", "lc-library-heading");
  const label = element("h2", "", title);
  label.id = `lc-dialog-${crypto.randomUUID()}`;
  dialog.setAttribute("aria-labelledby", label.id);
  heading.append(label);
  if (subtitle) heading.append(element("p", "lc-library-subtitle", subtitle));
  top.append(heading, iconButton("close", "Close", () => dialog.close()));
  let drag;
  top.addEventListener("pointerdown", (event) => {
    if (event.button !== 0 || event.target.closest("button,a,input")) return;
    const rect = dialog.getBoundingClientRect();
    drag = { x: event.clientX, y: event.clientY, left: rect.left, top: rect.top };
    dialog.style.margin = "0";
    dialog.style.left = rect.left + "px";
    dialog.style.top = rect.top + "px";
    top.setPointerCapture(event.pointerId);
    event.preventDefault();
  });
  top.addEventListener("pointermove", (event) => {
    if (!drag) return;
    dialog.style.left = Math.max(0, Math.min(window.innerWidth - dialog.offsetWidth, drag.left + event.clientX - drag.x)) + "px";
    dialog.style.top = Math.max(0, Math.min(window.innerHeight - dialog.offsetHeight, drag.top + event.clientY - drag.y)) + "px";
  });
  for (const type of ["pointerup", "pointercancel", "lostpointercapture"]) top.addEventListener(type, () => { drag = null; });
  shell.append(top);
  dialog.append(shell);
  document.body.append(dialog);
  dialog.addEventListener("click", (event) => {
    if (event.target !== dialog) return;
    const rect = dialog.getBoundingClientRect();
    if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) dialog.close();
  });
  for (const type of ["keydown", "pointerdown", "pointerup", "wheel"]) dialog.addEventListener(type, (event) => event.stopPropagation());
  dialog.addEventListener("close", () => dialog.remove(), { once: true });
  if (!deferred) dialog.showModal();
  return { dialog, shell };
}

function preview(url) {
  const art = element("div", "lc-library-preview");
  art.append(icon("image"), element("span", "", "No preview"));
  if (url) {
    const img = element("img");
    img.alt = "LoRA preview";
    img.loading = "lazy";
    img.decoding = "async";
    img.referrerPolicy = "no-referrer";
    img.src = url.startsWith("/") ? api.apiURL(url) : url;
    img.addEventListener("error", () => img.remove(), { once: true });
    art.append(img);
  }
  return art;
}

export function showLoraLibrary({ mode = "add", groupName = "", onSelect, onSelectBatch }) {
  const addMode = mode === "add", PAGE_SIZE = 50;
  const { dialog, shell } = modal(addMode ? "Add LoRAs" : "Replace LoRA", groupName, "lc-library-picker", true);
  makeLibraryResizable(dialog);
  const tools = element("div", "lc-library-tools");
  const search = element("input", "lc-library-search");
  search.type = "search";
  search.placeholder = "Search LoRAs by filename or folder…";
  search.setAttribute("aria-label", "Search LoRAs");
  tools.append(search);
  const body = element("div", "lc-library-body");
  const folders = element("nav", "lc-library-folders");
  folders.setAttribute("aria-label", "LoRA folders");
  const results = element("div", "lc-library-results");
  const grid = element("div", "lc-library-grid");
  const sentinel = element("div", "lc-library-sentinel");
  const footer = element("div", "lc-library-picker-footer");
  const count = element("div", "lc-library-picker-count");
  const notice = element("div", "lc-library-picker-notice");
  notice.setAttribute("role", "status");
  const selectedButton = element("button", "lc-library-selection-count");
  selectedButton.type = "button";
  const confirm = element("button", "lc-library-button is-primary lc-library-batch-confirm", "Confirm");
  confirm.type = "button";
  confirm.hidden = !addMode;
  footer.append(count, notice, confirm);
  results.append(grid, sentinel);
  body.append(folders, results);
  shell.append(tools, body, footer);
  let names = [], matches = [], folder = lastFolder, version = 0, rendered = 0, pageFrame = 0;
  let selectedOnly = false, previousQuery = "", loading = false;
  const selected = new Set(), cards = new Map();
  const normalized = (name) => name.replaceAll("\\", "/");
  const relativeFolder = (name) => normalized(name).split("/").slice(0, -1).join("/");
  const matchesFolder = (name) => !folder || relativeFolder(name) === folder || relativeFolder(name).startsWith(folder + "/");
  const setNotice = (text = "", error = false) => {
    notice.textContent = text;
    notice.classList.toggle("is-error", error);
  };
  function updateFooter() {
    if (addMode && (selected.size || selectedOnly)) {
      selectedButton.textContent = `${selected.size} added`;
      selectedButton.setAttribute("aria-label", `${selected.size} added · ${selectedOnly ? "Show all LoRAs" : "Show selected LoRAs"}`);
      selectedButton.setAttribute("aria-pressed", String(selectedOnly));
      selectedButton.classList.toggle("is-selected", selectedOnly);
      selectedButton.title = selectedOnly ? "Back to library" : "Show selected LoRAs";
      count.replaceChildren(selectedButton);
    } else count.textContent = `${matches.length} LoRA${matches.length === 1 ? "" : "s"}`;
    confirm.disabled = !selected.size || loading;
    confirm.textContent = selected.size ? `Confirm (${selected.size})` : "Confirm";
  }
  selectedButton.addEventListener("click", () => {
    selectedOnly = !selectedOnly;
    if (selectedOnly) { previousQuery = search.value; search.value = ""; }
    else search.value = previousQuery;
    renderFolders(); render();
  });
  // Only confirmed additions start automatic downloads; browse/selection stay local.
  async function fetchChosenInfo(items) {
    let index = 0;
    async function worker() {
      while (index < items.length) {
        const name = items[index++];
        try { await ensureLoraInfo(name); } catch { /* Details still allow retry. */ }
      }
    }
    await Promise.all([worker(), worker()]);
  }
  confirm.addEventListener("click", () => {
    if (!selected.size || loading) return;
    const items = [...selected];
    if (onSelectBatch?.(items) === false) return;
    dialog.close();
    void fetchChosenInfo(items);
  });
  const observer = new IntersectionObserver((entries) => {
    for (const entry of entries) if (entry.isIntersecting) {
      observer.unobserve(entry.target);
      const name = entry.target.dataset.name;
      getLoraInfo(name).then((info) => updateCard(name, info)).catch(() => {});
    }
  }, { root: results, rootMargin: "100px" });
  const pages = new IntersectionObserver((entries) => {
    if (entries.some((entry) => entry.isIntersecting) && rendered < matches.length && !pageFrame) {
      pageFrame = requestAnimationFrame(() => { pageFrame = 0; if (dialog.open) appendPage(); });
    }
  }, { root: results, rootMargin: "80px" });
  function updateCard(name, info) {
    const card = cards.get(name);
    if (!card || !dialog.open) return;
    const url = info.preview_url || "";
    if (card.dataset.previewUrl !== url) {
      card.dataset.previewUrl = url;
      card.querySelector(".lc-library-preview").replaceWith(preview(url));
    }
    const badge = card.querySelector(".lc-library-card-badge");
    badge.textContent = info.base_model || "";
    badge.hidden = !badge.textContent;
  }
  function updateSelection(card, name) {
    const checked = selected.has(name);
    card.classList.toggle("is-selected", checked);
    if (addMode) card.setAttribute("aria-pressed", String(checked));
    card.querySelector(".lc-library-card-check").hidden = !checked;
  }
  const unsubscribe = subscribeInfo(updateCard);
  dialog.addEventListener("close", () => {
    observer.disconnect(); pages.disconnect(); unsubscribe();
    if (pageFrame) cancelAnimationFrame(pageFrame);
  }, { once: true });
  function renderFolders() {
    folders.replaceChildren();
    const counts = new Map([["", names.length]]);
    for (const name of names) {
      const parts = relativeFolder(name).split("/").filter(Boolean);
      for (let i = 1; i <= parts.length; i++) {
        const path = parts.slice(0, i).join("/");
        counts.set(path, (counts.get(path) || 0) + 1);
      }
    }
    for (const path of [...counts.keys()].sort((a, b) => a.localeCompare(b))) {
      const button = element("button", "lc-library-folder");
      button.type = "button";
      button.title = path || "All folders";
      button.classList.toggle("is-selected", !selectedOnly && folder === path);
      button.setAttribute("aria-current", !selectedOnly && folder === path ? "true" : "false");
      button.style.paddingLeft = `${8 + Math.min(path.split("/").length - 1, 6) * 10}px`;
      button.append(icon("folder"), element("span", "lc-library-folder-name", path ? path.split("/").at(-1) : "All LoRAs"), element("span", "lc-library-count", counts.get(path)));
      button.addEventListener("click", () => {
        if (selectedOnly) search.value = previousQuery;
        selectedOnly = false; folder = path; lastFolder = path;
        renderFolders(); render();
      });
      folders.append(button);
    }
  }
  function createCard(name) {
    const card = element("div", "lc-library-card");
    card.tabIndex = 0;
    card.setAttribute("role", "button");
    card.addEventListener("keydown", (event) => {
      if (event.target === card && ["Enter", " "].includes(event.key)) { event.preventDefault(); card.click(); }
    });
    card.dataset.name = name; card.title = name;
    card.setAttribute("aria-label", `Select ${name}`);
    const copy = element("div", "lc-library-card-copy");
    copy.append(element("div", "lc-library-card-name", normalized(name).split("/").at(-1)), element("div", "lc-library-card-folder", relativeFolder(name) || "Root folder"));
    const badge = element("span", "lc-library-card-badge"); badge.hidden = true;
    const check = element("span", "lc-library-card-check", "✓"); check.setAttribute("aria-hidden", "true");
    card.append(preview(), copy, badge, check);
    updateSelection(card, name);
    card.addEventListener("click", () => {
      if (addMode) {
        if (selected.has(name)) selected.delete(name); else selected.add(name);
        if (selectedOnly) render();
        else { updateSelection(card, name); updateFooter(); }
      } else {
        if (onSelect(name) === false) return;
        dialog.close(); void fetchChosenInfo([name]);
      }
    });
    cards.set(name, card);
    return card;
  }
  function appendPage() {
    pages.unobserve(sentinel);
    const fragment = document.createDocumentFragment();
    const added = [];
    for (const name of matches.slice(rendered, rendered + PAGE_SIZE)) {
      const card = createCard(name); fragment.append(card); added.push(card);
    }
    rendered += added.length;
    grid.append(fragment);
    for (const card of added) observer.observe(card);
    sentinel.hidden = rendered >= matches.length;
    if (!sentinel.hidden) pages.observe(sentinel);
  }
  function render() {
    if (pageFrame) cancelAnimationFrame(pageFrame);
    pageFrame = 0;
    observer.disconnect(); pages.disconnect(); cards.clear();
    grid.replaceChildren();
    results.querySelector(".lc-library-empty")?.remove();
    results.scrollTop = 0;
    const query = search.value.trim().toLowerCase();
    matches = names.filter((name) => (selectedOnly ? selected.has(name) : matchesFolder(name)) && normalized(name).toLowerCase().includes(query));
    if (!matches.length) results.insertBefore(element("div", "lc-library-empty", selectedOnly ? "No selected LoRAs." : "No LoRAs found."), sentinel);
    rendered = 0; appendPage(); updateFooter();
  }
  async function load() {
    const token = ++version;
    loading = true; updateFooter();
    setNotice("Loading…");
    try {
      const data = await request("/library");
      const list = data.loras || [];
      if (!dialog.isConnected || token !== version) return;
      names = [...list];
      restoreLibraryBounds(dialog, data.session);
      const available = new Set(names);
      for (const name of selected) if (!available.has(name)) selected.delete(name);
      if (folder && !names.some(matchesFolder)) folder = "";
      setNotice(); renderFolders(); render(); search.focus();
    } catch (error) { if (dialog.isConnected) { if (!dialog.open) dialog.showModal(); setNotice(error.message, true); } }
    finally { if (token === version) { loading = false; updateFooter(); } }
  }
  search.addEventListener("input", render);
  load();
  return () => { if (dialog.open) dialog.close(); else { dialog.dispatchEvent(new Event("close")); dialog.remove(); } };
}

export function showLoraInfo(name) {
  const { dialog, shell } = modal("LoRA information", name, "lc-library-info");
  const content = element("div", "lc-library-info-content");
  const status = element("div", "lc-library-status", "Loading local information…");
  shell.append(content, status);

  function render(data) {
    if (!dialog.open) return;
    content.replaceChildren();
    const art = element("div", "lc-library-info-art");
    let index = 0;
    const images = data.images || [];
    const frame = preview(images[0]);
    art.append(frame);
    if (images.length > 1) {
      const nav = element("div", "lc-library-image-nav");
      const counter = element("span", "lc-library-count", `1 / ${images.length}`);
      const turn = (direction) => {
        index = (index + direction + images.length) % images.length;
        art.querySelector(".lc-library-preview").replaceWith(preview(images[index]));
        counter.textContent = `${index + 1} / ${images.length}`;
      };
      const prev = iconButton("chevron", "Previous preview", () => turn(-1));
      prev.style.transform = "rotate(180deg)";
      nav.append(prev, counter, iconButton("chevron", "Next preview", () => turn(1)));
      art.append(nav);
    }
    const details = element("div", "lc-library-info-details");
    details.append(element("h3", "", "MODEL DETAILS"));
    const fields = element("dl", "lc-library-info-grid");
    for (const [label, value] of [["Name", data.name], ["Version", data.version], ["Base model", data.base_model]]) {
      if (value) fields.append(element("dt", "", label), element("dd", "", value));
    }
    if (data.civitai_url) {
      const link = element("a", "lc-library-link", "View on Civitai ↗");
      link.href = data.civitai_url; link.target = "_blank"; link.rel = "noopener noreferrer";
      const value = element("dd"); value.append(link);
      fields.append(element("dt", "", "Civitai"), value);
    }
    details.append(fields, element("h3", "", "TRIGGER WORDS"));
    const chips = element("div", "lc-library-chips");
    for (const word of data.trigger_words || []) {
      const chip = element("button", "lc-library-chip", word);
      chip.title = "Copy trigger word";
      chip.addEventListener("click", async () => {
        try { await navigator.clipboard.writeText(word); status.textContent = `Copied: ${word}`; }
        catch { status.textContent = "Clipboard unavailable. Select and copy the word manually."; }
      });
      chips.append(chip);
    }
    if (!chips.childElementCount) chips.append(element("span", "lc-library-description", "No trigger words recorded."));
    details.append(chips);
    if (data.description) {
      const text = new DOMParser().parseFromString(data.description, "text/html").body.textContent;
      details.append(element("h3", "", "ABOUT"), element("div", "lc-library-description", text));
    }
    const download = iconButton("refresh", "Refresh model info", async () => {
      download.disabled = true; status.textContent = "Downloading info…";
      try {
        const fetched = await ensureLoraInfo(name, true);
        render({ ...await getLoraDetails(name), fetch_error: fetched.fetch_error });
      } catch (error) { status.textContent = error.message; download.disabled = false; }
    });
    download.classList.add("lc-library-info-refresh");
    const top = shell.querySelector(".lc-library-top");
    top.querySelector(".lc-library-info-refresh")?.remove();
    top.insertBefore(download, top.lastElementChild);
    content.append(art, details);
    status.textContent = data.fetch_error || "";
    status.classList.toggle("is-error", !!data.fetch_error);
  }
  getLoraDetails(name).then(render).catch((error) => { status.textContent = error.message; });
  const unsubscribe = subscribeInfo((file, info) => {
    if (file === name) getLoraDetails(name).then((details) => render({ ...details, fetch_error: info.fetch_error })).catch((error) => { status.textContent = error.message; });
  });
  dialog.addEventListener("close", unsubscribe, { once: true });
  return () => dialog.close();
}
