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
from block_specs import EmitCtx, emit_block
import slots


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
    # "preserve" (default, parity) keeps the template's pre-heading front matter;
    # "replace" removes it because the content supplies its own. Sourced from the
    # profile via logical.ir.json.
    front_matter_strategy: str = "preserve"


# strategy routing: clone-prototype (this planner) handles variable-length
# structured content. The alternative is officecli's native `merge` for
# fixed {{placeholder}} form templates — chosen by intent.strategy == "merge".
SUPPORTED_STRATEGIES = {"clone"}


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


# ── per-heading formatting (Issue #3: don't force one prototype on a style) ──
# A single style (e.g. Heading1) often carries per-paragraph formatting variants
# — a centred "DANH MỤC…" list title and left-aligned numbered chapters share the
# style yet differ in alignment. Picking ONE "best" prototype and stamping its
# props on every heading bakes that outlier in. Instead each emitted heading
# borrows the props of the TEMPLATE heading whose text it matches; headings with
# no template twin fall back to the style's REPRESENTATIVE (modal) formatting,
# not an arbitrary example. Both are discovered from the template — no hardcoding.

def _lcp_len(a: str, b: str) -> int:
    """Length of the longest common prefix of two strings."""
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def _match_heading_prototype(candidates: list, title: str):
    """Template prototype whose text best matches this heading title, or None.

    Exact normalized text wins; otherwise the prototype sharing the longest
    common prefix, accepted when that prefix is both ≥ 10 chars and ≥ half the
    shorter title — so a content "DANH MỤC CÁC HÌNH ẢNH" still inherits the
    template's centred "DANH MỤC CÁC BIỂU ĐỒ…, HÌNH ẢNH" list-heading format,
    while distinct chapters ("1. …" vs "2. …") never cross-match. Reuses slots'
    normalization so planner and slot classifier agree on what "same heading" is.
    """
    n = slots._norm(title)
    if len(n) < 3:
        return None
    exact = [c for c in candidates if slots._norm(c.text or "") == n]
    if exact:
        return exact[0]
    best, best_lcp = None, 0
    for c in candidates:
        cn = slots._norm(c.text or "")
        lcp = _lcp_len(n, cn)
        if lcp > best_lcp and lcp >= 10 and lcp >= 0.5 * min(len(n), len(cn)):
            best, best_lcp = c, lcp
    return best


def _representative_prototype(candidates: list):
    """The prototype carrying the style's MODAL alignment (so a lone centred
    outlier never wins), preferring a used (non-empty, explicitly-sized) one."""
    if not candidates:
        return None
    from collections import Counter
    modal_align = Counter((c.alignment or "") for c in candidates).most_common(1)[0][0]
    pool = [c for c in candidates if (c.alignment or "") == modal_align] or candidates
    pool = sorted(pool, key=lambda c: (
        0 if (c.text or "").strip() else 1, 0 if c.explicit_size else 1))
    return pool[0]


def _heading_props(template_ir: TemplateIR, style_name: str, title: str) -> dict:
    """Discovered SET-props for a heading, matched per-heading where possible."""
    candidates = template_ir.prototypes.get(style_name, [])
    content_cands = [c for c in candidates
                     if c.section_context == "CONTENT"] or candidates
    proto = (_match_heading_prototype(content_cands, title)
             or _representative_prototype(content_cands))
    if proto is not None:
        props = proto.build_props()
        props["style"] = style_name      # match may come from a co-styled variant
        return props
    return _props_for_style(template_ir, style_name)


# ── batch program builder ──────────────────────────────────────────

def build_batch_program(
    intent_ir: IntentIR,
    content_ir: dict,
    template_ir: TemplateIR,
    enforce_justify: bool = False,
) -> list[dict]:
    """Build the officecli batch array: remove slots, append content, move
    trailing furniture after it (see slots.py + docs design note)."""
    program: list[dict] = []

    # 1. Slot/furniture classification (genre-agnostic; preserve-by-default).
    # Remove only the paragraphs AND tables the content fills (the slot span);
    # every out-of-span paragraph/table (cover, TOC, letterhead, signature) is
    # furniture and is kept. `emitted_tags` keeps preserve-marked sections from
    # defining slots; `front_matter_strategy` controls the pre-span front region.
    emitted_tags = {s.node_id for s in intent_ir.sections
                    if s.intent in (INTENT_REPLACE, INTENT_INSERT)}
    cls = slots.classify(template_ir.body_sequence, template_ir.body_tables,
                         content_ir, emitted_tags=emitted_tags,
                         front_matter_strategy=intent_ir.front_matter_strategy)
    for pid in cls["slots"]:
        program.append({"command": "remove", "path": f"/body/p[@paraId={pid}]"})
    # In-span example/placeholder tables: remove by positional index. Highest
    # index first so each removal never shifts a not-yet-removed lower index.
    # Front/trailing tables keep their relative order, so the trailing-move
    # arithmetic below (kept_tables_before_trailing + 1) stays valid afterwards.
    for tbl_index in sorted(cls["slot_tables"], reverse=True):
        program.append({"command": "remove", "path": f"/body/tbl[{tbl_index}]"})

    # 2. Append new content (reconstruction model)
    content_sections = {s["tag"]: s for s in content_ir.get("sections", [])}
    # Body formatting: prefer the DISCOVERED body_format (direct font/size/align,
    # works even when body paragraphs have no explicit style name); fall back to
    # the named-style prototype only when body_format is unavailable.
    if template_ir.body_format:
        body_props = dict(template_ir.body_format)
        # Always carry a style name (every paragraph needs one); the discovered
        # direct font/size override whatever that style defines, so falling back
        # to "Normal" when no distinct body style exists is safe.
        body_props["style"] = template_ir.body_style or "Normal"
    else:
        body_style = template_ir.body_style or "Normal"
        body_props = _props_for_style(template_ir, body_style)
    # Optional Vietnamese-thesis policy: justify body text (opt-in, not hardcoded).
    if enforce_justify:
        body_props = {**body_props, "align": "both"}

    # Run-level body formatting (size/font). Needed when the body style does not
    # itself define size/font (style-less templates) — a run inherits from its
    # STYLE, not the paragraph mark. Derived from the discovered body_format;
    # empty for styled templates so their runs inherit the named style (parity).
    body_run_props: dict = {}
    if template_ir.body_format:
        if template_ir.body_format.get("size"):
            body_run_props["size"] = template_ir.body_format["size"]
        font = template_ir.body_format.get("font.ascii")
        if font:
            body_run_props["font.latin"] = font

    # All per-kind run/block emission lives in block_specs (the BlockSpec
    # registry). The planner owns only headings + body dispatch via the shared
    # EmitCtx, so a new content element is one BlockSpec, not a planner edit.
    ctx = EmitCtx(program=program, body_props=body_props, run_props=body_run_props)
    add_paragraph = ctx.add_paragraph

    def emit_body(content_sec: dict):
        """Prefer structured body_blocks (runs + tables); fall back to plain."""
        blocks = content_sec.get("body_blocks")
        if blocks is not None:
            for blk in blocks:
                emit_block(blk, ctx)
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

        # Heading runs inherit size/font from the heading style → no run_props.
        # Props are matched per-heading (see _heading_props) so a centred list
        # title and a left numbered chapter keep their own template alignment.
        add_paragraph(_heading_props(template_ir, heading_style,
                                     content_sec.get("title", "")),
                      content_sec.get("title", ""), run_props={})
        emit_body(content_sec)

    # 3. Re-order TRAILING furniture after the appended content. Content was
    # appended to /body end (the only place where `/body/p[last()]` reliably
    # targets the new paragraph — see docs/batch-contract.md §3a), so furniture
    # that must sit AFTER the content (signature block, "Nơi nhận", footnotes)
    # is now ahead of it. Move each trailing element to just BEFORE the body's
    # final `sectPr` (NOT `to=/body`, which appends AFTER the sectPr → invalid
    # OOXML). Moving in document order restores [lead furniture][content]
    # [trailing furniture] with the sectPr still last. Emitted AFTER all adds, so
    # they never perturb `p[last()]` during the build. A trailing table is always
    # at index (kept-tables-before-trailing + 1): each prior trailing table moved
    # out vacates that slot for the next one.
    tbl_src = cls["kept_tables_before_trailing"] + 1
    for elem in cls["trailing"]:
        if elem["kind"] == "p":
            program.append({"command": "move",
                            "path": f"/body/p[@paraId={elem['para_id']}]",
                            "before": "/body/sectPr"})
        else:
            program.append({"command": "move",
                            "path": f"/body/tbl[{tbl_src}]",
                            "before": "/body/sectPr"})

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
        front_matter_strategy=data.get("front_matter_strategy", "preserve"),
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

    import contracts
    content_ir = contracts.load_and_validate(args.content, "content.ir", "content IR")
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
    moves = sum(1 for op in program if op["command"] == "move")
    adds_p = sum(1 for op in program if op["command"] == "add" and op.get("type") == "p")
    adds_r = sum(1 for op in program if op["command"] == "add" and op.get("type") == "r")
    print(f"[planner] Wrote {args.output}: {len(program)} ops "
          f"({removes} remove, {adds_p} paragraphs, {adds_r} runs, "
          f"{moves} furniture moves)", file=sys.stderr)


if __name__ == "__main__":
    main()
