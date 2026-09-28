// Groups are workflow-only properties. Flat lora_rows remain the sampler input.
export function normalizeRows(rows, groups, makeId = () => crypto.randomUUID()) {
  const groupIds = new Set(groups.map((group) => group.id));
  const ids = new Set();
  return rows.filter((row) => row && typeof row === "object" && !Array.isArray(row)).map((row) => {
    const id = typeof row.id === "string" && !ids.has(row.id) ? row.id : makeId();
    ids.add(id);
    return { ...row, id, group: groupIds.has(row.group) ? row.group : "" };
  });
}

export function orderRows(rows, groups) {
  return [...groups.map((group) => group.id), ""].flatMap((id) => rows.filter((row) => (row.group || "") === id));
}

export function moveRow(rows, rowId, groupId, beforeId = null) {
  const original = rows.find((row) => row.id === rowId);
  if (!original || rowId === beforeId) return rows;
  const result = rows.filter((row) => row.id !== rowId);
  const before = beforeId ? result.findIndex((row) => row.id === beforeId && (row.group || "") === groupId) : -1;
  let insert = before;
  if (insert < 0) {
    const last = result.findLastIndex((row) => (row.group || "") === groupId);
    insert = last < 0 ? result.length : last + 1;
  }
  result.splice(insert, 0, { ...original, group: groupId });
  return result;
}

export function groupState(rows, groupId) {
  const members = rows.filter((row) => (row.group || "") === groupId);
  const active = members.filter((row) => row.on).length;
  return { total: members.length, active, checked: members.length > 0 && active === members.length, mixed: active > 0 && active < members.length };
}

export function toggleGroup(rows, groupId, enabled) {
  return rows.map((row) => (row.group || "") === groupId ? { ...row, on: enabled } : row);
}

export function removeGroup(rows, groupId) {
  return rows.map((row) => row.group === groupId ? { ...row, group: "" } : row);
}

// Only workflows saved with the feature's group marker migrate; stock loaders stay stock.
export function migrateGroupLoaders(graph) {
  for (const node of graph?.nodes || []) {
    if (!["LCLoraLoader", "LCLoraLoaderStack"].includes(node.type) || !Array.isArray(node.properties?.lc_lora_groups)) continue;
    const stack = node.type === "LCLoraLoaderStack";
    const originalTitle = stack ? "LC LoRA Loader Stack 🎚️" : "LC LoRA Loader 🎚️";
    const defaultTitle = node.title === node.type || node.title === originalTitle;
    node.type = stack ? "LCGroupLoraLoaderStack" : "LCGroupLoraLoader";
    if (defaultTitle) node.title = stack ? "LC Group LoRA Loader Stack 🎚️" : "LC Group LoRA Loader 🎚️";
  }
  for (const subgraph of graph?.definitions?.subgraphs || []) migrateGroupLoaders(subgraph);
}
