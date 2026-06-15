import type { BodyMap } from "./inspect_template"
import {
  validateAnchorFormat,
  validateRawHexAnchor,
  type OfficeCliOp,
} from "../schemas/execution-ops"

// ─── Type definitions ────────────────────────────────────────────────

interface ActionDecision {
  heading_text: string
  action: "update" | "keep" | "remove" | "add"
  new_text?: string
  after?: string
  insert_after_template_heading_id?: string
  md_heading?: string
  body_paragraphs?: string[]
  level?: number
}

// ─── Helper functions ─────────────────────────────────────────────────

function findBodyStyle(bodyMap: BodyMap): string {
  const normals = bodyMap.body_styles_seen.filter(
    (s) => /normal/i.test(s) && !/heading/i.test(s),
  )
  return normals[0] ?? bodyMap.body_styles_seen[0] ?? "Normal"
}

function headingStyleForLevel(bodyMap: BodyMap, level: number): string {
  const match = bodyMap.body_styles_seen.find(
    (s) => new RegExp(`heading\\s*${level}`, "i").test(s),
  )
  return match ?? `Heading${level}`
}

function normalizeText(t: string): string {
  return t
    .normalize("NFC")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase()
}

function extractLevel(style: string): number {
  const m = style.match(/heading\s*(\d)/i)
  return m ? parseInt(m[1], 10) : 0
}

// ─── Heading matching ────────────────────────────────────────────────

type HeadingMatch =
  | { found: true; heading: BodyMap["headings"][number] }
  | { found: false; reason: "not_found" }
  | { found: false; reason: "ambiguous"; heading_ids: string[] }

function findHeading(bodyMap: BodyMap, lookup: string): HeadingMatch {
  // Priority 1: exact heading_id match
  const byId = bodyMap.headings.find((h) => h.heading_id === lookup)
  if (byId) return { found: true, heading: byId }

  // Priority 2: canonical_key match
  const normalized = normalizeText(lookup)
  const byCanonical = bodyMap.headings.filter((h) => h.canonical_key === normalized)
  if (byCanonical.length === 1) return { found: true, heading: byCanonical[0] }
  if (byCanonical.length > 1) {
    return {
      found: false,
      reason: "ambiguous",
      heading_ids: byCanonical.map((h) => h.heading_id),
    }
  }

  // Priority 3: raw text match
  const byText = bodyMap.headings.filter(
    (h) => normalizeText(h.text) === normalized,
  )
  if (byText.length === 1) return { found: true, heading: byText[0] }
  if (byText.length > 1) {
    return {
      found: false,
      reason: "ambiguous",
      heading_ids: byText.map((h) => h.heading_id),
    }
  }

  return { found: false, reason: "not_found" }
}

function resolveAnchorPath(bodyMap: BodyMap, lookup: string): string | { error: string } {
  // Reject raw hex
  const hexErr = validateRawHexAnchor(lookup)
  if (hexErr) return { error: hexErr }

  // If already a valid path, accept it
  const anchorErr = validateAnchorFormat(lookup)
  if (anchorErr === null) {
    // Already a valid path — verify the paraId exists in bodyMap
    const paraIdMatch = lookup.match(/@paraId=([^\]]+)/)
    if (paraIdMatch) {
      const exists = bodyMap.paragraphs.some((p) => p.paraId === paraIdMatch[1])
      if (!exists) return { error: `Anchor references unknown paraId "${paraIdMatch[1]}"` }
    }
    return lookup
  }

  // Resolve heading_id or text → paraId → path
  const match = findHeading(bodyMap, lookup)
  if (!match.found) {
    if (match.reason === "ambiguous") {
      return {
        error: `Ambiguous heading match for "${lookup}": ${match.heading_ids.join(", ")}. Provide template_heading_id.`,
      }
    }
    return { error: `Heading "${lookup}" not found in template body_map` }
  }

  return `/body/p[@paraId=${match.heading.paraId}]`
}

// ─── Markdown parsing ────────────────────────────────────────────────

interface MarkdownSection {
  heading: string
  level: number
  body: string[]
}

function parseMarkdownSections(mdContent: string): MarkdownSection[] {
  const sections: MarkdownSection[] = []
  const lines = mdContent.split("\n")
  let currentSection: MarkdownSection | null = null

  for (const line of lines) {
    const hMatch = line.match(/^(#{1,6})\s+(.+)/)
    if (hMatch) {
      if (currentSection) sections.push(currentSection)
      currentSection = {
        heading: normalizeText(hMatch[2]),
        level: hMatch[1].length,
        body: [],
      }
    } else if (currentSection) {
      const trimmed = line.trim()
      if (trimmed) currentSection.body.push(trimmed)
    }
  }
  if (currentSection) sections.push(currentSection)

  return sections
}

function extractBodyParagraphs(
  contentMd: string,
  headingText: string,
  mdHeading?: string,
): string[] {
  if (!contentMd) return []

  const sections = parseMarkdownSections(contentMd)

  if (mdHeading) {
    const normalized = normalizeText(mdHeading)
    const section = sections.find((s) => s.heading === normalized)
    return section?.body ?? []
  }

  const normalized = normalizeText(headingText)
  const section = sections.find((s) => s.heading === normalized)
  return section?.body ?? []
}

function findBodyParagraphsForSection(
  bodyMap: BodyMap,
  heading: { index_in_body: number; level: number },
  sectionLevel: number,
): Array<{ path: string }> {
  const result: Array<{ path: string }> = []
  let j = heading.index_in_body + 1
  while (j < bodyMap.paragraphs.length) {
    const p = bodyMap.paragraphs[j]
    if (p.style && /heading/i.test(p.style)) {
      const pl = extractLevel(p.style)
      if (pl > 0 && pl <= sectionLevel) break
    }
    if (!p.style || !/heading/i.test(p.style)) {
      if (p.path) {
        result.push({ path: p.path })
      }
    }
    j++
  }
  return result
}

// ─── Core compilation ────────────────────────────────────────────────

export function compileOps(
  actionDecisions: ActionDecision[],
  bodyMap: BodyMap,
  tocRefresh: boolean,
  contentMd?: string,
): {
  ops_plan: OfficeCliOp[]
  errors: string[]
} {
  const ops: OfficeCliOp[] = []
  const errors: string[] = []
  const bodyStyle = findBodyStyle(bodyMap)

  for (let i = 0; i < actionDecisions.length; i++) {
    const d = actionDecisions[i]
    const action = d.action

    if (action === "keep") continue

    if (action === "remove") {
      const match = findHeading(bodyMap, d.heading_text)
      if (!match.found) {
        errors.push(
          `action[${i}]: heading "${d.heading_text}" not found in body_map${match.reason === "ambiguous" ? ` (ambiguous: ${match.heading_ids.join(", ")})` : ""}. Provide template_heading_id for unambiguous match.`,
        )
        continue
      }

      const h = match.heading
      const sectionLevel = h.level
      let j = h.index_in_body + 1
      while (j < bodyMap.paragraphs.length) {
        const p = bodyMap.paragraphs[j]
        if (p.style && /heading/i.test(p.style)) {
          const pl = extractLevel(p.style)
          if (pl > 0 && pl <= sectionLevel) break
        }
        j++
      }
      for (let k = h.index_in_body; k < j; k++) {
        if (bodyMap.paragraphs[k].path) {
          ops.push({ command: "remove", path: bodyMap.paragraphs[k].path! })
        }
      }
      continue
    }

    if (action === "update") {
      const match = findHeading(bodyMap, d.heading_text)
      if (!match.found) {
        errors.push(
          `action[${i}]: heading "${d.heading_text}" not found in body_map${match.reason === "ambiguous" ? ` (ambiguous: ${match.heading_ids.join(", ")})` : ""}. Provide template_heading_id.`,
        )
        continue
      }

      const h = match.heading
      if (d.new_text && d.new_text !== h.text) {
        ops.push({ command: "set", path: h.path, props: { text: d.new_text } })
      }

      const bodyParas =
        d.body_paragraphs && d.body_paragraphs.length > 0
          ? d.body_paragraphs
          : contentMd
            ? extractBodyParagraphs(contentMd, d.heading_text, d.md_heading)
            : []

      if (bodyParas.length > 0) {
        const sectionLevel = h.level
        const templateBodyParas = findBodyParagraphsForSection(bodyMap, h, sectionLevel)
        if (bodyParas.length > templateBodyParas.length) {
          errors.push(
            `action[${i}]: body paragraph count mismatch — ${bodyParas.length} in content.md but only ${templateBodyParas.length} placeholders in template. ` +
              `${bodyParas.length - templateBodyParas.length} paragraphs will be dropped.`,
          )
        }
        for (let bi = 0; bi < templateBodyParas.length && bi < bodyParas.length; bi++) {
          ops.push({
            command: "set",
            path: templateBodyParas[bi].path,
            props: { text: bodyParas[bi] },
          })
        }
      }
      continue
    }

    if (action === "add") {
      const level = d.level ?? 1
      const style = headingStyleForLevel(bodyMap, level)

      // Determine insert anchor: prefer insert_after_template_heading_id, fall back to after
      const anchorLookup = d.insert_after_template_heading_id ?? d.after ?? ""
      let anchorPath: string

      if (anchorLookup) {
        const resolved = resolveAnchorPath(bodyMap, anchorLookup)
        if (typeof resolved !== "string") {
          errors.push(`action[${i}]: ${resolved.error}`)
          continue
        }
        anchorPath = resolved
      } else {
        // No anchor specified — append at end of body
        const lastPara = bodyMap.paragraphs[bodyMap.paragraphs.length - 1]
        if (!lastPara) {
          errors.push(`action[${i}]: Cannot add — body_map has no paragraphs to anchor after`)
          continue
        }
        anchorPath = `/body/p[@paraId=${lastPara.paraId}]`
      }

      const bodyParas =
        d.body_paragraphs && d.body_paragraphs.length > 0
          ? d.body_paragraphs
          : contentMd
            ? extractBodyParagraphs(contentMd, d.heading_text, d.md_heading)
            : []

      ops.push({
        command: "add",
        parent: "/body",
        type: "paragraph",
        after: anchorPath,
        props: { text: d.new_text ?? d.heading_text, style },
      })

      for (const bp of bodyParas) {
        ops.push({
          command: "add",
          parent: "/body",
          type: "paragraph",
          after: anchorPath,
          props: { text: bp, style: bodyStyle },
        })
      }

      // Emit warning for legacy "after" field usage
      if (d.after && !d.insert_after_template_heading_id) {
        // Log but don't error — backward compatible
      }

      continue
    }
  }

  return { ops_plan: ops, errors }
}


export type { ActionDecision, OfficeCliOp }
