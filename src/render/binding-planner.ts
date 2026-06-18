import type { Manifest, Content } from "../manifest/schema.js";

export type Op =
  | { kind: "set"; path: string; props: Record<string, string> }
  | { kind: "clone"; parent: string; from: string; after?: string; before?: string }
  | { kind: "setCell"; path: string; props: Record<string, string> };

export function plan(content: Content, manifest: Manifest): Op[] {
  const ops: Op[] = [];

  // 1) Scalar fields -> set via resolved_path
  for (const [name, val] of Object.entries(content.fields)) {
    const f = manifest.fields[name];
    if (!f) continue;
    ops.push({ kind: "set", path: f.resolved_path, props: { text: String(val) } });
  }

  // 2) Repeaters -> clone block (reverse-clone strategy)
  // Reverse-clone: process items in reverse order so each new clone slides
  // between the anchor and the previous clone. The anchor path never moves,
  // and the freshly inserted node is always at position [1] relative to anchor.
  for (const [repeaterName, repeaterSpec] of Object.entries(manifest.repeaters || {})) {
    const items = content.blocks?.[repeaterName];
    if (!items || !Array.isArray(items)) continue;

    const reversedItems = [...items].reverse();
    for (const item of reversedItems) {
      ops.push({
        kind: "clone",
        parent: "/body",
        from: repeaterSpec.clone_from,
        after: repeaterSpec.insert_anchor.path,
      });

      // After reverse-clone, the newly inserted node is at anchor[1]
      const clonePath = `${repeaterSpec.insert_anchor.path}[1]`;
      for (const [fieldName, childPath] of Object.entries(repeaterSpec.item_fields)) {
        const val = item[fieldName];
        if (val !== undefined) {
          ops.push({
            kind: "setCell",
            path: `${clonePath}/${childPath}`,
            props: { text: String(val) },
          });
        }
      }
    }
  }

  // 3) Tables -> generate rows
  for (const [tableName, tableSpec] of Object.entries(manifest.tables || {})) {
    const rows = content.tables?.[tableName];
    if (!rows || !Array.isArray(rows)) continue;

    const basePath = tableSpec.path;
    rows.forEach((row: any, rowIdx: number) => {
      const trIdx = tableSpec.header_rows + 1 + rowIdx;
      tableSpec.columns.forEach((col: string, colIdx: number) => {
        const cellPath = `${basePath}/tr[${trIdx}]/tc[${colIdx + 1}]`;
        if (row[col] !== undefined) {
          ops.push({ kind: "setCell", path: cellPath, props: { text: String(row[col]) } });
        }
      });
    });
  }

  return ops;
}
