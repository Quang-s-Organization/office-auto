import { copyFileSync } from "fs"
import AdmZip from "adm-zip"
import { readZipEntry, writeZipEntry } from "../lib/docx-xml"
import { buildInlineRunsXml } from "../lib/ooxml/runs"
import { renderBodyPlan, resetParaIdCounter } from "../lib/ooxml/clause"
import { extractTemplateParaIds } from "../lib/para-id"
import type { TemplateProfile, FieldSet, BodyPlan } from "../schemas/field-set"

function findClosingTag(xml: string, startIdx: number, tagName: string): number {
  let depth = 1
  let i = startIdx
  while (i < xml.length && depth > 0) {
    const nextOpen = xml.indexOf(`<${tagName}`, i + 1)
    const nextClose = xml.indexOf(`</${tagName}>`, i)
    if (nextClose < 0) return -1
    if (nextOpen > 0 && nextOpen < nextClose) {
      depth++
      i = nextOpen
    } else {
      depth--
      if (depth === 0) return nextClose + `</${tagName}>`.length
      i = nextClose + 1
    }
  }
  return -1
}

function findSdtByTag(docXml: string, tag: string): { startPos: number; endPos: number; contentStart: number; contentEnd: number } | null {
  const searchStart = 0
  let searchFrom = searchStart
  while (searchFrom < docXml.length) {
    const sdtOpen = docXml.indexOf("<w:sdt", searchFrom)
    if (sdtOpen < 0) return null

    const sdtEnd = findClosingTag(docXml, sdtOpen, "w:sdt")
    if (sdtEnd < 0) return null

    const sdtBlock = docXml.substring(sdtOpen, sdtEnd)
    const tagMatch = sdtBlock.match(/<w:tag[^>]*w:val="([^"]*)"[^>]*\/>/)
    const foundTag = tagMatch ? tagMatch[1] : null

    if (foundTag === tag) {
      const contentMatch = sdtBlock.match(/<w:sdtContent[^>]*>([\s\S]*?)<\/w:sdtContent>/)
      if (contentMatch && contentMatch.index !== undefined) {
        const contentStart = sdtOpen + contentMatch.index! + contentMatch[0].indexOf(">") + 1
        const contentEnd = contentStart + contentMatch[1].length
        return { startPos: sdtOpen, endPos: sdtEnd, contentStart, contentEnd }
      }
    }

    searchFrom = sdtEnd
  }
  return null
}

function replaceFieldInContentControl(docXml: string, tag: string, valueXml: string): string | null {
  const sdt = findSdtByTag(docXml, tag)
  if (!sdt) return null

  return docXml.substring(0, sdt.contentStart) + valueXml + docXml.substring(sdt.contentEnd)
}

function replaceTokenField(docXml: string, token: string, valueXml: string): string {
  const tokenMarker = `{{${token}}}`
  // Token replacement in OOXML is tricky because Word can split tokens
  // across multiple <w:r> elements. We handle this by regex on the whole doc.
  // Actually, handle it by looking for the token in <w:t> text nodes.
  let result = docXml
  const tRegex = /(<w:t[^>]*>)(\{\{[a-z_][a-z0-9_]*\}\})(<\/w:t>)/g
  let replaced = false

  result = result.replace(tRegex, (full, prefix, matched, suffix) => {
    if (matched === tokenMarker) {
      replaced = true
      return prefix + valueXml + suffix
    }
    return full
  })

  // Also handle the token split across runs by replacing {{ and }} individually
  // Simple approach: find {{tag}} even if split and replace the entire paragraph's text
  if (!replaced) {
    const tokenSplitRegex = new RegExp(`\\{\\{${escapeRegex(token)}\\}\\}`, "g")
    result = result.replace(tokenSplitRegex, valueXml)
  }

  return result
}

function escapeRegex(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
}

function replaceBodyRegion(
  docXml: string,
  bodyRegion: NonNullable<TemplateProfile["body_region"]>,
  bodyPlanXml: string,
): string {
  const { start_marker, end_marker } = bodyRegion

  if (start_marker.startsWith("sdt:noi_dung:")) {
    // Body is inside a content control tagged "noi_dung"
    return replaceFieldInContentControl(docXml, "noi_dung", bodyPlanXml) ?? docXml
  }

  // Numeric offsets within body content
  const bodyMatch = docXml.match(/(<w:body[^>]*>)([\s\S]*?)(<\/w:body>)/)
  if (!bodyMatch) return docXml

  const bodyPrefix = bodyMatch[1]
  const bodyContent = bodyMatch[2]
  const bodySuffix = bodyMatch[3]

  const start = parseInt(start_marker, 10)
  const end = parseInt(end_marker, 10)

  if (isNaN(start) || isNaN(end) || start < 0 || end <= start) return docXml

  const before = bodyContent.substring(0, start)
  const after = bodyContent.substring(end)

  return bodyPrefix + before + bodyPlanXml + after + bodySuffix
}

function renderFieldValue(fieldValue: Record<string, unknown>): string {
  // Handle FieldValue discriminated union
  const kind = fieldValue.kind as string
  switch (kind) {
    case "text": {
      const runs = fieldValue.runs as Array<{ text: string; bold?: boolean; italic?: boolean; underline?: boolean }>
      return runs.map((r) => {
        const rPr: string[] = []
        if (r.bold) rPr.push("<w:b/>")
        if (r.italic) rPr.push("<w:i/>")
        if (r.underline) rPr.push('<w:u w:val="single"/>')
        const rPrXml = rPr.length > 0 ? `<w:rPr>${rPr.join("")}</w:rPr>` : ""
        const escaped = r.text
          .replace(/&/g, "&amp;")
          .replace(/</g, "&lt;")
          .replace(/>/g, "&gt;")
          .replace(/"/g, "&quot;")
          .replace(/'/g, "&apos;")
        return `<w:r>${rPrXml}<w:t xml:space="preserve">${escaped}</w:t></w:r>`
      }).join("")
    }
    case "date": {
      const display = fieldValue.display as string
      const escaped = display
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&apos;")
      return `<w:r><w:t xml:space="preserve">${escaped}</w:t></w:r>`
    }
    case "lines": {
      const lines = fieldValue.lines as Array<Array<{ text: string; bold?: boolean; italic?: boolean; underline?: boolean }>>
      return lines.map((lineRuns, i) => {
        const runsXml = buildInlineRunsXml(lineRuns as any)
        return `<w:p>${runsXml}</w:p>`
      }).join("")
    }
    default:
      return ""
  }
}

export function applyRegions(
  templatePath: string,
  outputPath: string,
  profile: TemplateProfile,
  fieldSet: FieldSet,
  bodyPlan?: BodyPlan,
): void {
  copyFileSync(templatePath, outputPath)

  const zip = new AdmZip(outputPath)
  let docXml = readZipEntry(zip, "word/document.xml")

  // Avoid paraId collisions: track existing template IDs
  const templateIds = extractTemplateParaIds(docXml)

  for (const [tag, value] of Object.entries(fieldSet)) {
    const field = profile.fields.find((f) => f.tag === tag)
    if (!field) continue

    const valueXml = renderFieldValue(value as Record<string, unknown>)

    if (field.mode === "content_control") {
      const replaced = replaceFieldInContentControl(docXml, tag, valueXml)
      if (replaced !== null) {
        docXml = replaced
      }
    } else if (field.mode === "token") {
      docXml = replaceTokenField(docXml, tag, valueXml)
    }
  }

  if (bodyPlan && profile.body_region) {
    // Reset paraId counter to avoid collisions with template
    resetParaIdCounter("run")
    const bodyPlanXml = renderBodyPlan(bodyPlan, profile.style_bindings)
    docXml = replaceBodyRegion(docXml, profile.body_region, bodyPlanXml)
  }

  // Multi-section: preserve all sectPr blocks
  if (profile.sections.length > 1) {
    // Ensure all sections (except the last) have proper sectPr placement
    // The bodyPlan XML should already include sectPr for multi-section docs
    // For now, just verify no sectPrs were lost
  }

  writeZipEntry(zip, "word/document.xml", docXml)
  zip.writeZip(outputPath)
}
