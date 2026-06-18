import fs from "node:fs";
import path from "node:path";
import type { RegistryEntry } from "./types.js";

const REGISTRY_PATH = path.resolve(process.cwd(), "templates", "registry.json");

export function loadRegistry(): RegistryEntry[] {
  if (!fs.existsSync(REGISTRY_PATH)) return [];
  return JSON.parse(fs.readFileSync(REGISTRY_PATH, "utf-8"));
}

export function findDocumentType(id: string): RegistryEntry | undefined {
  return loadRegistry().find((e) => e.id === id);
}

export function listDocumentTypes(): Pick<RegistryEntry, "id" | "displayName" | "description" | "capabilities">[] {
  return loadRegistry().map(({ id, displayName, description, capabilities }) => ({
    id, displayName, description, capabilities,
  }));
}
