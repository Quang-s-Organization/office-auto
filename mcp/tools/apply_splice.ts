import { existsSync, statSync, copyFileSync } from "fs"
import AdmZip from "adm-zip"
import { readZipEntry, writeZipEntry } from "../lib/docx-xml"

export function spliceDocxBody(
  templatePath: string,
  outputPath: string,
  bodyXml: string,
): void {
  copyFileSync(templatePath, outputPath)

  const zip = new AdmZip(outputPath)
  const docXml = readZipEntry(zip, "word/document.xml")

  const bodyTagOpen = docXml.indexOf("<w:body")
  const bodyCloseIdx = docXml.lastIndexOf("</w:body>")
  if (bodyTagOpen < 0 || bodyCloseIdx < 0) {
    throw new Error("Could not find w:body in document.xml")
  }

  const prefix = docXml.substring(0, bodyTagOpen)
  const suffix = docXml.substring(bodyCloseIdx + "</w:body>".length)
  const newDocXml = prefix + bodyXml + suffix

  writeZipEntry(zip, "word/document.xml", newDocXml)
  zip.writeZip(outputPath)
}

export interface SpliceResult {
  ok: boolean
  output_path: string
  output_size: number
  error_code?: string
  message?: string
}
