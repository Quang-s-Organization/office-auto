import AdmZip from "adm-zip"
import { readZipEntry } from "../lib/docx-xml"
import type { TemplateProfile, FieldSet } from "../schemas/field-set"

export interface ValidationResult {
  valid: boolean
  errors: string[]
  warnings: string[]
}

export function validateDocxXml(outputPath: string): ValidationResult {
  const errors: string[] = []
  const warnings: string[] = []

  try {
    const zip = new AdmZip(outputPath)
    const docXml = readZipEntry(zip, "word/document.xml")

    if (!docXml || docXml.trim().length === 0) {
      errors.push("word/document.xml is empty")
      return { valid: false, errors, warnings }
    }

    // XML well-formedness check (basic bracket balance)
    if (!isBalancedXml(docXml)) {
      errors.push("word/document.xml has unbalanced XML tags")
    }

    // Check for w:body
    if (!docXml.includes("<w:body") || !docXml.includes("</w:body>")) {
      errors.push("word/document.xml missing w:body tags")
    }

    // Check for leftover tokens {{...}}
    const leftoverTokens = docXml.match(/\{\{[a-z_][a-z0-9_]*\}\}/g)
    if (leftoverTokens) {
      errors.push(`Leftover tokens found: ${leftoverTokens.join(", ")}`)
    }

    // ParaId uniqueness check
    const paraIds = new Set<string>()
    const paraIdRegex = /w14:paraId="([^"]+)"/g
    let paraIdMatch
    const duplicates = new Set<string>()
    while ((paraIdMatch = paraIdRegex.exec(docXml)) !== null) {
      if (paraIds.has(paraIdMatch[1])) {
        duplicates.add(paraIdMatch[1])
      }
      paraIds.add(paraIdMatch[1])
    }
    if (duplicates.size > 0) {
      errors.push(`Duplicate paraIds found: ${[...duplicates].join(", ")}`)
    }

    // Check all content controls are filled (no empty sdtContent with tokens)
    const sdtRegex = /<w:sdtContent[^>]*>([\s\S]*?)<\/w:sdtContent>/g
    let sdtMatch
    while ((sdtMatch = sdtRegex.exec(docXml)) !== null) {
      const content = sdtMatch[1]
      const hasText = /<w:t[^>]*>[\s\S]*?<\/w:t>/.test(content) && content.replace(/\s/g, "").length > 0
      if (!hasText) {
        warnings.push(`Content control has empty content`)
      }
    }
  } catch (err: any) {
    errors.push(`Failed to validate document: ${err.message}`)
  }

  return {
    valid: errors.length === 0,
    errors,
    warnings,
  }
}

function isBalancedXml(xml: string): boolean {
  const tagStack: string[] = []
  const tagRegex = /<\/?([\w:]+)[^>]*\/?>|<\?[\s\S]*?\?>|<!--[\s\S]*?-->/g
  let match

  while ((match = tagRegex.exec(xml)) !== null) {
    const full = match[0]

    // Self-closing
    if (full.endsWith("/>")) continue
    // Processing instruction
    if (full.startsWith("<?")) continue
    // Comment
    if (full.startsWith("<!--")) continue

    const tagName = match[1]
    if (full.startsWith("</")) {
      // Closing tag
      if (tagStack.length === 0 || tagStack[tagStack.length - 1] !== tagName) {
        return false
      }
      tagStack.pop()
    } else {
      tagStack.push(tagName)
    }
  }

  return tagStack.length === 0
}

export function validateFieldSetCompleteness(
  fieldSet: FieldSet,
  requiredTags: string[],
): ValidationResult {
  const errors: string[] = []
  const warnings: string[] = []

  for (const tag of requiredTags) {
    if (!(tag in fieldSet)) {
      errors.push(`Required field "${tag}" is missing`)
    }
  }

  return {
    valid: errors.length === 0,
    errors,
    warnings,
  }
}
