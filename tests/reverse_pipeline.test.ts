import { describe, it, expect } from "vitest"
import { parseStylesXml, resolveStyleMap, extractChrome, xmlEscape, buildParagraphXml, buildBodyXml, generateParaId } from "../mcp/lib/docx-xml"
import { buildRenderList } from "../mcp/tools/build_render_list"
import type { SourcePacket } from "../mcp/schemas/source-packet"
import type { StyleMap, RenderItem } from "../mcp/schemas/style-map"

// ─── xmlEscape ────────────────────────────────────────────────────────────────

describe("xmlEscape", () => {
  it("escapes &, <, >, quotes", () => {
    expect(xmlEscape("a & b < c > d \"e\" 'f'")).toBe(
      "a &amp; b &lt; c &gt; d &quot;e&quot; &apos;f&apos;",
    )
  })

  it("passes normal text through", () => {
    expect(xmlEscape("Hello World 123")).toBe("Hello World 123")
  })

  it("handles Vietnamese characters", () => {
    expect(xmlEscape("CƠ SỞ LÝ THUYẾT")).toBe("CƠ SỞ LÝ THUYẾT")
  })
})

// ─── generateParaId ──────────────────────────────────────────────────────────

describe("generateParaId", () => {
  it("generates deterministic IDs based on index", () => {
    expect(generateParaId(0)).toBe("00000001")
    expect(generateParaId(1)).toBe("00000002")
    expect(generateParaId(255)).toBe("00000100")
  })
})

// ─── parseStylesXml + resolveStyleMap ─────────────────────────────────────────

describe("parseStylesXml", () => {
  it("extracts styleId and name from styles.xml", () => {
    const xml = `<?xml version="1.0"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
  <w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/></w:style>
  <w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/></w:style>
  <w:style w:type="paragraph" w:styleId="Heading3"><w:name w:val="heading 3"/></w:style>
  <w:style w:type="paragraph" w:styleId="Bngbiu-title"><w:name w:val="Bảng biểu - title"/></w:style>
</w:styles>`

    const styles = parseStylesXml(xml)
    expect(styles).toHaveLength(5)
    expect(styles.find((s) => s.styleId === "Normal")?.name).toBe("Normal")
    expect(styles.find((s) => s.styleId === "Heading1")?.name).toBe("heading 1")
  })
})

describe("resolveStyleMap", () => {
  const basicStyles = [
    { styleId: "Normal", name: "Normal", type: "paragraph" },
    { styleId: "Heading1", name: "heading 1", type: "paragraph" },
    { styleId: "Heading2", name: "heading 2", type: "paragraph" },
    { styleId: "Heading3", name: "heading 3", type: "paragraph" },
    { styleId: "Bngbiu-title", name: "Bảng biểu - title", type: "paragraph" },
    { styleId: "Bibliography", name: "Bibliography", type: "paragraph" },
    { styleId: "TOC1", name: "toc 1", type: "paragraph" },
  ]

  it("resolves heading styles", () => {
    const map = resolveStyleMap(basicStyles)
    expect(map.roles["heading 1"]).toBe("Heading1")
    expect(map.roles["heading 2"]).toBe("Heading2")
    expect(map.roles["heading 3"]).toBe("Heading3")
  })

  it("resolves Normal style", () => {
    const map = resolveStyleMap(basicStyles)
    expect(map.roles["Normal"]).toBe("Normal")
  })

  it("resolves caption style", () => {
    const map = resolveStyleMap(basicStyles)
    expect(map.roles["caption"]).toBe("Bngbiu-title")
  })

  it("resolves bibliography style", () => {
    const map = resolveStyleMap(basicStyles)
    expect(map.roles["bibliography"]).toBe("Bibliography")
  })

  it("resolves TOC style", () => {
    const map = resolveStyleMap(basicStyles)
    expect(map.roles["TOC"]).toBe("TOC1")
  })

  it("falls back to Noidung for Normal when Normal is absent", () => {
    const styles = basicStyles.filter((s) => s.styleId !== "Normal").concat([
      { styleId: "Noidung", name: "Noi dung", type: "paragraph" },
    ])
    const map = resolveStyleMap(styles)
    expect(map.roles["Normal"]).toBe("Noidung")
  })
})

// ─── extractChrome ────────────────────────────────────────────────────────────

describe("extractChrome", () => {
  it("extracts front matter and sectPr from document.xml body", () => {
    const docXml = `<?xml version="1.0"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p w14:paraId="F0000001"><w:pPr><w:pStyle w:val="TOC1"/></w:pPr><w:r><w:t>TOC entry</w:t></w:r></w:p>
    <w:p w14:paraId="F0000002"><w:pPr><w:pStyle w:val="Phan"/></w:pPr><w:r><w:t>Heading 1</w:t></w:r></w:p>
    <w:p w14:paraId="F0000003"><w:pPr><w:pStyle w:val="Normal"/></w:pPr><w:r><w:t>Body text</w:t></w:r></w:p>
    <w:sectPr w:rsidR="00ABCDEF"><w:pgSz w:w="11906" w:h="16838"/></w:sectPr>
  </w:body>
</w:document>`

    const chrome = extractChrome(docXml)
    expect(chrome.front_matter_xml).toContain("TOC1")
    expect(chrome.front_matter_xml).toContain("F0000001")
    expect(chrome.front_matter_xml).not.toContain("Phan")
    expect(chrome.front_matter_xml).not.toContain("Body text")
    expect(chrome.sect_pr_xml).toContain("w:sectPr")
    expect(chrome.sect_pr_xml).toContain("pgSz")
  })

  it("returns empty front_matter when no heading found", () => {
    const docXml = `<?xml version="1.0"?>
<w:document>
  <w:body>
    <w:p><w:r><w:t>Just a paragraph</w:t></w:r></w:p>
    <w:sectPr/>
  </w:body>
</w:document>`
    const chrome = extractChrome(docXml)
    expect(chrome.front_matter_xml).toBe("")
  })
})

// ─── buildParagraphXml ────────────────────────────────────────────────────────

describe("buildParagraphXml", () => {
  const styleMap: StyleMap = {
    schema_version: "style_map.v1",
    template_path: "",
    inspected_at: "",
    roles: {
      "heading 1": "Heading1",
      "heading 2": "Heading2",
      "heading 3": "Heading3",
      "heading 4": "Heading4",
      "heading 5": "Heading5",
      "heading 6": "Heading6",
      "Normal": "Normal",
      "caption": "Bngbiu-title",
      "bibliography": "Bibliography",
      "TOC": "TOC1",
    },
    all_style_ids: ["Normal", "Heading1", "Heading2"],
  }

  it("builds a heading paragraph", () => {
    const item: RenderItem = {
      text: "CƠ SỞ LÝ THUYẾT",
      styleId: "Heading1",
      role: "heading 1",
      level: 1,
      source_block_id: "md_0001",
    }
    const xml = buildParagraphXml(item, 0)
    expect(xml).toContain('<w:p w14:paraId="00000001"')
    expect(xml).toContain('<w:pStyle w:val="Heading1"')
    expect(xml).toContain("CƠ SỞ LÝ THUYẾT")
    expect(xml).toContain('xml:space="preserve"')
  })

  it("builds a body text paragraph with style", () => {
    const item: RenderItem = {
      text: "Nội dung văn bản.",
      styleId: "Normal",
      role: "Normal",
      source_block_id: "md_0005",
    }
    const xml = buildParagraphXml(item, 42)
    expect(xml).toContain('<w:p w14:paraId="0000002B"')
    expect(xml).toContain('<w:pStyle w:val="Normal"')
    expect(xml).toContain("Nội dung văn bản.")
  })

  it("escapes special XML characters", () => {
    const item: RenderItem = {
      text: 'a < b & c > d "e"',
      styleId: "Normal",
      role: "Normal",
      source_block_id: "md_0099",
    }
    const xml = buildParagraphXml(item, 0)
    expect(xml).toContain("a &lt; b &amp; c &gt; d &quot;e&quot;")
  })
})

// ─── buildBodyXml ─────────────────────────────────────────────────────────────

describe("buildBodyXml", () => {
  const F = '<w:p w14:paraId="F0000100"><w:pPr><w:pStyle w:val="TOC1"/></w:pPr><w:r><w:t>TOC</w:t></w:r></w:p>'
  const S = '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/></w:sectPr>'

  it("wraps front matter + paragraphs + sectPr in w:body", () => {
    const items: RenderItem[] = [
      { text: "H1", styleId: "Heading1", role: "heading 1", level: 1, source_block_id: "md_0001" },
      { text: "Body", styleId: "Normal", role: "Normal", source_block_id: "md_0002" },
    ]
    const xml = buildBodyXml(F, items, S, "")
    expect(xml).toMatch(/^<w:body>/)
    expect(xml).toMatch(/<\/w:body>$/)
    expect(xml).toContain("TOC")
    expect(xml).toContain("H1")
    expect(xml).toContain("Body")
    expect(xml).toContain("<w:sectPr>")
    expect(xml).toContain("<w:pgSz")
  })

  it("preserves body attributes", () => {
    const xml = buildBodyXml("", [], S, 'xmlns:w="http://example.com"')
    expect(xml).toContain('<w:body xmlns:w="http://example.com">')
  })

  it("last child of w:body is exactly sectPr", () => {
    const items: RenderItem[] = [
      { text: "H1", styleId: "Heading1", role: "heading 1", level: 1, source_block_id: "md_0001" },
    ]
    const xml = buildBodyXml("", items, S, "")
    const lastClosePara = xml.lastIndexOf("</w:p>")
    const sectPrStart = xml.indexOf("<w:sectPr>")
    expect(sectPrStart).toBeGreaterThan(lastClosePara)
  })

  it("all paraIds are unique", () => {
    const items: RenderItem[] = Array.from({ length: 10 }, (_, i) => ({
      text: `Para ${i}`,
      styleId: "Normal",
      role: "Normal" as const,
      source_block_id: `md_${String(i + 1).padStart(4, "0")}`,
    }))
    const xml = buildBodyXml("", items, S, "")
    const paraIds = xml.match(/w14:paraId="(\w+)"/g) ?? []
    const ids = paraIds.map((p) => p.match(/"(\w+)"/)![1])
    expect(new Set(ids).size).toBe(ids.length)
  })
})

// ─── buildRenderList ──────────────────────────────────────────────────────────

describe("buildRenderList", () => {
  const styleMap: StyleMap = {
    schema_version: "style_map.v1",
    template_path: "",
    inspected_at: "",
    roles: {
      "heading 1": "Heading1",
      "heading 2": "Heading2",
      "heading 3": "Heading3",
      "heading 4": "Heading4",
      "heading 5": "Heading5",
      "heading 6": "Heading6",
      "Normal": "Normal",
      "caption": "Caption",
      "bibliography": "Bibliography",
      "TOC": "TOC1",
    },
    all_style_ids: ["Normal", "Heading1", "Heading2", "Heading3", "Caption", "Bibliography"],
  }

  function makePacket(blocks: SourcePacket["blocks"]): SourcePacket {
    return {
      schema_version: "source_packet.v1",
      source_file: "test.md",
      created_at: "",
      blocks,
      total_blocks: blocks.length,
      source_sha256: "test",
    }
  }

  it("maps heading blocks to heading style roles", () => {
    const packet = makePacket([
      { block_id: "md_0001", type: "heading", level: 1, text: "Chương 1", sha256: "", byte_offset: 0, byte_length: 10 },
      { block_id: "md_0002", type: "heading", level: 2, text: "Mục 1.1", sha256: "", byte_offset: 10, byte_length: 8 },
      { block_id: "md_0003", type: "heading", level: 3, text: "Mục 1.1.1", sha256: "", byte_offset: 18, byte_length: 10 },
    ])
    const list = buildRenderList(packet, styleMap)
    expect(list.items).toHaveLength(3)
    expect(list.items[0].role).toBe("heading 1")
    expect(list.items[0].styleId).toBe("Heading1")
    expect(list.items[1].role).toBe("heading 2")
    expect(list.items[2].role).toBe("heading 3")
  })

  it("maps paragraph blocks to Normal", () => {
    const packet = makePacket([
      { block_id: "md_0001", type: "heading", level: 1, text: "H1", sha256: "", byte_offset: 0, byte_length: 3 },
      { block_id: "md_0002", type: "paragraph", text: "Body text here.", sha256: "", byte_offset: 3, byte_length: 15 },
    ])
    const list = buildRenderList(packet, styleMap)
    expect(list.items[1].role).toBe("Normal")
    expect(list.items[1].styleId).toBe("Normal")
  })

  it("detects caption lines", () => {
    const packet = makePacket([
      { block_id: "md_0001", type: "paragraph", text: "[Hình 1.1. Sơ đồ kiến trúc]", sha256: "", byte_offset: 0, byte_length: 30 },
      { block_id: "md_0002", type: "paragraph", text: "[Bảng 2.1. Thống kê dữ liệu]", sha256: "", byte_offset: 30, byte_length: 30 },
      { block_id: "md_0003", type: "paragraph", text: "[Hình 3.1. Mô hình CNN]", sha256: "", byte_offset: 60, byte_length: 26 },
    ])
    const list = buildRenderList(packet, styleMap)
    expect(list.items[0].role).toBe("caption")
    expect(list.items[1].role).toBe("caption")
    expect(list.items[2].role).toBe("caption")
  })

  it("detects reference blocks", () => {
    const packet = makePacket([
      { block_id: "md_0001", type: "heading", level: 1, text: "TÀI LIỆU THAM KHẢO", sha256: "", byte_offset: 0, byte_length: 20 },
      { block_id: "md_0002", type: "paragraph", text: "[1] Author (2020).", sha256: "", byte_offset: 20, byte_length: 18 },
    ])
    const list = buildRenderList(packet, styleMap)
    expect(list.items[1].role).toBe("bibliography")
  })

  it("clamps heading level to 6", () => {
    const packet = makePacket([
      { block_id: "md_0001", type: "heading", level: 7, text: "Deep", sha256: "", byte_offset: 0, byte_length: 5 },
    ])
    const list = buildRenderList(packet, styleMap)
    expect(list.items[0].role).toBe("heading 6")
  })

  it("covers 100% of source blocks", () => {
    const blocks: SourcePacket["blocks"] = [
      { block_id: "md_0001", type: "heading", level: 1, text: "H1", sha256: "", byte_offset: 0, byte_length: 3 },
      { block_id: "md_0002", type: "paragraph", text: "P1", sha256: "", byte_offset: 3, byte_length: 3 },
      { block_id: "md_0003", type: "heading", level: 2, text: "H2", sha256: "", byte_offset: 6, byte_length: 3 },
      { block_id: "md_0004", type: "paragraph", text: "P2", sha256: "", byte_offset: 9, byte_length: 3 },
      { block_id: "md_0005", type: "code", text: "console.log(1)", sha256: "", byte_offset: 12, byte_length: 14 },
      { block_id: "md_0006", type: "heading", level: 1, text: "TÀI LIỆU THAM KHẢO", sha256: "", byte_offset: 26, byte_length: 20 },
      { block_id: "md_0007", type: "paragraph", text: "[1] Ref", sha256: "", byte_offset: 46, byte_length: 8 },
      { block_id: "md_0008", type: "paragraph", text: "[Hình 1. Test]", sha256: "", byte_offset: 54, byte_length: 14 },
    ]
    const packet = makePacket(blocks)
    const list = buildRenderList(packet, styleMap)
    expect(list.total_items).toBe(packet.total_blocks)
  })
})
