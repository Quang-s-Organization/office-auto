import fs from "node:fs";
import path from "node:path";
import { ManifestSchema, type Manifest } from "./schema.js";
import { officecli } from "../render/officecli.js";

const MANIFEST_DIR = path.resolve(process.cwd(), "manifests");

function inferType(sdt: any): "scalar" | "date" {
  if (sdt.format?.type === "date" || sdt.type === "date") return "date";
  return "scalar";
}

export async function auditTemplate(docxPath: string): Promise<Manifest> {
  const absPath = path.resolve(docxPath);
  const baseName = path.basename(absPath, ".docx");

  const sdts = officecli(["query", absPath, "sdt"]);
  const outline = officecli(["view", absPath, "outline"]);

  const fields: Record<string, any> = {};

  if (sdts.success && Array.isArray(sdts.data?.results)) {
    for (const sdt of sdts.data.results) {
      const tag = sdt.format?.tag || sdt.tag;
      const sdtPath = sdt.path;
      if (tag && sdtPath) {
        fields[tag] = {
          sdt_tag: tag,
          resolved_path: sdtPath,
          type: inferType(sdt),
        };
      }
    }
  }

  const manifest = {
    template_id: baseName,
    mode: Object.keys(fields).length > 0 ? "strict-sdt" as const : "legacy-anchor" as const,
    locale: "vi-VN",
    fields,
    repeaters: {},
    tables: {},
    structural_invariants: {},
  };

  const parsed = ManifestSchema.parse(manifest);

  if (!fs.existsSync(MANIFEST_DIR)) {
    fs.mkdirSync(MANIFEST_DIR, { recursive: true });
  }
  fs.writeFileSync(
    path.join(MANIFEST_DIR, `${baseName}.manifest.json`),
    JSON.stringify(parsed, null, 2)
  );

  return parsed;
}

export function loadManifest(templateId: string): Manifest | null {
  const p = path.join(MANIFEST_DIR, `${templateId}.manifest.json`);
  if (!fs.existsSync(p)) return null;
  const raw = JSON.parse(fs.readFileSync(p, "utf-8"));
  return ManifestSchema.parse(raw);
}

// CLI entry
const docxPath = process.argv[2];
if (docxPath) {
  auditTemplate(docxPath)
    .then((m) => {
      console.log(JSON.stringify(m, null, 2));
    })
    .catch((err) => {
      console.error("Audit failed:", err);
      process.exit(1);
    });
}
