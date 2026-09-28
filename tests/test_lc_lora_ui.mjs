// Browser integration test with synthetic model files; no ComfyUI job or Civitai request.
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const testNodeType = process.env.LC_TEST_NODE_TYPE || "LCGroupLoraLoader";
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const stateSource = await fs.readFile(path.join(root, "web/lc_lora_state.js"), "utf8");
const state = await import(`data:text/javascript;base64,${Buffer.from(stateSource).toString("base64")}`);
const groups = [{ id: "g1", name: "Character" }, { id: "g2", name: "Style" }];
const baseRows = [{ id: "a", lora: "a", on: true, strength: 1, group: "" }, { id: "b", lora: "b", on: false, strength: 0.4, group: "g1" }];
const moved = state.moveRow(baseRows, "a", "g1", "b");
assert.deepEqual(moved.map((row) => [row.id, row.group]), [["a", "g1"], ["b", "g1"]]);
assert.equal(state.groupState(moved, "g1").mixed, true);
assert.equal(state.groupState(state.toggleGroup(moved, "g1", true), "g1").checked, true);
assert.equal(state.removeGroup(moved, "g1").every((row) => row.group === ""), true);
assert.deepEqual(state.normalizeRows([{ lora: "legacy", group: "missing", on: false }], groups, () => "id1"), [{ lora: "legacy", group: "", on: false, id: "id1" }]);

const migrated = {nodes:[{type:'LCLoraLoader',properties:{},title:'Original'}, {type:'LCLoraLoader',properties:{lc_lora_groups:[{id:'g1',name:'Group'}]},title:'LC LoRA Loader 🎚️',widgets_values:['rows'],pos:[1,2]}],definitions:{subgraphs:[{nodes:[{type:'LCLoraLoader',properties:{lc_lora_groups:[]},title:'Custom title'}]}]}};
state.migrateGroupLoaders(migrated);
assert.equal(migrated.nodes[0].type, 'LCLoraLoader');
assert.equal(migrated.nodes[1].type, 'LCGroupLoraLoader');
assert.equal(migrated.nodes[1].title, 'LC Group LoRA Loader 🎚️');
assert.deepEqual(migrated.nodes[1].widgets_values, ['rows']);
assert.deepEqual(migrated.nodes[1].pos, [1,2]);
assert.equal(migrated.definitions.subgraphs[0].nodes[0].title, 'Custom title');

const names = ["Characters/Aster.safetensors", "Characters/Mira.safetensors", "Styles/Soft pastel.safetensors", "Styles/Ink wash.safetensors", "Lighting/Golden hour.safetensors", "Lighting/Neon bloom.safetensors", "Detail/Film grain.safetensors", "Detail/Fine detail.safetensors"];
let libraryNames = [...names];
let serverSession = "test-session";
let libraryScans = 0;
let refreshError = null;
const savedInfo = new Set(names.slice(1));
const posts = [];
const postBodies = [];
const errors = [];
const browser = await chromium.launch({ headless: true, executablePath: process.env.LC_BROWSER_EXECUTABLE });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 });
page.on("pageerror", (error) => errors.push(error.message));
await page.route("**/*", async (route) => {
  const url = new URL(route.request().url());
  if (url.pathname === "/") return route.fulfill({ contentType: "text/html", body: `<!doctype html><html><head><meta charset="utf-8"><style>body{background:#17191f;color:#eee;font-family:system-ui;margin:60px}.node{width:430px;background:#24262c;border:1px solid #474139;border-radius:10px;box-shadow:0 10px 30px #0005;overflow:hidden}.title{background:#554736;font-size:14px;padding:10px 14px}h1{font-size:20px;color:#d1d3da}p{font-size:12px;color:#8d95a6}</style></head><body><h1>LoRA library · interaction test</h1><p>Synthetic fixtures · no generation</p><div class="node"><div class="title">LC Group LoRA Loader 🎚️</div><div id="node"></div></div><script type="module">
    import { app } from '/scripts/app.js';
    await import('/extensions/lc123/lc_lora_loader.js');
    await import('/extensions/lc123/lc_group_lora_loader.js');
    class Node {
      constructor() {this.id=1;this.widgets=[{name:'lora_rows',value:'[]',options:{}}];this.properties={};this.size=[430,100];this.pos=[200,150];}
      addDOMWidget(name,type,el,options) {document.querySelector('#node').replaceChildren(el);this.dom={name,type,el,options};return this.dom;}
      computeSize(){return [430,(this.dom?.options.getMinHeight()||80)+40];}
      setSize(value){this.size=value;}
      setDirtyCanvas(){}
    }
    const ext=window.extensions.find(ext=>ext.name==='LC123.GroupLoraLoader');
    await ext.beforeRegisterNodeDef(Node,{name:'${testNodeType}'});
    const oldExt=window.extensions.find(ext=>ext.name==='LC123.LoraLoader');
    await oldExt.beforeRegisterNodeDef(Node,{name:'${testNodeType}'});
    class OriginalNode {}
    await ext.beforeRegisterNodeDef(OriginalNode,{name:'LCLoraLoader'});
    if(OriginalNode.prototype.onNodeCreated) throw new Error('Group extension modified original loader');
    window.node=new Node();app.graph._nodes=[window.node];window.node.onNodeCreated();
    window.restore=()=>{const saved={properties:structuredClone(window.node.properties),value:window.node.widgets[0].value};window.node.onRemoved();window.node=new Node();window.node.properties=saved.properties;window.node.widgets[0].value=saved.value;window.node.onNodeCreated();window.node.onConfigure();app.graph._nodes=[window.node];};
  </script></body></html>` });
  if (url.pathname === "/scripts/app.js") return route.fulfill({ contentType: "text/javascript", body: `window.extensions=[];export const app={registerExtension(ext){window.extensions.push(ext)},graph:{_nodes:[]},canvas:{setDirty(){}},extensionManager:{workflow:{activeWorkflow:{changeTracker:{checkState(){}}}}}};window.app=app;` });
  if (url.pathname === "/scripts/api.js") return route.fulfill({ contentType: "text/javascript", body: `export const api={fetchApi:(url,opts)=>fetch(url,opts),apiURL:url=>url};` });
  if (url.pathname.startsWith("/extensions/lc123/")) {
    const file = path.basename(url.pathname);
    return route.fulfill({ contentType: "text/javascript", body: await fs.readFile(path.join(root, "web", file), "utf8") });
  }
  if (url.pathname.endsWith("/library")) {libraryScans++;return route.fulfill({ json: { loras: libraryNames, session:serverSession } });}
  if (url.pathname.endsWith("/info")) {
    const name = route.request().method() === "POST" ? route.request().postDataJSON().lora : url.searchParams.get("lora");
    if (route.request().method() === "POST") { posts.push(name); postBodies.push(route.request().postDataJSON()); savedInfo.add(name); }
    return route.fulfill({ json: {
      fetch_error: route.request().method() === "POST" ? refreshError : undefined,
      lora: name, name: name.split("/").at(-1).replace(".safetensors", ""), version: "V1", base_model: "Anima",
      has_info: savedInfo.has(name), has_info_file: savedInfo.has(name), info_file: savedInfo.has(name) ? "sample.civitai.info" : null,
      preview_url: `/lc123/group_lora_loader/preview?lora=${encodeURIComponent(name)}`, images: [`/lc123/group_lora_loader/preview?lora=${encodeURIComponent(name)}`],
      trigger_words: ["soft lighting", "gentle details"], metadata: { "modelspec.title": "Synthetic test LoRA" }, raw_info: { id: 123 }, civitai_url: "https://civitai.com/models/123?modelVersionId=456",
      description: "<b>Preview test</b> — cached model information.",
    } });
  }
  if (url.pathname.endsWith("/preview")) {
    const name = url.searchParams.get("lora"); const hue = (names.indexOf(name) * 37 + 20) % 360;
    return route.fulfill({ contentType: "image/svg+xml", body: `<svg xmlns="http://www.w3.org/2000/svg" width="400" height="500" viewBox="0 0 400 500"><defs><linearGradient id="g" x2="1" y2="1"><stop stop-color="hsl(${hue},36%,30%)"/><stop offset="1" stop-color="hsl(${hue+45},42%,13%)"/></linearGradient></defs><rect width="400" height="500" fill="url(#g)"/><circle cx="190" cy="165" r="85" fill="hsl(${hue},45%,72%)" opacity=".6"/><path d="M-30 500 Q40 160 240 270 T450 360 V500" fill="hsl(${hue+15},28%,58%)" opacity=".6"/><text x="25" y="460" fill="#eee" font-size="16" font-family="sans-serif">LIBRARY PREVIEW</text></svg>` });
  }
  return route.fulfill({ status: 404, body: "Not found" });
});

async function pointerDrag(source,target,dy) {
  const a=await source.boundingBox(),b=await target.boundingBox();
  await page.mouse.move(a.x+a.width/2,a.y+a.height/2);await page.mouse.down();
  await page.mouse.move(b.x+b.width/2,b.y+(dy??b.height/2),{steps:8});await page.mouse.up();
}
try {
  await page.goto("http://127.0.0.1:18764/");
  await page.evaluate(() => {
    window.libraryOpeningBounds = [];
    const original = HTMLDialogElement.prototype.showModal;
    HTMLDialogElement.prototype.showModal = function() {
      original.call(this);
      if (this.classList.contains('lc-library-picker')) window.libraryOpeningBounds.push(this.getBoundingClientRect().toJSON());
    };
    document.querySelector('.node').style.background = window.node.bgcolor;
  });
  await page.getByRole('button', {name:'Add LoRA',exact:true}).click();
  await page.locator(".lc-library-card").first().waitFor();
  assert.equal(posts.length, 0, "Browsing must not download Civitai info");
  assert.equal(await page.locator('.lc-library-grid').evaluate(el => getComputedStyle(el).gridTemplateColumns.split(' ').length), 5);
  assert.equal(await page.getByRole('button',{name:'Refresh library',exact:true}).count(), 0);
  await page.getByRole("button", { name: `Select ${names[0]}`, exact: true }).click();
  await page.getByRole("button", { name: `Select ${names[1]}`, exact: true }).click();
  assert.equal(await page.locator('.lc-library-card.is-selected').count(), 2);
  await page.locator('.lc-library-heading').hover();
  assert.equal(await page.getByRole('button',{name:'Redownload info'}).count(), 0);
  assert.equal(await page.locator('[data-group-id=""] button[aria-expanded]').count(), 0);
  assert.equal(await page.evaluate(() => JSON.parse(window.node.widgets[0].value).length), 0, 'Selection must stay pending');
  assert.equal(posts.length, 0, 'Pending selections must not download info');
  await page.getByRole("button", { name: `Select ${names[0]}`, exact: true }).click();
  assert.equal(await page.locator('.lc-library-card.is-selected').count(), 1, 'Second click deselects');
  await page.getByRole("button", { name: `Select ${names[0]}`, exact: true }).click();
  const countButton = page.getByRole('button', {name:'2 added · Show selected LoRAs',exact:true});
  const countRect = await countButton.boundingBox();
  assert.ok(countRect.width >= 88 && countRect.height >= 40);
  await countButton.click();
  assert.equal(await page.locator('.lc-library-card').count(), 2);
  await page.getByRole('button', {name:'2 added · Show all LoRAs',exact:true}).click();
  assert.equal(await page.locator('.lc-library-card').count(), names.length);
  const dialog = page.locator("dialog[open]");
  assert.equal(await dialog.locator('.lc-library-resize').count(), 1, 'Only corner resize is available');
  const oldRect = await dialog.boundingBox();
  const top = await dialog.locator(".lc-library-heading").boundingBox();
  await page.mouse.move(top.x + 30, top.y + 10); await page.mouse.down();
  await page.mouse.move(top.x + 80, top.y + 45, { steps: 5 }); await page.mouse.up();
  const newRect = await dialog.boundingBox();
  assert.ok(newRect.x > oldRect.x + 30 && newRect.y > oldRect.y + 20, "Dialog must move with header drag");
  const resize = await dialog.locator('.lc-library-resize-se').boundingBox();
  await page.mouse.move(resize.x + resize.width - 5, resize.y + resize.height - 5); await page.mouse.down();
  await page.mouse.move(resize.x + resize.width + 55, resize.y + resize.height + 20, {steps:5}); await page.mouse.up();
  const resized = await dialog.boundingBox();
  assert.ok(resized.width > newRect.width + 40 && resized.height > newRect.height + 15, 'Corner resize must grow both dimensions');
  assert.ok(Math.abs(resized.x-newRect.x)<1 && Math.abs(resized.y-newRect.y)<1, 'Resizing must not recenter');
  const output = process.env.LC_UI_SCREENSHOT_DIR;
  if (output) { await fs.mkdir(output, { recursive: true }); await page.screenshot({ path: path.join(output, "lora-library.png") }); }
  await page.getByRole('button', {name:'Confirm (2)',exact:true}).click();
  assert.equal(await page.locator('dialog[open]').count(), 0);
  await page.waitForFunction(() => JSON.parse(window.node.widgets[0].value).length === 2);
  await page.waitForFunction(() => document.querySelectorAll('[data-info-name].is-active').length === 2);
  assert.deepEqual(posts, [names[0]], "Only confirmed missing info should be downloaded");
  await page.getByRole('button', {name:'Add LoRA',exact:true}).click();
  await page.locator('.lc-library-card').first().waitFor();
  assert.equal(await page.locator('.lc-library-card.is-selected').count(), 0, 'Existing node LoRAs must not start selected');
  assert.equal(await page.locator('.lc-library-picker-count').innerText(), '8 LoRAs');
  const restoredBounds = await page.locator('dialog[open]').boundingBox();
  for (const key of ['x','y','width','height']) assert.ok(Math.abs(restoredBounds[key]-resized[key])<2, `Persisted ${key}`);
  const openingBounds = await page.evaluate(() => window.libraryOpeningBounds.at(-1));
  for (const key of ['x','y','width','height']) assert.ok(Math.abs(openingBounds[key]-resized[key])<2, `First visible frame restores ${key}`);
  assert.equal(libraryScans, 2, 'Every opening scans again');
  await page.getByRole('button', {name:`Select ${names[2]}`,exact:true}).click();
  await page.getByRole('button', {name:'Close',exact:true}).click();
  assert.equal(await page.evaluate(() => JSON.parse(window.node.widgets[0].value).length), 2, 'Closing must discard pending additions');

  serverSession = 'restarted-session';
  await page.getByRole('button', {name:'Add LoRA',exact:true}).click();
  await page.locator('.lc-library-card').first().waitFor();
  const resetBounds = await page.locator('dialog[open]').boundingBox();
  for (const key of ['x','y','width','height']) assert.ok(Math.abs(resetBounds[key]-oldRect[key])<2, `Restart resets ${key}`);
  await page.getByRole('button', {name:'Close',exact:true}).click();
  const themed = await page.evaluate(() => {
    document.documentElement.style.setProperty('--comfy-input-bg', 'rgb(12, 34, 56)');
    document.documentElement.style.setProperty('--input-text', 'rgb(210, 220, 230)');
    const button = document.querySelector('.lc-group-lora-add-group');
    const select = document.querySelector('.lc-group-lora-strength-mode');
    select.focus();
    const result = {background:getComputedStyle(button).backgroundColor, color:getComputedStyle(button).color, outline:getComputedStyle(select).outlineStyle};
    document.documentElement.style.removeProperty('--comfy-input-bg');
    document.documentElement.style.removeProperty('--input-text');
    return result;
  });
  assert.deepEqual(themed, {background:'rgba(0, 0, 0, 0)', color:'rgb(167, 171, 183)', outline:'none'});
  const nodeColors = await page.evaluate(() => {
    const node = window.node, original = node.bgcolor;
    const read = () => getComputedStyle(document.querySelector('.lc-group-lora-strength-mode'), '::picker(select)').backgroundColor;
    node.bgcolor = '#285a70'; node.onDrawForeground();
    const blue = read();
    document.documentElement.style.setProperty('--comfy-menu-bg', '#ffffff');
    const changedMenu = read();
    node.bgcolor = '#704030'; node.onDrawForeground();
    const brown = read();
    document.documentElement.style.removeProperty('--comfy-menu-bg');
    node.bgcolor = original; node.onDrawForeground();
    return {blue,changedMenu,brown};
  });
  assert.equal(nodeColors.blue, nodeColors.changedMenu, 'Node controls must use node background, not global menu background');
  assert.notEqual(nodeColors.blue, nodeColors.brown, 'Node color changes must update controls');
  assert.equal(await page.locator('.lc-group-lora-header').getByRole('button').count(), 1);
  assert.equal(await page.locator('.lc-group-lora-footer').innerText(), '➕ Add LoRA');
  assert.equal(await page.locator('.lc-group-lora-add').evaluate(el => getComputedStyle(el).borderTopStyle), 'solid');
  await page.getByRole("combobox", {name:"Show Strengths"}).selectOption("Separate Model & Clip");
  const firstRow = page.locator('.lc-group-lora-row').first();
  await firstRow.locator('[data-strength-field="strength"] .lc-group-lora-str-value').click();
  await page.getByRole('spinbutton', {name:'Model strength', exact:true}).fill('0');
  await page.getByRole('spinbutton', {name:'Model strength', exact:true}).press('Enter');
  await firstRow.locator('[data-strength-field="strengthTwo"] .lc-group-lora-str-value').click();
  await page.getByRole('spinbutton', {name:'CLIP strength', exact:true}).fill('0.65');
  await page.getByRole('spinbutton', {name:'CLIP strength', exact:true}).press('Enter');
  assert.deepEqual(await page.evaluate(() => {const row=JSON.parse(window.node.widgets[0].value)[0];return [row.strength,row.strengthTwo]}), [0,0.65]);
  await page.evaluate(() => window.restore());
  assert.equal(await page.getByRole("combobox", {name:"Show Strengths"}).inputValue(), "Separate Model & Clip");
  assert.equal(await firstRow.locator('[data-strength-field="strengthTwo"] .lc-group-lora-str-value').innerText(), '0.65');
  await page.locator(".lc-group-lora-file").first().click();
  await page.getByRole("searchbox", { name: "Search LoRAs" }).fill("Ink wash");
  await page.getByRole("button", { name: `Select ${names[3]}`, exact: true }).click();
  assert.equal(await page.locator("dialog[open]").count(), 0, "Replace picker must close");
  assert.equal(await page.evaluate(() => JSON.parse(window.node.widgets[0].value)[0].lora), names[3]);

  await page.getByRole("button", { name: "Add Group", exact: true }).click();
  await page.getByRole("textbox", { name: "Group name" }).fill("Character");
  await page.getByRole("textbox", { name: "Group name" }).press("Enter");
  assert.equal(await page.locator("dialog[open]").count(), 0, "Group editing must be inline");
  assert.equal(await page.locator('.lc-group-lora-group').last().getAttribute('data-group-id'), '');
  assert.equal(await page.locator('[data-group-id=""] .lc-group-lora-group-header').count(), 0);
  const groupId = await page.evaluate(() => window.node.properties.lc_lora_groups[0].id);
  const group = page.locator(`[data-group-id="${groupId}"]`);
  await pointerDrag(page.locator(".lc-group-lora-row .lc-group-lora-grip").first(), group.locator(".lc-group-lora-group-header"));
  await page.waitForFunction((id) => JSON.parse(window.node.widgets[0].value).some(row => row.group === id), groupId);
  await group.getByRole("checkbox", { name: "Toggle Character", exact: true }).uncheck();
  assert.equal(await page.evaluate((id) => JSON.parse(window.node.widgets[0].value).find(row => row.group === id).on, groupId), false);
  await group.getByRole("checkbox", { name: "Toggle Character", exact: true }).check();
  await group.getByRole("button", { name: "Collapse group", exact: true }).click();
  assert.equal(await group.locator(".lc-group-lora-row").count(), 0);
  const before = await page.evaluate(() => ({ rows: window.node.widgets[0].value, groups: JSON.stringify(window.node.properties.lc_lora_groups) }));
  await page.evaluate(() => window.restore());
  assert.deepEqual(await page.evaluate(() => ({ rows: window.node.widgets[0].value, groups: JSON.stringify(window.node.properties.lc_lora_groups) })), before, "Workflow restore must retain rows and groups");
  await group.getByRole("button", { name: "Expand group", exact: true }).click();
  await group.locator(".lc-group-lora-group-name").dblclick();
  await page.getByRole("textbox", { name: "Group name" }).fill("Style");
  await page.getByRole("textbox", { name: "Group name" }).press("Enter");
  await page.getByRole("button", { name: "Add Group", exact: true }).click();
  assert.equal(await page.getByRole("textbox", { name: "Group name" }).inputValue(), "new group");
  await page.getByRole("textbox", { name: "Group name" }).fill("Second");
  await page.getByRole("textbox", { name: "Group name" }).press("Enter");
  const secondId = await page.evaluate(() => window.node.properties.lc_lora_groups[1].id);
  const second = page.locator(`[data-group-id="${secondId}"]`);
  await pointerDrag(second.getByRole("button", {name:"Drag to move group",exact:true}), group.locator('.lc-group-lora-group-header'), 3);
  assert.equal(await page.evaluate(() => window.node.properties.lc_lora_groups[0].name), "Second");
  assert.equal(await page.locator('.lc-group-lora-group').last().getAttribute('data-group-id'), '');
  await page.evaluate(() => window.restore());
  assert.equal(await page.evaluate(() => window.node.properties.lc_lora_groups[0].name), "Second");
  await second.getByRole("button", { name: "Remove group · keep LoRAs in Ungrouped", exact: true }).click();
  if (output) {
    await page.mouse.move(600, 400);
    await page.screenshot({ path: path.join(output, "lora-groups.png") });
    await page.getByRole('combobox', {name:'Show Strengths'}).click();
    await page.screenshot({ path: path.join(output, "lora-strength-menu.png") });
    await page.keyboard.press('Escape');
  }
  await group.getByRole("button", { name: "LoRA information", exact: true }).click();
  await page.getByText("TRIGGER WORDS", { exact: true }).waitFor();
  assert.equal(await page.getByRole("button", { name: "soft lighting", exact: true }).count(), 1);
  assert.equal(await page.getByText("SOURCE", {exact:true}).count(), 0);
  assert.equal(await page.getByText("Info file", {exact:true}).count(), 0);
  assert.equal(await page.locator(".lc-library-info-grid").getByRole("link", {name:"View on Civitai ↗"}).getAttribute("href"), "https://civitai.com/models/123?modelVersionId=456");
  const previousPosts = posts.length;
  await page.getByRole('button',{name:'Refresh model info',exact:true}).click();
  await page.waitForFunction(() => !document.querySelector('.lc-library-info-refresh').disabled);
  assert.equal(posts.length, previousPosts + 1);
  assert.equal(postBodies.at(-1).force, true);
  refreshError = 'Could not download model information. Test connection failure.';
  await page.evaluate(async (name) => {
    const library = await import('/extensions/lc123/lc_lora_library.js');
    await library.ensureLoraInfo(name, true);
  }, names[3]);
  await page.waitForFunction(() => document.querySelector('.lc-library-status')?.textContent.includes('Test connection failure.'));
  assert.equal(await page.locator('.lc-library-status.is-error').count(), 1, 'Info subscribers must preserve refresh failures');
  refreshError = null;
  if (output) await page.screenshot({ path: path.join(output, "lora-info.png") });
  await page.getByRole("button", { name: "Close", exact: true }).click();
  await group.getByRole("button", { name: "Remove group · keep LoRAs in Ungrouped", exact: true }).click();
  assert.equal(await page.evaluate(() => JSON.parse(window.node.widgets[0].value).length), 2);
  assert.equal(await page.evaluate(() => window.node.properties.lc_lora_groups.length), 0);
  await page.getByRole("combobox", {name:"Show Strengths"}).selectOption("Single Strength");
  assert.ok(await page.evaluate(() => JSON.parse(window.node.widgets[0].value).every(row => !('strengthTwo' in row))));
  assert.equal(await page.locator('[data-strength-field="strengthTwo"]').count(), 0);
  await page.getByRole("combobox", {name:"Show Strengths"}).selectOption("Separate Model & Clip");
  await page.getByRole('button', {name:'Add LoRA',exact:true}).click();
  await page.getByRole('button', {name:`Select ${names[1]}`,exact:true}).click();
  await page.getByRole('button', {name:'Confirm (1)',exact:true}).click();
  const addedRow = page.locator('.lc-group-lora-row').last();
  await addedRow.locator('[data-strength-field="strength"] .lc-group-lora-str-value').click();
  await page.getByRole('spinbutton', {name:'Model strength',exact:true}).fill('0.2');
  await page.getByRole('spinbutton', {name:'Model strength',exact:true}).press('Enter');
  assert.deepEqual(await page.evaluate(() => {const row=JSON.parse(window.node.widgets[0].value).at(-1);return [row.strength,row.strengthTwo]}), [0.2,1]);
  await addedRow.getByRole('button',{name:'Remove LoRA',exact:true}).click();
  libraryNames = [...names, ...Array.from({length:120},(_,i)=>`More/LoRA ${String(i).padStart(3,'0')}.safetensors`)];
  await page.getByRole('button', {name:'Add LoRA',exact:true}).click();

  await page.waitForFunction(() => document.querySelectorAll('.lc-library-card').length === 50);
  const firstCardHandle = await page.locator('.lc-library-card').first().elementHandle();
  await page.locator('.lc-library-results').evaluate(el => {el.scrollTop=el.scrollHeight});
  await page.waitForFunction(() => document.querySelectorAll('.lc-library-card').length === 100);
  assert.equal(await firstCardHandle.evaluate(el=>el===document.querySelector('.lc-library-card')), true, 'Auto-loading must append without rebuilding existing cards');
  await page.locator('.lc-library-results').evaluate(el => {el.scrollTop=el.scrollHeight});
  await page.waitForFunction(() => document.querySelectorAll('.lc-library-card').length === 128);
  assert.equal(await page.getByText('Show more', {exact:false}).count(), 0);
  await page.getByRole('button', {name:'Select More/LoRA 100.safetensors',exact:true}).click();
  await page.getByRole('searchbox', {name:'Search LoRAs'}).fill('Mira');
  await page.getByRole('button', {name:`Select ${names[1]}`,exact:true}).click();
  await page.getByRole('button', {name:'2 added · Show selected LoRAs',exact:true}).click();
  assert.equal(await page.locator('.lc-library-card').count(), 2, 'Review must include choices from other pages and searches');
  await page.getByRole('button', {name:'Select More/LoRA 100.safetensors',exact:true}).click();
  assert.equal(await page.locator('.lc-library-card').count(), 1);
  await page.getByRole('button', {name:'1 added · Show all LoRAs',exact:true}).click();
  assert.equal(await page.getByRole('searchbox', {name:'Search LoRAs'}).inputValue(), 'Mira');
  await page.getByRole('button', {name:'Close',exact:true}).click();
  const dragPerf = await page.evaluate(async () => {
    window.node.widgets[0].value = JSON.stringify(Array.from({length:200}, (_,i) => ({id:`perf-${i}`,group:'',lora:'Characters/Mira.safetensors',on:true,strength:1})));
    window.node.onConfigure();
    const host = document.querySelector('.lc-group-lora-host');
    const rows = [...host.querySelectorAll('.lc-group-lora-row')];
    const destination = rows[1], rect = destination.getBoundingClientRect();
    rows[0].querySelector('[data-drag-kind]').dispatchEvent(new PointerEvent('pointerdown', {bubbles:true,button:0,clientX:rect.left+30,clientY:rect.top-20}));
    const frame = () => new Promise(resolve => requestAnimationFrame(resolve));
    const children = [...destination.children];
    const over = child => child.dispatchEvent(new PointerEvent('pointermove', {bubbles:true,cancelable:true,clientX:rect.left+70,clientY:rect.bottom - 3}));
    over(children[0]); await frame();
    const line = document.querySelector('.lc-group-lora-insert-line');
    let reads = 0, writes = 0;
    const original = Element.prototype.getBoundingClientRect;
    Element.prototype.getBoundingClientRect = function() {if(host.contains(this)) reads++;return original.call(this)};
    const watcher = new MutationObserver(records => {writes += records.length});
    watcher.observe(line, {attributes:true});
    const linePositions = [];
    try {
      for(let i=0;i<8;i++) {
        for(const child of children) {
          over(child);

        }
        await frame();
        linePositions.push([line.hidden,line.style.transform]);
      }
    } finally {Element.prototype.getBoundingClientRect=original;watcher.disconnect()}
    const stableRows = rows.every((row,i) => host.querySelectorAll('.lc-group-lora-row')[i] === row);
    const straight = getComputedStyle(line).borderRadius === '0px' && getComputedStyle(line).height === '2px';
    const ghostText = document.querySelector('.lc-group-lora-drag-preview');
    destination.dispatchEvent(new PointerEvent('pointerup',{bubbles:true,cancelable:true,clientX:rect.left+70,clientY:rect.bottom - 3}));
    const order = JSON.parse(window.node.widgets[0].value).slice(0,3).map(row=>row.id);
    return {reads,writes,stableRows,straight,ghostText,linePositions,order,linesAfter:document.querySelectorAll('.lc-group-lora-insert-line').length};
  });
  assert.equal(dragPerf.reads, 0, "Stationary drag across child elements must not remeasure rows");
  assert.equal(dragPerf.writes, 0, "Stationary drag must not repaint or hide its insertion line");
  assert.equal(dragPerf.stableRows, true, "Dragging must not rebuild list rows");
  assert.equal(dragPerf.straight, true);
  assert.ok(dragPerf.linePositions.every(([hidden,position])=>!hidden && position===dragPerf.linePositions[0][1]));
  assert.equal(dragPerf.ghostText, null);
  assert.deepEqual(dragPerf.order, ['perf-1','perf-0','perf-2']);
  assert.equal(dragPerf.linesAfter, 0);
  assert.deepEqual(errors, [], "Browser runtime errors");
  console.log("PASS: library, inline groups, independent weights, restore, pointer drag/drop and 200-row drag stability (no repeated layout reads or indicator writes).");
} catch (error) {
  console.error('Browser errors:', errors);
  console.error('Page text:', (await page.locator('body').innerText()).slice(0, 2000));
  if (process.env.LC_UI_SCREENSHOT_DIR) {
    await fs.mkdir(process.env.LC_UI_SCREENSHOT_DIR, { recursive: true });
    await page.screenshot({ path: path.join(process.env.LC_UI_SCREENSHOT_DIR, 'lora-failure.png') });
  }
  throw error;
} finally {
  await browser.close();
}
