import type { InlineRun } from "../../schemas/field-set"

export function xmlEscape(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;")
}

export function buildRunXml(run: InlineRun): string {
  const rPr: string[] = []
  if (run.bold) rPr.push("<w:b/>")
  if (run.italic) rPr.push("<w:i/>")
  if (run.underline) rPr.push('<w:u w:val="single"/>')

  const rPrXml = rPr.length > 0 ? `<w:rPr>${rPr.join("")}</w:rPr>` : ""

  // Split on \n — each becomes a separate <w:r> with <w:br/>
  const parts = run.text.split("\n")
  const runsXml: string[] = []

  for (let i = 0; i < parts.length; i++) {
    if (i > 0) {
      runsXml.push("<w:r><w:br/></w:r>")
    }
    if (parts[i].length > 0) {
      runsXml.push(
        `<w:r>${rPrXml}<w:t xml:space="preserve">${xmlEscape(parts[i])}</w:t></w:r>`,
      )
    }
  }

  if (runsXml.length === 0) {
    return `<w:r>${rPrXml}<w:t xml:space="preserve"></w:t></w:r>`
  }

  return runsXml.join("")
}

export function buildInlineRunsXml(runs: InlineRun[]): string {
  return runs.map((r) => buildRunXml(r)).join("")
}

export function plainRun(text: string): InlineRun {
  return { text }
}

export function boldRun(text: string): InlineRun {
  return { text, bold: true }
}

export function italicRun(text: string): InlineRun {
  return { text, italic: true }
}

export function underlineRun(text: string): InlineRun {
  return { text, underline: true }
}
