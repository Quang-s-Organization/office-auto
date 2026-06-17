import { fromMarkdown } from "mdast-util-from-markdown"
import { toString } from "mdast-util-to-string"
import type { Root, RootContent, Heading, Paragraph, Text, Strong, Emphasis, InlineCode, List, ListItem } from "mdast"
import type { InlineRun, BodyNode, BodyPlan } from "../schemas/field-set"

interface ParsedBlock {
  type: "heading" | "paragraph" | "list_ordered" | "list_unordered"
  depth?: number
  inlineRuns: InlineRun[]
  rawText: string
  listIndex?: number
}

function extractInlineRuns(node: Paragraph | Heading | ListItem | any): InlineRun[] {
  const runs: InlineRun[] = []

  function walk(n: any, bold: boolean, italic: boolean, underline: boolean) {
    if (n.type === "text") {
      const text = (n as Text).value
      if (text.length > 0) {
        runs.push({ text, bold, italic, underline })
      }
    } else if (n.type === "strong") {
      for (const child of (n as Strong).children) {
        walk(child, true, italic, underline)
      }
    } else if (n.type === "emphasis") {
      for (const child of (n as Emphasis).children) {
        walk(child, bold, true, underline)
      }
    } else if (n.type === "inlineCode") {
      runs.push({ text: (n as InlineCode).value, bold: false, italic: false, underline: false })
    } else if (n.type === "delete") {
      for (const child of (n as any).children ?? []) {
        walk(child, bold, italic, true)
      }
    } else if (n.type === "break" || n.type === "thematicBreak") {
      runs.push({ text: "\n" })
    } else if ("children" in n && Array.isArray((n as any).children)) {
      for (const child of (n as any).children) {
        walk(child, bold, italic, underline)
      }
    }
  }

  for (const child of (node as any).children ?? []) {
    walk(child, false, false, false)
  }

  // Merge adjacent runs with same formatting
  const merged: InlineRun[] = []
  for (const run of runs) {
    if (run.text === "\n" && merged.length === 0) continue
    const prev = merged[merged.length - 1]
    if (
      prev &&
      prev.bold === run.bold &&
      prev.italic === run.italic &&
      prev.underline === run.underline
    ) {
      prev.text += run.text
    } else {
      merged.push({ ...run })
    }
  }

  return merged
}

function parseBlocks(mdContent: string): ParsedBlock[] {
  const tree = fromMarkdown(mdContent)
  const blocks: ParsedBlock[] = []

  function processNode(node: RootContent) {
    switch (node.type) {
      case "heading": {
        const h = node as Heading
        blocks.push({
          type: "heading",
          depth: h.depth,
          inlineRuns: extractInlineRuns(h),
          rawText: toString(h),
        })
        break
      }
      case "paragraph": {
        const p = node as Paragraph
        const runs = extractInlineRuns(p)
        if (runs.length > 0) {
          blocks.push({
            type: "paragraph",
            inlineRuns: runs,
            rawText: toString(p),
          })
        }
        break
      }
      case "list": {
        const list = node as List
        const isOrdered = list.ordered === true
        let idx = list.start ?? 1
        for (const item of list.children) {
          const li = item as ListItem
          const runs = extractInlineRuns(li)
          if (runs.length > 0) {
            blocks.push({
              type: isOrdered ? "list_ordered" : "list_unordered",
              inlineRuns: runs,
              rawText: toString(li),
              listIndex: isOrdered ? idx : undefined,
            })
            if (isOrdered) idx++
          }
        }
        break
      }
      case "blockquote": {
        if ("children" in node) {
          for (const child of (node as any).children as RootContent[]) {
            processNode(child)
          }
        }
        break
      }
      case "code": {
        const code = node as any
        blocks.push({
          type: "paragraph",
          inlineRuns: [{ text: code.value }],
          rawText: code.value,
        })
        break
      }
      default:
        break
    }
  }

  for (const node of (tree as Root).children) {
    processNode(node)
  }

  return blocks
}

const CAN_CU_PATTERN = /^Căn\s*cứ\s+/i
const DIEU_PATTERN = /^Điều\s+(\d+)[\s.:]+/i

function isCanCu(runs: InlineRun[]): boolean {
  const fullText = runs.map((r) => r.text).join("")
  return CAN_CU_PATTERN.test(fullText)
}

function detectDieuNum(runs: InlineRun[]): number | null {
  const fullText = runs.map((r) => r.text).join("")
  const m = fullText.match(DIEU_PATTERN)
  return m ? parseInt(m[1], 10) : null
}

function toPlainString(runs: InlineRun[]): string {
  return runs.map((r) => r.text).join("")
}

export function parseMdToBodyPlan(mdContent: string): BodyPlan {
  const blocks = parseBlocks(mdContent)
  const nodes: BodyNode[] = []
  let currentDieu: Extract<BodyNode, { type: "dieu" }> | null = null
  let currentKhoan: Extract<BodyNode, { type: "khoan" }> | null = null

  for (const block of blocks) {
    if (block.type === "heading" && block.depth === 1) {
      // If there was a previous điều, add it
      if (currentDieu) {
        nodes.push(currentDieu)
        currentDieu = null
        currentKhoan = null
      }
      // This is the document title
      nodes.push({
        type: "para",
        align: "center",
        content: block.inlineRuns,
      })
      continue
    }

    if (block.type === "heading" && block.depth === 2) {
      const dieuNum = detectDieuNum(block.inlineRuns)
      if (dieuNum !== null) {
        if (currentDieu) {
          nodes.push(currentDieu)
          currentKhoan = null
        }
        currentDieu = {
          type: "dieu",
          num: dieuNum,
          title: block.inlineRuns.filter((r) => !DIEU_PATTERN.test(r.text)),
          children: [],
        }
        continue
      }
    }

    // Check for căn cứ
    if (isCanCu(block.inlineRuns)) {
      const cancu: Extract<BodyNode, { type: "cancu" }> = {
        type: "cancu",
        content: block.inlineRuns,
      }
      if (currentKhoan) {
        currentKhoan.children.push(cancu)
      } else if (currentDieu) {
        currentDieu.children.push(cancu)
      } else {
        nodes.push(cancu)
      }
      continue
    }

    // Check for khoản — ordered list items under điều or standalone
    if (block.type === "list_ordered" && block.listIndex !== undefined) {
      const khoanNum = block.listIndex
      currentKhoan = {
        type: "khoan",
        num: khoanNum,
        content: block.inlineRuns,
        children: [],
      }

      if (currentDieu) {
        currentDieu.children.push(currentKhoan)
      } else {
        nodes.push(currentKhoan)
        currentKhoan = null
      }
      continue
    }

    // Check for khoản (numbered paragraph starting with digit + dot) — plain paragraph fallback
    const plainText = toPlainString(block.inlineRuns)
    const khoanMatch = plainText.match(/^(\d+)\.\s/)
    if (khoanMatch && (currentDieu || block.inlineRuns.length > 0)) {
      const khoanNum = parseInt(khoanMatch[1], 10)
      const contentRuns = stripPrefix(block.inlineRuns, khoanMatch[0].length ?? (khoanMatch[1].length + 2))

      currentKhoan = {
        type: "khoan",
        num: khoanNum,
        content: contentRuns,
        children: [],
      }

      if (currentDieu) {
        currentDieu.children.push(currentKhoan)
      } else {
        // Standalone khoản
        if (!currentDieu) {
          // Push previous items
          currentDieu = null
        }
        nodes.push(currentKhoan)
        currentKhoan = null
      }
      continue
    }

    // Check for điểm (a), b), c)...)
    const diemMatch = plainText.match(/^([a-z])\)\s/)
    // Also handle multi-line điểm where mdast merges `a) ... \nb) ...`
    const multiDiemLines = plainText.split(/\n/)
    const allDiem = multiDiemLines.length > 1 && multiDiemLines.every((l) => /^[a-z]\)\s/.test(l.trim()))
    if (allDiem) {
      for (const line of multiDiemLines) {
        const m = line.trim().match(/^([a-z])\)\s+(.*)/)
        if (m) {
          const diem: Extract<BodyNode, { type: "diem" }> = {
            type: "diem",
            label: m[1],
            content: [{ text: m[2] }],
          }
          if (currentKhoan) {
            currentKhoan.children.push(diem)
          } else if (currentDieu) {
            currentDieu.children.push(diem)
          } else {
            nodes.push(diem)
          }
        }
      }
      continue
    }
    if (diemMatch) {
      const contentRuns = stripPrefix(block.inlineRuns, 3)
      const diem: Extract<BodyNode, { type: "diem" }> = {
        type: "diem",
        label: diemMatch[1],
        content: contentRuns,
      }
      if (currentKhoan) {
        currentKhoan.children.push(diem)
      } else if (currentDieu) {
        currentDieu.children.push(diem)
      } else {
        nodes.push(diem)
      }
      continue
    }

    // Regular paragraph or unordered list item
    const targets = currentKhoan ? currentKhoan.children :
      currentDieu ? currentDieu.children : nodes
    targets.push({
      type: "para",
      content: block.inlineRuns,
    })
  }

  // Add any remaining điều
  if (currentDieu) {
    nodes.push(currentDieu)
  }

  return {
    schema_version: "body_plan.v1",
    nodes,
  }
}

function stripPrefix(runs: InlineRun[], prefixLen: number): InlineRun[] {
  if (runs.length === 0) return []

  let remaining = prefixLen
  const result: InlineRun[] = []

  for (const run of runs) {
    if (remaining <= 0) {
      result.push({ ...run })
    } else if (run.text.length <= remaining) {
      remaining -= run.text.length
      // Don't add this run at all
    } else {
      result.push({ ...run, text: run.text.substring(remaining) })
      remaining = 0
    }
  }

  return result
}

export { parseBlocks, extractInlineRuns }
