#!/usr/bin/env python3
"""source_packet_to_ops.py — deterministic compiler from source_packet JSON to execution_ops.

This is the "compiler" — zero LLM involvement, zero reasoning, zero content generation.
It takes the mechanical source_packet.json, style_map.json, and replace_range.json,
and produces execution_ops.json deterministically.

Philosophy: LLM decides mapping (style_map, replace_range). This script compiles.
LLM never copies 125 blocks of text. Script does that deterministically.

Usage:
    python3 source_packet_to_ops.py \
        --run-dir <path> \
        [--source-packet <path>] \
        [--style-map <path>] \
        [--replace-range <path>]
"""
from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path
from typing import Any

from officecli_native import read_json, write_json

HEADING_PATTERN = re.compile(r'^(#{1,6})\s+(.*)')


def compute_text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def default_style_map() -> dict:
    return {
        "h1": "Heading1",
        "h2": "Heading2",
        "h3": "Heading3",
        "body": "Normal",
        "caption": "Caption",
        "toc": "TOC",
    }


def default_replace_range(first_anchor: str, placeholder_ids: list[str]) -> dict:
    return {
        "insert_after_path": first_anchor,
        "remove_paths": [f"/body/p[@paraId={pid}]" for pid in placeholder_ids],
    }


def strip_heading_markers(text: str) -> str:
    """Strip leading # markers and whitespace from heading text."""
    text = text.strip()
    m = HEADING_PATTERN.match(text)
    if m:
        return m.group(2).strip()
    return text


def determine_role(block_type: str, level: int | None = None) -> str:
    """Mechanically map block_type + optional level → op role.

    Block types from source_packet.py (mechanical):
      - heading        → role = h1/h2/h3 based on # count
      - paragraph      → role = body
      - caption_candidate → role = body (LLM decided style via style_map)
      - list_item      → role = body
      - empty_line     → role = body

    Returns the role string for use in execution_ops.
    """
    if block_type == "heading":
        if level is not None:
            return f"h{min(level, 9)}"
        return "h1"
    return "body"


def classify_heading_level_from_text(text: str) -> int:
    """Extract heading level from raw markdown heading text.

    Counts # characters. e.g., "## CHƯƠNG 1." → level 2.
    Falls back to 2 (h2) if not a heading.
    """
    m = HEADING_PATTERN.match(text.strip())
    if m:
        return len(m.group(1))
    return 2


def validate_style_map(style_map: dict, available_style_ids: set[str]) -> list[str]:
    """Validate that style_map references styles that exist in the template.

    Returns list of warning messages for styles not found.
    """
    warnings: list[str] = []
    style_keys = ("h1", "h2", "h3", "h4", "h5", "h6", "body", "caption", "toc")
    for key in style_keys:
        style_id = style_map.get(key)
        if style_id and style_id not in available_style_ids:
            warnings.append(
                f"style_map['{key}'] = '{style_id}' NOT found in template styles. "
                f"Executor will fail when applying this style."
            )
    return warnings


def compile_source_packet_to_ops(
    source_packet: dict,
    style_map: dict,
    replace_range: dict,
) -> dict:
    """Deterministically compile source_packet → execution_ops.

    Rules (NO exceptions, NO LLM involvement):
    1. First insert op uses insert_after_path as anchor
    2. All subsequent insert ops use PREVIOUS
    3. Heading blocks: strip #, use mapped style
    4. Body blocks: use body style
    5. Caption blocks: use caption style if available, else body
    6. Remove ops: one per remove_path in replace_range
    7. Every insert op gets source_block_id and source_text_sha256
    8. Text is COPIED VERBATIM, never paraphrased
    """
    blocks = source_packet.get("blocks", [])
    insert_after_path = replace_range.get("insert_after_path", "")
    remove_paths = replace_range.get("remove_paths", [])
    preserve_zones = replace_range.get("preserve_zones", [])

    ops: list[dict] = []
    anchored = False
    first_insert_anchor = insert_after_path

    for block in blocks:
        block_type = block.get("type", "paragraph")
        text = block.get("text", "")
        block_id = block.get("id", "?")

        if block_type in ("empty_line",):
            if not text.strip():
                ops.append({
                    "op": "insert_paragraph_after",
                    "role": "body",
                    "anchor": "PREVIOUS",
                    "style": style_map.get("body", "Normal"),
                    "text": "",
                    "source_block_id": block_id,
                    "source_text_sha256": compute_text_sha256(text),
                })
                continue
            ops.append({
                "op": "insert_paragraph_after",
                "role": "body",
                "anchor": "PREVIOUS",
                "style": style_map.get("body", "Normal"),
                "text": text,
                "source_block_id": block_id,
                "source_text_sha256": compute_text_sha256(text),
            })
            continue

        if block_type == "heading":
            level = classify_heading_level_from_text(text)
            cleaned_text = strip_heading_markers(text)
            role = f"h{level}"
            style_key = f"h{level}"
            style = style_map.get(style_key, style_map.get("h1", "Heading1"))
            anchor = insert_after_path if not anchored else "PREVIOUS"
            if not anchored:
                anchored = True
            ops.append({
                "op": "insert_paragraph_after",
                "role": role,
                "anchor": anchor,
                "style": style,
                "text": cleaned_text,
                "source_block_id": block_id,
                "source_text_sha256": compute_text_sha256(text),
            })
            continue

        if block_type == "caption_candidate":
            caption_style = style_map.get("caption", style_map.get("body", "Normal"))
            anchor = insert_after_path if not anchored else "PREVIOUS"
            if not anchored:
                anchored = True
            ops.append({
                "op": "insert_paragraph_after",
                "role": "body",
                "anchor": anchor,
                "style": caption_style,
                "text": text.strip(),
                "source_block_id": block_id,
                "source_text_sha256": compute_text_sha256(text),
            })
            continue

        if block_type in ("paragraph", "list_item"):
            body_style = style_map.get("body", "Normal")
            anchor = insert_after_path if not anchored else "PREVIOUS"
            if not anchored:
                anchored = True
            ops.append({
                "op": "insert_paragraph_after",
                "role": "body",
                "anchor": anchor,
                "style": body_style,
                "text": text,
                "source_block_id": block_id,
                "source_text_sha256": compute_text_sha256(text),
            })
            continue

        body_style = style_map.get("body", "Normal")
        anchor = insert_after_path if not anchored else "PREVIOUS"
        if not anchored:
            anchored = True
        ops.append({
            "op": "insert_paragraph_after",
            "role": "body",
            "anchor": anchor,
            "style": body_style,
            "text": text,
            "source_block_id": block_id,
            "source_text_sha256": compute_text_sha256(text),
        })

    # Add remove ops for all placeholder paths
    for rpath in remove_paths:
        ops.append({
            "op": "remove",
            "path": rpath,
        })

    return {
        "version": "2",
        "source_sha256": source_packet.get("sha256", ""),
        "source_file": source_packet.get("source_file", ""),
        "first_insert_anchor": first_insert_anchor,
        "compiled_by": "source_packet_to_ops.py (deterministic compiler)",
        "ops": ops,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="source_packet_to_ops: deterministic markdown→DOCX compiler — zero LLM."
    )
    parser.add_argument("--run-dir", required=True, help="Run directory")
    parser.add_argument("--source-packet", default=None,
                        help="Path to source_packet.json (default: <run-dir>/source_packet.json)")
    parser.add_argument("--style-map", default=None,
                        help="Path to style_map.json (default: <run-dir>/style_map.json)")
    parser.add_argument("--replace-range", default=None,
                        help="Path to replace_range.json (default: <run-dir>/replace_range.json)")
    parser.add_argument("--output", default=None,
                        help="Output path (default: <run-dir>/execution_ops.json)")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)

    # Load source_packet
    source_packet_path = Path(args.source_packet) if args.source_packet else run_dir / "source_packet.json"
    if not source_packet_path.exists():
        raise FileNotFoundError(f"source_packet.json not found: {source_packet_path}")
    source_packet = read_json(source_packet_path)

    # Load or default style_map
    style_map = default_style_map()
    style_map_path = Path(args.style_map) if args.style_map else run_dir / "style_map.json"
    if style_map_path.exists():
        loaded_style_map = read_json(style_map_path)
        if isinstance(loaded_style_map, dict):
            style_map.update(loaded_style_map)

    # Materialize style_map so final_gate can find it
    write_json(run_dir / "style_map.json", style_map)

    # Validate style_map against template styles
    styles_raw_file = run_dir / "docx_inspect_styles_raw.json"
    if styles_raw_file.exists():
        styles_raw = read_json(styles_raw_file)
        available_style_ids = {s.get("style_id") for s in styles_raw if s.get("style_id")}
        style_warnings = validate_style_map(style_map, available_style_ids)
        if style_warnings:
            print(f"[source_packet_to_ops] WARNING: {len(style_warnings)} style validation issue(s):")
            for w in style_warnings:
                print(f"  - {w}")
            write_json(run_dir / "style_validation_warnings.json", {"warnings": style_warnings})

    # Load or default replace_range
    replace_range: dict = {}
    replace_range_path = Path(args.replace_range) if args.replace_range else run_dir / "replace_range.json"
    if replace_range_path.exists():
        replace_range = read_json(replace_range_path)
    else:
        # Try from insert_plan_scaffold
        scaffold_path = run_dir / "insert_plan_scaffold.json"
        if scaffold_path.exists():
            scaffold = read_json(scaffold_path)
            first_anchor = scaffold.get("CRITICAL_FIRST_OP_ANCHOR", "")
            placeholder_ids = scaffold.get("body_placeholders", {}).get("para_ids", [])
            replace_range = default_replace_range(first_anchor, placeholder_ids)
        else:
            replace_range = default_replace_range("", [])

    # Materialize replace_range so final_gate can find it
    write_json(run_dir / "replace_range.json", replace_range)

    # Compile
    execution_ops = compile_source_packet_to_ops(source_packet, style_map, replace_range)

    # Write output
    output_path = Path(args.output) if args.output else run_dir / "execution_ops.json"
    write_json(output_path, execution_ops)

    insert_count = sum(1 for op in execution_ops["ops"] if op.get("op") != "remove")
    remove_count = sum(1 for op in execution_ops["ops"] if op.get("op") == "remove")
    print(f"[source_packet_to_ops] Compilation complete: "
          f"{insert_count} insert ops, {remove_count} remove ops")
    print(f"[source_packet_to_ops] First anchor: {execution_ops.get('first_insert_anchor', 'N/A')}")
    print(f"[source_packet_to_ops] Output: {output_path}")
    print(f"[source_packet_to_ops] Source blocks: {source_packet.get('block_count', '?')}")
    print(f"[source_packet_to_ops] Source SHA-256: {source_packet.get('sha256', '?'):.16s}...")


if __name__ == "__main__":
    main()
