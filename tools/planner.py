#!/usr/bin/env python3
"""Deterministic Planner (v5) — Semantic Intent → officecli batch program.

LLM produces only intent.json (semantic). This planner resolves it into a
`batch_program.json`: a single officecli `batch` array that the composer
executes in one open/save cycle.

Build model (see docs/batch-contract.md, verified Phase 0):
  1. remove the template's placeholder content region (first heading → last
     content paragraph), keeping front matter + trailing section paragraphs;
  2. APPEND new content to /body end via reconstruction
     (`add p {discovered props}` then `add r {text}`), so `/body/p[last()]`
     reliably targets the just-added paragraph.

All formatting props come from the DISCOVERED Template IR best_prototypes —
no hardcoded font/size/indent.

Usage:
    python3 tools/planner.py \\
        --template-ir .cache/template.ir.json \\
        --content content.ir.json \\
        --intent intent.json \\
        --output batch_program.json
"""

from __future__ import annotations
import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from template_ir import TemplateIR, StylePrototype


# ── Intent vocabulary ─────────────────────────────────────────────
INTENT_REPLACE = "replace"
INTENT_INSERT = "insert"
INTENT_PRESERVE = "preserve"
INTENT_REMOVE = "remove"

# presentation → heading style name (body_text resolves to discovered body_style)
PRESENTATION_TO_STYLE = {
    "major_section": "Heading1",
    "minor_section": "Heading2",
    "sub_section": "Heading3",
    "appendix": "Heading1",
}


@dataclass
class IntentSection:
    node_id: str
    intent: str
    presentation: str
    target_context: Optional[str] = None


@dataclass
class IntentIR:
    sections: list[IntentSection]
    initial_preserved: Optional[str] = None
    body_prototype: str = "body_text"
    strategy: str = "clone"   # "clone" (reconstruction, implemented) | "merge"


# strategy routing: clone-prototype (this planner) handles variable-length
# structured content. The alternative is officecli's native `merge` for
# fixed {{placeholder}} form templates — chosen by intent.strategy == "merge".
SUPPORTED_STRATEGIES = {"clone"}


# ── content-region detection (policy lives here, not in the inspector) ──

def compute_removable_ids(body_sequence: list[dict]) -> list[str]:
    """Para IDs of the placeholder content region to delete.

    Region = from the first heading paragraph through the last paragraph
    that is a heading or carries text. Front matter (before the first
    heading) and trailing empty section paragraphs are preserved.
    """
    heading_idxs = [i for i, p in enumerate(body_sequence) if p.get("is_heading")]
    if not heading_idxs:
        return []
    first = heading_idxs[0]
    last = first
    for i in range(first, len(body_sequence)):
        p = body_sequence[i]
        if p.get("is_heading") or p.get("has_text"):
            last = i
    return [
        body_sequence[i]["para_id"]
        for i in range(first, last + 1)
        if body_sequence[i].get("para_id")
    ]


# ── prop resolution from discovered Template IR ────────────────────

def _props_for_style(template_ir: TemplateIR, style_name: Optional[str]) -> dict:
    """Discovered SET-props for a style, from best_prototypes. No hardcoding."""
    if not style_name:
        return {}
    proto = template_ir.best_prototypes.get(style_name)
    if proto is not None:
        return proto.build_props()
    # Heading3 fallback: borrow Heading2 props (font/size) if available,
    # keeping style=Heading3 so Word's outline structure is preserved.
    if style_name == "Heading3":
        fallback = template_ir.best_prototypes.get("Heading2")
        if fallback:
            props = fallback.build_props()
            props["style"] = "Heading3"
            return props
    return {"style": style_name}


def _heading_style_for(presentation: str) -> str:
    return PRESENTATION_TO_STYLE.get(presentation, "Heading1")


# ── batch program builder ──────────────────────────────────────────

def build_batch_program(
    intent_ir: IntentIR,
    content_ir: dict,
    template_ir: TemplateIR,
    enforce_justify: bool = False,
) -> list[dict]:
    """Build the officecli batch array (remove region + append content)."""
    program: list[dict] = []

    # 1. Remove the placeholder content region
    for pid in compute_removable_ids(template_ir.body_sequence):
        program.append({"command": "remove", "path": f"/body/p[@paraId={pid}]"})

    # 2. Append new content (reconstruction model)
    content_sections = {s["tag"]: s for s in content_ir.get("sections", [])}
    body_style = template_ir.body_style or "Normal"
    body_props = _props_for_style(template_ir, body_style)
    # Optional Vietnamese-thesis policy: justify body text (opt-in, not hardcoded).
    if enforce_justify:
        body_props = {**body_props, "align": "both"}

    def _emit_runs(parent_path: str, runs, mono: bool = False):
        """Emit one `add r` per styled span (markdown emphasis -> bold/italic/
        superscript). `runs` is a plain string (single run) or a list of
        {text, bold, italic, sup, sub} spans. Empty spans are dropped.
        `mono=True` forces Courier New (code) and skips emphasis."""
        if isinstance(runs, str):
            runs = [{"text": runs}] if runs else []
        for r in runs:
            text = r.get("text", "")
            if not text:
                continue
            props = {"text": text}
            if mono:
                props["font.latin"] = "Courier New"
            else:
                if r.get("bold"):
                    props["bold"] = True
                if r.get("italic"):
                    props["italic"] = True
                if r.get("sup"):
                    props["vertAlign"] = "superscript"
                elif r.get("sub"):
                    props["vertAlign"] = "subscript"
            program.append({"command": "add", "parent": parent_path,
                            "type": "r", "props": props})

    def add_paragraph(props: dict, runs, mono: bool = False):
        program.append({"command": "add", "parent": "/body", "type": "p",
                        "props": dict(props)})
        _emit_runs("/body/p[last()]", runs, mono=mono)

    def emit_table(block: dict):
        """Build a real Word table. `add table {colWidths}` seeds one empty
        row; each `add row` auto-creates N grid cells. Cells are filled by
        adding runs to the cell's auto-created paragraph (tc[k]/p[last()])."""
        ncols = max(1, block.get("ncols", 1))
        col_w = max(1200, int(9000 / ncols))
        col_widths = ",".join([str(col_w)] * ncols)
        program.append({"command": "add", "parent": "/body", "type": "table",
                        "props": {"colWidths": col_widths}})
        for ri, row in enumerate(block.get("rows", [])):
            if ri > 0:                       # row 0 reuses the seeded default row
                program.append({"command": "add", "parent": "/body/tbl[last()]",
                                "type": "row", "props": {}})
            for ci in range(ncols):
                cell = row[ci] if ci < len(row) else []
                _emit_runs(f"/body/tbl[last()]/tr[last()]/tc[{ci + 1}]/p[last()]", cell)

    def emit_code(block: dict):
        """One paragraph per source line, runs forced to Courier New (raw text,
        no markdown tokenization — preserves `_`/`*` in identifiers)."""
        for line in block.get("lines", []):
            add_paragraph(body_props, [{"text": line}] if line else [{"text": " "}],
                          mono=True)

    def emit_equation(block: dict):
        """Display equation -> oMathPara via `add type=equation`. The LaTeX
        formula (\\tag stripped by the parser) is parsed into OMML by officecli."""
        mode = block.get("mode", "display")
        program.append({"command": "add", "parent": "/body", "type": "equation",
                        "props": {"formula": block.get("formula", ""), "mode": mode}})

    def emit_list(block: dict):
        """Native Word numbering: one paragraph per item with listStyle. A
        non-list block between two lists stops officecli auto-joining them."""
        list_style = "ordered" if block.get("ordered") else "bullet"
        for item in block.get("items", []):
            add_paragraph({**body_props, "listStyle": list_style}, item)

    def emit_callout(block: dict):
        """Didactic callout: keep the bold label, indent the block. The current
        template ships no didactic paragraph style, so this is direct format."""
        add_paragraph({**body_props, "leftIndent": "360"}, block.get("runs", []))

    def emit_blocks(blocks: list[dict]):
        for blk in blocks:
            kind = blk.get("kind")
            if kind == "table":
                emit_table(blk)
            elif kind == "code":
                emit_code(blk)
            elif kind == "equation":
                emit_equation(blk)
            elif kind == "list":
                emit_list(blk)
            elif kind == "callout":
                emit_callout(blk)
            else:
                add_paragraph(body_props, blk.get("runs") or blk.get("text", ""))

    def emit_body(content_sec: dict):
        """Prefer structured body_blocks (runs + tables); fall back to plain."""
        blocks = content_sec.get("body_blocks")
        if blocks is not None:
            emit_blocks(blocks)
        else:
            for para in content_sec.get("body_paragraphs", []):
                add_paragraph(body_props, para)

    for sec in intent_ir.sections:
        if sec.intent in (INTENT_PRESERVE, INTENT_REMOVE):
            continue
        content_sec = content_sections.get(sec.node_id)
        if not content_sec:
            print(f"[planner] WARN: intent node '{sec.node_id}' not in content IR",
                  file=sys.stderr)
            continue

        heading_style = _heading_style_for(sec.presentation)
        if sec.presentation == "body_text":
            # rare: a body-only node
            emit_body(content_sec)
            continue

        add_paragraph(_props_for_style(template_ir, heading_style),
                      content_sec.get("title", ""))
        emit_body(content_sec)

    return program


# ── loaders ─────────────────────────────────────────────────────────

def load_intent(path: str) -> Optional[IntentIR]:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[planner] ERROR: Cannot load intent: {e}", file=sys.stderr)
        return None
    sections = [
        IntentSection(
            node_id=s.get("node_id", ""),
            intent=s.get("intent", "insert"),
            presentation=s.get("presentation", "body_text"),
            target_context=s.get("target_context"),
        )
        for s in data.get("sections", [])
    ]
    return IntentIR(
        sections=sections,
        initial_preserved=data.get("initial_preserved"),
        body_prototype=data.get("body_prototype", "body_text"),
        strategy=data.get("strategy", "clone"),
    )


def _load_json(path: str, label: str):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[planner] ERROR: Cannot load {label}: {e}", file=sys.stderr)
        sys.exit(1)


# ── CLI ───────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Planner v5 — Semantic Intent → officecli batch program"
    )
    parser.add_argument("--template-ir", required=True)
    parser.add_argument("--content", required=True)
    parser.add_argument("--logical",
                        help="logical.ir.json (v6 three-tier flow; preferred). "
                             "Superset of intent.json — planner reads the same "
                             "node_id/intent/presentation fields.")
    parser.add_argument("--intent",
                        help="intent.json (legacy v5 flow; used if --logical absent)")
    parser.add_argument("--output", "-o", default="batch_program.json")
    parser.add_argument("--enforce-justify", action="store_true",
                        help="Apply align=both to body text (Vietnamese-thesis policy; opt-in)")
    args = parser.parse_args()

    intent_path = args.logical or args.intent
    if not intent_path:
        print("[planner] ERROR: provide --logical (v6) or --intent (legacy)",
              file=sys.stderr)
        sys.exit(1)
    intent = load_intent(intent_path)
    if intent is None:
        sys.exit(1)
    if intent.strategy not in SUPPORTED_STRATEGIES:
        print(f"[planner] ERROR: strategy '{intent.strategy}' not implemented by the "
              f"planner. For fixed {{{{placeholder}}}} templates use `officecli merge` "
              f"directly. Implemented: {sorted(SUPPORTED_STRATEGIES)}", file=sys.stderr)
        sys.exit(2)

    content_ir = _load_json(args.content, "content IR")
    template_ir = TemplateIR.from_json(_load_json(args.template_ir, "template IR"))

    print(f"[planner] Planning {len(intent.sections)} intent sections "
          f"(body_style={template_ir.body_style})...", file=sys.stderr)
    program = build_batch_program(intent, content_ir, template_ir,
                                  enforce_justify=args.enforce_justify)

    out_dir = os.path.dirname(args.output)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(program, f, ensure_ascii=False, indent=2)

    removes = sum(1 for op in program if op["command"] == "remove")
    adds_p = sum(1 for op in program if op["command"] == "add" and op["type"] == "p")
    adds_r = sum(1 for op in program if op["command"] == "add" and op["type"] == "r")
    print(f"[planner] Wrote {args.output}: {len(program)} ops "
          f"({removes} remove, {adds_p} paragraphs, {adds_r} runs)", file=sys.stderr)


if __name__ == "__main__":
    main()
