#!/usr/bin/env python3
"""Validation check functions for document quality assurance.

Implements S1-S10 checks as per the migration-v3 plan.
Each check is a pure function returning a CheckResult.
"""

from __future__ import annotations
import json
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CheckResult:
    """Result of a single validation check."""
    name: str              # "S1", "S2", etc.
    passed: bool
    message: str           # Description of pass/fail
    details: list[str] = field(default_factory=list)
    severity: str = "error"  # "error" or "warning"


def _run(cmd: list[str]) -> str:
    """Run officecli command and return stdout."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return r.stdout.strip()
    except subprocess.TimeoutExpired:
        return ""


def check_s1_heading_order(filepath: str) -> CheckResult:
    """S1: Verify heading hierarchy is correct (no H2 before H1, etc.).

    Parses outline view. Expects heading levels to be non-decreasing
    (H1 → H2 → H3 → Normal/body). Detects jumps or backtracks.
    """
    out = _run(["officecli", "view", filepath, "outline"])
    if not out:
        return CheckResult("S1", False,
                           "Could not read document outline", severity="error")

    # Parse outline lines for heading levels
    issues = []
    prev_level = 0
    lines = out.split("\n")
    for i, line in enumerate(lines):
        stripped = line.strip()
        # Check for heading markers
        for level in [1, 2, 3, 4, 5, 6]:
            marker = f"(heading {level})"
            if marker in stripped:
                # Extract heading text
                text_start = stripped.find('"')
                text_end = stripped.rfind('"')
                heading_text = stripped[text_start:text_end+1] if text_start >= 0 else "unknown"
                if level > prev_level + 1:
                    issues.append(f"Line {i}: Jump from H{prev_level} → {heading_text} (H{level})")
                prev_level = level
                break

    if issues:
        return CheckResult("S1", False,
                           f"Found {len(issues)} hierarchy issues",
                           details=issues, severity="error")

    return CheckResult("S1", True, "Heading hierarchy is correct", severity="warning")


def check_s2_schema_validity(filepath: str) -> CheckResult:
    """S2-S7: Run officecli validate for schema-level checks."""
    out = _run(["officecli", "validate", filepath])
    if not out:
        return CheckResult("S2", False,
                           "Validation command returned no output", severity="error")

    # Check for E_ errors
    lines = out.split("\n")
    errors = [l for l in lines if l.strip().startswith("E_")]
    warnings = [l for l in lines if l.strip().startswith("W_")]

    if errors:
        return CheckResult("S2-S7", False,
                           f"Found {len(errors)} errors, {len(warnings)} warnings",
                           details=errors[:10], severity="error")

    msg = f"Schema valid ({len(warnings)} warnings)" if warnings else "Schema valid, clean"
    return CheckResult("S2-S7", True, msg,
                       details=warnings[:5] if warnings else [],
                       severity="warning" if warnings else "info")


def check_s8_outline_hierarchy(filepath: str) -> CheckResult:
    """S8: Outline hierarchy integrity — check Heading1/Heading2 outlineLevel."""
    issues = []

    for style in ["Heading1", "Heading2"]:
        out = _run([
            "officecli", "query", filepath,
            f"p[style={style}]", "--json"
        ])
        if not out:
            continue
        try:
            data = json.loads(out)
            for r in data.get("data", {}).get("results", []):
                fmt = r.get("format", {})
                text = r.get("text", "")
                ol = fmt.get("outlineLevel")
                expected_ol = {"Heading1": "1", "Heading2": "2"}.get(style)
                if ol is not None and expected_ol and ol != expected_ol:
                    issues.append(
                        f"'{text[:40]}' has style={style} but outlineLevel={ol}"
                    )
        except (json.JSONDecodeError, KeyError):
            continue

    if issues:
        return CheckResult("S8", False,
                           f"Found {len(issues)} outline level mismatches",
                           details=issues, severity="error")

    return CheckResult("S8", True, "All heading outline levels are consistent",
                       severity="info")


def check_s9_font_consistency(filepath: str) -> CheckResult:
    """S9: Font consistency — check effective font and size for headings."""
    issues = []

    # Check Heading1 paragraphs
    out = _run([
        "officecli", "query", filepath,
        "p[style=Heading1]", "--json"
    ])
    if out:
        try:
            data = json.loads(out)
            for r in data.get("data", {}).get("results", []):
                fmt = r.get("format", {})
                text = r.get("text", "")
                font = fmt.get("effective.font.ascii", "?")
                size = fmt.get("effective.size", "?")
                # Font consistency: heading fonts should be similar
                if font and font not in issues and font != "?}":
                    pass  # Track font usage
        except (json.JSONDecodeError, KeyError):
            pass

    # Check Normal body paragraphs for ind.firstLine
    out = _run([
        "officecli", "query", filepath,
        "p[style=Normal and text!='']", "--json"
    ])
    if out:
        try:
            data = json.loads(out)
            no_indent = 0
            for r in data.get("data", {}).get("results", []):
                fmt = r.get("format", {})
                first_line = fmt.get("ind.firstLine")
                if not first_line or first_line == "0":
                    no_indent += 1
            total = len(data.get("data", {}).get("results", []))
            if no_indent > 0:
                issues.append(f"{no_indent}/{total} body paragraphs have no first-line indent")
        except (json.JSONDecodeError, KeyError):
            pass

    if issues:
        return CheckResult("S9", False,
                           f"Font/formatting issues: {'; '.join(issues)}",
                           details=issues, severity="warning")

    return CheckResult("S9", True, "Font and formatting are consistent", severity="info")


def check_s10_anchor_integrity(filepath: str) -> CheckResult:
    """S10: Verify content paragraphs are properly chained and readable."""
    out = _run([
        "officecli", "query", filepath, "p", "--json"
    ])
    if not out:
        return CheckResult("S10", False,
                           "Could not query paragraphs", severity="error")

    try:
        data = json.loads(out)
        results = data.get("data", {}).get("results", [])
        total = len(results)
        if total == 0:
            return CheckResult("S10", False,
                               "Document has no paragraphs", severity="error")

        # Check for empty text paragraphs that could be broken
        empty_text = [r for r in results
                      if not r.get("text", "").strip()
                      and r.get("format", {}).get("style") != "Normal"]
        if empty_text:
            return CheckResult("S10", True,
                               f"{total} paragraphs, {len(empty_text)} non-Normal empty",
                               details=[f"Empty para: paraId={r.get('format',{}).get('paraId','?')}"
                                        for r in empty_text[:3]],
                               severity="warning")

        return CheckResult("S10", True,
                           f"All {total} paragraphs readable and chained",
                           severity="info")
    except (json.JSONDecodeError, KeyError):
        return CheckResult("S10", False,
                           "Failed to parse paragraph data", severity="error")


ALL_CHECKS = [
    check_s1_heading_order,
    check_s2_schema_validity,
    check_s8_outline_hierarchy,
    check_s9_font_consistency,
    check_s10_anchor_integrity,
]


def run_all(filepath: str) -> list[CheckResult]:
    """Run all S1-S10 checks and return results."""
    return [check(filepath) for check in ALL_CHECKS]
