import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js"
import { z } from "zod"
import type { BodyMap } from "./inspect_template"
import { logArtifact } from "./run_logger"

interface ActionDecision {
  heading_text: string
  action: "update" | "keep" | "remove" | "add"
  new_text?: string
  after?: string
  /** Markdown heading in content.md to extract body paragraphs from. Code, not LLM, does the extraction. */
  md_heading?: string
  /** DEPRECATED: kept for backward compat; prefer md_heading + content_md extraction. */
  body_paragraphs?: string[]
  /** Level for new heading when action=add */
  level?: number
}

interface OfficeCliOp {
  command: "set" | "add" | "remove"
  path?: string
  parent?: string
  type?: string
  after?: string
  props?: Record<string, string>
}

const ActionDecisionZod = z.object({
  heading_text: z.string().min(1, "heading_text must not be empty"),
  action: z.enum(["update", "keep", "remove", "add"], {
    errorMap: () => ({ message: "action must be one of: update, keep, remove, add" }),
  }),
  new_text: z.string().optional(),
  after: z.string().optional(),
  md_heading: z.string().optional(),
  body_paragraphs: z.array(z.string()).optional(),
  level: z.number().int().min(1).max(6).optional(),
})

function findBodyStyle(bodyMap: BodyMap): string {
  const normals = bodyMap.body_styles_seen.filter(
    s => /normal/i.test(s) && !/heading/i.test(s)
  )
  return normals[0] ?? bodyMap.body_styles_seen[0] ?? "Normal"
}

function headingStyleForLevel(bodyMap: BodyMap, level: number): string {
  const match = bodyMap.body_styles_seen.find(
    s => new RegExp(`heading\\s*${level}`, "i").test(s)
  )
  return match ?? `Heading${level}`
}

function findHeadingParaId(bodyMap: BodyMap, headingText: string): string | null {
  const h = bodyMap.headings.find(
    h => normalizeText(h.text) === normalizeText(headingText)
  )
  return h?.paraId ?? null
}

function normalizeText(t: string): string {
  return t
    .normalize("NFC")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase()
}

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
    const section = sections.find(s => s.heading === normalized)
    return section?.body ?? []
  }

  const normalized = normalizeText(headingText)
  const section = sections.find(s => s.heading === normalized)
  return section?.body ?? []
}

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
      const h = bodyMap.headings.find(h => normalizeText(h.text) === normalizeText(d.heading_text))
      if (!h) {
        errors.push(`action[${i}]: heading "${d.heading_text}" not found in body_map`)
        continue
      }
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
        ops.push({ command: "remove", path: bodyMap.paragraphs[k].path })
      }
      continue
    }

    if (action === "update") {
      const h = bodyMap.headings.find(h => normalizeText(h.text) === normalizeText(d.heading_text))
      if (!h) {
        errors.push(`action[${i}]: heading "${d.heading_text}" not found in body_map`)
        continue
      }
      if (d.new_text && d.new_text !== h.text) {
        ops.push({ command: "set", path: h.path, props: { text: d.new_text } })
      }

      const bodyParas = d.body_paragraphs && d.body_paragraphs.length > 0
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
      const afterText = d.after ?? ""
      const anchorParaId = afterText ? findHeadingParaId(bodyMap, afterText) : null
      const lastParaId = bodyMap.paragraphs[bodyMap.paragraphs.length - 1]?.paraId ?? ""

      const bodyParas = d.body_paragraphs && d.body_paragraphs.length > 0
        ? d.body_paragraphs
        : contentMd
          ? extractBodyParagraphs(contentMd, d.heading_text, d.md_heading)
          : []

      // All add ops use the same anchor — OfficeCLI batch processes ops relative
      // to original document state (single-pass), maintaining insertion order.
      // If OfficeCLI processes sequentially, body paragraphs would reverse; in that
      // case the orchestrator should fall back to individual add operations.
      const afterPath = anchorParaId
        ? `/body/p[@paraId=${anchorParaId}]`
        : `/body/p[@paraId=${lastParaId}]`

      ops.push({
        command: "add",
        parent: "/body",
        type: "paragraph",
        after: afterPath,
        props: { text: d.new_text ?? d.heading_text, style },
      })

      for (const bp of bodyParas) {
        ops.push({
          command: "add",
          parent: "/body",
          type: "paragraph",
          after: afterPath,
          props: { text: bp, style: bodyStyle },
        })
      }
      continue
    }
  }

  return { ops_plan: ops, errors }
}

function extractLevel(style: string): number {
  const m = style.match(/heading\s*(\d)/i)
  return m ? parseInt(m[1], 10) : 0
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
      result.push({ path: p.path })
    }
    j++
  }
  return result
}

export function registerCompileOpsTool(server: McpServer, worktree: string) {
  server.tool(
    "compile_ops",
    "Deterministically transform action_decisions + body_map into OfficeCLI ops_plan. LLM only writes action_decisions with routing (no body_paragraphs needed); this tool extracts content from content.md deterministically.",
    {
      action_decisions_json: z.string().describe("JSON string of ActionDecision[] — LLM routing output"),
      body_map_json: z.string().describe("JSON string of body_map from inspect_template"),
      toc_refresh: z.boolean().default(false).describe("Whether TOC needs refresh"),
      content_md: z.string().optional().describe("Full content.md text. If provided, body_paragraphs are extracted from here (code, not LLM). LLM should still include md_heading for sections where markdown heading differs from template heading text."),
    },
    async ({ action_decisions_json, body_map_json, toc_refresh, content_md }) => {
      let decisions: ActionDecision[]
      try {
        decisions = JSON.parse(action_decisions_json)
      } catch {
        return {
          content: [{
            type: "text",
            text: JSON.stringify({
              ops_plan: [],
              errors: ["Failed to parse action_decisions JSON. Ensure the output is valid JSON."],
              ops_count: 0,
              toc_refresh,
              validated: false,
            }),
          }],
        }
      }

      const validated = ActionDecisionZod.array().safeParse(decisions)
      if (!validated.success) {
        const zodErrors = validated.error.issues.map(issue =>
          `Entry ${issue.path[0]}: field "${issue.path[issue.path.length - 1]}" — ${issue.message}`
        )
        return {
          content: [{
            type: "text",
            text: JSON.stringify({
              ops_plan: [],
              errors: ["Schema validation failed: " + zodErrors.join("; ")],
              ops_count: 0,
              toc_refresh,
              validated: false,
            }),
          }],
        }
      }

      const bodyMap: BodyMap = JSON.parse(body_map_json)
      const { ops_plan, errors } = compileOps(validated.data, bodyMap, toc_refresh, content_md)

      const result = {
        ops_plan,
        errors,
        ops_count: ops_plan.length,
        toc_refresh,
        validated: errors.length === 0,
      }

      logArtifact("ops_plan.json", result)

      return {
        content: [{
          type: "text",
          text: JSON.stringify(result),
        }],
      }
    }
  )
}

export type { ActionDecision, OfficeCliOp }
