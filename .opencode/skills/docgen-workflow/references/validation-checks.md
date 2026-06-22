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
