import AdmZip from "adm-zip"
import { readZipEntry } from "./docx-xml"
import type { TemplateProfile, StyleBinding } from "../schemas/field-set"

interface ContentControlField {
  tag: string
  content: string
  startPos: number
  endPos: number
}

interface TokenField {
  token: string
  startPos: number
  endPos: number
}

function extractAttr(tag: string, attrName: string): string | null {
  const regex = new RegExp(`${attrName}\\s*=\\s*"([^"]*)"`)
  const m = tag.match(regex)
  return m ? m[1] : null
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

function extractTextContent(xml: string): string {
  const parts: string[] = []
  const runRegex = /<w:r[ >][\s\S]*?<\/w:r>/g
  let match
  while ((match = runRegex.exec(xml)) !== null) {
    const tMatch = match[0].match(/<w:t[^>]*>([\s\S]*?)<\/w:t>/)
    if (tMatch) parts.push(tMatch[1])
  }
  return parts.join("")
}

function discoverContentControlFields(docXml: string): ContentControlField[] {
  const fields: ContentControlField[] = []
  const sdtRegex = /<w:sdt[ >]/g
  let match
  while ((match = sdtRegex.exec(docXml)) !== null) {
    const startIdx = match.index
    const endIdx = findClosingTag(docXml, startIdx, "w:sdt")
    if (endIdx < 0) continue

    const sdtBlock = docXml.substring(startIdx, endIdx)
    const tag = (extractAttr(sdtBlock, "w:val") ?? "").trim()
    if (!tag) continue

    const sdtContentMatch = sdtBlock.match(/<w:sdtContent[^>]*>([\s\S]*?)<\/w:sdtContent>/)
    if (!sdtContentMatch) continue

    const content = extractTextContent(sdtContentMatch[1])

    fields.push({
      tag,
      content,
      startPos: startIdx,
      endPos: endIdx,
    })
  }
  return fields
}

function discoverTokenFields(docXml: string): TokenField[] {
  const fields: TokenField[] = []

  const bodyMatch = docXml.match(/(<w:body[^>]*>)([\s\S]*?)(<\/w:body>)/)
  if (!bodyMatch) return fields

  const bodyContent = bodyMatch[2]
  const paraRegex = /<w:p[ >][\s\S]*?<\/w:p>/g
  let paraMatch
  while ((paraMatch = paraRegex.exec(bodyContent)) !== null) {
    const paraBlock = paraMatch[0]
    const textContent = extractTextContent(paraBlock)
    const tokenRegex = /\{\{([a-z_][a-z0-9_]*)\}\}/g
    let tokenMatch
    while ((tokenMatch = tokenRegex.exec(textContent)) !== null) {
      const token = tokenMatch[1]
      if (!token) continue

      const tokenMarker = `{{${token}}}`
      const tokenPos = textContent.indexOf(tokenMarker, tokenMatch.index)
      if (tokenPos < 0) continue

      fields.push({
        token,
        startPos: bodyContent.indexOf(paraBlock) + tokenPos,
        endPos: bodyContent.indexOf(paraBlock) + tokenPos + tokenMarker.length,
      })
    }
  }
  return fields
}

function locateBodyRegion(docXml: string, ccFields: ContentControlField[]): { start_marker: string; end_marker: string } | null {
  // First: check for a content control tagged "noi_dung"
  const bodyCC = ccFields.find((f) => f.tag === "noi_dung")
  if (bodyCC) {
    return {
      start_marker: `sdt:noi_dung:start`,
      end_marker: `sdt:noi_dung:end`,
    }
  }

  // Heuristic: find the region after "QUYẾT ĐỊNH" / "NGHỊ QUYẾT" / etc.
  // and before the signature block markers
  const bodyMatch = docXml.match(/(<w:body[^>]*>)([\s\S]*?)(<\/w:body>)/)
  if (!bodyMatch) return null

  const bodyContent = bodyMatch[2]

  const noidungStartPatterns = [
    /QUYẾT\s*ĐỊNH\s*:/,
    /NGHỊ\s*QUYẾT\s*:/,
    /CÔNG\s*VĂN\s*:/,
    /TỜ\s*TRÌNH\s*:/,
    /THÔNG\s*BÁO\s*:/,
  ]

  const signaturePatterns = [
    /TM\.\s*/,
    /KT\.\s*/,
    /Q\.\s*/,
    /TL\.\s*/,
    /TUQ\.\s*/,
    /Nơi\s*nhận\s*:/,
  ]

  let startPos = -1
  for (const pattern of noidungStartPatterns) {
    const match = bodyContent.match(pattern)
    if (match && match.index !== undefined) {
      // Move past this declaration line
      const afterMatch = bodyContent.substring(match.index)
      const nextParaEnd = afterMatch.indexOf("</w:p>")
      if (nextParaEnd > 0) {
        startPos = match.index + nextParaEnd + "</w:p>".length
        break
      }
    }
  }

  if (startPos < 0) return null

  let endPos = bodyContent.length
  for (const pattern of signaturePatterns) {
    const match = bodyContent.substring(startPos).match(pattern)
    if (match && match.index !== undefined) {
      const absPos = startPos + match.index
      // Find the paragraph start before this match
      const beforeChunk = bodyContent.substring(startPos, absPos)
      const lastParaOpen = beforeChunk.lastIndexOf("<w:p")
      if (lastParaOpen > 0) {
        endPos = startPos + lastParaOpen
      } else {
        endPos = absPos
      }
      break
    }
  }

  if (endPos <= startPos) return null

  return {
    start_marker: String(startPos),
    end_marker: String(endPos),
  }
}

function discoverSections(docXml: string): Array<{ sect_pr_index: number; sect_pr_xml: string }> {
  const sections: Array<{ sect_pr_index: number; sect_pr_xml: string }> = []
  const sectPrRegex = /<w:sectPr[\s>][\s\S]*?<\/w:sectPr>/g
  let index = 0
  let match
  while ((match = sectPrRegex.exec(docXml)) !== null) {
    sections.push({
      sect_pr_index: index,
      sect_pr_xml: match[0],
    })
    index++
  }
  return sections
}

function buildStyleBindings(stylesXml: string): StyleBinding[] {
  const bindings: StyleBinding[] = []
  const styleRegex = /<w:style[^>]*>/g
  let match
  while ((match = styleRegex.exec(stylesXml)) !== null) {
    const startIdx = match.index
    const endIdx = findClosingTag(stylesXml, startIdx, "w:style")
    if (endIdx < 0) continue

    const block = stylesXml.substring(startIdx, endIdx)
    const styleId = extractAttr(block, "w:styleId")
    const name = (block.match(/<w:name[^>]*w:val="([^"]*)"/) ?? [])[1] ?? styleId

    if (!styleId) continue

    const role = classifyStyleRole(name, styleId)
    if (role) {
      bindings.push({
        role,
        styleId,
        source: "exact_match",
        confidence: 1.0,
      })
    }
  }
  return bindings
}

function classifyStyleRole(name: string, styleId: string): StyleBinding["role"] | null {
  const lower = (name + styleId).toLowerCase()

  if (/heading\s*1|dieu\b/i.test(lower)) return "dieu"
  if (/heading\s*2|khoan\b/i.test(lower)) return "khoan"
  if (/heading\s*3|diem\b/i.test(lower)) return "diem"
  if (/heading\s*[4-6]|tieude|tieu\s*de/i.test(lower)) return "tieude"
  if (/cancu|can\s*cu|căn\s*cứ/i.test(lower)) return "cancu"
  if (/table|bang|bảng|danh\s*sach/i.test(lower)) return "table"
  if (/normal|body|noidung|noi\s*dung|paragraph|justified/i.test(lower)) return "para"

  return null
}

export function introspectTemplate(templatePath: string): TemplateProfile {
  const zip = new AdmZip(templatePath)
  const docXml = readZipEntry(zip, "word/document.xml")
  const stylesXml = readZipEntry(zip, "word/styles.xml")

  const ccFields = discoverContentControlFields(docXml)
  const tokenFields = discoverTokenFields(docXml)
  const bodyRegion = locateBodyRegion(docXml, ccFields)
  const sections = discoverSections(docXml)
  const styleBindings = buildStyleBindings(stylesXml)

  // Merge fields: content controls take priority, tokens are fallback
  const seenTags = new Set<string>()
  const fields: TemplateProfile["fields"] = []

  for (const cc of ccFields) {
    seenTags.add(cc.tag)
    fields.push({ tag: cc.tag, mode: "content_control", required: true })
  }

  for (const tf of tokenFields) {
    if (!seenTags.has(tf.token)) {
      seenTags.add(tf.token)
      fields.push({ tag: tf.token, mode: "token", required: true })
    }
  }

  // Mark optional fields
  const requiredSet = new Set([
    "so_ky_hieu", "ten_co_quan", "dia_danh_ngay",
    "ten_loai", "trich_yeu", "noi_dung",
    "chuc_vu_ky", "ho_ten_ky", "noi_nhan",
  ])
  for (const field of fields) {
    if (!requiredSet.has(field.tag)) {
      field.required = false
    }
  }

  return {
    schema_version: "template_profile.v1",
    template_path: templatePath,
    inspected_at: new Date().toISOString(),
    fields,
    body_region: bodyRegion,
    style_bindings: styleBindings,
    sections,
  }
}
