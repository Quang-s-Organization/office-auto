import { spawnSync } from "child_process"
import { BodyMapZ, type BodyMap, type ParagraphEntry, type HeadingEntry } from "../schemas/body-map"
import { canonicalHeadingKey } from "../lib/heading-normalize"

function run(args: string[]): string {
  const r = spawnSync("officecli", args, { encoding: "utf-8" })
  if (r.error) throw r.error
  if (r.status !== 0) throw new Error(`officecli ${args[0]} failed: ${r.stderr}`)
  return r.stdout
}

function extractHeadingLevel(style: string): number {
  const m = style.match(/heading\s*(\d)/i)
  return m ? parseInt(m[1], 10) : 0
}

function extractParagraphNodes(data: unknown): any[] {
  if (!data || typeof data !== "object") return []

  // Fast paths first — common OfficeCLI response shapes
  const obj = data as Record<string, any>
  let children = obj?.data?.body?.children
    ?? obj?.data?.children
    ?? obj?.body?.children
    ?? obj?.children
    ?? obj?.paragraphs

  if (Array.isArray(children)) return children

  // Fallback: recursive scan for paragraph-like nodes
  const results: any[] = []
  function scan(node: unknown) {
    if (!node || typeof node !== "object") return
    // Skip array itself — its items get scanned individually
    const arr = node as Record<string, any>

    // Check if this looks like a paragraph node
    if (
      (arr.text !== undefined && arr.path !== undefined) ||
      (arr.type === "paragraph" && arr.text !== undefined) ||
      (arr.paraId !== undefined && arr.text !== undefined)
    ) {
      results.push(arr)
      return
    }

    // Recursively check all values
    for (const val of Object.values(arr)) {
      if (Array.isArray(val)) {
        for (const item of val) scan(item)
      } else if (val && typeof val === "object") {
        scan(val)
      }
    }
  }

  scan(data)
  return results
}

function buildParagraphEntry(p: any, idx: number, headingIndex: number): ParagraphEntry {
  const paraId: string | null =
    p.paraId ??
    (p.path ? (p.path.match(/@paraId=([^\]]+)/)?.[1] ?? null) : null)

  const path: string | null =
    p.path ??
    (paraId ? `/body/p[@paraId=${paraId}]` : null)

  const addressable = !!(paraId && path)

  return {
    style: p.style ?? null,
    text: p.text ?? "",
    path,
    paraId,
    index_in_body: idx,
    addressable,
  }
}

function isValidBodyMap(candidate: unknown): { ok: true; bodyMap: BodyMap } | { ok: false; errors: string[] } {
  const result = BodyMapZ.safeParse(candidate)
  if (result.success) return { ok: true, bodyMap: result.data }
  const errors = result.error.issues.map(
    (issue) => `Field "${issue.path.join(".")}": ${issue.message}`,
  )
  return { ok: false, errors }
}

export function inspectTemplate(template_path: string): unknown {
  run(["open", template_path])
  const raw = run(["get", template_path, "/body", "--depth", "3", "--json"])
  const outline = run(["view", template_path, "outline"])
  run(["close", template_path])

  const data = JSON.parse(raw)
  const nodes = extractParagraphNodes(data)

  if (nodes.length === 0) {
    return {
      ok: false,
      phase: "INSPECT_TEMPLATE",
      error_code: "INSPECT_EMPTY",
      recoverable: false,
      message: "Cannot extract paragraph nodes from OfficeCLI JSON.",
      next_allowed_actions: ["STOP", "retry inspect_template with debug=true"],
    }
  }

  const paragraphs: ParagraphEntry[] = []
  const styles = new Set<string>()

  nodes.forEach((p: any, idx: number) => {
    const style: string | null = p.style ?? null
    if (style) styles.add(style)
    paragraphs.push(buildParagraphEntry(p, idx, idx))
  })

  let headingCount = 0
  const headings: HeadingEntry[] = paragraphs
    .filter((p) => p.style && /heading/i.test(p.style) && p.path && p.paraId)
    .map((p) => {
      headingCount++
      const headingId = `h_${String(headingCount).padStart(4, "0")}`
      const key = canonicalHeadingKey(p.text)
      return {
        style: p.style!,
        text: p.text,
        path: p.path!,
        paraId: p.paraId!,
        index_in_body: p.index_in_body,
        level: extractHeadingLevel(p.style!),
        heading_id: headingId,
        canonical_key: key,
        raw_text: p.text,
      }
    })

  const bodyMapCandidate = {
    schema_version: "body_map.v1" as const,
    template_path,
    inspected_at: new Date().toISOString(),
    headings,
    paragraphs,
    body_styles_seen: [...styles],
    toc_present: /TOC|Table of Contents/i.test(outline),
    total_paragraphs: paragraphs.length,
  }

  const validated = isValidBodyMap(bodyMapCandidate)
  if (!validated.ok) {
    return {
      ok: false,
      phase: "INSPECT_TEMPLATE",
      error_code: "BODY_MAP_SCHEMA_INVALID",
      recoverable: false,
      errors: validated.errors,
      message: "Generated body_map failed schema validation.",
    }
  }

  return {
    ok: true,
    body_map: validated.bodyMap,
  }
}

export function inspectTemplateRaw(template_path: string): { raw: string; data: unknown } {
  run(["open", template_path])
  const raw = run(["get", template_path, "/body", "--depth", "3", "--json"])
  const outline = run(["view", template_path, "outline"])
  run(["close", template_path])
  return { raw, data: JSON.parse(raw) }
}

// Re-export types for backward compatibility
export type { BodyMap, ParagraphEntry, HeadingEntry }
