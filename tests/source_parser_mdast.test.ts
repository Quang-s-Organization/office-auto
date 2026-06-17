import { describe, it, expect } from "vitest"
import { parseMdToBodyPlan } from "../mcp/lib/source-parser-mdast"
import type { BodyNode } from "../mcp/schemas/field-set"

describe("parseMdToBodyPlan", () => {
  it("parses a heading-level-1 as centered paragraph (title)", () => {
    const plan = parseMdToBodyPlan("# QUYẾT ĐỊNH")
    expect(plan.schema_version).toBe("body_plan.v1")
    expect(plan.nodes.length).toBeGreaterThan(0)
    const title = plan.nodes[0]
    expect(title.type).toBe("para")
    if (title.type === "para") {
      expect(title.align).toBe("center")
    }
  })

  it("parses Điều with heading level 2", () => {
    const plan = parseMdToBodyPlan("## Điều 1. Quy định chung\n\nNội dung điều 1")
    expect(plan.nodes.length).toBe(1)
    const dieu = plan.nodes[0]
    expect(dieu.type).toBe("dieu")
    if (dieu.type === "dieu") {
      expect(dieu.num).toBe(1)
      expect(dieu.children.length).toBe(1)
    }
  })

  it("parses khoản as numbered paragraphs under điều", () => {
    const plan = parseMdToBodyPlan("## Điều 1. Quy định\n\n1. Khoản thứ nhất\n\n2. Khoản thứ hai")
    expect(plan.nodes.length).toBe(1)
    const dieu = plan.nodes[0]
    expect(dieu.type).toBe("dieu")
    if (dieu.type === "dieu") {
      expect(dieu.children.length).toBe(2)
      expect(dieu.children[0].type).toBe("khoan")
      expect(dieu.children[1].type).toBe("khoan")
    }
  })

  it("parses điểm under khoản", () => {
    const plan = parseMdToBodyPlan("## Điều 1.\n\n1. Khoản thứ nhất\n\na) Điểm a\nb) Điểm b")
    expect(plan.nodes.length).toBe(1)
    const dieu = plan.nodes[0]
    if (dieu.type === "dieu") {
      expect(dieu.children.length).toBe(1)
      const khoan = dieu.children[0]
      expect(khoan.type).toBe("khoan")
      if (khoan.type === "khoan") {
        expect(khoan.children.length).toBe(2)
        expect(khoan.children[0].type).toBe("diem")
        expect(khoan.children[1].type).toBe("diem")
      }
    }
  })

  it("parses căn cứ lines as cancu type", () => {
    const plan = parseMdToBodyPlan("Căn cứ Luật Tổ chức chính quyền địa phương;")
    const cancu = plan.nodes[0]
    expect(cancu.type).toBe("cancu")
  })

  it("parses bold inline formatting", () => {
    const plan = parseMdToBodyPlan("**QUYẾT ĐỊNH:** về việc")
    expect(plan.nodes.length).toBeGreaterThan(0)
    const para = plan.nodes[0]
    if (para.type === "para") {
      const hasBold = para.content.some((r: { bold?: boolean }) => r.bold === true)
      expect(hasBold).toBe(true)
    }
  })

  it("parses italic inline formatting", () => {
    const plan = parseMdToBodyPlan("*Căn cứ Luật ban hành văn bản*")
    expect(plan.nodes.length).toBeGreaterThan(0)
    const node = plan.nodes[0]
    if ("content" in node) {
      const content = node.content as any[]
      const hasItalic = content.some((r) => r.italic === true)
      expect(hasItalic).toBe(true)
    }
  })

  it("handles multiple điều in sequence", () => {
    const plan = parseMdToBodyPlan("## Điều 1.\n\nNội dung điều 1\n\n## Điều 2.\n\nNội dung điều 2")
    expect(plan.nodes.length).toBe(2)
    expect(plan.nodes[0].type).toBe("dieu")
    expect(plan.nodes[1].type).toBe("dieu")
  })

  it("handles standalone khoản without điều", () => {
    const plan = parseMdToBodyPlan("1. Khoản độc lập\n\n2. Khoản tiếp theo")
    expect(plan.nodes.length).toBe(2)
    expect(plan.nodes[0].type).toBe("khoan")
    expect(plan.nodes[1].type).toBe("khoan")
  })
})
