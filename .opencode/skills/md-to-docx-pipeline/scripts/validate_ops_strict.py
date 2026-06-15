#!/usr/bin/env python3
"""validate_ops_strict.py — strict validator with hard-block on high severity errors.

Unlike docx_validate_ops.py (warn-only), this script:
- HARD FAILS (exit code 1) on high severity errors
- Blocks apply if validation fails
- Returns structured blocking_errors list

Usage:
    python3 validate_ops_strict.py --run-dir <path> [--ops-file <path>]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from officecli_native import read_json, write_json

# Import the existing validator's core logic
import importlib.util
import os as _os

_scripts_dir = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "docx_validate_ops",
    str(_scripts_dir / "docx_validate_ops.py"),
)
_docx_validate_ops = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_docx_validate_ops)

validate_ops_payload = _docx_validate_ops.validate_ops_payload
_warnonly_write_planning_report = getattr(_docx_validate_ops, "_write_planning_report", None)

SUPPORTED_OPS = {
    "insert_paragraph_after",
    "insert_paragraph_before",
    "remove",
    "update_text",
    "insert_table",
    "insert_table_after",
    "set_page_layout",
    "insert_image",
}


def strict_invariant_checks(ops: list[dict], template_inspection: dict) -> list[dict]:
    """Additional invariant checks that must pass before apply.

    These are hard invariants — any violation = blocking error.
    """
    blocking: list[dict] = []

    all_para_ids = template_inspection.get("all_para_ids", [])
    front_matter = _docx_validate_ops.collect_front_matter_para_ids(template_inspection)
    para_meta = _docx_validate_ops.build_para_meta_index(template_inspection)

    # Invariant 1: First insert op must have explicit anchor (not PREVIOUS)
    insert_ops = [op for op in ops if op.get("op") in ("insert_paragraph_after", "insert_paragraph_before")]
    if insert_ops:
        first_anchor = insert_ops[0].get("anchor", "")
        if not first_anchor or str(first_anchor).upper() == "PREVIOUS":
            blocking.append({
                "invariant": "first_insert_must_have_explicit_anchor",
                "severity": "high",
                "message": "First insert op has no explicit anchor or uses PREVIOUS. Must provide real anchor path.",
            })

    # Invariant 2: CRITICAL_FIRST_OP_ANCHOR must not be in remove paths
    insert_anchors = set()
    for op in insert_ops:
        anchor = op.get("anchor", "")
        if anchor and str(anchor).startswith("/body/p[@paraId="):
            insert_anchors.add(str(anchor))

    remove_ops = [op for op in ops if op.get("op") == "remove"]
    for rop in remove_ops:
        path = rop.get("path", "")
        if str(path) in insert_anchors:
            blocking.append({
                "invariant": "anchor_removed_after_insert",
                "severity": "high",
                "message": f"Remove op targets {path} which is also an insert anchor.",
                "conflicting_path": str(path),
            })

    # Invariant 3: remove_paths must not include front_matter
    front_matter_paths = {f"/body/p[@paraId={pid}]" for pid in front_matter}
    for rop in remove_ops:
        path = str(rop.get("path", ""))
        if path in front_matter_paths:
            blocking.append({
                "invariant": "remove_front_matter",
                "severity": "high",
                "message": f"Remove op targets front matter: {path}",
                "conflicting_path": path,
            })

    # Invariant 4: All insert ops after first must use PREVIOUS
    for i, op in enumerate(insert_ops):
        if i == 0:
            continue
        anchor = str(op.get("anchor", ""))
        if anchor.upper() != "PREVIOUS":
            blocking.append({
                "invariant": "non_previous_mid_sequence",
                "severity": "high",
                "message": f"Insert op #{i+1} uses anchor '{anchor}' instead of PREVIOUS. "
                           f"Only the first insert op should have an explicit anchor.",
                "op_index": i + 1,
            })

    # Invariant 5: No duplicate source_block_id in insert ops
    seen_ids = {}
    for i, op in enumerate(insert_ops):
        block_id = op.get("source_block_id", "")
        if block_id and block_id in seen_ids:
            blocking.append({
                "invariant": "duplicate_source_block",
                "severity": "high",
                "message": f"Insert op #{i+1} reuses source_block_id '{block_id}' "
                           f"already used by op #{seen_ids[block_id]}",
                "op_index": i + 1,
            })
        elif block_id:
            seen_ids[block_id] = i + 1

    # Invariant 6: Schema version must be "2"
    # Handled by caller

    # Invariant 7: No unsupported op types
    for i, op in enumerate(ops):
        op_name = str(op.get("op") or "")
        if not op_name:
            blocking.append({
                "invariant": "missing_op_type",
                "severity": "high",
                "message": f"Op #{i+1} has no 'op' field.",
                "op_index": i + 1,
            })
        elif op_name not in SUPPORTED_OPS:
            blocking.append({
                "invariant": "unsupported_op",
                "severity": "high",
                "message": f"Op #{i+1} has unsupported op type '{op_name}'. Supported: {sorted(SUPPORTED_OPS)}",
                "op_index": i + 1,
            })

    # Invariant 8: Remove ops must use "path" not "at"
    for i, op in enumerate(ops):
        if op.get("op") == "remove" and op.get("at") and not op.get("path"):
            blocking.append({
                "invariant": "remove_uses_at_not_path",
                "severity": "high",
                "message": f"Remove op #{i+1} uses 'at' instead of 'path'. Must use 'path'.",
                "op_index": i + 1,
            })

    # Invariant 9: All styles must exist in template
    styles_for_llm = template_inspection.get("styles_for_llm", {})
    available_styles = styles_for_llm.get("available_styles", [])
    if available_styles:
        # Build set of valid style IDs and names
        valid_style_ids = {s.get("style_id") for s in available_styles if s.get("style_id")}
        valid_style_names = {s.get("name") for s in available_styles if s.get("name")}
        valid_styles = valid_style_ids | valid_style_names
        
        for i, op in enumerate(ops):
            style = op.get("style")
            if not style:
                continue
            style_str = str(style)
            if style_str not in valid_styles:
                blocking.append({
                    "invariant": "style_not_in_template",
                    "severity": "high",
                    "message": f"Op #{i+1} uses style '{style_str}' which does not exist in template. "
                               f"Available styles: {sorted(list(valid_styles))[:10]}{'...' if len(valid_styles) > 10 else ''}",
                    "op_index": i + 1,
                })

    return blocking


def validate_strict(run_dir: Path, ops_file: Path) -> dict:
    """Run strict validation including all warn-only checks + hard invariants.

    Returns {"valid": bool, "blocking_errors": [...], "warnings": [...]}
    """
    ops_payload = read_json(ops_file)

    inspect_file = run_dir / "docx_inspect_output.json"
    if not inspect_file.exists():
        inspect_file = run_dir / "template_inspection_raw.json"
    if not inspect_file.exists():
        return {
            "valid": False,
            "blocking_errors": [{
                "type": "missing_inspection",
                "severity": "high",
                "message": f"No inspection file found in {run_dir}",
            }],
            "warnings": [],
        }

    template_inspection = read_json(inspect_file)
    ops_list = ops_payload.get("ops", []) if isinstance(ops_payload, dict) else ops_payload

    # Check version
    version = ops_payload.get("version") if isinstance(ops_payload, dict) else None
    if version != "2":
        return {
            "valid": False,
            "blocking_errors": [{
                "type": "invalid_schema_version",
                "severity": "high",
                "message": f"Schema version must be '2', got '{version}'",
            }],
            "warnings": [],
        }

    # Run warn-only validation (existing logic)
    warnings = validate_ops_payload(ops_payload, template_inspection)

    # Run strict invariant checks
    blocking = strict_invariant_checks(ops_list, template_inspection)

    # Also pull high-severity warnings into blocking
    for w in warnings:
        if w.get("severity") == "high":
            blocking.append({
                "type": w.get("type", "high_warning"),
                "severity": "high",
                "message": w.get("message", ""),
                "op_index": w.get("op_index"),
                "code": w.get("code"),
            })

    valid = len(blocking) == 0

    return {
        "valid": valid,
        "blocking_errors": blocking,
        "warnings": [w for w in warnings if w.get("severity") != "high"],
        "high_severity_count": len(blocking),
        "warning_count": len(warnings),
        "total_ops": len(ops_list),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="validate_ops_strict: strict validator — hard fail on high severity errors."
    )
    parser.add_argument("--run-dir", required=True, help="Run directory")
    parser.add_argument("--ops-file", default=None, help="Path to execution_ops.json")
    parser.add_argument("--output", default=None, help="Output report path")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    ops_file = Path(args.ops_file) if args.ops_file else run_dir / "execution_ops.json"

    if not ops_file.exists():
        print(f"[validate_ops_strict] ERROR: ops file not found: {ops_file}")
        sys.exit(1)

    result = validate_strict(run_dir, ops_file)

    output_path = Path(args.output) if args.output else run_dir / "strict_validation.json"
    write_json(output_path, result)

    if result["valid"]:
        print(f"[validate_ops_strict] ✅ VALID — {result['total_ops']} ops, "
              f"{result['warning_count']} warnings (non-blocking)")
    else:
        print(f"[validate_ops_strict] ❌ INVALID — {result['high_severity_count']} blocking errors:")
        for err in result["blocking_errors"][:10]:
            print(f"  - [{err.get('type', 'unknown')}] {err.get('message', '')[:120]}")

    print(f"[validate_ops_strict] Report: {output_path}")

    if not result["valid"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
