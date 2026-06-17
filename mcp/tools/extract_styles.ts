import AdmZip from "adm-zip"
import { readZipEntry, parseStylesXml, resolveStyleMap, extractChrome } from "../lib/docx-xml"
import type { StyleMap, Chrome } from "../schemas/style-map"

export function extractStyleMap(templatePath: string): StyleMap {
  const zip = new AdmZip(templatePath)
  const stylesXml = readZipEntry(zip, "word/styles.xml")
  const styles = parseStylesXml(stylesXml)
  const styleMap = resolveStyleMap(styles)
  styleMap.template_path = templatePath
  return styleMap
}

export function extractChromeFromTemplate(templatePath: string): Chrome {
  const zip = new AdmZip(templatePath)
  const docXml = readZipEntry(zip, "word/document.xml")
  return extractChrome(docXml)
}
