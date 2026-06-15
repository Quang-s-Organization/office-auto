import { describe, it, expect } from "vitest"
import {
  stripLeadingNumbering,
  canonicalHeadingKey,
  detectAmbiguity,
} from "../mcp/lib/heading-normalize"

describe("stripLeadingNumbering", () => {
  it('strips "1." prefix', () => {
    expect(stripLeadingNumbering("1. CƠ SỞ LÝ THUYẾT")).toBe("CƠ SỞ LÝ THUYẾT")
  })

  it('strips "1.2" prefix', () => {
    expect(stripLeadingNumbering("1.2 Các phương pháp sinh dữ liệu ảnh truyền thống")).toBe(
      "Các phương pháp sinh dữ liệu ảnh truyền thống",
    )
  })

  it('strips "1.2.3" multi-level numbering', () => {
    expect(stripLeadingNumbering("1.2.3 Chi tiết")).toBe("Chi tiết")
  })

  it('strips "I." Roman numeral', () => {
    expect(stripLeadingNumbering("I. Introduction")).toBe("Introduction")
  })

  it('strips "A." letter numbering', () => {
    expect(stripLeadingNumbering("A. Appendix")).toBe("Appendix")
  })

  it('strips "Chương 1:" Vietnamese prefix', () => {
    expect(stripLeadingNumbering("Chương 1: Giới thiệu")).toBe("Giới thiệu")
  })

  it("keeps text without numbering unchanged", () => {
    expect(stripLeadingNumbering("CƠ SỞ LÝ THUYẾT")).toBe("CƠ SỞ LÝ THUYẾT")
  })

  it('strips "(a)" parenthetical numbering', () => {
    expect(stripLeadingNumbering("(a) Item one")).toBe("Item one")
  })

  it("handles empty string", () => {
    expect(stripLeadingNumbering("")).toBe("")
  })

  it("handles only whitespace", () => {
    expect(stripLeadingNumbering("  ")).toBe("")
  })
})

describe("canonicalHeadingKey", () => {
  it("produces same key for numbered and unnumbered versions", () => {
    const key1 = canonicalHeadingKey("1. CƠ SỞ LÝ THUYẾT")
    const key2 = canonicalHeadingKey("CƠ SỞ LÝ THUYẾT")
    expect(key1).toBe(key2)
  })

  it("produces same key for multi-level numbered and unnumbered", () => {
    const key1 = canonicalHeadingKey("1.2 Các phương pháp sinh dữ liệu ảnh truyền thống")
    const key2 = canonicalHeadingKey("Các phương pháp sinh dữ liệu ảnh truyền thống")
    expect(key1).toBe(key2)
  })

  it("collapses multiple whitespace", () => {
    const key = canonicalHeadingKey("  Hello   World  ")
    expect(key).toBe("hello world")
  })

  it("is case-insensitive", () => {
    const key1 = canonicalHeadingKey("CƠ SỞ LÝ THUYẾT")
    const key2 = canonicalHeadingKey("cơ sở lý thuyết")
    expect(key1).toBe(key2)
  })

  it("uses Unicode NFC normalization", () => {
    const composed = "CƠ SỞ LÝ THUYẾT".normalize("NFC")
    const decomposed = "CƠ SỞ LÝ THUYẾT".normalize("NFD")
    const key1 = canonicalHeadingKey(composed)
    const key2 = canonicalHeadingKey(decomposed)
    expect(key1).toBe(key2)
  })

  it("preserves Vietnamese diacritics", () => {
    const key = canonicalHeadingKey("Cơ sở lý thuyết")
    expect(key).toBe("cơ sở lý thuyết")
  })

  it('strips "Chương" prefix', () => {
    const key1 = canonicalHeadingKey("Chương 1: Giới thiệu")
    const key2 = canonicalHeadingKey("Giới thiệu")
    expect(key1).toBe(key2)
  })
})

describe("detectAmbiguity", () => {
  it("detects no ambiguity for unique keys", () => {
    const headings = [
      { heading_id: "h_0001", canonical_key: "chapter 1" },
      { heading_id: "h_0002", canonical_key: "chapter 2" },
      { heading_id: "h_0003", canonical_key: "chapter 3" },
    ]
    const result = detectAmbiguity(headings)
    expect(result).toHaveLength(0)
  })

  it("detects duplicate canonical keys", () => {
    const headings = [
      { heading_id: "h_0001", canonical_key: "tổng quan" },
      { heading_id: "h_0002", canonical_key: "chi tiết" },
      { heading_id: "h_0003", canonical_key: "tổng quan" },
    ]
    const result = detectAmbiguity(headings)
    expect(result).toHaveLength(1)
    expect(result[0].canonical_key).toBe("tổng quan")
    expect(result[0].heading_ids).toContain("h_0001")
    expect(result[0].heading_ids).toContain("h_0003")
  })

  it("detects multiple ambiguous groups", () => {
    const headings = [
      { heading_id: "h_0001", canonical_key: "a" },
      { heading_id: "h_0002", canonical_key: "a" },
      { heading_id: "h_0003", canonical_key: "b" },
      { heading_id: "h_0004", canonical_key: "b" },
    ]
    const result = detectAmbiguity(headings)
    expect(result).toHaveLength(2)
  })

  it("handles empty array", () => {
    const result = detectAmbiguity([])
    expect(result).toHaveLength(0)
  })
})
