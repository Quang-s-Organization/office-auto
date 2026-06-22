#!/usr/bin/env python3
"""
markdown-parser.py — Parse noidung.md → content.ir.json

Usage:
  python3 tools/markdown-parser.py noidung.md [--out content.ir.json]

Output: Content Intermediate Representation (IR) with:
  - Flat ordered section list (document order)
  - Heading level → type mapping
  - Paragraph count via \n\n boundary
  - Full body text (verbatim)
  - verbatim: false for sections missing from source
"""

import sys, json, os, re, argparse
from pathlib import Path

def slugify(text: str) -> str:
    """Create URL-safe slug from heading text."""
    s = text.lower().strip()
    s = re.sub(r'[àáạảãâầấậẩẫăằắặẳẵ]', 'a', s)
    s = re.sub(r'[èéẹẻẽêềếệểễ]', 'e', s)
    s = re.sub(r'[ìíịỉĩ]', 'i', s)
    s = re.sub(r'[òóọỏõôồốộổỗơờớợởỡ]', 'o', s)
    s = re.sub(r'[ùúụủũưừứựửữ]', 'u', s)
    s = re.sub(r'[ỳýỵỷỹ]', 'y', s)
    s = re.sub(r'[đ]', 'd', s)
    s = re.sub(r'[^a-z0-9-]', '-', s)
    s = re.sub(r'-+', '-', s)
    s = s.strip('-')
    return s


def parse_markdown(filepath: str) -> dict:
    """Parse markdown file into content IR."""
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Build raw section list
    raw_sections = []  # list of {level, title, body_lines}
    current_level = 0
    current_title = None
    current_body = []

    for line in lines:
        stripped = line.rstrip('\n')
        heading_match = re.match(r'^(#{1,3})\s+(.+)$', stripped)
        if heading_match:
            # Save previous section
            if current_title is not None:
                raw_sections.append({
                    'level': current_level,
                    'title': current_title,
                    'body': current_body
                })
            level = len(heading_match.group(1))
            title = heading_match.group(2).strip()
            current_level = level
            current_title = title
            current_body = []
        else:
            if current_title is not None:
                current_body.append(stripped)

    # Save last section
    if current_title is not None:
        raw_sections.append({
            'level': current_level,
            'title': current_title,
            'body': current_body
        })

    # Build content IR
    h1_counter = 0
    h2_counter = {}  # h1_idx -> h2_counter
    h3_counter = {}  # h2_tag -> h3_counter
    current_h1 = -1
    current_h2 = None
    sections = []
    seen_headings = set()

    for i, sec in enumerate(raw_sections):
        level = sec['level']
        title = sec['title']
        body_text = '\n'.join(sec['body']).strip()

        # Count paragraphs
        if body_text:
            paragraphs = [p.strip() for p in re.split(r'\n\n+', body_text) if p.strip()]
        else:
            paragraphs = []

        # Generate tag
        if level == 1:
            h1_counter += 1
            current_h1 = h1_counter
            tag = f"h1_{h1_counter}"
        elif level == 2:
            if current_h1 not in h2_counter:
                h2_counter[current_h1] = 0
            h2_counter[current_h1] += 1
            tag = f"h2_{current_h1}_{h2_counter[current_h1]}"
        elif level == 3:
            h2_key = f"h2_{current_h1}_{h2_counter.get(current_h1, 0)}"
            if h2_key not in h3_counter:
                h3_counter[h2_key] = 0
            h3_counter[h2_key] += 1
            tag = f"h3_{current_h1}_{h2_counter.get(current_h1, 0)}_{h3_counter[h2_key]}"
        else:
            tag = f"sec_{i}"

        # Determine type
        type_map = {1: 'heading1', 2: 'heading2', 3: 'heading3'}
        sec_type = type_map.get(level, 'body_text')

        # Verbatim: true if heading exists in source
        title_key = title.lower().strip()
        verbatim = True

        # Detect generation_hint sections (no matching heading in noidung.md)
        generation_hint = None

        # Check for heading anchors in body (existing struct-spec convention)
        # For now, all parsed sections are verbatim

        section = {
            'tag': tag,
            'type': sec_type,
            'title': title,
            'level': level,
            'body_paragraphs': paragraphs,
            'paragraph_count': len(paragraphs),
            'verbatim': verbatim,
            'source_anchor': slugify(title)
        }

        if generation_hint:
            section['generation_hint'] = generation_hint

        sections.append(section)
        seen_headings.add(title_key)

    return {
        'source_file': os.path.basename(filepath),
        'generated_at': None,  # filled by --date
        'sections': sections,
        'section_count': len(sections)
    }


def generate_extra_sections(content_ir: dict) -> list:
    """
    Detect and generate extra sections not found in markdown.
    Heuristic: if struct-spec or manifest exists, use them.
    Otherwise, no extra sections are added.
    """
    # This is a placeholder — the pipeline's discovery step
    # will handle verbatim:false detection based on struct-spec needs
    return []


def main():
    parser = argparse.ArgumentParser(description='Parse markdown to content IR')
    parser.add_argument('input', help='Path to noidung.md')
    parser.add_argument('--out', '-o', default=None, help='Output path')
    parser.add_argument('--date', '-d', default=None, help='ISO date string')
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: {args.input} not found", file=sys.stderr)
        sys.exit(1)

    content_ir = parse_markdown(args.input)
    content_ir['generated_at'] = args.date or ''

    output = json.dumps(content_ir, indent=2, ensure_ascii=False)

    if args.out:
        with open(args.out, 'w', encoding='utf-8') as f:
            f.write(output)
        print(f"Written {args.out}")
    else:
        print(output)


if __name__ == '__main__':
    main()
