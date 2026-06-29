#!/usr/bin/env python3
"""inline.py — inline markdown → styled runs (deterministic, no LLM).

Shared by markdown-parser.py (reader) and block_specs.py (block parse handlers)
so the emphasis grammar lives in exactly ONE place. Moving this out of the
hyphenated `markdown-parser.py` module also makes it importable.

A "run" is {text, bold, italic[, sup, sub]}. Order in RE_SPAN matters:
***x*** (bold+italic) before **x** (bold) before <sup>/<sub> before *x*/_x_.
The underscore-italic arm is WORD-BOUNDARIED so identifiers like
`combined_loss` / `d_k` are NOT mangled into italics (docs markdown-fidelity §3.2).
"""

from __future__ import annotations
import re

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

# Inline math spans. MUST be carved out BEFORE emphasis tokenization, otherwise
# the `_` / `*` inside LaTeX (e.g. `\text{SOFA}_{t}`, `a*b`) get eaten as
# emphasis markers and the formula is corrupted. `$$..$$` before `$..$`.
RE_MATH = re.compile(r'\$\$(.+?)\$\$|\$(.+?)\$', re.DOTALL)

# Markdown link `[text](url)`. Rendered as its visible text (the raw
# `[..](..)` syntax must never reach the document). Resolved before math/
# emphasis so the URL's parens/underscores can't be misparsed.
RE_LINK = re.compile(r'\[([^\]]*)\]\(([^)]*)\)')


def _link_repr(text: str, url: str) -> str:
    """Visible representation of a markdown link. Keep just the text (covers
    `[email](mailto:email)` cleanly); for a bare `[](url)` fall back to the url."""
    return text or url


def _emit_run(runs: list[dict], text: str, bold: bool, italic: bool,
              sup: bool = False, sub: bool = False) -> None:
    run = {"text": text, "bold": bold, "italic": italic}
    if sup:
        run["sup"] = True
    if sub:
        run["sub"] = True
    runs.append(run)


def _tokenize_prose(text: str, base_bold: bool, base_italic: bool,
                    runs: list[dict]) -> None:
    """Emphasis tokenization for a math-free text segment (appends to `runs`)."""
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


def tokenize_inline(text: str, base_bold: bool = False, base_italic: bool = False) -> list[dict]:
    """Split text into runs, stripping markdown emphasis markers.

    Returns a list of {text, bold, italic[, sup, sub, math]}. A `math` run carries
    raw LaTeX (no `$`) for inline-equation rendering. Adjacent NON-math runs with
    identical styling are merged. `base_*` force a baseline style on every run
    (used for heading-like / header-cell text)."""
    text = RE_LINK.sub(lambda m: _link_repr(m.group(1), m.group(2)), text)
    runs: list[dict] = []
    pos = 0
    for mm in RE_MATH.finditer(text):
        if mm.start() > pos:
            _tokenize_prose(text[pos:mm.start()], base_bold, base_italic, runs)
        latex = mm.group(1) if mm.group(1) is not None else mm.group(2)
        runs.append({"text": latex, "bold": False, "italic": False, "math": True})
        pos = mm.end()
    if pos < len(text):
        _tokenize_prose(text[pos:], base_bold, base_italic, runs)

    def _key(r):
        return (r["bold"], r["italic"], r.get("sup", False), r.get("sub", False))
    merged: list[dict] = []
    for r in runs:
        if not r["text"]:
            continue
        if r.get("math") or (merged and merged[-1].get("math")):
            merged.append(r)          # math runs never merge with neighbours
        elif merged and _key(merged[-1]) == _key(r):
            merged[-1]["text"] += r["text"]
        else:
            merged.append(r)
    if not merged:
        merged = [{"text": text, "bold": base_bold, "italic": base_italic}]
    return merged


def strip_inline(text: str) -> str:
    """Plain text with all emphasis markers removed (for titles, counts)."""
    return "".join(r["text"] for r in tokenize_inline(text))


def parse_table_cells(line: str) -> list[str]:
    """Split a markdown table row '| a | b |' into raw cell strings."""
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]
