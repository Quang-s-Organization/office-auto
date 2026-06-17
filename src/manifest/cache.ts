import fs from "node:fs";
import path from "node:path";
import type { Manifest } from "./schema.js";

const CACHE_DIR = path.resolve(process.cwd(), "manifests");

export function getCachedManifest(templateId: string): string | null {
  const p = path.join(CACHE_DIR, `${templateId}.manifest.json`);
  if (!fs.existsSync(p)) return null;
  return p;
}

export function getManifestPath(templateId: string): string {
  return path.join(CACHE_DIR, `${templateId}.manifest.json`);
}
