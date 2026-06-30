#!/usr/bin/env python3
"""Validation checks (v5) — verify output against the DISCOVERED Template IR.

No hardcoded font/size/indent. Expected formatting is read from
template.ir.json (best_prototypes), so the same checks work for any template.
Each check: fn(filepath, template_ir=None, content_ir=None) -> CheckResult.
"""

from __future__ import annotations
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import slots


@dataclass
class CheckResult:
    name: str
    passed: bool
    message: str
    details: list[str] = field(default_factory=list)
    severity: str = "error"  # error | warning | info


_ENV_NO_RESIDENT = None  # set lazily


def _run(cmd: list[str]) -> str:
    import os
    global _ENV_NO_RESIDENT
    if _ENV_NO_RESIDENT is None:
        _ENV_NO_RESIDENT = {**os.environ, "OFFICECLI_NO_AUTO_RESIDENT": "1"}
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60,
                           env=_ENV_NO_RESIDENT)
        return r.stdout.strip()
    except subprocess.TimeoutExpired:
        return ""


def _query(filepath: str, selector: str) -> list[dict]:
    out = _run(["officecli", "query", filepath, selector, "--json"])
    i = out.find("{")
    if i < 0:
        return []
    try:
        return json.loads(out[i:]).get("data", {}).get("results", [])
    except json.JSONDecodeError:
        return []


def _best(template_ir: Optional[dict], style: str) -> Optional[dict]:
    if not template_ir:
        return None
    return template_ir.get("best_prototypes", {}).get(style)


def _furniture(template_ir: Optional[dict], content_ir: Optional[dict],
               logical_ir: Optional[dict] = None) -> set:
    """Para IDs of preserved template furniture — formatting checks (S3/S4/S6)
    must judge the EMITTED content, not the template's own boilerplate (e.g. a
    footnote block with its own font/spacing). Empty when inputs are missing.

    Threads the SAME slot inputs the planner used (emitted tags +
    front_matter_strategy) so the validator's furniture set matches the build."""
    if not template_ir or not content_ir:
        return set()
    try:
        return slots.furniture_paraids(
            template_ir, content_ir,
            emitted_tags=slots.emitted_tags_from_logical(logical_ir),
            front_matter_strategy=(logical_ir or {}).get(
                "front_matter_strategy", "preserve"))
    except Exception:
        return set()


# ── S1: heading hierarchy order ────────────────────────────────────

def check_s1_heading_order(filepath, template_ir=None, content_ir=None, logical_ir=None) -> CheckResult:
    out = _run(["officecli", "view", filepath, "outline"])
    if not out:
        return CheckResult("S1", False, "Could not read outline", severity="error")
    issues, prev = [], 0
    for i, line in enumerate(out.split("\n")):
        for level in (1, 2, 3, 4, 5, 6):
            if f"(heading {level})" in line:
                if level > prev + 1 and prev > 0:
                    issues.append(f"line {i}: jump H{prev} -> H{level}")
                prev = level
                break
    if issues:
        return CheckResult("S1", False, f"{len(issues)} hierarchy jumps",
                           details=issues, severity="warning")
    return CheckResult("S1", True, "Heading hierarchy OK", severity="info")


# ── S2: OOXML schema validity ──────────────────────────────────────

def check_s2_schema_validity(filepath, template_ir=None, content_ir=None, logical_ir=None) -> CheckResult:
    out = _run(["officecli", "validate", filepath])
    if not out:
        return CheckResult("S2", False, "validate returned nothing", severity="error")
    if "no errors" in out.lower() or "passed" in out.lower():
        return CheckResult("S2", True, "Schema valid", severity="info")
    # any reported error
    return CheckResult("S2", False, out.split("\n")[0][:120],
                       details=out.split("\n")[1:6], severity="error")


# ── S3: font/size match DISCOVERED template prototypes ─────────────

def check_s3_font_size_vs_template(filepath, template_ir=None, content_ir=None, logical_ir=None) -> CheckResult:
    if not template_ir:
        return CheckResult("S3", True, "No template IR — skipped", severity="info")
    body_style = template_ir.get("body_style")
    styles = ["Heading1", "Heading2", "Heading3"] + ([body_style] if body_style else [])
    furn = _furniture(template_ir, content_ir, logical_ir)
    issues = []
    checked = 0
    for style in styles:
        bp = _best(template_ir, style)
        if not bp:
            continue
        exp_font = bp.get("effective_font")
        exp_size = bp.get("explicit_size") or bp.get("effective_size")
        for r in _query(filepath, f"p[style={style}]"):
            f = r.get("format", {})
            if not (r.get("text") or "").strip():
                continue
            if f.get("paraId") in furn:        # preserved template furniture
                continue
            checked += 1
            font = f.get("effective.font.ascii")
            size = f.get("effective.size") or f.get("size")
            if exp_font and font and font != exp_font:
                issues.append(f"{style}: font '{font}' != expected '{exp_font}'")
            if exp_size and size and size != exp_size:
                issues.append(f"{style}: size '{size}' != expected '{exp_size}'")
    if issues:
        return CheckResult("S3", False, f"{len(set(issues))} font/size mismatches vs template",
                           details=list(dict.fromkeys(issues))[:6], severity="warning")
    return CheckResult("S3", True, f"Font/size match template ({checked} paragraphs)",
                       severity="info")


# ── S4: first-line indent matches DISCOVERED body prototype ────────

def check_s4_first_line_indent(filepath, template_ir=None, content_ir=None, logical_ir=None) -> CheckResult:
    body_style = (template_ir or {}).get("body_style")
    bp = _best(template_ir, body_style) if body_style else None
    if not bp:
        return CheckResult("S4", True, "No body prototype — skipped", severity="info")
    expected = bp.get("ind_first_line")
    if not expected or expected in ("0", "0pt", "0cm"):
        return CheckResult("S4", True,
                           "Template body has no first-line indent — nothing to enforce",
                           severity="info")
    furn = _furniture(template_ir, content_ir, logical_ir)
    bad = []
    for r in _query(filepath, f"p[style={body_style}]"):
        if not (r.get("text") or "").strip():
            continue
        if r.get("format", {}).get("paraId") in furn:
            continue
        got = r.get("format", {}).get("ind.firstLine")
        if got != expected:
            bad.append(f"'{(r.get('text') or '')[:30]}' indent={got} (exp {expected})")
    if bad:
        return CheckResult("S4", False, f"{len(bad)} body paragraphs wrong indent",
                           details=bad[:5], severity="warning")
    return CheckResult("S4", True, f"Body first-line indent = {expected}", severity="info")


# ── S5: stray empty non-body paragraphs at end ─────────────────────

def check_s5_trailing_empties(filepath, template_ir=None, content_ir=None, logical_ir=None) -> CheckResult:
    rs = _query(filepath, "p")
    if not rs:
        return CheckResult("S5", False, "No paragraphs", severity="error")
    body_style = (template_ir or {}).get("body_style")
    keep = {body_style, "Normal", "TOC", "No Spacing", "Header", "Footer"}
    empty = [r for r in rs[-6:]
             if not (r.get("text") or "").strip()
             and r.get("format", {}).get("style") not in keep]
    if empty:
        return CheckResult("S5", True, f"{len(empty)} trailing empty paras (informational)",
                           severity="info")
    return CheckResult("S5", True, "No stray trailing empties", severity="info")


# ── S6: line-spacing rule parity vs DISCOVERED body format ─────────

def check_s6_line_spacing(filepath, template_ir=None, content_ir=None, logical_ir=None) -> CheckResult:
    """Body line spacing must match the template's discovered rule.

    Guards the failure where a fixed pt lineSpacing is re-applied as
    lineRule="exact": the line height locks (e.g. 1.3pt) and 13pt text
    collapses into overlapping black bars. The template used "atLeast"/"auto"
    (lines grow to fit), so an "exact" body rule is a hard rendering fault."""
    fmt = (template_ir or {}).get("body_format") or {}
    exp_rule = fmt.get("lineRule")
    exp_spacing = fmt.get("lineSpacing")
    if not exp_spacing:
        return CheckResult("S6", True, "No body line-spacing to enforce", severity="info")
    body_style = (template_ir or {}).get("body_style") or "Normal"
    furn = _furniture(template_ir, content_ir, logical_ir)
    bad, checked = [], 0
    for r in _query(filepath, f"p[style={body_style}]"):
        if not (r.get("text") or "").strip():
            continue
        f = r.get("format", {})
        if f.get("paraId") in furn:            # template furniture keeps its own spacing
            continue
        checked += 1
        rule = f.get("lineRule")
        # An "exact" rule on body prose crushes the text — always a fault here,
        # regardless of the template (no template body uses fixed exact spacing).
        if rule == "exact" and exp_rule != "exact":
            bad.append(f"'{(r.get('text') or '')[:30]}' lineRule=exact (exp {exp_rule})")
    if bad:
        return CheckResult("S6", False,
                           f"{len(bad)} body paragraphs use exact line height (text crush)",
                           details=bad[:5], severity="error")
    return CheckResult("S6", True,
                       f"Body line spacing OK ({checked} paragraphs, rule={exp_rule})",
                       severity="info")


# presentation (logical IR) -> heading style produced by the planner
_PRESENTATION_TO_STYLE = {
    "major_section": "Heading1",
    "minor_section": "Heading2",
    "sub_section": "Heading3",
}


def _emitted_tags(logical_ir) -> Optional[set]:
    """Tags of nodes the planner emits (intent != preserve/remove), or None."""
    if not logical_ir:
        return None
    return {s["node_id"] for s in logical_ir.get("sections", [])
            if s.get("intent") not in ("preserve", "remove")}


# ── S7: content completeness vs content IR ─────────────────────────

def check_s7_completeness(filepath, template_ir=None, content_ir=None, logical_ir=None) -> CheckResult:
    body_style = (template_ir or {}).get("body_style") or "Normal"
    actual = len([r for r in _query(filepath, f"p[style={body_style}]")
                  if (r.get("text") or "").strip()])
    if content_ir:
        emitted = _emitted_tags(logical_ir)
        secs = content_ir.get("sections", [])
        if emitted is not None:  # exclude preserved front matter
            secs = [s for s in secs if s.get("tag") in emitted]
        expected = sum(s.get("paragraph_count", 0) for s in secs)
        if expected and actual < 0.85 * expected:
            return CheckResult("S7", False,
                               f"Incomplete: {actual}/{expected} body paragraphs",
                               severity="error")
        return CheckResult("S7", True, f"Content complete: {actual}/{expected} body paragraphs",
                           severity="info")
    return CheckResult("S7", True if actual else False,
                       f"{actual} body paragraphs", severity="info" if actual else "warning")


# ── S8: heading count matches content IR ───────────────────────────

def check_s8_heading_counts(filepath, template_ir=None, content_ir=None, logical_ir=None) -> CheckResult:
    if not content_ir and not logical_ir:
        return CheckResult("S8", True, "No content IR — skipped", severity="info")
    exp = {"Heading1": 0, "Heading2": 0, "Heading3": 0}
    if logical_ir:
        # v6: expected style = planner's resolution of each EMITTED node's
        # presentation (accounts for preserve + outline shift).
        for s in logical_ir.get("sections", []):
            if s.get("intent") in ("preserve", "remove"):
                continue
            style = _PRESENTATION_TO_STYLE.get(s.get("presentation"))
            if style:
                exp[style] += 1
    else:
        for s in content_ir.get("sections", []):
            t = s.get("type")
            if t == "heading1": exp["Heading1"] += 1
            elif t == "heading2": exp["Heading2"] += 1
            elif t == "heading3": exp["Heading3"] += 1
    issues = []
    for style, e in exp.items():
        got = len([r for r in _query(filepath, f"p[style={style}]")
                   if (r.get("text") or "").strip()])
        if got != e:
            issues.append(f"{style}: {got} in doc != {e} expected")
    if issues:
        return CheckResult("S8", False, "Heading counts differ from source",
                           details=issues, severity="error")
    return CheckResult("S8", True, "Heading counts match source", severity="info")


# ── S9: template furniture survived the build ──────────────────────
# The backstop for the slot/furniture model: a build that destroys scaffolding
# (header/letterhead/signature tables, "Nơi nhận"/footnote blocks) must FAIL,
# not pass green. Recomputes the SAME slot/furniture split the planner used
# (slots.classify) and asserts every furniture paragraph + table is still in the
# output. Genre-agnostic — it compares discovered furniture, no hardcoded names.

def check_s9_furniture_survived(filepath, template_ir=None, content_ir=None,
                                logical_ir=None) -> CheckResult:
    if not template_ir or not content_ir:
        return CheckResult("S9", True, "No template/content IR — skipped", severity="info")
    cls = slots.classify(
        template_ir.get("body_sequence", []),
        template_ir.get("body_tables", []), content_ir,
        emitted_tags=slots.emitted_tags_from_logical(logical_ir),
        front_matter_strategy=(logical_ir or {}).get(
            "front_matter_strategy", "preserve"))
    exp_paras = {p for p in cls["furniture_paras"] if p}
    exp_tables = len(cls["furniture_tables"])
    if not exp_paras and not exp_tables:
        return CheckResult("S9", True, "Template has no furniture to preserve",
                           severity="info")
    present = {r.get("format", {}).get("paraId") for r in _query(filepath, "p")}
    missing = sorted(p for p in exp_paras if p not in present)
    got_tables = len([r for r in _query(filepath, "tbl")
                      if (r.get("path") or "").startswith("/body/tbl")])
    issues = []
    if missing:
        issues.append(f"{len(missing)} furniture paragraph(s) deleted: "
                      f"{', '.join(missing[:5])}")
    if got_tables < exp_tables:
        issues.append(f"furniture tables: {got_tables}/{exp_tables} survive "
                      f"({exp_tables - got_tables} deleted)")
    if issues:
        return CheckResult("S9", False, "Template furniture was destroyed",
                           details=issues, severity="error")
    return CheckResult("S9", True,
                       f"Furniture preserved ({len(exp_paras)} paras, {exp_tables} tables)",
                       severity="info")


ALL_CHECKS = [
    check_s1_heading_order,
    check_s2_schema_validity,
    check_s3_font_size_vs_template,
    check_s4_first_line_indent,
    check_s5_trailing_empties,
    check_s6_line_spacing,
    check_s7_completeness,
    check_s8_heading_counts,
    check_s9_furniture_survived,
]


def run_all(filepath, template_ir=None, content_ir=None, logical_ir=None) -> list[CheckResult]:
    # Every check now accepts logical_ir (formatting checks need it to compute the
    # same furniture set the planner used; S7-S9 already did) — pass it uniformly.
    return [c(filepath, template_ir, content_ir, logical_ir) for c in ALL_CHECKS]
