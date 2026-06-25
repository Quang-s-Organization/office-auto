#!/usr/bin/env python3
"""Template Inspector — Extracts structured Template IR from a DOCX template.

Usage:
    python3 tools/template_inspector.py <template.docx> [--out <output.json>]

Discovers all style prototypes (Heading1/2/3/Normal), classifies them by section
context, selects the best prototype for each style, and outputs a Template IR JSON.
"""

from __future__ import annotations
import argparse
import json
import re
import subprocess
import sys
import os

# Ensure we can import sibling modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from template_ir import StylePrototype, TemplateIR


# ── officecli wrapper ──────────────────────────────────────────────

def run_officecli(args: list[str], timeout: int = 30) -> dict:
    """Run an officecli command and parse JSON output."""
    cmd = ["officecli"] + args
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if r.returncode != 0:
            print(f"[inspector] WARN: officecli {' '.join(args)} failed: {r.stderr[:200]}",
                  file=sys.stderr)
            return {"success": False, "error": r.stderr[:200]}
        return json.loads(r.stdout)
    except json.JSONDecodeError as e:
        print(f"[inspector] WARN: JSON parse error: {e}", file=sys.stderr)
        return {"success": False, "error": str(e)}
    except subprocess.TimeoutExpired:
        print(f"[inspector] WARN: officecli timed out after {timeout}s", file=sys.stderr)
        return {"success": False, "error": "timeout"}


# Section context is classified STRUCTURALLY (by position in the body), not by
# matching hardcoded heading names. A prototype is "CONTENT" if it lives in the
# main content region (from the first heading to the last content paragraph) and
# "FRONT" otherwise. This works for any template / language.
CTX_CONTENT = "CONTENT"
CTX_FRONT = "FRONT"


# ── prototype extraction ───────────────────────────────────────────

def _extract_proto(r: dict) -> StylePrototype:
    """Convert an officecli query result row into a StylePrototype."""
    fmt = r.get("format", {})
    para_id = fmt.get("paraId", "")
    style_raw = fmt.get("style", "Normal")
    # Normalize style name: "heading 1" -> "Heading1"
    style_name = style_raw.title().replace(" ", "")
    text = r.get("text", "")

    # Section context is assigned later (structurally) in inspect_template.
    section_context = ""

    # Effective properties
    eff_size = fmt.get("effective.size")
    eff_font = fmt.get("effective.font.ascii")
    bold = fmt.get("effective.bold")

    # Explicit properties (preferred over effective).
    # Use Latin-script axes (ascii / hAnsi) for font, NOT font.ea (East Asian).
    # Vietnamese text is rendered via w:ascii + w:hAnsi; font.ea only affects CJK.
    explicit_size = fmt.get("markRPr.size") or fmt.get("size")
    explicit_font = fmt.get("font.ascii") or fmt.get("font.hAnsi")
    align = fmt.get("align")
    line_spacing = fmt.get("lineSpacing")
    space_before = fmt.get("effective.spaceBefore")
    space_after = fmt.get("effective.spaceAfter")

    # outlineLevel — may be missing, infer from style
    ol_raw = fmt.get("outlineLevel")
    if ol_raw is not None:
        outline_level = int(ol_raw)
    elif style_name == "Heading1":
        outline_level = 1
    elif style_name == "Heading2":
        outline_level = 2
    elif style_name == "Heading3":
        outline_level = 3
    else:
        outline_level = None

    ind_first = fmt.get("ind.firstLine")

    return StylePrototype(
        style_name=style_name,
        para_id=para_id,
        text=text,
        effective_size=explicit_size or eff_size,
        effective_font=explicit_font or eff_font,
        bold=bold,
        outline_level=outline_level,
        ind_first_line=ind_first,
        section_context=section_context,
        space_before=space_before,
        space_after=space_after,
        alignment=align,
        line_spacing=line_spacing,
        explicit_size=explicit_size,
        explicit_font=explicit_font,
    )


def query_prototypes(filepath: str, style: str) -> list[StylePrototype]:
    """Query ALL paragraphs of a given style from the template."""
    # Pattern: p[style=Heading1]
    pattern = f'p[style={style}]'
    result = run_officecli(["query", filepath, pattern, "--json"])
    if not result.get("success"):
        return []
    rows = result.get("data", {}).get("results", [])
    return [_extract_proto(r) for r in rows]


def get_outline(filepath: str) -> list[dict]:
    """Get the document outline as a list of {level, text, style}."""
    try:
        r = subprocess.run(
            ["officecli", "view", filepath, "outline"],
            capture_output=True, text=True, timeout=30
        )
        raw = r.stdout
    except subprocess.TimeoutExpired:
        print(f"[inspector] WARN: view outline timed out", file=sys.stderr)
        return []

    outline = []
    for line in raw.strip().split("\n"):
        # Pattern: "├── [N] "heading text" (style name)"  or
        #          "  ├── [N] "sub heading" (style name)"  (indented for sub-levels)
        m = re.match(
            r'[\s├└─]+\[(\d+)\]\s+"([^"]*)"\s+\(([^)]+)\)',
            line
        )
        if m:
            outline.append({
                "index": int(m.group(1)),
                "text": m.group(2).strip(),
                "style": m.group(3),
            })
    return outline


# ── prototype selection (structural, language-agnostic) ────────────

def select_best_prototype(candidates: list[StylePrototype]) -> "StylePrototype | None":
    """Pick the best prototype for a style.

    Priorities (lower score = better), all structural:
    1. Prefer a prototype that lives in the main CONTENT region (a real body
       heading) over one in the front matter (TOC/cover).
    2. Prefer non-empty text (a used example) over an empty placeholder.
    3. Prefer explicit (markRPr) sizing over inherited-only.
    """
    if not candidates:
        return None

    def score(c: StylePrototype) -> tuple:
        in_content = 0 if c.section_context == CTX_CONTENT else 1
        has_text = 0 if (c.text or "").strip() else 1
        explicit = 0 if c.explicit_size else 1
        return (in_content, has_text, explicit)

    best = sorted(candidates, key=score)[0]
    print(f"[inspector] Best {best.style_name} prototype: '{(best.text or '')[:40]}' "
          f"(ctx={best.section_context or '-'}, size={best.effective_size}, "
          f"font={best.effective_font}, paraId={best.para_id})", file=sys.stderr)
    return best


# ── body sequence discovery ────────────────────────────────────────

_HEADING_STYLES = {"Heading1", "Heading2", "Heading3"}


def get_body_sequence(filepath: str) -> list[dict]:
    """Return the ordered list of /body/p paragraphs with minimal metadata.

    Each entry: {para_id, style, has_text, is_heading, outline_level}.
    This is pure discovered state — the planner decides what to do with it.
    """
    result = run_officecli(["query", filepath, "p", "--json"])
    if not result.get("success"):
        return []
    seq = []
    for r in result.get("data", {}).get("results", []):
        fmt = r.get("format", {})
        style_raw = fmt.get("style")
        style = style_raw.title().replace(" ", "") if style_raw else None
        text = (r.get("text") or "").strip()
        ol = fmt.get("outlineLevel")
        seq.append({
            "para_id": fmt.get("paraId"),
            "style": style,
            "has_text": bool(text),
            "is_heading": style in _HEADING_STYLES,
            "outline_level": int(ol) if ol is not None and str(ol).isdigit() else None,
        })
    return seq


def discover_body_style(body_sequence: list[dict]) -> Optional[str]:
    """Discover the style used for body text within the content region.

    The content region starts at the first heading. Among non-heading
    paragraphs there that carry text, the most common style is the body
    style (e.g. 'Normalstyle'). No hardcoded style name assumed.
    """
    first_heading = next((i for i, p in enumerate(body_sequence) if p["is_heading"]), None)
    if first_heading is None:
        region = body_sequence
    else:
        region = body_sequence[first_heading:]
    from collections import Counter
    counts = Counter(
        p["style"] for p in region
        if not p["is_heading"] and p["has_text"] and p["style"]
    )
    if counts:
        return counts.most_common(1)[0][0]
    # Fallback: any non-heading style that exists as a prototype
    return None


# ── main entry point ───────────────────────────────────────────────

def _content_region_ids(body_sequence: list[dict]) -> set:
    """Para IDs in the main content region (first heading -> last content para)."""
    heading_idxs = [i for i, p in enumerate(body_sequence) if p.get("is_heading")]
    if not heading_idxs:
        return set()
    first = heading_idxs[0]
    last = first
    for i in range(first, len(body_sequence)):
        if body_sequence[i].get("is_heading") or body_sequence[i].get("has_text"):
            last = i
    return {body_sequence[i]["para_id"] for i in range(first, last + 1)
            if body_sequence[i].get("para_id")}


def inspect_template(filepath: str) -> TemplateIR:
    """Run full template inspection: query, classify, select, return TemplateIR."""
    abs_path = os.path.abspath(filepath)
    print(f"[inspector] Inspecting: {abs_path}", file=sys.stderr)

    # Get outline
    outline = get_outline(abs_path)
    print(f"[inspector] Outline: {len(outline)} sections", file=sys.stderr)

    # Query all style prototypes
    styles_to_query = ["Heading1", "Heading2", "Heading3", "Normal"]
    prototypes: dict[str, list[StylePrototype]] = {}
    for style in styles_to_query:
        candidates = query_prototypes(abs_path, style)
        prototypes[style] = candidates
        print(f"[inspector] {style}: {len(candidates)} candidates", file=sys.stderr)

    # Enrich outline entries with para_id from heading prototypes
    _heading_paras = {}
    for style in ["Heading1", "Heading2", "Heading3"]:
        for p in prototypes.get(style, []):
            if p.para_id and p.text:
                _heading_paras[p.text.strip().rstrip()] = p.para_id

    for entry in outline:
        txt = entry["text"].strip().rstrip()
        # Try exact match
        if txt in _heading_paras:
            entry["para_id"] = _heading_paras[txt]
        else:
            # Try prefix match for truncated titles
            for title, pid in _heading_paras.items():
                if txt and (title.startswith(txt) or txt.startswith(title[:min(len(txt), 10)])):
                    entry["para_id"] = pid
                    break


    # Collect all heading paraIds for outline verification
    all_heading_ids: list[str] = []
    for style in ["Heading1", "Heading2", "Heading3"]:
        for p in prototypes.get(style, []):
            if p.para_id:
                all_heading_ids.append(p.para_id)

    # Discover the ordered body sequence and the real body text style
    body_sequence = get_body_sequence(abs_path)
    body_style = discover_body_style(body_sequence)
    print(f"[inspector] Body: {len(body_sequence)} paragraphs, body_style={body_style}",
          file=sys.stderr)

    # Query the discovered body style as a prototype too (to read its props)
    if body_style and body_style not in prototypes:
        prototypes[body_style] = query_prototypes(abs_path, body_style)

    # Tag every prototype structurally: CONTENT (in main body region) vs FRONT
    region_ids = _content_region_ids(body_sequence)
    for plist in prototypes.values():
        for p in plist:
            p.section_context = CTX_CONTENT if p.para_id in region_ids else CTX_FRONT

    # Select best prototype for each style (headings + body style)
    select_styles = list(styles_to_query)
    if body_style and body_style not in select_styles:
        select_styles.append(body_style)
    best_prototypes: dict[str, StylePrototype] = {}
    for style in select_styles:
        candidates = prototypes.get(style, [])
        best = select_best_prototype(candidates)
        if best:
            best_prototypes[style] = best

    ir = TemplateIR(
        file_path=abs_path,
        prototypes=prototypes,
        outline=outline,
        best_prototypes=best_prototypes,
        all_heading_ids=all_heading_ids,
        body_sequence=body_sequence,
        body_style=body_style,
    )

    print(f"[inspector] Done. Best: {list(best_prototypes.keys())}", file=sys.stderr)
    return ir


def main():
    parser = argparse.ArgumentParser(
        description="Inspect a DOCX template and produce Template IR"
    )
    parser.add_argument("template", help="Path to template.docx")
    parser.add_argument("--out", "-o", default=None,
                        help="Output path for template.ir.json")
    args = parser.parse_args()

    if not os.path.exists(args.template):
        print(f"ERROR: Template not found: {args.template}", file=sys.stderr)
        sys.exit(1)

    ir = inspect_template(args.template)
    output = ir.to_json()

    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"[inspector] Written to {args.out}", file=sys.stderr)
    else:
        print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
