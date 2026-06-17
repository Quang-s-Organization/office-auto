import { describe, it, expect } from "vitest"
import { renderBodyPlan, renderBodyNode } from "../mcp/lib/ooxml/clause"
import type { BodyNode, StyleBinding } from "../mcp/schemas/field-set"

const testBindings: StyleBinding[] = [
  { role: "dieu", styleId: "DieuStyle", source: "exact_match", confidence: 1.0 },
  { role: "khoan", styleId: "KhoanStyle", source: "exact_match", confidence: 1.0 },
  { role: "diem", styleId: "DiemStyle", source: "exact_match", confidence: 1.0 },
  { role: "para", styleId: "NormalStyle", source: "exact_match", confidence: 1.0 },
  { role: "cancu", styleId: "CanCuStyle", source: "exact_match", confidence: 1.0 },
  { role: "tieude", styleId: "TieuDeStyle", source: "exact_match", confidence: 1.0 },
]

describe("ooxml/clause", () => {
  it("renders a plain paragraph", () => {
    const node: Extract<BodyNode, { type: "para" }> = {
      type: "para",
      content: [{ text: "Hello world" }],
    }
    const xml = renderBodyNode(node, testBindings, 0)
    expect(xml).toBeTruthy()
    expect(xml).toContain("NormalStyle")
    expect(xml).toContain("Hello world")
  })

  it("renders Điều with bold label", () => {
    const node: Extract<BodyNode, { type: "dieu" }> = {
      type: "dieu",
      num: 1,
      title: [{ text: " Quy định chung" }],
      children: [],
    }
    const xml = renderBodyNode(node, testBindings, 0)
    expect(xml).toBeTruthy()
    expect(xml).toContain("Điều 1.")
    expect(xml).toContain("<w:b/>")
    expect(xml).toContain("DieuStyle")
  })

  it("renders Khoản with bold number", () => {
    const node: Extract<BodyNode, { type: "khoan" }> = {
      type: "khoan",
      num: 1,
      content: [{ text: "Nội dung khoản" }],
      children: [],
    }
    const xml = renderBodyNode(node, testBindings, 0)
    expect(xml).toBeTruthy()
    expect(xml).toContain("1.")
    expect(xml).toContain("KhoanStyle")
  })

  it("renders Điểm with bold label", () => {
    const node: Extract<BodyNode, { type: "diem" }> = {
      type: "diem",
      label: "a",
      content: [{ text: "Nội dung điểm" }],
    }
    const xml = renderBodyNode(node, testBindings, 0)
    expect(xml).toBeTruthy()
    expect(xml).toContain("a)")
    expect(xml).toContain("DiemStyle")
  })

  it("renders Căn cứ in italic", () => {
    const node: Extract<BodyNode, { type: "cancu" }> = {
      type: "cancu",
      content: [{ text: "Căn cứ Luật ban hành văn bản" }],
    }
    const xml = renderBodyNode(node, testBindings, 0)
    expect(xml).toBeTruthy()
    expect(xml).toContain("<w:i/>")
    expect(xml).toContain("CanCuStyle")
  })

  it("renders page break", () => {
    const node: Extract<BodyNode, { type: "pagebreak" }> = {
      type: "pagebreak",
    }
    const xml = renderBodyNode(node, testBindings, 0)
    expect(xml).toBeTruthy()
    expect(xml).toContain('<w:br w:type="page"/>')
  })

  it("returns null for unsupported nodes", () => {
    const node: Extract<BodyNode, { type: "unsupported" }> = {
      type: "unsupported",
      reason: "test",
      raw: "test",
    }
    const xml = renderBodyNode(node, testBindings, 0)
    expect(xml).toBeNull()
  })

  it("renders a table with rows and cells", () => {
    const node: Extract<BodyNode, { type: "table" }> = {
      type: "table",
      rows: [
        [[{ text: "STT" }], [{ text: "Họ tên" }]],
        [[{ text: "1" }], [{ text: "Nguyễn Văn A" }]],
      ],
    }
    const xml = renderBodyNode(node, testBindings, 0)
    expect(xml).toBeTruthy()
    expect(xml).toContain("<w:tbl>")
    expect(xml).toContain("<w:tr>")
    expect(xml).toContain("<w:tc>")
    expect(xml).toContain("STT")
    expect(xml).toContain("Nguyễn Văn A")
  })
})
