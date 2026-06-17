import { createHash } from "crypto"

const NEW_PARA_PREFIX = "AD" // v4-AD generated paragraphs prefix

export function generateSafeParaId(runId: string, index: number): string {
  const hash = createHash("sha256")
    .update(`${runId}:${index}`, "utf-8")
    .digest("hex")
  const hex = hash.substring(0, 6).toUpperCase()
  return `${NEW_PARA_PREFIX}${hex}`
}

export function isTemplateParaId(paraId: string): boolean {
  return !paraId.startsWith(NEW_PARA_PREFIX)
}

export function extractTemplateParaIds(docXml: string): Set<string> {
  const ids = new Set<string>()
  const regex = /w14:paraId="([^"]+)"|w14:paraId=([^\s>]+)/g
  let match
  while ((match = regex.exec(docXml)) !== null) {
    const id = match[1] ?? match[2]
    if (id) ids.add(id)
  }
  return ids
}

export function renderSectPrXml(sectPrXml: string, nextSectionIdx: number): string {
  // If we have multiple section properties, track and use the correct one
  return sectPrXml
}
