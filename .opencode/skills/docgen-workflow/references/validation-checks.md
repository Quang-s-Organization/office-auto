# Validation Checks (S1-S7)

Run these AFTER content insertion and `officecli refresh`.

## CHECK-S1 — Heading Order
Query document outline. Verify chapters appear in the expected order from `content.ir.json`.
```
officecli view <file> outline
```
If order is wrong → FAIL with specific location.

## CHECK-S2 — Chapter Count
Count H1 headings. Expected count = section count from `content.ir.json`.
If count != N → FAIL. "Missing chapters detected."

## CHECK-S3 — No Duplicate Headings
Heading text must be unique. If same text appears twice → FAIL.

## CHECK-S4 — Caption Safety
No paragraph starting with "[Hình" or "[Bảng" should have Heading style.
Violation → FAIL.

## CHECK-S5 — Content Length
Each body paragraph must have ≥ 50 words. If < 50 → WARN.

## CHECK-S6 — Clone Positioning (NEW)
Verify cloned paragraphs appear in correct order relative to their headings:
1. `officecli query <file> "p[style=Normal]" --json`
2. Check each Normal paragraph's position relative to surrounding headings
3. If any body paragraph appears BEFORE its section heading → FAIL

## CHECK-S7 — PRESERVE Section Integrity
Verify PRESERVE sections were not modified:
- Query template via `officecli query <file> sdt` — TOC field codes must still exist
- Headers/footers unchanged (verify via visual inspection or metadata check)
- Cover page content intact
- Reference: use `officecli view <file> outline` to check first heading position
  (anything before the first H1 is preserved front matter — must not be modified)
Violation → FAIL.

---

## CHECK-S8 — Outline Hierarchy Integrity (NEW — prevents issue #2)

Verify every heading has the correct OOXML `outlineLevel` matching its heading style:

```bash
officecli query <file> "p[style=Heading1]" --props style,outlineLevel,text
officecli query <file> "p[style=Heading2]" --props style,outlineLevel,text  
officecli query <file> "p[style=Heading3]" --props style,outlineLevel,text
```

**Pass criteria:**
- All Heading1 paragraphs have `outlineLevel=1` or empty (empty = default outline level)
- All Heading2 paragraphs have `outlineLevel=2`
- All Heading3 paragraphs have `outlineLevel=3`
- Any heading with missing/incorrect `outlineLevel` → WARN

**Edge case:** If `outlineLevel` prop doesn't exist in officecli output, the heading might still work
correctly in Word through its style definition. Only flag as FAIL if headings visually appear
at wrong hierarchy level in `officecli view outline`.

## CHECK-S9 — Font/Style Consistency (NEW — prevents issues #4, #5)

Verify all headings of the same style have consistent formatting:

```bash
# Compare ALL Heading1 font sizes
officecli query <file> "p[style=Heading1]" --json --props effective.size,effective.font.ascii,text,style
```

**Pass criteria:**
- All inserted Heading1 paragraphs must have the same font size (±1pt) as the template's CHAPTER heading
- All inserted Heading2 paragraphs must have the same font size as the template reference
- Font face must be consistent across all same-style paragraphs
- Exception: ACKNOWLEDGEMENTS may differ from CHAPTER — that's OK

**Fail condition:** If inserted content has 24pt but CHAPTER headings use 16pt → FAIL.

## CHECK-S10 — First-Line Indent (NEW — prevents issue #3)

Verify body paragraphs have proper first-line indent:

```bash
officecli query <file> "p[style=Normal and text!='']" --json --props ind.firstLine,text,paraId
```

**Pass criteria:**
- All body paragraphs (Normal style) that contain content (non-empty) should have `ind.firstLine` set
- Acceptable values: `1.27cm`, `2ch`, `720` (twips ≈ 1.27cm)
- Body paragraphs WITHOUT first-line indent → WARN

**Fail condition:** If >50% of body paragraphs lack `ind.firstLine` → FAIL (document is not ready for delivery).

---
