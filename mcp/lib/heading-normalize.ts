export function stripLeadingNumbering(s: string): string {
  return s
    .replace(/^\s*(?:\d+(?:\.\d+)*\.?|[IVXLCDM]+\.|[A-Z]\.|\([a-z0-9]+\))\s+/i, "")
    .replace(/^\s*chương\s+\d+\s*[:.\-–—]?\s*/i, "")
    .trim()
}

export function canonicalHeadingKey(s: string): string {
  return stripLeadingNumbering(s)
    .normalize("NFC")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase()
}

export interface AmbiguityReport {
  canonical_key: string
  heading_ids: string[]
}

export function detectAmbiguity(
  headings: Array<{ heading_id: string; canonical_key: string }>,
): AmbiguityReport[] {
  const map = new Map<string, string[]>()
  for (const h of headings) {
    const existing = map.get(h.canonical_key) ?? []
    existing.push(h.heading_id)
    map.set(h.canonical_key, existing)
  }
  return [...map.entries()]
    .filter(([, ids]) => ids.length > 1)
    .map(([canonical_key, heading_ids]) => ({ canonical_key, heading_ids }))
}
