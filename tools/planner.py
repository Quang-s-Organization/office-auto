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
    return {"style": style_name}


def _heading_style_for(presentation: str) -> str:
    return PRESENTATION_TO_STYLE.get(presentation, "Heading1")


# ── batch program builder ──────────────────────────────────────────

def build_batch_program(
    intent_ir: IntentIR,
    content_ir: dict,
    template_ir: TemplateIR,
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

    def add_paragraph(props: dict, text: str):
        program.append({"command": "add", "parent": "/body", "type": "p",
                        "props": dict(props)})
        if text:
            program.append({"command": "add", "parent": "/body/p[last()]",
                            "type": "r", "props": {"text": text}})

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
            for para in content_sec.get("body_paragraphs", []):
                add_paragraph(body_props, para)
            continue

        add_paragraph(_props_for_style(template_ir, heading_style),
                      content_sec.get("title", ""))
        for para in content_sec.get("body_paragraphs", []):
            add_paragraph(body_props, para)

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
    parser.add_argument("--intent", required=True)
    parser.add_argument("--output", "-o", default="batch_program.json")
    args = parser.parse_args()

    intent = load_intent(args.intent)
    if intent is None:
        sys.exit(1)
    content_ir = _load_json(args.content, "content IR")
    template_ir = TemplateIR.from_json(_load_json(args.template_ir, "template IR"))

    print(f"[planner] Planning {len(intent.sections)} intent sections "
          f"(body_style={template_ir.body_style})...", file=sys.stderr)
    program = build_batch_program(intent, content_ir, template_ir)

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
