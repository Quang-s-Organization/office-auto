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


# ── section context classification ─────────────────────────────────

_CONTEXT_PATTERNS = [
    (r"ACKNOWLEDGEMENTS?", "ACKNOWLEDGEMENTS"),
    (r"ABSTRACT", "ABSTRACT"),
    (r"TABLE\s+OF\s+CONTENTS", "TABLE OF CONTENTS"),
    (r"LIST\s+OF\s+ABBREVIATIONS?", "LIST OF ABBREVIATIONS"),
    (r"LIST\s+OF\s+TABLES?", "LIST OF TABLES"),
    (r"CHAPTER", "CHAPTER"),
    (r"INTRODUCTION", "INTRODUCTION"),
    (r"REFERENCES?", "REFERENCES"),
    (r"APPENDIX", "APPENDIX"),
    (r"SUPERVISOR", "SUPERVISOR"),
    (r"TÀI\s+LIỆU\s+THAM\s+KHẢO", "REFERENCES"),
    (r"CƠ\s+SỞ\s+LÝ\s+THUYẾT", "CHAPTER"),
    (r"PHƯƠNG\s+PHÁP", "CHAPTER"),
    (r"KẾT\s+QUẢ", "CHAPTER"),
    (r"KẾT\s+LUẬN", "CHAPTER"),
]


def classify_context(text: str) -> str:
    """Classify a heading into a section context based on its text."""
    for pattern, context in _CONTEXT_PATTERNS:
        if re.search(pattern, text.upper()):
            return context
    return "OTHER"


# ── prototype extraction ───────────────────────────────────────────

def _extract_proto(r: dict) -> StylePrototype:
    """Convert an officecli query result row into a StylePrototype."""
    fmt = r.get("format", {})
    para_id = fmt.get("paraId", "")
    style_raw = fmt.get("style", "Normal")
    # Normalize style name: "heading 1" -> "Heading1"
    style_name = style_raw.title().replace(" ", "")
    text = r.get("text", "")

    # Section context from text
    section_context = classify_context(text)

    # Effective properties
    eff_size = fmt.get("effective.size")
    eff_font = fmt.get("effective.font.ascii")
    bold = fmt.get("effective.bold")

    # Explicit properties (preferred over effective)
    explicit_size = fmt.get("markRPr.size") or fmt.get("size")
    explicit_font = fmt.get("font.ea")
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


# ── prototype selection ────────────────────────────────────────────

def _context_rank(context: str) -> int:
    """Rank section contexts: CHAPTER content > back/front matter."""
    if context in ("CHAPTER", "INTRODUCTION"):
        return 0  # Best — main content
    elif context == "REFERENCES":
        return 1
    elif context in ("ACKNOWLEDGEMENTS", "ABSTRACT"):
        return 2
    elif context in ("TABLE OF CONTENTS", "LIST OF ABBREVIATIONS", "LIST OF TABLES"):
        return 3
    elif context == "APPENDIX":
        return 4
    elif context == "SUPERVISOR":
        return 5
    return 6


def select_best_prototype(
    candidates: list[StylePrototype],
    preferred_context: str = "CHAPTER"
) -> StylePrototype | None:
    """Select the best prototype from a list of candidates.

    Heuristics (in priority order):
    1. Prefer candidates whose section_context matches preferred_context
    2. Prefer candidates with explicit_size (markRPr) over effective-only
    3. Prefer candidates with larger font size (CHAPTER headings > front matter)
    4. Fallback to first candidate
    """
    if not candidates:
        return None

    # Score each candidate (lower is better)
    def score(c: StylePrototype) -> int:
        s = 0
        # STRONG penalty for empty text (only for Normal style — body text)
        if c.style_name == "Normal" and not c.text.strip():
            s += 100
        # Context match: preferred_context gets 0, others get penalty
        ctx = c.section_context
        if ctx == preferred_context:
            s += 0
        elif ctx == "OTHER":
            s += 20
        else:
            s += 10 + _context_rank(ctx) * 2
        # Explicit props preferred
        if c.explicit_size:
            s -= 5
        # Parse size for sorting
        if c.effective_size:
            sz = c.effective_size
            num = float(re.sub(r'[^\d.]', '', sz)) if re.search(r'\d', sz) else 0
            # Prefer larger (CHAPTER = 16pt > ACKNOWLEDGEMENTS = 14pt)
            s -= num
        return s

    candidates_sorted = sorted(candidates, key=score)
    best = candidates_sorted[0]

    # Debug output
    print(f"[inspector] Best {best.style_name} prototype: '{best.text[:40]}' "
          f"(ctx={best.section_context}, size={best.effective_size}, "
          f"font={best.effective_font}, paraId={best.para_id})",
          file=sys.stderr)

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

def inspect_template(
    filepath: str,
    preferred_context: str = "CHAPTER"
) -> TemplateIR:
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

    # Select best prototype for each style (headings + body style)
    select_styles = list(styles_to_query)
    if body_style and body_style not in select_styles:
        select_styles.append(body_style)
    best_prototypes: dict[str, StylePrototype] = {}
    for style in select_styles:
        candidates = prototypes.get(style, [])
        best = select_best_prototype(candidates, preferred_context)
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
    parser.add_argument("--context", default="CHAPTER",
                        help="Preferred section context for prototype selection")
    args = parser.parse_args()

    if not os.path.exists(args.template):
        print(f"ERROR: Template not found: {args.template}", file=sys.stderr)
        sys.exit(1)

    ir = inspect_template(args.template, args.context)
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
