import fs from "node:fs";
import crypto from "node:crypto";
import path from "node:path";
import { ManifestSchema, type Manifest } from "./schema.js";
import { officecli } from "../render/officecli.js";

const MANIFEST_DIR = path.resolve(process.cwd(), "manifests");

function sha256(filePath: string): string {
  const buf = fs.readFileSync(filePath);
  return crypto.createHash("sha256").update(buf).digest("hex");
}

function inferType(sdt: any): "scalar" | "date" {
  if (sdt.format?.type === "date" || sdt.type === "date") return "date";
  return "scalar";
}

function slugify(text: string): string {
  return text
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_|_$/g, "")
    .slice(0, 40);
}

function isHeading(style: string | undefined): boolean {
  if (!style) return false;
  return /^heading\s*\d/i.test(style);
}

function isPlaceholder(text: string | undefined): boolean {
  if (!text) return false;
  const t = text.trim();
  if (/^Nội\s*dung/i.test(t)) return true;
  if (/^…+$/.test(t) || /^\.{3,}$/.test(t)) return true;
  return false;
}

export async function auditTemplate(docxPath: string): Promise<Manifest> {
  const absPath = path.resolve(docxPath);
  const baseName = path.basename(absPath, ".docx");

  const sdts = officecli(["query", absPath, "sdt"]);
  const fields: Record<string, any> = {};
  let hasSDT = false;

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
        hasSDT = true;
      }
    }
  }

  // Legacy-anchor mode: scan headings → placeholder mapping
  if (!hasSDT) {
    const allParas = officecli(["query", absPath, "p"]);
    if (allParas.success && Array.isArray(allParas.data?.results)) {
      const results = allParas.data.results;
      for (let i = 0; i < results.length - 1; i++) {
        const curr = results[i];
        const next = results[i + 1];
        if (isHeading(curr.style) && curr.text?.trim() && isPlaceholder(next.text)) {
          const key = slugify(curr.text.trim());
          const uniqueKey = fields[key] ? `${key}_${i}` : key;
          fields[uniqueKey] = {
            sdt_tag: uniqueKey,
            resolved_path: next.path,
            type: "scalar" as const,
            heading: curr.text.trim(),
            heading_path: curr.path,
          };
        }
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
    template_sha: sha256(absPath),
    audited_at: new Date().toISOString(),
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
  const manifest = ManifestSchema.parse(raw);

  // Staleness check: compare template SHA with cached manifest
  const templatePath = path.resolve(process.cwd(), "templates", `${templateId}.docx`);
  if (fs.existsSync(templatePath)) {
    const currentSha = sha256(templatePath);
    if ((manifest as any).template_sha && currentSha !== (manifest as any).template_sha) {
      console.error(`WARNING: Manifest for "${templateId}" is stale. Template has changed. Re-audit recommended.`);
    }
  }

  return manifest;
}

// CLI entry — only runs when executed directly, not on import
const runningAsScript = process.argv[1]?.includes("auditor") ?? false;
if (runningAsScript) {
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
}
