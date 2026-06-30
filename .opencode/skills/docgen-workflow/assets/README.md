# Design Assets

## Batch build — IMPLEMENTED (v5)

The whole document is composed with a single `officecli batch` (one open/save
cycle). `tools/planner.py` emits `batch_program.json`; `tools/doc_composer.py`
runs it (remove cycle, then add cycle).

This replaced the old per-paragraph `add → query → set` loop (O(N²), ~400s) with
one batch (~3–5s). The earlier "Batch Operation IR (v5, todo)" note is done —
`officecli batch` is the native mechanism, no custom executor needed.

See `clone-workflow.json` for a minimal batch sample and `docs/batch-contract.md`
for the verified rules (append-to-end, reconstruct don't clone-then-set,
two cycles, no off-Windows refresh).
