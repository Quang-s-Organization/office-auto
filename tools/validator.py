#!/usr/bin/env python3
"""Deterministic Validator — Runs S1-S10 checks on a DOCX output.

Usage:
    python3 tools/validator.py report.docx
    python3 tools/validator.py out/report.docx --json    # JSON output

Exit code: 0 if all error-level checks pass, 1 if any fail.
"""

from __future__ import annotations
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from validation_checks import run_all, CheckResult


def main():
    parser = argparse.ArgumentParser(
        description="Run S1-S10 validation checks on a DOCX file"
    )
    parser.add_argument("filepath", help="Path to the DOCX file to validate")
    parser.add_argument("--json", action="store_true",
                        help="Output results as JSON")
    parser.add_argument("--check", nargs="*",
                        help="Run specific checks only (e.g. S1 S8)")
    args = parser.parse_args()

    start = time.time()

    from validation_checks import ALL_CHECKS, run_all

    if args.check:
        # Build check map dynamically from ALL_CHECKS
        check_map = {}
        for check_fn in ALL_CHECKS:
            # Derive S-number from function name
            parts = check_fn.__name__.split("_")
            for p in parts:
                if p.startswith("s") and p[1:].isdigit():
                    s_num = f"S{p[1:]}"
                    check_map[s_num] = check_fn
                    break

        results = []
        for name in args.check:
            fn = check_map.get(name)
            if fn:
                results.append(fn(args.filepath))
            else:
                print(f"Unknown check: {name}", file=sys.stderr)
    else:
        results = run_all(args.filepath)

    elapsed = time.time() - start

    errors = [r for r in results if not r.passed and r.severity == "error"]
    warnings = [r for r in results if not r.passed and r.severity == "warning"]
    passed = [r for r in results if r.passed]

    if args.json:
        output = {
            "elapsed_seconds": round(elapsed, 1),
            "total": len(results),
            "passed": len(passed),
            "errors": len(errors),
            "warnings": len(warnings),
            "checks": [
                {
                    "name": r.name,
                    "passed": r.passed,
                    "message": r.message,
                    "details": r.details[:5],
                    "severity": r.severity,
                }
                for r in results
            ],
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(f"[validator] {len(results)} checks in {elapsed:.1f}s")
        for r in results:
            status = "✓" if r.passed else ("⚠" if r.severity == "warning" else "✗")
            print(f"  {status} {r.name}: {r.message}")
            for d in r.details[:3]:
                print(f"       {d}")

        print()
        if errors:
            print(f"[validator] FAILED: {len(errors)} error(s)")
            sys.exit(1)
        elif warnings:
            print(f"[validator] PASSED with {len(warnings)} warning(s)")
            sys.exit(0)
        else:
            print(f"[validator] PASSED — all checks clean")
            sys.exit(0)


if __name__ == "__main__":
    main()
