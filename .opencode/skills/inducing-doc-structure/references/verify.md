# verify — re-sequencing & scoring (evaluator-optimizer)

> VERIFY is **deterministic**: the data, not you, judges a hypothesis. Regenerate what each
> rule predicts, compare to what was observed, score, keep the best, iterate.

## The idea
A grammar hypothesis makes a falsifiable claim: "level L2 is decimal, resets per L1". Replay
that claim to predict the ordinal sequence, then diff against the observed sequence
(`inventories.md` §3). A good rule reproduces the document; a bad one desynchronizes.

## Metrics
- **coverage** = classified structural blocks ÷ total structural blocks. Target ~1.0. Every
  unclassified block goes into `anomalies` (honest residue).
- **sequence-fit** = ordinals the rule reproduces ÷ ordinals observed.
  - *manual numbering:* regenerate `1,2,3,…` (with the reset rule) and compare to the ordinals
    the probe read from text. A gap ("Điều 5" after "Điều 3") lowers fit or flags an anomaly.
  - *auto numbering:* the number isn't in text, so fit reduces to "do the item counts form a
    consistent monotone run under the reset rule" — auto lists are consistent by construction,
    so the real test is coverage + level assignment.

## Procedure
1. For each hypothesis, assign every structural block to a level (or to anomalies).
2. Compute coverage.
3. For each level with `source=manual`, regenerate its ordinal sequence from
   `(scheme, delim, reset)` and compare to observed; compute sequence-fit.
4. Pick the hypothesis with the best (coverage, fit). If coverage < ~0.95 or fit is low or two
   hypotheses tie → **return to INDUCE** (max 3 rounds), revising the weak level.
5. Record the winning scores as `document.confidence` (be conservative) and list every
   residual block in `anomalies`.

## Reference implementation
`evals/score.py` implements this deterministically (induce from `evidence.json`, score against
a ground-truth spec). Read it to see the exact induction + coverage computation; generate the
equivalent at runtime rather than shipping it inside the skill.

Verified on `sample-01-generic-auto.docx`: coverage 1.000, sequence-fit 1.000,
level-match 1.000.

## Honesty rule
Never inflate confidence to look finished. A shallow grammar with `confidence: 0.4` and three
anomalies is a **correct** output for a messy document — the builder and the human need to
know. Fabricating structure onto a document that has none is the one true failure.
