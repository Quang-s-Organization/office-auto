import { createHash } from "crypto"
import type { SourcePacket, SourceBlock } from "../schemas/source-packet"

function sha256Hex(data: string): string {
  return createHash("sha256").update(data, "utf-8").digest("hex")
}

export function parseMarkdownToSourcePacket(
  contentMd: string,
  sourceFile: string,
): SourcePacket {
  const blocks: SourceBlock[] = []
  const lines = contentMd.split("\n")
  let byteOffset = 0
  let blockId = 0

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    const hMatch = line.match(/^(#{1,6})\s+(.+)/)

    if (hMatch) {
      const level = hMatch[1].length
      const text = hMatch[2].trim()

      blockId++
      const block: SourceBlock = {
        block_id: `md_${String(blockId).padStart(4, "0")}`,
        type: "heading",
        level,
        text,
        normalized_key: text
          .normalize("NFC")
          .replace(/\s+/g, " ")
          .trim()
          .toLowerCase(),
        sha256: sha256Hex(text),
        byte_offset: byteOffset,
        byte_length: Buffer.byteLength(text, "utf-8"),
      }
      blocks.push(block)
      byteOffset += Buffer.byteLength(line, "utf-8") + 1 // +1 for \n
      continue
    }

    // Non-heading: collect consecutive non-empty lines into a paragraph block
    const trimmed = line.trim()
    byteOffset += Buffer.byteLength(line, "utf-8") + 1

    if (!trimmed) continue

    // Check for code fences
    if (trimmed.startsWith("```")) {
      blockId++
      const codeLines: string[] = []
      i++
      while (i < lines.length && !lines[i].trim().startsWith("```")) {
        codeLines.push(lines[i])
        byteOffset += Buffer.byteLength(lines[i], "utf-8") + 1
        i++
      }
      byteOffset += Buffer.byteLength(lines[i] ?? "", "utf-8") + 1

      const codeText = codeLines.join("\n")
      blocks.push({
        block_id: `md_${String(blockId).padStart(4, "0")}`,
        type: "code",
        text: codeText,
        sha256: sha256Hex(codeText),
        byte_offset: byteOffset - Buffer.byteLength(codeText, "utf-8") - 2,
        byte_length: Buffer.byteLength(codeText, "utf-8"),
      })
      continue
    }

    // Merge consecutive non-heading, non-code lines into one paragraph
    const paraLines: string[] = [trimmed]
    const paraStartOffset = byteOffset - Buffer.byteLength(line, "utf-8") - 1
    let paraByteLen = Buffer.byteLength(line, "utf-8")

    i++
    while (i < lines.length) {
      const nextLine = lines[i]
      const nextTrimmed = nextLine.trim()
      if (!nextTrimmed) break
      if (nextLine.match(/^(#{1,6})\s+/)) break
      if (nextTrimmed.startsWith("```")) break
      paraLines.push(nextLine)
      paraByteLen += Buffer.byteLength(nextLine, "utf-8") + 1
      byteOffset += Buffer.byteLength(nextLine, "utf-8") + 1
      i++
    }
    i--

    blockId++
    const paraText = paraLines.join("\n")
    blocks.push({
      block_id: `md_${String(blockId).padStart(4, "0")}`,
      type: "paragraph",
      text: paraText,
      sha256: sha256Hex(paraText),
      byte_offset: paraStartOffset,
      byte_length: paraByteLen,
    })
  }

  const sourceSha256 = sha256Hex(contentMd)

  return {
    schema_version: "source_packet.v1",
    source_file: sourceFile,
    created_at: new Date().toISOString(),
    blocks,
    total_blocks: blocks.length,
    source_sha256: sourceSha256,
  }
}
