#!/usr/bin/env python3
"""Pre-execution validator (v5) — structural checks on batch_program.json.

Catches structural mistakes before the composer runs the batch. Validates the
officecli batch program against the Template IR and Content IR.

Usage:
    python3 tools/plan_validator.py --batch batch_program.json \\
        --template-ir .cache/template.ir.json --content content.ir.json [--json]

Exit code: 0 if all pass, 1 otherwise.
"""

from __future__ import annotations
import argparse
import json
import re
import sys
from dataclasses import dataclass, field


@dataclass
class Result:
    name: str
    passed: bool
    message: str
    details: list = field(default_factory=list)


_PARAID_RE = re.compile(r"@paraId=([0-9A-Fa-f]+)")


def check_program_nonempty(program, template_ir, content_ir):
    if not program:
        return Result("nonempty", False, "batch program is empty")
    return Result("nonempty", True, f"{len(program)} ops")


def check_remove_targets_exist(program, template_ir, content_ir):
    body_ids = {p.get("para_id") for p in template_ir.get("body_sequence", [])}
    missing = []
    for op in program:
        if op.get("command") == "remove":
            m = _PARAID_RE.search(op.get("path", ""))
            if m and m.group(1) not in body_ids:
                missing.append(m.group(1))
    if missing:
        return Result("remove_targets", False,
                      f"{len(missing)} remove paraIds not in template body",
                      details=missing[:8])
    return Result("remove_targets", True, "all remove targets exist in template")


def check_add_p_has_style(program, template_ir, content_ir):
    bad = [i for i, op in enumerate(program)
           if op.get("command") == "add" and op.get("type") == "p"
           and not op.get("props", {}).get("style")]
    if bad:
        return Result("add_p_style", False, f"{len(bad)} add-p ops missing style",
                      details=bad[:8])
    return Result("add_p_style", True, "all paragraphs carry a style")


def check_runs_nonempty(program, template_ir, content_ir):
    empty = [i for i, op in enumerate(program)
             if op.get("command") == "add" and op.get("type") == "r"
             and not (op.get("props", {}).get("text") or "").strip()]
    if empty:
        return Result("runs_nonempty", False, f"{len(empty)} empty run texts",
                      details=empty[:8])
    return Result("runs_nonempty", True, "all runs carry text")


def check_paragraph_count(program, template_ir, content_ir, emitted_tags=None):
    if not content_ir:
        return Result("para_count", True, "no content IR — skipped")
    # When a logical IR is supplied, only EMITTED nodes (intent != preserve/remove)
    # contribute paragraphs; preserved front matter is kept from the template.
    secs = content_ir.get("sections", [])
    if emitted_tags is not None:
        secs = [s for s in secs if s.get("tag") in emitted_tags]
    expected_headings = sum(1 for s in secs
                            if s.get("type", "").startswith("heading"))
    expected_body = sum(s.get("paragraph_count", 0) for s in secs)
    added_p = sum(1 for op in program
                  if op.get("command") == "add" and op.get("type") == "p")
    expected = expected_headings + expected_body
    if added_p != expected:
        return Result("para_count", False,
                      f"{added_p} paragraphs built != {expected} expected "
                      f"({expected_headings} headings + {expected_body} body)")
    return Result("para_count", True, f"{added_p} paragraphs == content IR")


ALL = [check_program_nonempty, check_remove_targets_exist, check_add_p_has_style,
       check_runs_nonempty, check_paragraph_count]


def validate(program, template_ir, content_ir, emitted_tags=None):
    results = []
    for c in ALL:
        if c is check_paragraph_count:
            results.append(c(program, template_ir, content_ir, emitted_tags))
        else:
            results.append(c(program, template_ir, content_ir))
    return results


def _load(path, label):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[plan-validator] ERROR loading {label}: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    ap = argparse.ArgumentParser(description="Validate batch_program.json pre-execution")
    ap.add_argument("--batch", required=True)
    ap.add_argument("--template-ir", required=True)
    ap.add_argument("--content", required=True)
    ap.add_argument("--logical", help="logical.ir.json — excludes preserved "
                    "(intent=preserve/remove) nodes from the para_count check")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    program = _load(args.batch, "batch program")
    template_ir = _load(args.template_ir, "template IR")
    content_ir = _load(args.content, "content IR")

    emitted_tags = None
    if args.logical:
        logical = _load(args.logical, "logical IR")
        emitted_tags = {s["node_id"] for s in logical.get("sections", [])
                        if s.get("intent") not in ("preserve", "remove")}

    results = validate(program, template_ir, content_ir, emitted_tags)
    failures = [r for r in results if not r.passed]

    if args.json:
        print(json.dumps({"failed": len(failures),
                          "checks": [{"name": r.name, "passed": r.passed,
                                      "message": r.message, "details": r.details[:5]}
                                     for r in results]}, ensure_ascii=False, indent=2))
    else:
        for r in results:
            print(f"  {'✓' if r.passed else '✗'} {r.name}: {r.message}")
            for d in r.details[:3]:
                print(f"       {d}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
