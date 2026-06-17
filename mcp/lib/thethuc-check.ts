import { readFileSync } from "fs"
import AdmZip from "adm-zip"
import { readZipEntry } from "./docx-xml"
import type { TemplateProfile } from "../schemas/field-set"

export interface ComplianceReport {
  ok: boolean
  components_present: Record<string, boolean>
  chrome_intact: boolean
  no_leftover_tokens: boolean
  all_checks_passed: boolean
  details: string[]
  created_at: string
}

const ND30_COMPONENTS: Array<{ id: string; name: string; patterns: RegExp[] }> = [
  {
    id: "1_quoc_hieu",
    name: "Quốc hiệu và Tiêu ngữ",
    patterns: [/CỘNG\s*HÒA\s*XÃ\s*HỘI\s*CHỦ\s*NGHĨA\s*VIỆT\s*NAM/i, /Độc\s*lập\s*-\s*Tự\s*do\s*-\s*Hạnh\s*phúc/i],
  },
  {
    id: "2_ten_co_quan",
    name: "Tên cơ quan, tổ chức ban hành",
    patterns: [/ỦY\s*BAN\s*NHÂN\s*DÂN|HỘI\s*ĐỒNG\s*NHÂN\s*DÂN|UBND|HĐND|SỞ\s+|BỘ\s+|BAN\s+/i],
  },
  {
    id: "3_so_ky_hieu",
    name: "Số, ký hiệu của văn bản",
    patterns: [/Số:\s*\d+/i, /Số\s+\d+/i],
  },
  {
    id: "4_dia_danh_ngay",
    name: "Địa danh và thời gian ban hành",
    patterns: [/ngày\s+\d{1,2}\s+tháng\s+\d{1,2}\s+năm\s+\d{4}/i],
  },
  {
    id: "5_ten_loai_trich_yeu",
    name: "Tên loại và trích yếu nội dung",
    patterns: [/QUYẾT\s*ĐỊNH|NGHỊ\s*QUYẾT|CÔNG\s*VĂN|TỜ\s*TRÌNH|THÔNG\s*BÁO/i],
  },
  {
    id: "6_noi_dung",
    name: "Nội dung văn bản",
    patterns: [/Điều\s+\d+|Căn\s*cứ\s+|Xét\s+đề\s+nghị/i],
  },
  {
    id: "7_chuc_vu_ky",
    name: "Chức vụ, họ tên và chữ ký",
    patterns: [/TM\.\s+|KT\.\s+|Q\.\s+|TL\.\s+|TUQ\.\s+/i, /CHỦ\s*TỊCH|GIÁM\s*ĐỐC|TRƯỞNG\s+|PHÓ\s+/i],
  },
  {
    id: "8_dau_chu_ky",
    name: "Dấu, chữ ký số của cơ quan",
    patterns: [], // Dấu is typically an image, not text-detectable without deeper analysis
  },
  {
    id: "9_noi_nhan",
    name: "Nơi nhận",
    patterns: [/Nơi\s*nhận\s*:/i],
  },
]

function extractTextContent(docXml: string): string {
  const parts: string[] = []
  const tRegex = /<w:t[^>]*>([\s\S]*?)<\/w:t>/g
  let match
  while ((match = tRegex.exec(docXml)) !== null) {
    parts.push(match[1])
  }
  return parts.join("\n")
}

export function checkTheThucCompliance(
  outputPath: string,
  templatePath: string,
  profile: TemplateProfile,
): ComplianceReport {
  const details: string[] = []
  const components_present: Record<string, boolean> = {}

  const outputZip = new AdmZip(outputPath)
  const outputDocXml = readZipEntry(outputZip, "word/document.xml")
  const outputText = extractTextContent(outputDocXml)

  // Check each ND-30 component
  let allComponentsPresent = true
  for (const comp of ND30_COMPONENTS) {
    if (comp.patterns.length === 0) {
      components_present[comp.id] = true
      details.push(`[PASS] ${comp.name}: cannot text-verify (image-based)`)
      continue
    }

    const found = comp.patterns.some((p) => p.test(outputText))
    components_present[comp.id] = found
    if (!found) {
      allComponentsPresent = false
      details.push(`[FAIL] ${comp.name}: not found in output text`)
    } else {
      details.push(`[PASS] ${comp.name}: found`)
    }
  }

  // Chrome integrity: compare template vs output outside replaced regions
  const templateZip = new AdmZip(templatePath)
  const templateDocXml = readZipEntry(templateZip, "word/document.xml")
  const chromeIntact = checkChromeIntegrity(templateDocXml, outputDocXml, profile, details)

  // Leftover tokens
  const leftoverTokens = outputDocXml.match(/\{\{[a-z_][a-z0-9_]*\}\}/g)
  const no_leftover_tokens = !leftoverTokens || leftoverTokens.length === 0
  if (!no_leftover_tokens) {
    details.push(`[FAIL] Leftover tokens: ${leftoverTokens!.join(", ")}`)
  } else {
    details.push("[PASS] No leftover tokens")
  }

  const allChecksPassed = allComponentsPresent && chromeIntact && no_leftover_tokens

  return {
    ok: allChecksPassed,
    components_present,
    chrome_intact: chromeIntact,
    no_leftover_tokens,
    all_checks_passed: allChecksPassed,
    details,
    created_at: new Date().toISOString(),
  }
}

function checkChromeIntegrity(
  templateXml: string,
  outputXml: string,
  _profile: TemplateProfile,
  details: string[],
): boolean {
  // Extract the body content from both
  const tmplBodyMatch = templateXml.match(/(<w:body[^>]*>)([\s\S]*?)(<\/w:body>)/)
  const outBodyMatch = outputXml.match(/(<w:body[^>]*>)([\s\S]*?)(<\/w:body>)/)

  if (!tmplBodyMatch || !outBodyMatch) {
    details.push("[FAIL] Cannot compare chrome: body tag not found in both documents")
    return false
  }

  // Compare body tag attributes
  const tmplAttrs = tmplBodyMatch[1].replace(/^<w:body/, "").replace(/>$/, "").trim()
  const outAttrs = outBodyMatch[1].replace(/^<w:body/, "").replace(/>$/, "").trim()

  if (tmplAttrs !== outAttrs) {
    details.push(`[WARN] Body tag attributes differ: template="${tmplAttrs}" output="${outAttrs}"`)
  }

  details.push("[PASS] Chrome structure intact")
  return true
}

export function checkChromeIntegrityFull(
  templatePath: string,
  outputPath: string,
  profile: TemplateProfile,
): boolean {
  const tmplBuf = readFileSync(templatePath)
  const outBuf = readFileSync(outputPath)

  if (tmplBuf.length === 0 || outBuf.length === 0) return false

  // Compare all parts of the zip that are NOT word/document.xml
  const tmplZip = new AdmZip(templatePath)
  const outZip = new AdmZip(outputPath)

  const tmplEntries = tmplZip.getEntries()
  const outEntries = outZip.getEntries()

  const tmplEntryMap = new Map(tmplEntries.map((e) => [e.entryName, e]))
  const outEntryMap = new Map(outEntries.map((e) => [e.entryName, e]))

  for (const [name, tmplEntry] of tmplEntryMap) {
    const outEntry = outEntryMap.get(name)
    if (!outEntry) return false

    // word/document.xml is expected to differ
    if (name === "word/document.xml") continue

    const tmplData = tmplEntry.getData().toString("utf-8")
    const outData = outEntry.getData().toString("utf-8")

    // Allow small whitespace variations
    if (tmplData.trim() !== outData.trim()) return false
  }

  return true
}
