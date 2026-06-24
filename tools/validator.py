#!/usr/bin/env python3
"""Deterministic Validator (v5) — run S-checks against discovered Template IR.

Usage:
    python3 tools/validator.py out/report.docx \\
        --template-ir .cache/template.ir.json --content content.ir.json [--json]

Exit code: 0 if no error-severity failures, 1 otherwise.
"""

from __future__ import annotations
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from validation_checks import run_all


def _load(path):
    if not path:
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def main():
    ap = argparse.ArgumentParser(description="Run S-checks on a DOCX vs Template IR")
    ap.add_argument("filepath")
    ap.add_argument("--template-ir")
    ap.add_argument("--content")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    template_ir = _load(args.template_ir)
    content_ir = _load(args.content)

    start = time.time()
    results = run_all(args.filepath, template_ir, content_ir)
    elapsed = time.time() - start

    errors = [r for r in results if not r.passed and r.severity == "error"]
    warnings = [r for r in results if not r.passed and r.severity == "warning"]

    if args.json:
        print(json.dumps({
            "elapsed_seconds": round(elapsed, 1),
            "errors": len(errors), "warnings": len(warnings),
            "checks": [{"name": r.name, "passed": r.passed, "severity": r.severity,
                        "message": r.message, "details": r.details[:5]} for r in results],
        }, ensure_ascii=False, indent=2))
    else:
        print(f"[validator] {len(results)} checks in {elapsed:.1f}s")
        for r in results:
            mark = "✓" if r.passed else ("⚠" if r.severity == "warning" else "✗")
            print(f"  {mark} {r.name}: {r.message}")
            for d in r.details[:3]:
                print(f"       {d}")
        print()
        if errors:
            print(f"[validator] FAILED: {len(errors)} error(s)")
        elif warnings:
            print(f"[validator] PASSED with {len(warnings)} warning(s)")
        else:
            print("[validator] PASSED — all checks clean")

    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
