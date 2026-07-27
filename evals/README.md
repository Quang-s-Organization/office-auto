# evals — harness & metrics for the two skills

Eval-driven development (plan [11 §6](../docs/11-implementation-plan.md), Anthropic §7.3):
build eval + baseline **before** writing long skill bodies; every reference must be
verifiable on a sample. This directory holds the harness, **not** part of a shipped skill.

## Files
- `probe.lua` — the probe filter (mirror of the template in
  `inducing-doc-structure/references/probing.md`). Emits a structural-evidence JSON to
  stderr. The skill teaches the agent to *generate* this at runtime; here it is pinned so
  the harness is reproducible.
- `score.py` — deterministic inducer + scorer (the VERIFY-able logic). Encodes the same
  induction the skill performs at runtime.
- `run.sh` — `run.sh <docx> <spec.json>`: probe then score.

## Metrics (plan §6)
| metric | meaning | target |
|---|---|---|
| **coverage** | % structural blocks assigned to some induced level | ~1.0 |
| **sequence-fit** | % of per-level ordinal sequences that reconstruct monotonically | high |
| **level-match** | induced vs ground-truth levels on (scheme, delim, source), in order | ≥0.95 |
| **round-trip parity** | % format fields matching after Skill2→Skill1 (decision D3) | ≥0.95 |
| **zero-prior delta** | coverage/fit drop when VN priors are disabled (generality) | small |

## Scenarios (≥3, Anthropic `{skills, query, files, expected_behavior[]}`)
1. **generic auto** — `sample-01-generic-auto.docx`: 3-level auto-numbered outline, no VN
   priors apply. Expected: 3 levels, upperRoman/decimal/lowerAlpha, all `source=auto`,
   coverage 1.0. *(non-VN → also the generality probe.)*
2. **VN legal manual** — `example.spec.json` fixture (+ a built docx in P4/P5): Chương/Điều/
   Khoản/Điểm with `source=manual`, header_block present. Expected: ordinals detected in
   text, no double-numbering on rebuild.
3. **out-of-domain** *(P6)* — a contract or English document: measures whether induction
   holds without legal priors.

## Baseline (no-skill), recorded 2026-07-01
Naive extraction `pandoc -f docx -t markdown sample-01` (path #1, no skill) renders:

```
I.  Scope and definitions
    1.  This document defines terms.
        a)  First qualifying condition.
    ...
```

**Where it stumbles vs the skill:**
- Produces prose, **no machine-readable IR** — no `scheme`/`delim`/`source` contract for a
  builder to consume; the builder would have to re-parse text and guess.
- **auto vs manual is invisible**: flat markdown can't tell a Word-rendered number from a
  typed one → rebuild double-numbers.
- No `confidence`, no `anomalies` — silent guessing instead of honest limits.
- On off-standard files (hand-typed, converted) the flat pass mislabels or drops levels.

The skill path (`probe.lua` → induce → `structure-spec.json`) produced, on the same file:
**coverage 1.000, sequence-fit 1.000, level-match 1.000 (PASS)** — see below.

> **Must also be measured on Qwen3.6-A3B** ([09](../docs/09-model-qwen3.6-a3b.md)), not only
> frontier models — A3B needs the low-freedom recipe + copy-in checklist.

## Latest run (2026-07-01)
Induce-and-score on the ground-truth docx:
```
$ evals/run.sh samples/sample-01-generic-auto.docx samples/sample-01-generic-auto.spec.json
coverage       : 1.000  (13/13 content blocks classified)
sequence-fit   : 1.000
level-match    : 1.000
VERDICT: PASS
```

Full round-trip parity (IR_in → build → save → probe → IR_out → diff format-only, D3):
```
$ python3 evals/build_from_spec.py samples/sample-01-generic-auto.spec.json samples/output-auto.docx 2
$ pandoc -f docx+styles samples/output-auto.docx -L evals/probe.lua -t native >/dev/null 2> ev.json
$ python3 evals/score.py ev.json samples/sample-01-generic-auto.spec.json
coverage 1.000  sequence-fit 1.000  level-match 1.000  VERDICT: PASS   # parity green
```
The built docx is a FRESH instance (different content/counts), so a matching re-induced grammar
is a true round-trip, not a re-read.

## Verified: what round-trips through pandoc (parity honesty)
- ✅ scheme, delim, `numbering.source` (auto/manual), nesting/level, `bold` (→`Strong`).
- ⚠️ `all_caps` only if written as literal uppercase text.
- ❌ `align` (pandoc drops it), `indent` (pandoc turns left-indent into `BlockQuote`).
  → Verify `align`/`indent` via **officecli readback**, not pandoc. See
  `building-docx-from-structure/references/parity.md`.
