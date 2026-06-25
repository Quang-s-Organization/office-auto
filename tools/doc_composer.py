#!/usr/bin/env python3
"""Deterministic Composer (v5) — execute a batch program into a DOCX.

Thin executor: copy template → output, run the planner's `batch_program.json`
in a SINGLE `officecli batch` (one open/save cycle), refresh fields, report.

No per-operation officecli calls, no paraId diff-tracking, no hardcoded props.
All formatting + ordering decisions live in batch_program.json (from planner).

Usage:
    python3 tools/doc_composer.py \\
        --template templates/format_template.docx \\
        --batch batch_program.json \\
        --output report.docx
"""

from __future__ import annotations
import argparse
import json
import os
import shutil
import subprocess
import sys
import time


# Disable resident caching: the composer rewrites the output file on disk
# (shutil.copy2). A stale in-memory resident would shadow that fresh copy and
# operate on accumulated state. Each batch is a single open/save anyway.
_ENV = {**os.environ, "OFFICECLI_NO_AUTO_RESIDENT": "1"}


def _run(cmd: list[str], timeout: int = 120) -> tuple[int, str, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                            timeout=timeout, env=_ENV)
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return 124, "", f"timeout after {timeout}s"


def _parse_json(stdout: str) -> dict:
    i = stdout.find("{")
    if i < 0:
        return {}
    try:
        return json.loads(stdout[i:])
    except json.JSONDecodeError:
        return {}


def run_batch(doc: str, batch_path: str) -> dict:
    """Execute a batch program. Returns {success, summary, failures[]}."""
    code, out, err = _run(["officecli", "batch", doc, "--input", batch_path, "--json"])
    data = _parse_json(out)
    results = data.get("data", {}).get("results", [])
    summary = data.get("data", {}).get("summary", {})
    failures = [r for r in results if not r.get("success")]
    return {
        "success": bool(data.get("success")) and not failures,
        "summary": summary,
        "failures": failures,
        "raw_error": err[:300] if code != 0 and not data else "",
    }


def refresh(doc: str) -> None:
    """Refresh TOC/field values. May be a no-op off-Windows; tolerated."""
    _run(["officecli", "refresh", doc])


def _write_tmp(ops: list, path: str) -> str:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(ops, f, ensure_ascii=False)
    return path


def compose(template: str, batch_path: str, output: str) -> dict:
    t0 = time.time()
    out_dir = os.path.dirname(output) or "."
    os.makedirs(out_dir, exist_ok=True)

    # Compose into an isolated temp path this process owns exclusively —
    # no prior officecli resident can exist for a PID-scoped name.
    # This sidesteps the resident-shadow problem: `shutil.copy2` to a
    # known path (output) is useless if a stale resident for that path
    # exists in memory; the batch would operate on RAM, not the fresh copy.
    # After all batches complete we evict the output-path resident and
    # atomically rename temp → output.
    tmp_output = os.path.join(out_dir, f".compose-{os.getpid()}.docx")
    shutil.copy2(template, tmp_output)
    print(f"[composer] Copied template -> tmp", file=sys.stderr)

    with open(batch_path, encoding="utf-8") as f:
        program = json.load(f)

    # Run removes and adds as SEPARATE batch cycles. Doing both in one
    # open/save cycle makes officecli's auto TOC-bookmark id counter collide
    # (duplicate w:id -> schema error). Two cycles keep ids unique.
    removes = [op for op in program if op.get("command") == "remove"]
    adds = [op for op in program if op.get("command") != "remove"]

    failures = []
    summary = {"total": len(program), "succeeded": 0, "failed": 0}
    for label, ops in (("cleanup", removes), ("build", adds)):
        if not ops:
            continue
        tmp_batch = _write_tmp(ops, os.path.join(out_dir, f".batch_{label}.json"))
        print(f"[composer] {label}: {len(ops)} ops via officecli batch...", file=sys.stderr)
        r = run_batch(tmp_output, tmp_batch)
        os.remove(tmp_batch)
        failures += r["failures"]
        summary["succeeded"] += r.get("summary", {}).get("succeeded", 0)
        summary["failed"] += r.get("summary", {}).get("failed", 0)

    # Publish: evict any stale resident for the destination, then atomic rename.
    # NOTE: `officecli refresh` is intentionally NOT called here. It requires a
    # Word backend (Windows); on Linux/WSL it fails AND leaves duplicate
    # TOC-bookmark ids (schema error). Word regenerates TOC on open instead.
    _run(["officecli", "close", output])
    os.replace(tmp_output, output)
    print(f"[composer] Published -> {output}", file=sys.stderr)

    return {
        "success": not failures,
        "summary": summary,
        "failures": failures,
        "elapsed_seconds": round(time.time() - t0, 1),
        "output": output,
    }


def main():
    ap = argparse.ArgumentParser(description="Composer v5 — run a batch program into a DOCX")
    ap.add_argument("--template", required=True)
    ap.add_argument("--batch", required=True)
    ap.add_argument("--output", "-o", default="report.docx")
    args = ap.parse_args()

    res = compose(args.template, args.batch, args.output)
    print(json.dumps({
        "success": res["success"],
        "summary": res.get("summary", {}),
        "failure_count": len(res.get("failures", [])),
        "failures": res.get("failures", [])[:5],
        "output": res["output"],
        "elapsed_seconds": res["elapsed_seconds"],
    }, ensure_ascii=False, indent=2))
    sys.exit(0 if res["success"] else 1)


if __name__ == "__main__":
    main()
