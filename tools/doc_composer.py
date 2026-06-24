#!/usr/bin/env python3
"""Deterministic Composer — Builds DOCX from Content IR + Template IR + Mapping Table.

Usage:
    python3 tools/doc_composer.py \\
        --template templates/format_template.docx \\
        --template-ir .cache/template.ir.json \\
        --content content.ir.json \\
        --mapping mapping_table.json \\
        --output report.docx

No LLM involvement. All operations are deterministic officecli calls.
"""

from __future__ import annotations
import argparse
import json
import os
import shutil
import sys
import time
from dataclasses import dataclass, field
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from doc_composer_ops import (
    open_doc, close_doc, add_paragraph, set_text, set_prop,
    remove_paragraph, refresh_doc, get_text, query_heading_info
)
from template_ir import TemplateIR


# ── Data classes ──────────────────────────────────────────────────

@dataclass
class MappingEntry:
    """One content section → document insertion."""
    content_tag: str              # "h1_1"
    heading_text: str             # Section title
    prototype: str                # "Heading1", "Heading2", "Heading3", "Normal"
    body_prototype: str           # "Normal" (for body paragraphs)
    body_paragraphs: list[str]    # List of body paragraph texts
    ooxml_overrides: dict = field(default_factory=dict)
    # overrides: {outlineLevel: 3, size: "13pt", ...}


@dataclass
class MappingTable:
    """Complete mapping from content → template, produced by LLM."""
    initial_anchor: str           # paraId to insert first content after
    cleanup_ids: list[str]        # paraIds of placeholder elements to remove
    entries: list[MappingEntry]   # Content sections in insertion order
    pre_clone: dict[str, str] | None = None
    # pre_clone: {prototype_name: para_id} — prototypes to clone BEFORE cleanup


@dataclass
class ComposeResult:
    """Result of a compose operation."""
    success: bool
    total_paragraphs: int
    errors: list[str]
    output_path: str
    elapsed_seconds: float = 0.0


# ── Default OOXML properties ──────────────────────────────────────

DEFAULT_PROPS = {
    "heading1": {
        "outlineLevel": "1",
        "size": "16pt",
        "font.ea": "Calibri",
    },
    "heading2": {
        "outlineLevel": "2",
        "size": "14pt",
        "font.ea": "Calibri",
    },
    "heading3": {
        "outlineLevel": "3",
        "size": "14pt",
        "font.ea": "Calibri",
    },
}

BODY_PROPS = {
    "ind.firstLine": "1.27cm",
}


# ── Verbatim self-check ───────────────────────────────────────────

def _verbatim_check(
    filepath: str, para_id: str, expected_text: str
) -> tuple[bool, str]:
    """Check that a paragraph contains the expected text.

    Returns (passed, message).
    """
    stored = get_text(filepath, para_id)
    if stored is None:
        return False, "Could not read back paragraph"

    # Check first 80 chars
    expected_prefix = expected_text[:80].strip()
    stored_prefix = stored[:80].strip()
    if expected_prefix != stored_prefix:
        return False, (
            f"Prefix mismatch:\n"
            f"  Expected: '{expected_prefix}'\n"
            f"  Got:      '{stored_prefix}'"
        )

    # Check word count (>= 90%)
    expected_words = len(expected_text.split())
    stored_words = len(stored.split())
    if expected_words > 0 and stored_words < 0.9 * expected_words:
        return False, (
            f"Word count mismatch: expected ~{expected_words}, got {stored_words}"
        )

    return True, "OK"


# ── Main compose logic ────────────────────────────────────────────

def _load_mapping_table(path: str) -> Optional[MappingTable]:
    """Load and validate mapping table from JSON."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[composer] ERROR: Cannot load mapping table: {e}", file=sys.stderr)
        return None

    entries = []
    for e in data.get("entries", []):
        entries.append(MappingEntry(
            content_tag=e.get("content_tag", ""),
            heading_text=e.get("heading_text", ""),
            prototype=e.get("prototype", "Heading1"),
            body_prototype=e.get("body_prototype", "Normal"),
            body_paragraphs=e.get("body_paragraphs", []),
            ooxml_overrides=e.get("ooxml_overrides", {}),
        ))

    return MappingTable(
        initial_anchor=data.get("initial_anchor", ""),
        cleanup_ids=data.get("cleanup_ids", []),
        entries=entries,
        pre_clone=data.get("pre_clone"),
    )


def _get_prototype_para_id(
    template_ir: TemplateIR, prototype_key: str
) -> Optional[str]:
    """Resolve a prototype key like 'Heading1' or 'CHAPTER' to a paraId.

    Tries:
    1. template_ir.best_prototypes[prototype_key].para_id
    2. Look through all prototypes to find one matching the key
    """
    # Direct match in best_prototypes
    if prototype_key in template_ir.best_prototypes:
        return template_ir.best_prototypes[prototype_key].para_id

    # Try matching by section_context
    for style_name, candidates in template_ir.prototypes.items():
        for candidate in candidates:
            if candidate.section_context == prototype_key:
                return candidate.para_id

    # Try matching as style name
    if prototype_key in template_ir.prototypes:
        cands = template_ir.prototypes[prototype_key]
        if cands:
            return cands[0].para_id

    return None


def compose_document(
    template_path: str,
    template_ir_path: str,
    content_ir_path: str,
    mapping_table_path: str,
    output_path: str,
    skip_verbatim_check: bool = False,
) -> ComposeResult:
    """Run the full deterministic composition.

    Steps:
    1. Load IRs and mapping table
    2. Copy template → output
    3. Open document
    4. Remove cleanup paras
    5. For each mapping entry: clone heading → set text → apply props → clone body → set text → apply props → chain
    6. Close document
    7. Return result
    """
    errors: list[str] = []
    start_time = time.time()

    # ── 1. Load IRs ──
    print("[composer] Loading Template IR...", file=sys.stderr)
    try:
        with open(template_ir_path, encoding="utf-8") as f:
            template_ir = TemplateIR.from_json(json.load(f))
    except Exception as e:
        return ComposeResult(False, 0, [f"Cannot load Template IR: {e}"], output_path)

    print("[composer] Loading Content IR...", file=sys.stderr)
    try:
        with open(content_ir_path, encoding="utf-8") as f:
            content_ir = json.load(f)
    except Exception as e:
        return ComposeResult(False, 0, [f"Cannot load Content IR: {e}"], output_path)

    print("[composer] Loading Mapping Table...", file=sys.stderr)
    mapping = _load_mapping_table(mapping_table_path)
    if mapping is None:
        return ComposeResult(False, 0, ["Cannot load mapping table"], output_path)

    # ── 2. Copy template → output ──
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    shutil.copy2(template_path, output_path)
    print(f"[composer] Copied template to {output_path}", file=sys.stderr)

    # ── 3. Open document ──
    print("[composer] Opening document...", file=sys.stderr)
    if not open_doc(output_path):
        errors.append("Failed to open document")
        return ComposeResult(False, 0, errors, output_path)

    # ── 4. Pre-clone prototypes (before cleanup) ──
    # Prototypes that will be removed by cleanup must be cloned first
    # into a safe area (after initial_anchor, which is a preserved element).
    cloned_prototypes: dict[str, str] = {}
    if mapping.pre_clone:
        print(f"[composer] Pre-cloning {len(mapping.pre_clone)} prototypes...",
              file=sys.stderr)
        for name, pid in mapping.pre_clone.items():
            new_pid = add_paragraph(output_path, pid, mapping.initial_anchor)
            if new_pid:
                cloned_prototypes[name] = new_pid
                print(f"[composer]   {name}: {pid} → {new_pid}", file=sys.stderr)
            else:
                print(f"[composer] WARN: pre-clone {name} ({pid}) failed",
                      file=sys.stderr)

    # ── 5. Cleanup ──
    print(f"[composer] Cleaning up {len(mapping.cleanup_ids)} placeholders...",
          file=sys.stderr)
    for pid in mapping.cleanup_ids:
        if not remove_paragraph(output_path, pid):
            print(f"[composer] WARN: could not remove {pid}", file=sys.stderr)

    # ── 6. Build content ──
    total_paras = 0
    anchor = mapping.initial_anchor
    if not anchor:
        errors.append("No initial_anchor in mapping table")
        close_doc(output_path)
        return ComposeResult(False, 0, errors, output_path)

    print(f"[composer] Building {len(mapping.entries)} sections...",
          file=sys.stderr)

    for idx, entry in enumerate(mapping.entries):
        # 6a. Resolve prototype paraId
        # Check cloned prototypes first (if pre-cloned before cleanup)
        if entry.prototype in cloned_prototypes:
            proto_id = cloned_prototypes[entry.prototype]
        else:
            proto_id = _get_prototype_para_id(template_ir, entry.prototype)
        if not proto_id:
            # Fallback: use first available Heading1 style
            h1_list = template_ir.prototypes.get("Heading1", [])
            if h1_list:
                proto_id = h1_list[0].para_id
                print(f"[composer] WARN: prototype '{entry.prototype}' not found, "
                      f"fallback to Heading1[{proto_id[:8]}...]",
                      file=sys.stderr)
            else:
                err = f"No prototype for '{entry.prototype}' and no fallback"
                errors.append(err)
                print(f"[composer] ERROR: {err}", file=sys.stderr)
                continue

        body_proto_id = _get_prototype_para_id(template_ir, entry.body_prototype)
        if not body_proto_id:
            # Check cloned prototypes
            if entry.body_prototype in cloned_prototypes:
                body_proto_id = cloned_prototypes[entry.body_prototype]
            else:
                norm_list = template_ir.prototypes.get("Normal", [])
                if norm_list:
                    body_proto_id = norm_list[0].para_id
                else:
                    errors.append(f"No body prototype '{entry.body_prototype}'")
                    continue

        # 5b. Clone heading
        h_id = add_paragraph(output_path, proto_id, anchor)
        if not h_id:
            errors.append(f"Failed to clone heading for '{entry.heading_text[:40]}'")
            continue
        set_text(output_path, h_id, entry.heading_text)
        total_paras += 1

        # 5c. Apply heading OOXML properties
        heading_type = entry.prototype.lower()
        if heading_type in DEFAULT_PROPS:
            props = DEFAULT_PROPS[heading_type].copy()
        elif entry.prototype == "Heading1":
            props = DEFAULT_PROPS["heading1"].copy()
        elif entry.prototype == "Heading2":
            props = DEFAULT_PROPS["heading2"].copy()
        elif entry.prototype == "Heading3":
            props = DEFAULT_PROPS["heading3"].copy()
        else:
            props = {}

        # Apply overrides from mapping table
        props.update(entry.ooxml_overrides)

        for key, val in props.items():
            set_prop(output_path, h_id, key, val)

        anchor = h_id

        # 5d. Clone body paragraphs
        for body_text in entry.body_paragraphs:
            b_id = add_paragraph(output_path, body_proto_id, anchor)
            if not b_id:
                errors.append(f"Failed to clone body para after '{entry.heading_text[:30]}'")
                continue
            set_text(output_path, b_id, body_text)
            for key, val in BODY_PROPS.items():
                set_prop(output_path, b_id, key, val)

            # Verbatim check (optional)
            if not skip_verbatim_check:
                passed, msg = _verbatim_check(output_path, b_id, body_text)
                if not passed:
                    errors.append(f"Verbatim check failed for '{body_text[:40]}...': {msg}")
                    print(f"[composer] WARN: {msg}", file=sys.stderr)

            anchor = b_id
            total_paras += 1

        print(f"[composer]   [{idx+1}/{len(mapping.entries)}] '{entry.heading_text[:50]}' "
              f"→ {1 + len(entry.body_paragraphs)} paragraphs",
              file=sys.stderr)

    # ── 7. Post-cleanup (remove pre-clone leftovers) ──
    pre_clone_para_ids = list(cloned_prototypes.values())
    if pre_clone_para_ids:
        print(f"[composer] Post-cleanup {len(pre_clone_para_ids)} pre-clone leftovers...",
              file=sys.stderr)
        for pid in pre_clone_para_ids:
            if not remove_paragraph(output_path, pid):
                print(f"[composer] WARN: post-cleanup could not remove {pid}",
                      file=sys.stderr)

    # ── 8. Refresh + close ──
    print("[composer] Refreshing TOC...", file=sys.stderr)
    refresh_doc(output_path)  # will be inside open/close

    print("[composer] Closing document...", file=sys.stderr)
    close_doc(output_path)

    elapsed = time.time() - start_time
    success = len(errors) == 0

    print(f"[composer] Done in {elapsed:.1f}s. {total_paras} paragraphs, "
          f"{'✓' if success else f'{len(errors)} errors'}",
          file=sys.stderr)

    return ComposeResult(
        success=success,
        total_paragraphs=total_paras,
        errors=errors,
        output_path=output_path,
        elapsed_seconds=elapsed,
    )


# ── CLI ───────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Deterministic DOCX composer from Content IR + Template IR + Mapping"
    )
    parser.add_argument("--template", required=True, help="Path to template.docx")
    parser.add_argument("--template-ir", required=True, help="Path to template.ir.json")
    parser.add_argument("--content", required=True, help="Path to content.ir.json")
    parser.add_argument("--mapping", required=True, help="Path to mapping_table.json")
    parser.add_argument("--output", "-o", default="report.docx", help="Output path")
    parser.add_argument("--skip-verbatim", action="store_true",
                        help="Skip verbatim self-check")
    args = parser.parse_args()

    result = compose_document(
        template_path=args.template,
        template_ir_path=args.template_ir,
        content_ir_path=args.content,
        mapping_table_path=args.mapping,
        output_path=args.output,
        skip_verbatim_check=args.skip_verbatim,
    )

    # Print result summary as JSON
    print(json.dumps({
        "success": result.success,
        "total_paragraphs": result.total_paragraphs,
        "error_count": len(result.errors),
        "errors": result.errors[:5],  # First 5 only
        "output": result.output_path,
        "elapsed_seconds": round(result.elapsed_seconds, 1),
    }, ensure_ascii=False, indent=2))

    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()
