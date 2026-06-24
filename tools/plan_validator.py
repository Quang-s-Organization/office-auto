#!/usr/bin/env python3
"""Pre-execution Plan Validator — PlanCompiler-style structural checks.

Validates a mapping_table.json against content.ir.json and template.ir.json
BEFORE the composer runs. Catches structural errors early instead of
letting them surface as runtime failures.

Usage:
    python3 tools/plan_validator.py \\
        --template-ir .cache/template.ir.json \\
        --content content.ir.json \\
        --mapping mapping_table.json

Exit code: 0 if all checks pass, 1 if any fail.
"""

from __future__ import annotations
import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ValidationResult:
    """Result of a single validation check."""
    name: str
    passed: bool
    message: str
    details: list[str] = field(default_factory=list)


def check_1_prototype_exists(
    mapping_data: dict, template_ir: dict
) -> ValidationResult:
    """Check 1: All prototype IDs in pre_clone exist in Template IR."""
    pre_clone = mapping_data.get("pre_clone")
    if not pre_clone:
        return ValidationResult("CHECK 1", True,
                                "No pre_clone entries to validate")

    all_template_ids = set()
    for style, protos in template_ir.get("prototypes", {}).items():
        for p in protos:
            all_template_ids.add(p.get("para_id", ""))

    missing = []
    for name, pid in pre_clone.items():
        if pid not in all_template_ids:
            # Check best_prototypes too
            found = False
            for bp in template_ir.get("best_prototypes", {}).values():
                if bp.get("para_id") == pid:
                    found = True
                    break
            if not found:
                missing.append(f"{name}: {pid}")

    if missing:
        return ValidationResult("CHECK 1", False,
                                f"{len(missing)} pre_clone paraIds not found in Template IR",
                                details=missing)

    return ValidationResult("CHECK 1", True,
                            f"All {len(pre_clone)} pre_clone paraIds exist in Template IR")


def check_2_content_tags_exist(
    mapping_data: dict, content_ir: dict
) -> ValidationResult:
    """Check 2: All content tags in mapping entries exist in Content IR."""
    content_tags = {s["tag"] for s in content_ir.get("sections", [])}
    mapping_tags = {e.get("content_tag", "") for e in mapping_data.get("entries", [])}

    missing = [t for t in mapping_tags if t and t not in content_tags]

    if missing:
        return ValidationResult("CHECK 2", False,
                                f"{len(missing)} content_tags not found in Content IR",
                                details=missing)

    return ValidationResult("CHECK 2", True,
                            f"All {len(mapping_tags)} content_tags exist in Content IR")


def check_3_no_overlap(
    mapping_data: dict
) -> ValidationResult:
    """Check 3: pre_clone paraIds don't overlap with cleanup_ids."""
    pre_clone = mapping_data.get("pre_clone") or {}
    cleanup_ids = set(mapping_data.get("cleanup_ids", []))
    pre_clone_ids = set(pre_clone.values())

    overlap = pre_clone_ids & cleanup_ids

    if overlap:
        return ValidationResult("CHECK 3", False,
                                f"{len(overlap)} paraIds appear in both pre_clone AND cleanup_ids",
                                details=list(overlap))

    return ValidationResult("CHECK 3", True,
                            "No overlap between pre_clone and cleanup_ids")


def check_4_paragraph_count(
    mapping_data: dict, content_ir: dict
) -> ValidationResult:
    """Check 4: Entry body_paragraphs count matches Content IR paragraph_count."""
    content_sections = {s["tag"]: s for s in content_ir.get("sections", [])}
    mismatches = []

    for entry in mapping_data.get("entries", []):
        tag = entry.get("content_tag", "")
        expected = content_sections.get(tag, {}).get("paragraph_count", 0)
        actual = len(entry.get("body_paragraphs", []))

        # Allow ±1 for edge cases (LLM may split/merge slightly)
        if abs(actual - expected) > 1:
            mismatches.append(
                f"'{tag}': expected ~{expected} paragraphs, got {actual}"
            )

    if mismatches:
        return ValidationResult("CHECK 4", False,
                                f"{len(mismatches)} entries have paragraph count mismatch",
                                details=mismatches[:10])

    return ValidationResult("CHECK 4", True,
                            f"All {len(mapping_data.get('entries', []))} entries have correct paragraph counts")


def check_5_no_orphan_cleanup(
    mapping_data: dict, template_ir: dict
) -> ValidationResult:
    """Check 5: cleanup_ids reference real paraIds in the template."""
    all_template_ids = set()
    for style, protos in template_ir.get("prototypes", {}).items():
        for p in protos:
            all_template_ids.add(p.get("para_id", ""))
    all_template_ids.update(template_ir.get("all_heading_ids", []))

    cleanup_ids = mapping_data.get("cleanup_ids", [])
    orphaned = [pid for pid in cleanup_ids if pid not in all_template_ids]

    if orphaned:
        return ValidationResult("CHECK 5", False,
                                f"{len(orphaned)} cleanup_ids not found in Template IR",
                                details=orphaned[:10])

    return ValidationResult("CHECK 5", True,
                            f"All {len(cleanup_ids)} cleanup_ids reference real template elements")


def check_6_anchor_exists(
    mapping_data: dict, template_ir: dict
) -> ValidationResult:
    """Check 6: initial_anchor exists in template."""
    anchor = mapping_data.get("initial_anchor", "")

    if not anchor:
        return ValidationResult("CHECK 6", False,
                                "initial_anchor is empty", details=[])

    all_ids = set(template_ir.get("all_heading_ids", []))
    for style, protos in template_ir.get("prototypes", {}).items():
        for p in protos:
            all_ids.add(p.get("para_id", ""))

    if anchor not in all_ids:
        return ValidationResult("CHECK 6", False,
                                f"initial_anchor '{anchor}' not found in Template IR",
                                details=[])

    return ValidationResult("CHECK 6", True,
                            f"initial_anchor '{anchor[:20]}...' exists in template")


def check_7_required_fields(
    mapping_data: dict
) -> ValidationResult:
    """Check 7: All required fields present in each entry."""
    required_entry_fields = ["content_tag", "heading_text", "prototype", "body_paragraphs"]
    missing_fields = []

    for i, entry in enumerate(mapping_data.get("entries", [])):
        for field in required_entry_fields:
            if field not in entry:
                missing_fields.append(f"entry[{i}]: missing '{field}'")

    if missing_fields:
        return ValidationResult("CHECK 7", False,
                                f"{len(missing_fields)} required fields missing",
                                details=missing_fields)

    return ValidationResult("CHECK 7", True,
                            f"All {len(mapping_data.get('entries', []))} entries have required fields")


ALL_CHECKS = [
    check_1_prototype_exists,
    check_2_content_tags_exist,
    check_3_no_overlap,
    check_4_paragraph_count,
    check_5_no_orphan_cleanup,
    check_6_anchor_exists,
    check_7_required_fields,
]


def validate_plan(
    mapping_data: dict, content_ir: dict, template_ir: dict
) -> list[ValidationResult]:
    """Run all 7 structural checks against the mapping table."""
    results = []
    for check in ALL_CHECKS:
        sig = check.__code__.co_varnames[:check.__code__.co_argcount]
        if "content_ir" in sig and "template_ir" in sig:
            r = check(mapping_data, template_ir, content_ir)
        elif "template_ir" in sig:
            r = check(mapping_data, template_ir)
        elif "content_ir" in sig:
            r = check(mapping_data, content_ir)
        else:
            r = check(mapping_data)
        results.append(r)
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Validate mapping_table.json before composer runs"
    )
    parser.add_argument("--template-ir", required=True,
                        help="Path to template.ir.json")
    parser.add_argument("--content", required=True,
                        help="Path to content.ir.json")
    parser.add_argument("--mapping", required=True,
                        help="Path to mapping_table.json")
    parser.add_argument("--json", action="store_true",
                        help="Output results as JSON")
    args = parser.parse_args()

    start = time.time()

    # Load files
    try:
        with open(args.mapping, encoding="utf-8") as f:
            mapping_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[plan-validator] ERROR: Cannot load mapping table: {e}",
              file=sys.stderr)
        sys.exit(1)

    try:
        with open(args.content, encoding="utf-8") as f:
            content_ir = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[plan-validator] ERROR: Cannot load content IR: {e}",
              file=sys.stderr)
        sys.exit(1)

    try:
        with open(args.template_ir, encoding="utf-8") as f:
            template_ir = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[plan-validator] ERROR: Cannot load template IR: {e}",
              file=sys.stderr)
        sys.exit(1)

    # Run checks
    results = []
    for check in ALL_CHECKS:
        # Check signature to determine args
        sig = check.__code__.co_varnames[:check.__code__.co_argcount]
        if "content_ir" in sig and "template_ir" in sig:
            r = check(mapping_data, template_ir, content_ir)
        elif "template_ir" in sig:
            r = check(mapping_data, template_ir)
        elif "content_ir" in sig:
            r = check(mapping_data, content_ir)
        else:
            r = check(mapping_data)
        results.append(r)

    elapsed = time.time() - start
    failures = [r for r in results if not r.passed]

    if args.json:
        output = {
            "elapsed_seconds": round(elapsed, 2),
            "total": len(results),
            "passed": len(results) - len(failures),
            "failed": len(failures),
            "checks": [
                {"name": r.name, "passed": r.passed, "message": r.message,
                 "details": r.details[:5]}
                for r in results
            ],
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(f"[plan-validator] {len(results)} checks in {elapsed:.2f}s")
        for r in results:
            status = "✓" if r.passed else "✗"
            print(f"  {status} {r.name}: {r.message}")
            for d in r.details[:3]:
                print(f"       {d}")

    if failures:
        print(f"\n[plan-validator] FAILED: {len(failures)} check(s) failed",
              file=sys.stderr)
        sys.exit(1)
    else:
        print(f"\n[plan-validator] PASSED — all checks clean")
        sys.exit(0)


if __name__ == "__main__":
    main()
