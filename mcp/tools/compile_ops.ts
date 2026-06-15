import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js"
import { z } from "zod"
import type { BodyMap } from "./inspect_template"

interface ActionDecision {
  heading_text: string
  action: "update" | "keep" | "remove" | "add"
  new_text?: string
  after?: string
  /** Body paragraphs following this heading (for add or update) */
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
  return t.replace(/\s+/g, " ").trim().toLowerCase()
}

export function compileOps(actionDecisions: ActionDecision[], bodyMap: BodyMap, tocRefresh: boolean): {
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
      // Find all paragraphs in this section: heading + everything after until next same-or-higher level heading
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
      // Remove from heading back to (j-1)
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
      // Update body paragraphs for this section if provided
      if (d.body_paragraphs && d.body_paragraphs.length > 0) {
        const sectionLevel = h.level
        const bodyParas = findBodyParagraphsForSection(bodyMap, h, sectionLevel)
        for (let bi = 0; bi < bodyParas.length && bi < d.body_paragraphs.length; bi++) {
          ops.push({
            command: "set",
            path: bodyParas[bi].path,
            props: { text: d.body_paragraphs[bi] },
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

      if (!anchorParaId) {
        // Fall through: append after last paragraph
      }

      ops.push({
        command: "add",
        parent: "/body",
        type: "paragraph",
        after: anchorParaId ? `/body/p[@paraId=${anchorParaId}]` : `/body/p[@paraId=${bodyMap.paragraphs[bodyMap.paragraphs.length - 1]?.paraId ?? ""}]`,
        props: { text: d.new_text ?? d.heading_text, style },
      })

      // Add body paragraphs after the new heading (will use same anchor for simplicity)
      if (d.body_paragraphs) {
        for (const bp of d.body_paragraphs) {
          ops.push({
            command: "add",
            parent: "/body",
            type: "paragraph",
            after: anchorParaId ? `/body/p[@paraId=${anchorParaId}]` : `/body/p[@paraId=${bodyMap.paragraphs[bodyMap.paragraphs.length - 1]?.paraId ?? ""}]`,
            props: { text: bp, style: bodyStyle },
          })
        }
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
    "Deterministically transform action_decisions + body_map into OfficeCLI ops_plan. LLM only writes action_decisions; this tool does all paraId/command mapping.",
    {
      action_decisions_json: z.string().describe("JSON string of ActionDecision[] — LLM output"),
      body_map_json: z.string().describe("JSON string of body_map from inspect_template"),
      toc_refresh: z.boolean().default(false).describe("Whether TOC needs refresh"),
    },
    async ({ action_decisions_json, body_map_json, toc_refresh }) => {
      const decisions: ActionDecision[] = JSON.parse(action_decisions_json)
      const bodyMap: BodyMap = JSON.parse(body_map_json)
      const { ops_plan, errors } = compileOps(decisions, bodyMap, toc_refresh)

      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            ops_plan,
            errors,
            ops_count: ops_plan.length,
            toc_refresh,
            validated: errors.length === 0,
          }),
        }],
      }
    }
  )
}

export type { ActionDecision, OfficeCliOp }
