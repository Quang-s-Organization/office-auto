# priors — common patterns as STARTING hypotheses (NOT rules)

> 🚩 **Status: soft priors.** Use these only to seed INDUCE so Hypothesis Search converges
> faster. **VERIFY on the actual document decides.** If the file disagrees with a prior,
> trust the file and drop the prior. A prior that fires without verification is a bug.

Priors speed up the common case; induction (`primitives.md` + `verify.md`) guarantees
correctness on the uncommon one. This is how the skill is both accurate on VN legal docs and
generic beyond them.

## Prior A — Vietnamese legal (QPPL), full hierarchy
Legal basis: Nghị định 34/2016/NĐ-CP (drafting technique). Full depth:
```
Phần → Chương → Mục → Tiểu mục → Điều → Khoản → Điểm
```
Short documents drop upper levels (often just Điều → Khoản → Điểm).

| Candidate level | scheme (IR) | delim | typical format | example |
|---|---|---|---|---|
| Phần | `upperRoman` | `none` | bold, all_caps, center | `Phần I` |
| Chương | `upperRoman` | `none` | bold, all_caps, center | `Chương I` |
| Mục | `decimal` | `none` | bold, all_caps, center | `Mục 1` |
| Tiểu mục | `decimal` | `none` | bold, center | `Tiểu mục 1` |
| Điều | `decimal` | `period` | bold, left; title same line | `Điều 1. Phạm vi` |
| Khoản | `decimal` | `period` | plain | `1.` |
| Điểm | `lowerAlpha` | `oneParen` | plain | `a)` |

Common `source`: **manual** (typed) is very frequent in real VN files — but many use Word
auto-numbering. **Always check per level** (`detect-auto-vs-manual`).

⚠️ **Điểm alphabet is Vietnamese**: `a, b, c, d, đ, e, …` (has `đ`). Not ASCII a–z. Account for
it when regenerating the sequence in VERIFY.

Typical `reset`: Điều often runs continuously across Chương (`reset: none`); Khoản resets per
Điều; Điểm resets per Khoản.

## Prior B — VN "Hướng dẫn / Công văn" (the off-Điều branch)
These usually do **not** use "Điều". Instead:
```
I, II, III (upperRoman) → 1, 2, 3 (decimal) → a, b, c (lowerAlpha)
```
If you see roman top-level headings and no "Điều", prefer this prior over Prior A.

## Prior C — document-type signals (for `detected_type`)
Strongest → weakest:
1. **Code in the doc number**: `…/TT-…`=Thông tư · `…/NĐ-CP`=Nghị định · `…/QĐ-…`=Quyết định ·
   `…/NQ-…`=Nghị quyết · `…/HD-…` or `…/CV-…`=Hướng dẫn/Công văn.
2. **All-caps type name** in the header block: "THÔNG TƯ", "NGHỊ ĐỊNH"…
3. **Issuing body**: Quốc hội→Luật/Nghị quyết; Chính phủ→Nghị định; Bộ→Thông tư.
These populate `document.detected_type` and `header_block`; they never override VERIFY.

## Prior D — generic hierarchical (non-VN)
Contracts, standards (ISO/TCVN), RFCs, textbooks: expect Article/Section/Clause or numeric
`1 / 1.1 / 1.1.1`, or `I / A / 1 / a`. No VN vocabulary applies — induce purely from signals.
`sample-01-generic-auto` is exactly this case; it must score high with **all VN priors off**
(the zero-prior test, plan [11 §6](../../../docs/11-implementation-plan.md)).

## Prior E — real-world traps (from doc 03 §6)
- typed number vs Word auto-number → set `numbering.source` correctly (double-number guard).
- style name lies: "Heading 2" might be Điều OR Chương → match the text prefix, not the name.
- transitional/《điều khoản thi hành》 articles are ordinary Điều.
- `a) b)` (formal Điểm) vs `-` bullets (informal) → only the formal ordinal is a level.
- Phụ lục / tables at the end have different structure → separate branch (P6), may be anomaly.

## How to use a prior
1. Read the signals (inventories). 2. If they resemble a prior, adopt it as **one**
hypothesis. 3. Run VERIFY. 4. Keep it only if coverage/fit support it; otherwise induce from
scratch. Report `confidence` from the verification, not from the prior's existence.
