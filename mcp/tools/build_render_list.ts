import type { SourcePacket } from "../schemas/source-packet"
import type { StyleMap, RenderItem, RenderList, StyleRole } from "../schemas/style-map"

const CAPTION_PATTERN = /^\[(?:Hình|Bảng|Hình)\s+\d/

function isCaptionLine(text: string): boolean {
  return CAPTION_PATTERN.test(text.trim())
}

function isReferenceBlock(text: string, allBlocks: SourcePacket["blocks"], currentIdx: number): boolean {
  const trimmed = text.trim()
  if (/^#+\s*(?:TÀI\s+LIỆU\s+THAM\s+KHẢO|REFERENCES|BIBLIOGRAPHY)/i.test(trimmed)) return true

  const prevBlock = currentIdx > 0 ? allBlocks[currentIdx - 1] : null
  if (prevBlock && prevBlock.type === "heading") {
    const prevText = prevBlock.text.trim().toLowerCase()
    if (/tài\s*liệu\s*tham\s*khảo|references|bibliography/i.test(prevText)) {
      return true
    }
  }
  return false
}

function roleForSourceBlock(
  block: SourcePacket["blocks"][number],
  allBlocks: SourcePacket["blocks"],
  idx: number,
  styleMap: StyleMap,
): StyleRole | null {
  if (block.type === "heading") {
    const level = block.level ?? 1
    const clamped = Math.min(level, 6)
    return `heading ${clamped}` as StyleRole
  }

  const text = block.text.trim()

  if (isCaptionLine(text)) {
    return "caption"
  }

  if (isReferenceBlock(text, allBlocks, idx)) {
    return "bibliography"
  }

  return "Normal"
}

export function buildRenderList(
  sourcePacket: SourcePacket,
  styleMap: StyleMap,
): RenderList {
  const items: RenderItem[] = []

  for (let i = 0; i < sourcePacket.blocks.length; i++) {
    const block = sourcePacket.blocks[i]
    const role = roleForSourceBlock(block, sourcePacket.blocks, i, styleMap)
    if (!role) continue

    const styleId = styleMap.roles[role]
    if (!styleId) continue

    items.push({
      text: block.text,
      styleId,
      role,
      level: block.level,
      source_block_id: block.block_id,
    })
  }

  return {
    schema_version: "render_list.v1",
    source_file: sourcePacket.source_file,
    created_at: new Date().toISOString(),
    items,
    total_items: items.length,
  }
}
