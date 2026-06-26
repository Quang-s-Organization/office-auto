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
  - para_metadata per paragraph (images, LaTeX, bold, italic detection)
  - Section-level aggregate flags (has_image, has_math, has_bold, has_italic)
  - verbatim: false for sections missing from source
"""

import sys, json, os, re, argparse
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inline import tokenize_inline, strip_inline
from block_specs import (BLOCK_PARSERS, paragraph_block, count_block,
                         A_BLOCK, A_SKIP, A_BUFFER, A_ADVANCE)

# Regex patterns for inline format detection (metadata flags only — the run
# tokenizer + block grammar live in inline.py / block_specs.py)
RE_IMAGE = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')           # ![alt](url)
RE_MATH_INLINE = re.compile(r'(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)')  # $...$
RE_MATH_BLOCK = re.compile(r'\$\$(.+?)\$\$', re.DOTALL)      # $$...$$
RE_BOLD = re.compile(r'\*\*(.+?)\*\*')                        # **...**
RE_ITALIC = re.compile(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)')  # *...*


def parse_body_blocks(body_lines: list[str]) -> list[dict]:
    """Parse a section's raw body lines into ordered blocks.

    The per-kind grammar lives in block_specs.BLOCK_PARSERS (one handler per
    block kind, tried in priority order). This function only owns the text
    buffer + paragraph flush; adding a new block kind means adding a BlockSpec,
    not editing this loop. Block kinds: table, code, equation, list, callout,
    paragraph (see block_specs.py)."""
    blocks: list[dict] = []
    i = 0
    n = len(body_lines)
    text_buf: list[str] = []

    def flush_text():
        if not text_buf:
            return
        chunk = "\n".join(text_buf).strip("\n")
        for para in re.split(r'\n\s*\n', chunk):
            para = para.strip()
            if not para:
                continue
            blocks.append(paragraph_block(para))
        text_buf.clear()

    while i < n:
        for handler in BLOCK_PARSERS:
            res = handler(body_lines, i)
            if res is None:
                continue
            action, payload, ni = res
            if action == A_BLOCK:
                flush_text()
                blocks.append(payload)
            elif action == A_SKIP:
                flush_text()
            elif action == A_BUFFER:
                text_buf.append(payload)
            elif action == A_ADVANCE:
                pass
            i = ni
            break
        else:
            text_buf.append(body_lines[i])
            i += 1
    flush_text()
    return blocks


def count_paragraphs(blocks: list[dict]) -> int:
    """Number of `add p` ops the planner emits for these blocks (body only).

    Delegates to block_specs.count_block so the count stays in lock-step with
    the emit handler for every kind (drives validator S7 / plan_validator)."""
    return sum(count_block(b) for b in blocks)


def detect_paragraph_metadata(text: str) -> dict:
    """Detect images, LaTeX, bold, italic in a paragraph.
    Returns a dict with boolean flags and extracted values."""
    meta = {
        'has_image': False,
        'has_math': False,
        'has_bold': False,
        'has_italic': False,
        'images': [],      # list of {alt, url}
    }
    # Images: ![alt](url)
    for match in RE_IMAGE.finditer(text):
        meta['has_image'] = True
        meta['images'].append({
            'alt': match.group(1),
            'url': match.group(2)
        })
    # LaTeX: $$...$$ (block) or $...$ (inline)
    if RE_MATH_BLOCK.search(text):
        meta['has_math'] = True
    if RE_MATH_INLINE.search(text):
        meta['has_math'] = True
    # Bold: **...**
    if RE_BOLD.search(text):
        meta['has_bold'] = True
    # Italic: *...* (single asterisk)
    if RE_ITALIC.search(text):
        meta['has_italic'] = True
    return meta


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
        title = strip_inline(sec['title'])

        # Parse body into ordered blocks (paragraphs + tables), stripping
        # markdown emphasis and recognising heading-like lines / tables.
        body_blocks = parse_body_blocks(sec['body'])
        # body_paragraphs = plain prose text (paragraph + callout blocks), used
        # for the document tree / first_paragraph and metadata flags. The
        # planner-accurate paragraph count (incl. list items + code lines) is
        # computed separately so validator S7 / plan_validator para_count match.
        paragraphs = [b['text'] for b in body_blocks
                      if b['kind'] in ('paragraph', 'callout')]

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

        # Detect metadata on each paragraph
        para_metadata = [detect_paragraph_metadata(p) for p in paragraphs]

        section = {
            'tag': tag,
            'type': sec_type,
            'title': title,
            'level': level,
            'body_paragraphs': paragraphs,
            'body_blocks': body_blocks,
            'para_metadata': para_metadata,
            'paragraph_count': count_paragraphs(body_blocks),
            'verbatim': verbatim,
            'source_anchor': slugify(title)
        }
        # Aggregate: section-level flags (any paragraph has it)
        if para_metadata:
            section['has_image'] = any(m['has_image'] for m in para_metadata)
            section['has_math'] = any(m['has_math'] for m in para_metadata)
            section['has_bold'] = any(m['has_bold'] for m in para_metadata)
            section['has_italic'] = any(m['has_italic'] for m in para_metadata)

        if generation_hint:
            section['generation_hint'] = generation_hint

        sections.append(section)
        seen_headings.add(title_key)

    return {
        'source_file': os.path.basename(filepath),
        'generated_at': None,  # filled by --date
        'sections': sections,
        'section_count': len(sections),
        'document_tree': build_document_tree(sections)
    }


def _word_count(text: str) -> int:
    """Count whitespace-delimited tokens (cheap, language-agnostic enough for VN)."""
    return len(text.split())


def build_document_tree(sections: list[dict]) -> list[dict]:
    """Build a nested heading tree from the flat (document-ordered) section list.

    Deterministic — derived purely from `level` + order (nest while level
    increases, pop while it decreases). Each node carries `word_count` (own
    body), `child_word_count` (sum of descendants) and a truncated
    `first_paragraph` used only as a lazy-load source for the semantic tier;
    no styling/role info lives here.
    """
    roots: list[dict] = []
    stack: list[dict] = []  # nodes currently open, by increasing level

    for sec in sections:
        first_para = sec["body_paragraphs"][0] if sec.get("body_paragraphs") else ""
        own_words = sum(_word_count(p) for p in sec.get("body_paragraphs", []))
        node = {
            "node_id": sec["tag"],
            "title": sec["title"],
            "level": sec["level"],
            "word_count": own_words,
            "child_word_count": 0,
            "first_paragraph": first_para[:200],
            "children": [],
        }
        # Pop deeper-or-equal nodes; remaining top of stack is the parent.
        while stack and stack[-1]["level"] >= sec["level"]:
            stack.pop()
        if stack:
            stack[-1]["children"].append(node)
        else:
            roots.append(node)
        stack.append(node)

    # Roll up descendant word counts (post-order).
    def _rollup(node: dict) -> int:
        total = 0
        for child in node["children"]:
            total += child["word_count"] + _rollup(child)
        node["child_word_count"] = total
        return total

    for root in roots:
        _rollup(root)
    return roots


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
