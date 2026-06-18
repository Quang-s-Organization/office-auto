import fs from "node:fs";
import path from "node:path";
import { randomBytes } from "node:crypto";
import { tmpdir } from "node:os";
import { spawnSync } from "node:child_process";
import type { Op } from "./binding-planner.js";
import type { Manifest } from "../manifest/schema.js";
import { parseOfficeCLI, officecliBatch } from "./officecli.js";

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

function uniqueOutputPath(templatePath: string, outputPath?: string): string {
  if (outputPath) return outputPath;
  const base = path.basename(templatePath, ".docx");
  const ts = Date.now();
  const rand = randomBytes(4).toString("hex");
  return path.resolve(process.cwd(), "out", `${base}_${ts}_${rand}.docx`);
}

function officecliMerge(template: string, output: string, mergeData: Record<string, string>): void {
  const tmpFile = path.join(tmpdir(), `merge-${Date.now()}-${randomBytes(4).toString("hex")}.json`);
  fs.writeFileSync(tmpFile, JSON.stringify(mergeData));

  const result = spawnSync("officecli", ["merge", template, output, tmpFile, "--json"], {
    encoding: "utf-8",
    maxBuffer: 50 * 1024 * 1024,
    timeout: 120_000,
  });

  try { fs.unlinkSync(tmpFile); } catch {}

  const parsed = parseOfficeCLI(result);
  if (!parsed.success) {
    throw new Error(`Merge failed: ${parsed.error || "unknown error"}`);
  }
}

export async function render(
  ops: Op[],
  templatePath: string,
  outputPath?: string,
  manifest?: Manifest
): Promise<string> {
  const absTemplate = path.resolve(templatePath);
  const outPath = uniqueOutputPath(absTemplate, outputPath);

  // Ensure out directory exists
  const outDir = path.dirname(outPath);
  if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });

  // Separate scalar set ops from structural ops
  const scalarOps = ops.filter((op) => op.kind === "set");
  let structuralOps: Op[] = ops.filter((op) => op.kind !== "set");

  // Check if merge_fields is configured (manifest-driven merge strategy)
  const mergeFields = (manifest as any)?.merge_fields as Record<string, string> | undefined;
  if (mergeFields && scalarOps.length > 0) {
    // Strategy 1: Use native `merge` for scalar fields mapped via merge_fields
    const mergeData: Record<string, string> = {};
    const handled = new Set<Op>();

    for (const op of scalarOps) {
      // merge_fields maps resolved_path → {{key}}
      const placeholderKey = mergeFields[op.path]?.replace(/[{}]/g, "");
      if (placeholderKey) {
        mergeData[placeholderKey] = op.props.text;
        handled.add(op);
      }
    }

    if (Object.keys(mergeData).length > 0) {
      officecliMerge(absTemplate, outPath, mergeData);
      // Remove handled scalar ops from structural batch — they're already applied
      structuralOps = structuralOps.filter((op) => !handled.has(op));
    } else {
      fs.copyFileSync(absTemplate, outPath);
    }
  } else {
    // No merge_fields: copy template for batch-based scalar set
    fs.copyFileSync(absTemplate, outPath);
    // Scalar set ops go through batch as before
    structuralOps = ops;
  }

  // Strategy 2: Batch for remaining structural ops
  if (structuralOps.length > 0) {
    const batch = toBatch(structuralOps);

    // Timestamped batch log for audit trail
    const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
    fs.writeFileSync(path.join(outDir, `batch-${timestamp}.json`), JSON.stringify(batch, null, 2));

    const result = officecliBatch(outPath, batch, { stopOnError: true });
    if (!result.success) {
      throw new Error(`Batch render failed: ${result.error || "unknown error"}`);
    }
  }

  return outPath;
}
