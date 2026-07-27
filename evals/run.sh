#!/usr/bin/env bash
# run.sh — probe a sample docx and score the induced IR against its ground-truth spec.
# Usage: evals/run.sh samples/sample-01-generic-auto.docx samples/sample-01-generic-auto.spec.json
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
DOCX="${1:?usage: run.sh <file.docx> <file.spec.json>}"
SPEC="${2:?usage: run.sh <file.docx> <file.spec.json>}"
EV="$(mktemp --suffix=.json)"

# PROBE: emit structural-evidence JSON on stderr (skill's probe.lua)
pandoc -f docx+styles "$DOCX" -L "$HERE/probe.lua" -t native >/dev/null 2> "$EV"

# INDUCE + SCORE
python3 "$HERE/score.py" "$EV" "$SPEC"
