import AdmZip from "adm-zip"
import type { StyleMap, StyleRole, RenderItem, Chrome } from "../schemas/style-map"

export function readZipEntry(zip: AdmZip, entryPath: string): string {
  const entry = zip.getEntry(entryPath)
  if (!entry) throw new Error(`ZIP entry not found: ${entryPath}`)
  return entry.getData().toString("utf-8")
}

export function writeZipEntry(zip: AdmZip, entryPath: string, content: string): void {
  zip.updateFile(entryPath, Buffer.from(content, "utf-8"))
}

// ─── Style extraction ──────────────────────────────────────────────────────

interface ParsedStyle {
  styleId: string
  name: string
  type: string
}

export function parseStylesXml(xml: string): ParsedStyle[] {
  const results: ParsedStyle[] = []
  const styleRegex = /<w:style[^>]*>/g
  let match
  while ((match = styleRegex.exec(xml)) !== null) {
    const fullTag = match[0]
    const startIdx = match.index
    const endIdx = findClosingTag(xml, startIdx, "w:style")
    if (endIdx < 0) continue

    const block = xml.substring(startIdx, endIdx)
    const styleId = extractAttr(block, "w:styleId")
    const name = extractName(block)
    const type = extractAttr(block, "w:type") ?? "paragraph"

    if (styleId) {
      results.push({ styleId, name: name ?? styleId, type })
    }
  }
  return results
}

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

function extractAttr(tag: string, attrName: string): string | null {
  const regex = new RegExp(`${attrName}\\s*=\\s*"([^"]*)"`)
  const m = tag.match(regex)
  return m ? m[1] : null
}

function extractName(block: string): string | null {
  const m = block.match(/<w:name[^>]*w:val="([^"]*)"/)
  return m ? m[1] : null
}

// ─── Style role resolution ─────────────────────────────────────────────────

export function resolveStyleMap(styles: ParsedStyle[], existing: Map<string, string> = new Map()): StyleMap {
  const roles: Record<string, string> = {}
  const allIds = styles.map((s) => s.styleId)

  for (const s of styles) {
    if (/^heading\s*1$/i.test(s.name) || s.styleId === "Heading1") {
      roles["heading 1"] = s.styleId
    } else if (/^heading\s*2$/i.test(s.name) || s.styleId === "Heading2") {
      roles["heading 2"] = s.styleId
    } else if (/^heading\s*3$/i.test(s.name) || s.styleId === "Heading3") {
      roles["heading 3"] = s.styleId
    } else if (/^heading\s*4$/i.test(s.name) || s.styleId === "Heading4") {
      roles["heading 4"] = s.styleId
    } else if (/^heading\s*5$/i.test(s.name) || s.styleId === "Heading5") {
      roles["heading 5"] = s.styleId
    } else if (/^heading\s*6$/i.test(s.name) || s.styleId === "Heading6") {
      roles["heading 6"] = s.styleId
    }
  }

  const bodyCandidates = [
    "Normal", "Normalstyle", "Normal1", "BodyText", "BodyText2",
    "BodyText3", "Noidung", "StyleNoiDung", "StyleVnTime13ptJustifiedBefore3ptAfter3ptLine",
  ]
  for (const candidate of bodyCandidates) {
    if (allIds.includes(candidate)) {
      roles["Normal"] = candidate
      break
    }
  }
  if (!roles["Normal"]) {
    for (const s of styles) {
      if (s.name && /\bnormal\b/i.test(s.name) && !/heading/i.test(s.name) && !/table/i.test(s.name)) {
        roles["Normal"] = s.styleId
        break
      }
    }
  }

  const captionCandidates = ["Bngbiu-title", "Caption", "Bngbiu", "Hinh", "TableofFigures"]
  for (const candidate of captionCandidates) {
    if (allIds.includes(candidate)) {
      roles["caption"] = candidate
      break
    }
  }

  const bibCandidates = ["Bibliography", "TaiLieuThamKhao", "references"]
  for (const candidate of bibCandidates) {
    if (allIds.includes(candidate)) {
      roles["bibliography"] = candidate
      break
    }
  }

  const tocCandidates = ["TOC1", "toc 1", "TOCHeading", "TOC"]
  for (const candidate of tocCandidates) {
    if (allIds.includes(candidate)) {
      roles["TOC"] = candidate
      break
    }
  }

  return {
    schema_version: "style_map.v1",
    template_path: "",
    inspected_at: new Date().toISOString(),
    roles: roles as Record<StyleRole, string>,
    all_style_ids: allIds,
  }
}

// ─── Chrome extraction (front matter + sectPr) ─────────────────────────────

export function extractChrome(docXml: string): Chrome {
  const bodyMatch = docXml.match(/(<w:body[^>]*>)([\s\S]*?)(<\/w:body>)/)
  if (!bodyMatch) throw new Error("Could not find w:body in document.xml")

  const bodyTag = bodyMatch[1]
  const bodyContent = bodyMatch[2]

  const bodyAttrs = bodyTag.replace(/^<w:body/, "").replace(/>$/, "").trim()

  const sectPrMatch = bodyContent.match(/<w:sectPr[\s>][\s\S]*?<\/w:sectPr>/)
  const sectPrXml = sectPrMatch ? sectPrMatch[0] : ""

  const frontMatterXml = extractFrontMatter(bodyContent)

  return {
    front_matter_xml: frontMatterXml,
    sect_pr_xml: sectPrXml,
    body_attributes: bodyAttrs,
  }
}

function extractFrontMatter(bodyXml: string): string {
  const firstHeadingIdx = findFirstHeadingParagraph(bodyXml)
  if (firstHeadingIdx < 0) return ""

  const prefix = bodyXml.substring(0, firstHeadingIdx)

  const lastParaEnd = prefix.lastIndexOf("</w:p>")
  if (lastParaEnd < 0) return prefix

  return prefix.substring(0, lastParaEnd + "</w:p>".length)
}

function findFirstHeadingParagraph(bodyXml: string): number {
  const headingStyles = ["Phan", "Heading1", "Heading11", "Heading 1",
    "StyleHeading11", "StyleHeading111pt", "StyleHeading113pt",
    "StyleTenMucChinh", "Muc1", "IEEEHeading1", "jmstmclnvd1",
    "Tit-1", "Style1", "Style10"]
  let earliest = bodyXml.length

  for (const hs of headingStyles) {
    const idx = bodyXml.indexOf(`<w:pStyle w:val="${hs}"`)
    if (idx >= 0 && idx < earliest) earliest = idx
  }
  return earliest < bodyXml.length ? earliest : -1
}

// ─── XML building helpers ──────────────────────────────────────────────────

export function xmlEscape(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;")
}

export function generateParaId(index: number): string {
  const hex = (index + 1).toString(16).toUpperCase()
  return hex.padStart(8, "0")
}

export function buildParagraphXml(item: RenderItem, index: number): string {
  const pId = generateParaId(index)
  return `<w:p w14:paraId="${pId}"><w:pPr><w:pStyle w:val="${xmlEscape(item.styleId)}"/></w:pPr><w:r><w:t xml:space="preserve">${xmlEscape(item.text)}</w:t></w:r></w:p>`
}

export function buildBodyXml(frontMatterXml: string, paragraphs: RenderItem[], sectPrXml: string, bodyAttrs: string): string {
  const parts: string[] = []

  if (frontMatterXml) {
    parts.push(frontMatterXml)
  }

  for (let i = 0; i < paragraphs.length; i++) {
    parts.push(buildParagraphXml(paragraphs[i], i))
  }

  const bodyInner = parts.join("") + sectPrXml
  const openTag = bodyAttrs ? `<w:body ${bodyAttrs}>` : "<w:body>"
  return `${openTag}${bodyInner}</w:body>`
}


