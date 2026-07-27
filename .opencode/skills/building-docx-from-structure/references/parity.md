# parity — round-trip diff, scoring, and what pandoc can actually read back

> Round-trip parity is the evaluator-optimizer across both skills and the system's "it's
> alive" signal: build → re-probe → diff on FORMAT only → fix → repeat.

```
IR_in ──build──► output.docx ──(officecli save!)──► inducing-doc-structure.PROBE ──► IR_out
        diff(IR_in, IR_out) on FORMAT fields  →  parity score  (threshold D3)
```
⚠️ `officecli save "$OUT"` **before** pandoc reads it, or pandoc reads empty (flush trap).

## What round-trips through pandoc — and what does NOT (verified 3.8)
Parity is only honest if it scores fields the re-probe can actually observe. Verified:

| Field | Round-trips via pandoc? | How to verify |
|---|---|---|
| `numbering.scheme` (auto) | ✅ yes — `OrderedList` `ListNumberStyle` | pandoc re-probe |
| `numbering.delim` (auto) | ✅ yes — `ListNumberDelim` | pandoc re-probe |
| `numbering.source` | ✅ yes — auto→`OrderedList`, manual→ordinal in text | pandoc re-probe |
| level / nesting | ✅ yes — list depth or Header level | pandoc re-probe |
| `format.bold` | ✅ yes — `Strong` | pandoc re-probe |
| `format.all_caps` | ⚠️ only if written as **literal uppercase text** (not a `w:caps` prop) | pandoc re-probe (text is upper) |
| `format.align` | ❌ **no** — pandoc drops paragraph alignment | **officecli** `get`/`view annotated` |
| `format.indent` | ❌ **no** — pandoc turns left-indent into `BlockQuote`, not a twips value | **officecli** `get` |

**Consequence (honest design):**
- Score `scheme, delim, source, level, bold, all_caps` via the **pandoc re-probe** — this is
  the D3 parity score.
- Verify `align, indent` via **officecli readback** (`officecli get "$OUT" "/body/p[N]"` or
  `view annotated`) against the spec — they are build-time asserted, not pandoc-observable.
  Do NOT let unreadable-by-pandoc fields fail the pandoc parity score; report them separately.

## Diff procedure
1. `officecli save "$OUT"`.
2. Run `inducing-doc-structure` on `$OUT` → `IR_out` (structure-spec.json).
3. Align `IR_out.levels[]` to `IR_in.levels[]` in order.
4. Per level, compare the **observable** fields (table above, ✅/⚠️ rows). Build a table:
   ```
   level  field    in         out        match
   L1     scheme   upperRoman upperRoman  OK
   L1     delim    none       none        OK
   L1     source   auto       auto        OK
   ...
   ```
5. **parity = matched observable fields ÷ total observable fields.**
6. Verify `align`/`indent` separately via officecli readback; note results.

## Threshold (decision D3)
- **parity ≥ 0.95** on observable format fields → pass.
- **Hard-fail** (regardless of score) if any level is **dropped** or any **scheme** changes —
  those are structural regressions, not cosmetic drift.
- Below threshold or hard-fail → fix the batch (usually a numbering `source`/scheme mismatch or
  a heading style not named "Heading N" with an outline level) and loop steps build→diff.

## Reference implementation
`evals/score.py` computes level-match on `(scheme, delim, source)` from a re-probe. Round-trip
parity reuses it: probe `$OUT`, score against `IR_in`. Verified green on the auto sample
(`sample-01`): parity 1.000.
