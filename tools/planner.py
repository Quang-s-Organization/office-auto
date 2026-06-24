#!/usr/bin/env python3
"""Deterministic Planner — Converts Semantic Intent → Execution Plan.

This is the core architectural innovation of v4:
- LLM outputs ONLY semantic intent (intent.json) — no paraIds, no cleanup_ids
- Planner (pure Python, deterministic) resolves intent → execution plan
- Composer reads the execution plan (same mapping_table.json format)

Usage:
    python3 tools/planner.py \\
        --template-ir .cache/template.ir.json \\
        --content content.ir.json \\
        --intent intent.json \\
        --output mapping_table.json

Input:  intent.json (LLM output, semantic only)
Output: mapping_table.json (execution plan, ready for composer)
"""

from __future__ import annotations
import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Optional


# ── Semantic Roles ────────────────────────────────────────────────

# These are the ONLY concepts the LLM needs to understand
INTENT_PRESERVE = "preserve"      # Keep template section as-is
INTENT_REPLACE = "replace"         # Replace template section with content
INTENT_INSERT = "insert"           # Insert new content (no template target)
INTENT_REMOVE = "remove"           # Delete template element

# Presentation intents — map to style prototypes
PRESENTATION_MAJOR_SECTION = "major_section"    # → Heading1
PRESENTATION_MINOR_SECTION = "minor_section"    # → Heading2
PRESENTATION_SUB_SECTION = "sub_section"        # → Heading3
PRESENTATION_BODY_TEXT = "body_text"            # → Normal
PRESENTATION_APPENDIX = "appendix"              # → Appendix style
PRESENTATION_QUOTE = "quote"                    # → Quote style

# Default presentation → prototype mapping
DEFAULT_PRESENTATION_MAP = {
    PRESENTATION_MAJOR_SECTION: "Heading1",
    PRESENTATION_MINOR_SECTION: "Heading2",
    PRESENTATION_SUB_SECTION: "Heading3",
    PRESENTATION_BODY_TEXT: "Normal",
    PRESENTATION_APPENDIX: "Heading1",     # Fallback — appendix sections use Heading1
    PRESENTATION_QUOTE: "Normal",          # Fallback — quotes use Normal style
}


@dataclass
class IntentSection:
    """One content node's semantic intent — the ONLY thing LLM produces."""
    node_id: str                # "h1_1", "h2_1_1", etc.
    intent: str                 # "preserve" | "replace" | "insert" | "remove"
    presentation: str           # "major_section" | "minor_section" | ...
    target_context: Optional[str] = None  # Optional: explicit template section context


@dataclass
class IntentIR:
    """Complete semantic intent — LLM's entire output for the pipeline."""
    initial_preserved: str              # section_context to anchor after ("ACKNOWLEDGEMENTS")
    sections: list[IntentSection]
    preserve_contexts: list[str] = field(
        default_factory=lambda: [
            "ACKNOWLEDGEMENTS", "ABSTRACT", "TABLE OF CONTENTS",
            "LIST OF ABBREVIATIONS", "LIST OF TABLES",
            "SUPERVISOR", "APPENDIX",
        ]
    )
    body_prototype: str = "Normal"       # Style to use for body paragraphs


# ── Planner Logic ─────────────────────────────────────────────────

def find_prototype_for_presentation(
    template_ir: dict,
    presentation: str,
    style_map: Optional[dict] = None,
) -> Optional[str]:
    """Find the best prototype paraId for a given presentation intent.

    Uses the style_map to resolve presentation → style name,
    then finds the best prototype for that style in template IR.
    """
    if style_map is None:
        style_map = DEFAULT_PRESENTATION_MAP

    style_name = style_map.get(presentation)
    if not style_name:
        return None

    # Check best_prototypes first
    best = template_ir.get("best_prototypes", {}).get(style_name)
    if best:
        return best.get("para_id")

    # Fallback: check all prototypes
    candidates = template_ir.get("prototypes", {}).get(style_name, [])
    if candidates:
        return candidates[0].get("para_id")

    return None


def find_section_anchor(
    template_ir: dict,
    target_context: str,
) -> Optional[str]:
    """Find the paraId to anchor after for a given template section context.

    The anchor is the last paragraph of the element BEFORE the target section.
    This is typically the last heading of the previous section.
    """
    outline = template_ir.get("outline", [])

    # Find target section in outline
    target_idx = None
    for i, entry in enumerate(outline):
        ctx = entry.get("section_context", entry.get("text", "")).upper()
        if target_context.upper() in ctx:
            target_idx = i
            break

    if target_idx is None:
        return None

    # Anchor = paraId of the element just before the target section
    if target_idx > 0:
        return outline[target_idx - 1].get("para_id")

    # If target is the first section, return the section's own first para as anchor
    return outline[0].get("para_id") if outline else None


def determine_cleanup_ids(
    template_ir: dict,
    intent_sections: list[IntentSection],
    preserve_contexts: list[str],
) -> list[str]:
    """Determine which template paragraphs to remove.

    Strategy:
    - Remove all template sections that are marked REPLACE by intent
    - Keep all sections in preserve_contexts
    - Remove placeholder paragraphs (empty headings with no content)
    - Remove sections whose intent is "remove"
    """
    cleanup = set()
    remove_contexts = set()
    replace_contexts = set()

    for sec in intent_sections:
        if sec.intent == INTENT_REMOVE:
            remove_contexts.add(sec.target_context or "")
        elif sec.intent == INTENT_REPLACE:
            replace_contexts.add(sec.target_context or "")

    # Collect all heading IDs from replace/remove sections
    outline = template_ir.get("outline", [])
    all_heading_ids = template_ir.get("all_heading_ids", [])

    for entry in outline:
        text = entry.get("text", "")
        para_id = entry.get("para_id", "")
        if not para_id:
            continue

        # Check if this section should be removed or replaced
        should_remove = False
        for ctx in remove_contexts:
            if ctx and ctx.upper() in text.upper():
                should_remove = True
                break
        if not should_remove:
            for ctx in replace_contexts:
                if ctx and ctx.upper() in text.upper():
                    should_remove = True
                    break

        # Never remove preserved sections
        for preserved in preserve_contexts:
            if preserved.upper() in text.upper():
                should_remove = False
                break

        if should_remove:
            cleanup.add(para_id)

    # Also add all heading IDs from replace/remove contexts
    for pid in all_heading_ids:
        if pid in cleanup:
            continue
        # Add heading IDs that belong to a replace context
        # (the outline may not have all paraIds)
        pass

    return list(cleanup)


def determine_pre_clone(
    template_ir: dict,
    cleanup_ids: list[str],
    presentation_map: dict,
) -> dict[str, str]:
    """Determine which prototypes need to be cloned before cleanup.

    If a prototype's paraId will be removed by cleanup, it must be
    pre-cloned into a safe area to serve as a clone source.
    """
    cleanup_set = set(cleanup_ids)
    all_best_prototypes = template_ir.get("best_prototypes", {})

    pre_clone = {}
    for style_name, proto in all_best_prototypes.items():
        para_id = proto.get("para_id", "")
        if para_id in cleanup_set:
            pre_clone[style_name] = para_id

    return pre_clone


def build_execution_plan(
    intent_ir: IntentIR,
    content_ir: dict,
    template_ir: dict,
) -> dict:
    """Convert Semantic Intent IR → Execution Plan (mapping_table.json).

    This is the core planning logic — entirely deterministic, no LLM involved.
    """
    # 1. Build style map from presentation defaults
    style_map = dict(DEFAULT_PRESENTATION_MAP)

    # 2. Find initial anchor — paraId of the preserved section before content
    initial_anchor_id = find_section_anchor(template_ir, intent_ir.initial_preserved)
    if not initial_anchor_id:
        # Fallback: use the first outline entry's paraId
        outline = template_ir.get("outline", [])
        if outline:
            initial_anchor_id = outline[0].get("para_id", "")
        else:
            initial_anchor_id = ""

    # 3. Determine cleanup IDs
    cleanup_ids = determine_cleanup_ids(
        template_ir, intent_ir.sections, intent_ir.preserve_contexts
    )

    # 4. Determine pre_clone needs
    pre_clone = determine_pre_clone(template_ir, cleanup_ids, style_map)

    # 5. Build entries
    content_sections = {s["tag"]: s for s in content_ir.get("sections", [])}
    entries = []

    for sec in intent_ir.sections:
        if sec.intent == INTENT_PRESERVE or sec.intent == INTENT_REMOVE:
            continue  # Skip — handled by cleanup/preserve logic

        content_sec = content_sections.get(sec.node_id)
        if not content_sec:
            continue

        prototype_style = style_map.get(sec.presentation, "Normal")
        body_style = intent_ir.body_prototype

        entry = {
            "content_tag": sec.node_id,
            "heading_text": content_sec.get("title", ""),
            "prototype": prototype_style,
            "body_prototype": body_style,
            "body_paragraphs": content_sec.get("body_paragraphs", []),
            "ooxml_overrides": {},
        }

        # Apply presentation-specific overrides
        if sec.presentation == PRESENTATION_APPENDIX:
            entry["ooxml_overrides"] = {"outlineLevel": "6"}  # Appendix level

        entries.append(entry)

    # 6. Build the execution plan
    plan = {
        "initial_anchor": initial_anchor_id,
        "cleanup_ids": cleanup_ids,
        "entries": entries,
    }

    if pre_clone:
        plan["pre_clone"] = pre_clone

    return plan


def load_intent(path: str) -> Optional[IntentIR]:
    """Load intent.json and parse into IntentIR."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[planner] ERROR: Cannot load intent: {e}", file=sys.stderr)
        return None

    sections = []
    for sec in data.get("sections", []):
        sections.append(IntentSection(
            node_id=sec.get("node_id", ""),
            intent=sec.get("intent", "insert"),
            presentation=sec.get("presentation", "body_text"),
            target_context=sec.get("target_context"),
        ))

    return IntentIR(
        initial_preserved=data.get("initial_preserved", "ACKNOWLEDGEMENTS"),
        sections=sections,
        preserve_contexts=data.get(
            "preserve_contexts",
            ["ACKNOWLEDGEMENTS", "ABSTRACT", "TABLE OF CONTENTS",
             "LIST OF ABBREVIATIONS", "LIST OF TABLES",
             "SUPERVISOR", "APPENDIX"],
        ),
        body_prototype=data.get("body_prototype", "Normal"),
    )


# ── CLI ───────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Deterministic Planner — converts Semantic Intent → Execution Plan"
    )
    parser.add_argument("--template-ir", required=True,
                        help="Path to template.ir.json")
    parser.add_argument("--content", required=True,
                        help="Path to content.ir.json")
    parser.add_argument("--intent", required=True,
                        help="Path to intent.json (LLM semantic output)")
    parser.add_argument("--output", "-o", default="mapping_table.json",
                        help="Output execution plan path")
    parser.add_argument("--validate", action="store_true",
                        help="Run plan validation after generation")
    args = parser.parse_args()

    # Load inputs
    intent = load_intent(args.intent)
    if intent is None:
        sys.exit(1)

    try:
        with open(args.content, encoding="utf-8") as f:
            content_ir = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[planner] ERROR: Cannot load content IR: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(args.template_ir, encoding="utf-8") as f:
            template_ir = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[planner] ERROR: Cannot load template IR: {e}", file=sys.stderr)
        sys.exit(1)

    # Generate execution plan
    print(f"[planner] Planning with {len(intent.sections)} intent sections...",
          file=sys.stderr)

    plan = build_execution_plan(intent, content_ir, template_ir)

    # Optional: run plan validation
    if args.validate:
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from plan_validator import validate_plan, ALL_CHECKS as VALID_CHECKS

            results = []
            for check in VALID_CHECKS:
                sig = check.__code__.co_varnames[:check.__code__.co_argcount]
                if "content_ir" in sig and "template_ir" in sig:
                    r = check(plan, template_ir, content_ir)
                elif "template_ir" in sig:
                    r = check(plan, template_ir)
                elif "content_ir" in sig:
                    r = check(plan, content_ir)
                else:
                    r = check(plan)
                results.append(r)

            failures = [r for r in results if not r.passed]
            if failures:
                print(f"[planner] VALIDATION: {len(failures)} check(s) failed",
                      file=sys.stderr)
                for r in failures:
                    print(f"  ✗ {r.name}: {r.message}", file=sys.stderr)
            else:
                print(f"[planner] VALIDATION: all checks passed",
                      file=sys.stderr)
        except ImportError:
            print("[planner] WARN: plan_validator not available, skipping validation",
                  file=sys.stderr)

    # Write execution plan
    output_dir = os.path.dirname(args.output)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)

    print(f"[planner] Generated execution plan: {args.output}",
          file=sys.stderr)
    print(f"[planner]   {len(plan['entries'])} entries, "
          f"{len(plan['cleanup_ids'])} cleanup IDs",
          file=sys.stderr)
    if plan.get("pre_clone"):
        print(f"[planner]   {len(plan['pre_clone'])} pre-clone prototypes",
              file=sys.stderr)


if __name__ == "__main__":
    main()
