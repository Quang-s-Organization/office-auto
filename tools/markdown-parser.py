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

# Regex patterns for inline format detection
RE_IMAGE = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')           # ![alt](url)
RE_MATH_INLINE = re.compile(r'(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)')  # $...$
RE_MATH_BLOCK = re.compile(r'\$\$(.+?)\$\$', re.DOTALL)      # $$...$$
RE_BOLD = re.compile(r'\*\*(.+?)\*\*')                        # **...**
RE_ITALIC = re.compile(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)')  # *...*


# ── inline markdown → runs (deterministic; no LLM) ──────────────────
# Order matters: ***x*** (bold+italic) before **x** (bold) before <sup>/<sub>
# before *x*/_x_ (italic). The underscore-italic arm is WORD-BOUNDARIED so
# identifiers like `combined_loss` / `d_k` are NOT mangled into italics
# (see docs §3.2 — the old `_(.+?)_` arm swallowed `_`).
RE_SPAN = re.compile(
    r'\*\*\*(.+?)\*\*\*'                          # 1: bold+italic
    r'|___(.+?)___'                               # 2: bold+italic (underscore)
    r'|\*\*(.+?)\*\*'                             # 3: bold
    r'|__(.+?)__'                                 # 4: bold (underscore)
    r'|<sup>(.+?)</sup>'                          # 5: superscript
    r'|<sub>(.+?)</sub>'                          # 6: subscript
    r'|\*(.+?)\*'                                 # 7: italic
    r'|(?<![A-Za-z0-9])_(.+?)_(?![A-Za-z0-9])'    # 8: italic (underscore, word-boundaried)
)
RE_HEADINGLIKE = re.compile(r'^#{4,6}\s+(.+)$')          # #### / ##### / ######
RE_NUMBERED = re.compile(r'^\d+(\.\d+)*\.?\s')           # 1.1.1  / 2.1.  etc.
RE_TABLE_ROW = re.compile(r'^\s*\|.*\|\s*$')
RE_TABLE_SEP = re.compile(r'^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$')

# block-level markers (parse_body_blocks)
RE_CODE_FENCE = re.compile(r'^\s*(```|~~~)\s*([A-Za-z0-9_+-]*)\s*$')
RE_THEMATIC = re.compile(r'^\s*([-*_])\1{2,}\s*$')        # --- / *** / ___ alone
RE_BULLET = re.compile(r'^\s*[-*+]\s+(.*)$')             # - item / * item / + item
RE_ORDERED = re.compile(r'^\s*\d+[.)]\s+(.*)$')          # 1. item / 2) item
RE_BLOCKQUOTE = re.compile(r'^\s*>\s?(.*)$')
RE_MATH_FENCE = re.compile(r'^\s*\$\$')                   # $$ display-math line
RE_TAG = re.compile(r'\\tag\{[^}]*\}')                   # \tag{1} — not auto-numbered
CALLOUT_LABELS = {"important", "definition", "warning", "example",
                  "note", "tip", "caution", "remark", "theorem", "lemma"}


def _emit_run(runs: list[dict], text: str, bold: bool, italic: bool,
              sup: bool = False, sub: bool = False) -> None:
    run = {"text": text, "bold": bold, "italic": italic}
    if sup:
        run["sup"] = True
    if sub:
        run["sub"] = True
    runs.append(run)


def tokenize_inline(text: str, base_bold: bool = False, base_italic: bool = False) -> list[dict]:
    """Split text into runs, stripping markdown emphasis markers.

    Returns a list of {text, bold, italic[, sup, sub]}. Adjacent runs with
    identical styling are merged. `base_*` force a baseline style on every
    run (used for heading-like / header-cell text)."""
    runs: list[dict] = []
    pos = 0
    for m in RE_SPAN.finditer(text):
        if m.start() > pos:
            _emit_run(runs, text[pos:m.start()], base_bold, base_italic)
        if m.group(1) is not None or m.group(2) is not None:       # bold+italic
            inner = m.group(1) if m.group(1) is not None else m.group(2)
            _emit_run(runs, inner, True, True)
        elif m.group(3) is not None or m.group(4) is not None:     # bold
            inner = m.group(3) if m.group(3) is not None else m.group(4)
            _emit_run(runs, inner, True, base_italic)
        elif m.group(5) is not None:                                # superscript
            _emit_run(runs, m.group(5), base_bold, base_italic, sup=True)
        elif m.group(6) is not None:                                # subscript
            _emit_run(runs, m.group(6), base_bold, base_italic, sub=True)
        else:                                                       # italic
            inner = m.group(7) if m.group(7) is not None else m.group(8)
            _emit_run(runs, inner, base_bold, True)
        pos = m.end()
    if pos < len(text):
        _emit_run(runs, text[pos:], base_bold, base_italic)
    # merge adjacent same-style runs; drop empties
    def _key(r):
        return (r["bold"], r["italic"], r.get("sup", False), r.get("sub", False))
    merged: list[dict] = []
    for r in runs:
        if not r["text"]:
            continue
        if merged and _key(merged[-1]) == _key(r):
            merged[-1]["text"] += r["text"]
        else:
            merged.append(r)
    if not merged:
        merged = [{"text": text, "bold": base_bold, "italic": base_italic}]
    return merged


def strip_inline(text: str) -> str:
    """Plain text with all emphasis markers removed (for titles, counts)."""
    return "".join(r["text"] for r in tokenize_inline(text))


def _parse_table_cells(line: str) -> list[str]:
    """Split a markdown table row '| a | b |' into raw cell strings."""
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def parse_body_blocks(body_lines: list[str]) -> list[dict]:
    """Parse a section's raw body lines into ordered blocks.

    Block kinds (each maps to a deterministic Word primitive in the planner):
      - table     : {ncols, header, rows:[[<cell runs>]...]}
      - code      : {lang, lines:[<raw strings>]}        — verbatim, NOT tokenized
      - equation  : {formula, mode:"display"}            — LaTeX, \\tag stripped
      - list      : {ordered:bool, items:[<runs>...]}    — bullet / numbered
      - callout   : {label, runs}                        — Important/Definition/…
      - paragraph : {runs, text}                         — prose (+ heading_like)
    Thematic breaks (---/***/___) are dropped. Blockquote markers (>) are
    stripped, the quoted text kept as a paragraph. Markers are removed; raw
    code is the only text that bypasses inline tokenization (so `_`/`*` in
    identifiers survive — see docs §3.2)."""
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
            blocks.append(_paragraph_block(para))
        text_buf.clear()

    while i < n:
        line = body_lines[i]

        # fenced code block: ```lang ... ``` — verbatim, no tokenization
        mfence = RE_CODE_FENCE.match(line)
        if mfence:
            flush_text()
            lang = mfence.group(2) or ""
            j = i + 1
            code_lines: list[str] = []
            while j < n and not RE_CODE_FENCE.match(body_lines[j]):
                code_lines.append(body_lines[j])
                j += 1
            blocks.append({"kind": "code", "lang": lang, "lines": code_lines})
            i = j + 1 if j < n else j      # skip the closing fence
            continue

        # display math: $$ ... $$ (single- or multi-line)
        if RE_MATH_FENCE.match(line):
            flush_text()
            buf = [line]
            j = i
            # a single line may open and close ($$...$$); otherwise scan on.
            if line.count("$$") < 2:
                j = i + 1
                while j < n:
                    buf.append(body_lines[j])
                    if "$$" in body_lines[j]:
                        break
                    j += 1
            raw = "\n".join(buf)
            formula = raw.replace("$$", " ")
            formula = RE_TAG.sub("", formula).strip()
            if formula:
                blocks.append({"kind": "equation", "formula": formula, "mode": "display"})
            i = j + 1
            continue

        # thematic break: ---, ***, ___  → dropped
        if RE_THEMATIC.match(line):
            flush_text()
            i += 1
            continue

        # list: a run of consecutive bullet or ordered items
        if RE_BULLET.match(line) or RE_ORDERED.match(line):
            flush_text()
            ordered = RE_ORDERED.match(line) is not None
            items: list[list[dict]] = []
            j = i
            while j < n:
                mb, mo = RE_BULLET.match(body_lines[j]), RE_ORDERED.match(body_lines[j])
                if mo:
                    items.append(tokenize_inline(mo.group(1).strip()))
                elif mb:
                    items.append(tokenize_inline(mb.group(1).strip()))
                else:
                    break
                j += 1
            blocks.append({"kind": "list", "ordered": ordered, "items": items})
            i = j
            continue

        # table: a run of '| ... |' rows
        if RE_TABLE_ROW.match(line):
            j = i
            rows_raw = []
            while j < n and RE_TABLE_ROW.match(body_lines[j]):
                if not RE_TABLE_SEP.match(body_lines[j]):
                    rows_raw.append(_parse_table_cells(body_lines[j]))
                j += 1
            if rows_raw:
                flush_text()
                ncols = max(len(r) for r in rows_raw)
                rows = [[tokenize_inline(c, base_bold=False) for c in (r + [""] * (ncols - len(r)))]
                        for r in rows_raw]
                blocks.append({"kind": "table", "ncols": ncols,
                               "header": len(rows) > 1, "rows": rows})
            i = j
            continue

        # blockquote: keep the quoted text, drop the '>' marker
        mq = RE_BLOCKQUOTE.match(line)
        if mq:
            text_buf.append(mq.group(1))
            i += 1
            continue

        text_buf.append(line)
        i += 1
    flush_text()
    return blocks


def _paragraph_block(para: str) -> dict:
    """Build a paragraph/callout block; heading-like single lines become bold."""
    single = para.replace("\n", " ").strip()
    m = RE_HEADINGLIKE.match(para.strip())
    if m:
        runs = tokenize_inline(m.group(1).strip(), base_bold=True)
        return {"kind": "paragraph", "runs": runs, "text": strip_inline(m.group(1).strip()),
                "heading_like": True}
    # ***num...*** style pseudo-heading: a single line that is entirely one
    # bold-italic span and matches a section-number pattern.
    full = RE_SPAN.fullmatch(para.strip())
    if full and (full.group(1) is not None or full.group(2) is not None):
        inner = (full.group(1) or full.group(2)).strip()
        if RE_NUMBERED.match(inner):
            return {"kind": "paragraph",
                    "runs": [{"text": inner, "bold": True, "italic": True}],
                    "text": inner, "heading_like": True}
    runs = tokenize_inline(single)
    # callout: a paragraph that opens with a bold didactic label
    # (**Important** …, **Definition** …). Render with the label kept bold +
    # an indent in the planner; the template provides no didactic style here.
    if runs and runs[0].get("bold") and runs[0]["text"].strip().lower() in CALLOUT_LABELS:
        return {"kind": "callout", "label": runs[0]["text"].strip(),
                "runs": runs, "text": strip_inline(single)}
    return {"kind": "paragraph", "runs": runs, "text": strip_inline(single)}


def count_paragraphs(blocks: list[dict]) -> int:
    """Number of `add p` ops the planner emits for these blocks (body only).

    Drives validator S7 / plan_validator para_count, so it must match the
    planner exactly: paragraph & callout = 1 each; list = one per item; code =
    one per line; table & equation emit no body `add p`."""
    n = 0
    for b in blocks:
        k = b.get("kind")
        if k in ("paragraph", "callout"):
            n += 1
        elif k == "list":
            n += len(b.get("items", []))
        elif k == "code":
            n += len(b.get("lines", []))
    return n


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
