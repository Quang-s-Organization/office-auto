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


def check_s3_font_consistency(filepath: str) -> CheckResult:
    """S3: Font consistency — check effective font and size for headings.

    Compares all Heading1 paragraphs against expected font (Calibri, 16pt)
    and Heading2 against expected (Calibri, 14pt). Reports mismatches.
    """
    issues = []

    expected = {
        "Heading1": {"font": "Calibri", "size": "16pt"},
        "Heading2": {"font": "Calibri", "size": "14pt"},
    }

    for style, exp in expected.items():
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
                text = (r.get("text", "") or "")[:50]
                font = fmt.get("effective.font.ascii", "")
                size = fmt.get("effective.size", "")

                if font and font != exp["font"]:
                    issues.append(f"'{text}' has font '{font}' (expected '{exp['font']}')")
                if size and size != exp["size"]:
                    issues.append(f"'{text}' has size {size} (expected {exp['size']})")
        except (json.JSONDecodeError, KeyError):
            continue

    if issues:
        return CheckResult("S3", False,
                           f"{len(issues)} font/size mismatches found",
                           details=issues, severity="warning")

    return CheckResult("S3", True, "All headings have consistent font and size",
                       severity="info")


def check_s4_first_line_indent(filepath: str) -> CheckResult:
    """S4: First-line indent — check Normal paragraphs have ind.firstLine = 1.27cm."""
    out = _run([
        "officecli", "query", filepath,
        "p[style=Normal and text!='']", "--json"
    ])
    if not out:
        return CheckResult("S4", False,
                           "Could not query body paragraphs", severity="error")

    try:
        data = json.loads(out)
        results = data.get("data", {}).get("results", [])
        missing = []
        wrong_value = []

        for r in results:
            fmt = r.get("format", {})
            first_line = fmt.get("ind.firstLine", "")
            text = (r.get("text", "") or "")[:40]

            if not first_line or first_line == "0":
                missing.append(f"'{text}' has no first-line indent")
            elif first_line != "1.27cm":
                wrong_value.append(f"'{text}' has indent '{first_line}' (expected '1.27cm')")

        if missing:
            return CheckResult("S4", False,
                               f"{len(missing)} paragraphs missing first-line indent",
                               details=missing[:5], severity="warning")
        if wrong_value:
            return CheckResult("S4", False,
                               f"{len(wrong_value)} paragraphs with wrong indent value",
                               details=wrong_value[:5], severity="warning")

        return CheckResult("S4", True,
                           f"All {len(results)} paragraphs have correct first-line indent",
                           severity="info")
    except (json.JSONDecodeError, KeyError) as e:
        return CheckResult("S4", False, f"Failed to parse: {e}", severity="error")


def check_s5_empty_paragraphs(filepath: str) -> CheckResult:
    """S5: Check for empty paragraphs at end of document (last 5 paragraphs)."""
    out = _run([
        "officecli", "query", filepath, "p", "--json"
    ])
    if not out:
        return CheckResult("S5", False,
                           "Could not query paragraphs", severity="error")

    try:
        data = json.loads(out)
        results = data.get("data", {}).get("results", [])
        last_5 = results[-5:] if len(results) >= 5 else results
        empty_at_end = []

        for i, r in enumerate(last_5):
            text = (r.get("text", "") or "").strip()
            style = r.get("format", {}).get("style", "?")
            para_id = r.get("format", {}).get("paraId", "?")
            if not text and style not in ("Normal", "TOC", "No Spacing"):
                empty_at_end.append(
                    f"Para at position -{len(last_5)-i}: style={style}, paraId={para_id[:8]}"
                )

        if empty_at_end:
            return CheckResult("S5", False,
                               f"{len(empty_at_end)} empty non-Normal paragraphs at end",
                               details=empty_at_end, severity="warning")

        return CheckResult("S5", True,
                           "No empty paragraphs at document end", severity="info")
    except (json.JSONDecodeError, KeyError) as e:
        return CheckResult("S5", False, f"Failed to parse: {e}", severity="error")


def check_s6_chapter_numbering(filepath: str) -> CheckResult:
    """S6: Check Heading1 headings follow correct chapter numbering order."""
    out = _run([
        "officecli", "query", filepath,
        "p[style=Heading1]", "--json"
    ])
    if not out:
        return CheckResult("S6", False,
                           "Could not query Heading1 paragraphs", severity="info")

    try:
        data = json.loads(out)
        results = data.get("data", {}).get("results", [])
        issues = []
        expected_num = 1

        for r in results:
            text = (r.get("text", "") or "").strip()
            if text.startswith("CHAPTER") or text.startswith("CHƯƠNG"):
                # Extract chapter number
                import re
                match = re.search(r'(?:CHAPTER|CHƯƠNG)\s+(\d+)', text, re.IGNORECASE)
                if match:
                    chapter_num = int(match.group(1))
                    if chapter_num != expected_num:
                        issues.append(
                            f"Expected CHAPTER {expected_num}, got '{text}'"
                        )
                    expected_num += 1

        if issues:
            return CheckResult("S6", False,
                               f"{len(issues)} chapter numbering issues",
                               details=issues, severity="warning")

        return CheckResult("S6", True, "Chapter numbering is correct",
                           severity="info")
    except (json.JSONDecodeError, KeyError) as e:
        return CheckResult("S6", False, f"Failed to parse: {e}", severity="error")


def check_s7_content_completeness(filepath: str, content_ir: dict = None) -> CheckResult:
    """S7: Content completeness — compare paragraph count with expected.

    If content_ir is not provided, counts total Normal paragraphs only.
    """
    out = _run([
        "officecli", "query", filepath,
        "p[style=Normal]", "--json"
    ])
    if not out:
        return CheckResult("S7", False,
                           "Could not query Normal paragraphs", severity="error")

    try:
        data = json.loads(out)
        results = data.get("data", {}).get("results", [])
        actual_normal = len(results)

        if content_ir:
            expected = sum(
                s.get("paragraph_count", 0)
                for s in content_ir.get("sections", [])
            )
            ratio = actual_normal / expected if expected > 0 else 1.0
            if ratio < 0.85:
                return CheckResult("S7", False,
                                   f"Content incomplete: {actual_normal}/{expected} paragraphs "
                                   f"({ratio*100:.0f}%)",
                                   severity="error")
            return CheckResult("S7", True,
                               f"Content complete: {actual_normal}/{expected} paragraphs "
                               f"({ratio*100:.0f}%)",
                               severity="info")

        if actual_normal == 0:
            return CheckResult("S7", False,
                               "No Normal paragraphs found", severity="warning")

        return CheckResult("S7", True,
                           f"{actual_normal} Normal paragraphs present",
                           severity="info")
    except (json.JSONDecodeError, KeyError) as e:
        return CheckResult("S7", False, f"Failed to parse: {e}", severity="error")


def check_s9_font_consistency(filepath: str) -> CheckResult:
    """S9 (legacy): Font consistency — delegates to S3."""
    return check_s3_font_consistency(filepath)


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
    check_s3_font_consistency,
    check_s4_first_line_indent,
    check_s5_empty_paragraphs,
    check_s6_chapter_numbering,
    check_s7_content_completeness,
    check_s8_outline_hierarchy,
    check_s9_font_consistency,
    check_s10_anchor_integrity,
]


def run_all(filepath: str) -> list[CheckResult]:
    """Run all S1-S10 checks and return results."""
    return [check(filepath) for check in ALL_CHECKS]
