import { describe, it, expect } from "vitest"
import { parseMarkdownToSourcePacket } from "../mcp/lib/source-parser"
import { createHash } from "crypto"

function sha256Hex(data: string): string {
  return createHash("sha256").update(data, "utf-8").digest("hex")
}

describe("source-parser", () => {
  it("parses a simple markdown with headings and paragraphs", () => {
    const md = `# Cơ sở lý thuyết

Nội dung tiếng Việt có dấu: dữ liệu, huấn luyện, kiểm chứng.

Thêm một đoạn nữa.

## Phương pháp

Mô tả phương pháp ở đây.
`
    const packet = parseMarkdownToSourcePacket(md, "test.md")
    expect(packet.schema_version).toBe("source_packet.v1")
    expect(packet.source_file).toBe("test.md")
    expect(packet.total_blocks).toBeGreaterThan(0)

    const headings = packet.blocks.filter((b) => b.type === "heading")
    expect(headings).toHaveLength(2)
    expect(headings[0].text).toBe("Cơ sở lý thuyết")
    expect(headings[0].level).toBe(1)
    expect(headings[0].normalized_key).toBe("cơ sở lý thuyết")

    const paragraphs = packet.blocks.filter((b) => b.type === "paragraph")
    expect(paragraphs.length).toBeGreaterThan(0)
  })

  it("preserves Vietnamese Unicode in text", () => {
    const md = "# Cơ sở lý thuyết\n\nNội dung tiếng Việt: dữ liệu, huấn luyện, kiểm chứng."
    const packet = parseMarkdownToSourcePacket(md, "vi.md")
    const heading = packet.blocks.find((b) => b.type === "heading")
    expect(heading?.text).toBe("Cơ sở lý thuyết")

    const para = packet.blocks.find((b) => b.type === "paragraph")
    expect(para?.text).toBe("Nội dung tiếng Việt: dữ liệu, huấn luyện, kiểm chứng.")
  })

  it("produces stable SHA256 for blocks", () => {
    const md = "# Heading\n\nBody text."
    const packet1 = parseMarkdownToSourcePacket(md, "test.md")
    const packet2 = parseMarkdownToSourcePacket(md, "test.md")

    expect(packet1.blocks[0].sha256).toBe(packet2.blocks[0].sha256)
  })

  it("parses multi-level headings", () => {
    const md = "# H1\n## H2\n### H3\n#### H4\n##### H5\n###### H6"
    const packet = parseMarkdownToSourcePacket(md, "levels.md")
    const headings = packet.blocks.filter((b) => b.type === "heading")
    expect(headings).toHaveLength(6)
    expect(headings[0].level).toBe(1)
    expect(headings[1].level).toBe(2)
    expect(headings[5].level).toBe(6)
  })

  it("handles empty markdown", () => {
    const packet = parseMarkdownToSourcePacket("", "empty.md")
    expect(packet.blocks).toHaveLength(0)
    expect(packet.total_blocks).toBe(0)
  })

  it("includes block IDs in sequential format", () => {
    const md = "# H1\n\nPara 1\n\nPara 2"
    const packet = parseMarkdownToSourcePacket(md, "test.md")
    expect(packet.blocks[0].block_id).toBe("md_0001")
    expect(packet.blocks[1].block_id).toBe("md_0002")
    expect(packet.blocks[2].block_id).toBe("md_0003")
  })

  it("has consistent source_sha256", () => {
    const md = "# Test\n\nContent here."
    const expected = sha256Hex(md)
    const packet = parseMarkdownToSourcePacket(md, "test.md")
    expect(packet.source_sha256).toBe(expected)
  })

  it("handles markdown with only whitespace lines", () => {
    const md = "# A\n\n\n\nPara\n\n\n"
    const packet = parseMarkdownToSourcePacket(md, "test.md")
    const headings = packet.blocks.filter((b) => b.type === "heading")
    expect(headings).toHaveLength(1)
    const paragraphs = packet.blocks.filter((b) => b.type === "paragraph")
    expect(paragraphs).toHaveLength(1)
  })

  it("handles code fences", () => {
    const md = "# Example\n\n```\nconst x = 1\nconsole.log(x)\n```\n\nAfter code."
    const packet = parseMarkdownToSourcePacket(md, "test.md")
    const codeBlocks = packet.blocks.filter((b) => b.type === "code")
    expect(codeBlocks).toHaveLength(1)
    expect(codeBlocks[0].text).toContain("const x = 1")
  })
})
