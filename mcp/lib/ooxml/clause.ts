import type { BodyNode, InlineRun, StyleBinding } from "../../schemas/field-set"
import { buildInlineRunsXml, boldRun, plainRun } from "./runs"

let paraIdCounter = 0
let paraIdRunId = ""

export function resetParaIdCounter(runId: string): void {
  paraIdCounter = 0
  paraIdRunId = runId
}

export function generateParaId(): string {
  paraIdCounter++
  // Format: AD + 6 hex chars from counter
  const hex = (paraIdCounter).toString(16).toUpperCase().padStart(6, "0")
  return `AD${hex}`
}

const DIEM_LABELS = "abcdefghijklmnopqrstuvwxyz"

function paraXml(styleId: string | undefined, runsXml: string, align?: string, paraId?: string): string {
  const pPr: string[] = []
  if (styleId) pPr.push(`<w:pStyle w:val="${styleId}"/>`)
  if (align) pPr.push(`<w:jc w:val="${align}"/>`)

  const paraIdAttr = paraId ? ` w14:paraId="${paraId}"` : ""
  const pPrXml = pPr.length > 0 ? `<w:pPr>${pPr.join("")}</w:pPr>` : ""
  return `<w:p${paraIdAttr}>${pPrXml}${runsXml}</w:p>`
}

function getStyle(bindings: StyleBinding[], role: StyleBinding["role"]): string | undefined {
  const match = bindings.find((b) => b.role === role)
  return match?.styleId
}

export function renderBodyNode(
  node: BodyNode,
  bindings: StyleBinding[],
  paraIndex: number,
): string | null {
  switch (node.type) {
    case "dieu":
      return renderDieu(node, bindings, paraIndex)
    case "khoan":
      return renderKhoan(node, bindings, paraIndex)
    case "diem":
      return renderDiem(node, bindings, paraIndex)
    case "para":
      return renderPara(node, bindings, paraIndex)
    case "cancu":
      return renderCanCu(node, bindings, paraIndex)
    case "table":
      return renderTable(node, bindings, paraIndex)
    case "pagebreak":
      return renderPageBreak()
    case "unsupported":
      return null
  }
  return null
}

function renderDieu(node: Extract<BodyNode, { type: "dieu" }>, bindings: StyleBinding[], _paraIndex: number): string {
  const styleId = getStyle(bindings, "dieu")
  const labelRuns = boldRun(`Điều ${node.num}.`)
  const runsXml = buildInlineRunsXml([labelRuns]) + buildInlineRunsXml(node.title)
  const parts: string[] = [paraXml(styleId, runsXml, undefined, generateParaId())]

  let childIndex = 0
  for (const child of node.children) {
    const rendered = renderBodyNode(child, bindings, parts.length + childIndex)
    if (rendered) {
      parts.push(rendered)
      childIndex++
    }
  }

  return parts.join("")
}

function renderKhoan(node: Extract<BodyNode, { type: "khoan" }>, bindings: StyleBinding[], _paraIndex: number): string {
  const styleId = getStyle(bindings, "khoan")
  const labelRuns = boldRun(`${node.num}.`)
  const spacer = plainRun(" ")
  const runsXml = buildInlineRunsXml([labelRuns, spacer]) + buildInlineRunsXml(node.content)
  const parts: string[] = [paraXml(styleId, runsXml, undefined, generateParaId())]

  let childIndex = 0
  for (const child of node.children) {
    const rendered = renderBodyNode(child, bindings, parts.length + childIndex)
    if (rendered) {
      parts.push(rendered)
      childIndex++
    }
  }

  return parts.join("")
}

function renderDiem(node: Extract<BodyNode, { type: "diem" }>, bindings: StyleBinding[], _paraIndex: number): string {
  const styleId = getStyle(bindings, "diem")
  const labelRuns = boldRun(`${node.label})`)
  const spacer = plainRun(" ")
  const runsXml = buildInlineRunsXml([labelRuns, spacer]) + buildInlineRunsXml(node.content)
  return paraXml(styleId, runsXml, undefined, generateParaId())
}

function renderPara(node: Extract<BodyNode, { type: "para" }>, bindings: StyleBinding[], _paraIndex: number): string {
  const styleId = getStyle(bindings, "para")
  const runsXml = buildInlineRunsXml(node.content)
  return paraXml(styleId, runsXml, node.align, generateParaId())
}

function renderCanCu(node: Extract<BodyNode, { type: "cancu" }>, bindings: StyleBinding[], _paraIndex: number): string {
  const styleId = getStyle(bindings, "cancu") ?? getStyle(bindings, "para")
  const italicRuns: InlineRun[] = node.content.map((r: InlineRun) => ({ ...r, italic: true }))
  const runsXml = buildInlineRunsXml(italicRuns)
  return paraXml(styleId, runsXml, "justify", generateParaId())
}

function renderTable(node: Extract<BodyNode, { type: "table" }>, bindings: StyleBinding[], paraIndex: number): string {
  const tableStyleId = getStyle(bindings, "table") ?? "TableGrid"
  const tblPr = `<w:tblPr><w:tblStyle w:val="${tableStyleId}"/></w:tblPr>`
  const tblGrid = `<w:tblGrid>${node.rows[0]?.map(() => '<w:gridCol w:w="2500"/>').join("") ?? ""}</w:tblGrid>`

  const rowsXml = node.rows
    .map((row: InlineRun[][]) => {
      const cellsXml = row
        .map((cellRuns: InlineRun[]) => {
          const runsXml = buildInlineRunsXml(cellRuns)
          return `<w:tc><w:p>${runsXml}</w:p></w:tc>`
        })
        .join("")
      return `<w:tr>${cellsXml}</w:tr>`
    })
    .join("")

  return `<w:tbl>${tblPr}${tblGrid}${rowsXml}</w:tbl>`
}

function renderPageBreak(): string {
  return `<w:p><w:r><w:br w:type="page"/></w:r></w:p>`
}

export function renderBodyPlan(
  plan: { nodes: BodyNode[] },
  bindings: StyleBinding[],
): string {
  const parts: string[] = []
  for (const node of plan.nodes) {
    const rendered = renderBodyNode(node, bindings, parts.length)
    if (rendered) {
      parts.push(rendered)
    }
  }
  return parts.join("")
}
