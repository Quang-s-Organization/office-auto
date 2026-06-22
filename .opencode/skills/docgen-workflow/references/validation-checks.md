# Validation Checks (S1-S8)

Run these AFTER content insertion and `officecli refresh`.

## CHECK-S1 — Heading Order
Query document outline. Verify chapters appear in the expected order from `manifests/<id>.struct-spec.json`.
```
officecli view <file> outline
```
If order is wrong → FAIL with specific location.

## CHECK-S2 — Chapter Count
Count H1 headings. Expected count = N from struct-spec.json invariants.
If count != N → FAIL. "Missing chapters detected."

## CHECK-S3 — No Duplicate Headings
Heading text must be unique. If same text appears twice → FAIL.

## CHECK-S4 — Caption Safety
No paragraph starting with "[Hình" or "[Bảng" should have Heading style.
Violation → FAIL.

## CHECK-S5 — Content Length
Each body field must have ≥ 50 words. If < 50 → WARN.

## CHECK-S6 — No Leftover Placeholders
`W_LEFTOVER` from `officecli validate` must be 0.

## CHECK-S7 — PRESERVE Section Integrity
Verify PRESERVE sections were not modified (per struct-spec.json):
- TOC field codes still exist
- Headers/footers unchanged
- Cover page content intact
Violation → FAIL.

## CHECK-S8 — Content Presence (NEW)
For sections inserted via Strategy B (paragraph insert):
1. `officecli query <file> "p[style=Normal]" --json`
2. Verify paragraphs exist after the anchor heading
3. Count total words → should be close to source section word count
If no paragraphs found after anchor → FAIL.
If word count < 50% of source → WARN.
