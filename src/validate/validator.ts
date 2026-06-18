import type { Manifest } from "../manifest/schema.js";
import { officecli } from "../render/officecli.js";

export interface ValidationResult {
  ok: boolean;
  schema: any;
  issues: any[];
  leftover: any[];
  invariants: { ok: boolean; missing?: string[] };
}

export function checkInvariants(
  file: string,
  invariants: Manifest["structural_invariants"]
): { ok: boolean; missing?: string[] } {
  if (!invariants || !invariants.required_sections?.length) {
    return { ok: true };
  }

  const missing: string[] = [];
  for (const section of invariants.required_sections) {
    const q = officecli(["query", file, `:contains("${section}")`]);
    if (!q.success || !q.data?.results?.length) {
      missing.push(section);
    }
  }

  return { ok: missing.length === 0, missing: missing.length > 0 ? missing : undefined };
}

export async function validate(file: string, manifest: Manifest): Promise<ValidationResult> {
  const schema = officecli(["validate", file]);
  const issues = officecli(["view", file, "issues"]);

  const placeholderPatterns = [
    "{{",
    "__",
    "Nội dung...",
    "Nội dung …",
    "Nội dung",
  ];

  const allLeftover: any[] = [];
  for (const pattern of placeholderPatterns) {
    const r = officecli(["query", file, `:contains("${pattern}")`]);
    if (r.success && Array.isArray(r.data?.results)) {
      allLeftover.push(...r.data.results);
    }
  }

  // Deduplicate by path
  const seen = new Set<string>();
  const deduped = allLeftover.filter((item: any) => {
    if (seen.has(item.path)) return false;
    seen.add(item.path);
    return true;
  });

  const invariants = checkInvariants(file, manifest.structural_invariants);

  const issuesList = issues.success && Array.isArray(issues.data?.results) ? issues.data.results : [];

  return {
    ok: schema.success && issuesList.length === 0 && deduped.length === 0 && invariants.ok,
    schema: schema.data,
    issues: issuesList,
    leftover: deduped,
    invariants,
  };
}
