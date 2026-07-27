# numbering — abstractNum/num recipes per scheme, delim & reset (verified)

> The single place a wrong `numbering.source` **double-numbers**. Read the spec's
> `numbering.source` per level and take the matching branch.

## §map — IR → officecli (verified on 1.0.125)
| IR `scheme` | officecli abstractnum `format` |
|---|---|
| `decimal` | `decimal` |
| `upperRoman` | `upperRoman` |
| `lowerRoman` | `lowerRoman` |
| `upperAlpha` | `upperLetter` |
| `lowerAlpha` | `lowerLetter` |

| IR `delim` | `text`/`lvlText` pattern for level N (0-based ilvl → `%<N+1>`) |
|---|---|
| `period` | `%N.`  (e.g. level0 → `%1.`) |
| `oneParen` | `%N)` |
| `twoParens` | `(%N)` |
| `none` | `%N` |

## Branch A — `source = auto` (Word renders the number)
Define ONE multi-level `abstractnum` with a per-level `format` + `text`, one `num`, then set
`numId`+`ilvl` on each paragraph. **Verified** to round-trip cleanly through pandoc.

```bash
# 3-level example: L1 upperRoman "%1", L2 decimal "%2.", L3 lowerLetter "%3)"
officecli add "$F" /numbering --type abstractnum \
  --prop level0.format=upperRoman  --prop level0.text='%1' \
  --prop level1.format=decimal     --prop level1.text='%2.' \
  --prop level2.format=lowerLetter --prop level2.text='%3)'
officecli add "$F" /numbering --type num --prop abstractNumId=0     # -> num id=1
# body paragraphs carry numId + ilvl; text is BODY ONLY (no number in text)
officecli add "$F" /body --type paragraph --prop text="Scope and definitions" --prop numId=1 --prop ilvl=0
officecli add "$F" /body --type paragraph --prop text="This document defines terms." --prop numId=1 --prop ilvl=1
officecli add "$F" /body --type paragraph --prop text="First condition." --prop numId=1 --prop ilvl=2
```
Verified readback (`officecli view text`): `I Scope…`, `  1. This…`, `    a) First…`.
Verified pandoc re-probe: nested `OrderedList` `UpperRoman`/`Decimal`+`Period`/`LowerAlpha`+
`OneParen` — matches the spec exactly.

**Reset:** a single multi-level list auto-resets each child counter under its parent
(`reset = per_parent`/parent id). If a level must run continuously across parents
(`reset = none`, e.g. VN "Điều" across "Chương"), that needs a separate `num` or a
level `lvlRestart=0` — check `help docx level`.

## Branch B — `source = manual` (ordinal is literal text)
Write the ordinal into `text=` exactly as it should appear. **Do NOT set `numId`** on these
paragraphs (that would add a second, rendered number).

```bash
officecli add "$F" /body --type paragraph --prop text="Chương I" --prop bold=true --prop align=center
officecli add "$F" /body --type paragraph --prop text="Điều 1. Phạm vi điều chỉnh" --prop bold=true
officecli add "$F" /body --type paragraph --prop text="1. Nội dung khoản một." --prop align=justify
officecli add "$F" /body --type paragraph --prop text="a) Nội dung điểm a." --prop align=justify --prop indent=720
```
You (not Word) own the sequence: emit `1., 2., …`, `a), b), …` yourself, honoring each level's
`reset`. For VN `Điểm`, use the **Vietnamese alphabet** `a,b,c,d,đ,e,…` (has `đ`).

## Mixed documents
Different levels may differ in `source` (auto khoản + manual chương is common). Decide
**per level** from the spec; never assume the whole document is one or the other.
