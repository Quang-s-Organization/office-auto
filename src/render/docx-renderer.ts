import fs from "node:fs";
import path from "node:path";
import type { Op } from "./binding-planner.js";
import { officecli, officecliBatch } from "./officecli.js";

export interface BatchItem {
  command: string;
  path?: string;
  props?: Record<string, string>;
  parent?: string;
  from?: string;
  after?: string;
  before?: string;
  type?: string;
}

function toBatch(ops: Op[]): BatchItem[] {
  return ops.map((op) => {
    switch (op.kind) {
      case "set":
        return { command: "set", path: op.path, props: op.props };
      case "clone":
        return {
          command: "add",
          parent: op.parent,
          from: op.from,
          ...(op.after ? { after: op.after } : {}),
          ...(op.before ? { before: op.before } : {}),
        };
      case "setCell":
        return { command: "set", path: op.path, props: op.props };
    }
  });
}

export async function render(
  ops: Op[],
  templatePath: string,
  outputPath?: string
): Promise<string> {
  const absTemplate = path.resolve(templatePath);

  // Create output file by copying template
  const outPath = outputPath || absTemplate.replace(/\.docx$/, ".out.docx");
  fs.copyFileSync(absTemplate, outPath);

  const batch = toBatch(ops);

  // Write batch.json for audit/regression
  const outDir = path.resolve(process.cwd(), "out");
  if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });
  fs.writeFileSync(path.join(outDir, "batch.json"), JSON.stringify(batch, null, 2));

  // Execute batch via officecli
  const result = officecliBatch(outPath, batch, { stopOnError: true });

  if (!result.success) {
    throw new Error(`Batch render failed: ${result.error || "unknown error"}`);
  }

  return outPath;
}
