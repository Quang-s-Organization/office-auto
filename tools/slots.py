#!/usr/bin/env python3
"""slots.py — genre-agnostic SLOT / FURNITURE classification of a template body.

The core question for ANY (template × content) pair: which template elements are
SLOTS the incoming content fills, and which are FIXED FURNITURE the content never
mentions? An element is a SLOT (→ remove + rebuild from content) when there is
positive evidence the content fills it; otherwise it is FURNITURE (→ preserve).

This is the inversion described in docs/design-preserve-generalization-2026-06-29.md:
removal requires positive evidence, so the safe default is PRESERVE. No per-genre
lists — the same signals work for admin / academic / legal / advertising. The
anchors are chosen ADAPTIVELY by the strongest structural signal the template
actually provides, so the same code fits both archetypes:

  1. heading anchors  — a paragraph on a real Heading style. STYLED templates
     (theses, reports) carry these; they define the content region precisely.
  2. placeholder text — empty-in-context, dotted leaders "……", "____", "{{…}}",
     "[…]", "xxx", "Lorem" (intrinsic, language-agnostic).
  3. content alignment — a paragraph whose text matches a section the planner
     will EMIT (catches bare form labels like "QUYẾT ĐỊNH" in UNSTYLED admin
     templates that have no heading styles at all).

Signal (3) is a FALLBACK, used only when the template has NO heading anchors.
In a styled template the headings already bound the content region exactly, and
matching against content titles there does harm — a cover line or a Table-of-
Contents entry whose text equals a section title ("BỘ GIÁO DỤC…", "DANH MỤC…")
would drag the span up into the front matter and delete the cover/TOC. So when
headings exist we trust them and ignore (3); only a style-less template (where
the heading signal is empty) leans on content alignment. And (3) only counts
sections that are actually emitted (intent replace/insert) — a section the
profile marks `preserve`/`remove` is NOT going to fill a slot, so it must not
define one (this is what `emitted_tags` carries).

Anchors define a SLOT SPAN [first anchor … last anchor]; every direct paragraph
AND every table inside the span is a slot (rebuilt from content). Everything
OUTSIDE the span is furniture (preserved): front matter / cover / TOC before the
span, signature / "Nơi nhận" / footnote scaffolding after it. Tables outside the
span (letterhead, signature grids) are never touched; tables inside it are
example/placeholder tables the content replaces. `front_matter_strategy` lets a
profile override the pre-span front region: "preserve" (default) keeps it,
"replace" absorbs it into the span because the content supplies its own.

Shared by planner.py (emits removes + trailing-furniture moves) and
validation_checks.py (S9 furniture-survival). Both pass the SAME inputs so the
two agree on what counts as furniture.
"""

from __future__ import annotations
import re

# ── intrinsic placeholder patterns (genre/language-agnostic) ───────────────
_DOTS = re.compile(r"[.…]{3,}")        # "...." or "……" (3+ dots / ellipses)
_UNDERSCORES = re.compile(r"_{3,}")
_MUSTACHE = re.compile(r"\{\{.*?\}\}")
_BRACKET = re.compile(r"^\s*\[[^\]]*\]\s*$")
_XXX = re.compile(r"\bx{3,}\b", re.IGNORECASE)
_LOREM = re.compile(r"lorem ipsum", re.IGNORECASE)


def is_placeholder(text: str) -> bool:
    """True when a NON-empty paragraph looks like a fill-in slot (not real prose).
    Empty paragraphs are handled positionally (interior-of-span), not here."""
    t = (text or "").strip()
    if not t:
        return False
    if _DOTS.search(t) or _UNDERSCORES.search(t) or _MUSTACHE.search(t):
        return True
    if _BRACKET.match(t) or _XXX.search(t) or _LOREM.search(t):
        return True
    if "…" in t:                       # a lone ellipsis char, e.g. "Về việc …"
        return True
    return False


def _norm(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[.…]+", "", s)        # drop dotted leaders
    s = re.sub(r"\s+", " ", s)
    return s.strip(" :-")


def _content_titles(content_ir: dict, emitted_tags: "set | None" = None) -> list[str]:
    """Normalized titles of content sections used to detect content-aligned slots.

    When `emitted_tags` is given, only sections the planner will EMIT
    (intent replace/insert) contribute — a preserve/remove section fills no slot,
    so it must not define one. `None` means "no intent info" → use all titles.
    """
    out = []
    for s in (content_ir or {}).get("sections", []):
        if not (s.get("title") or "").strip():
            continue
        if emitted_tags is not None and s.get("tag") not in emitted_tags:
            continue
        out.append(_norm(s.get("title") or ""))
    return out


def emitted_tags_from_logical(logical_ir: "dict | None") -> "set | None":
    """Tags of nodes the planner emits (intent != preserve/remove), or None when
    no logical IR is available. Mirrors validation_checks._emitted_tags so the
    planner and the validator agree on which sections define slots."""
    if not logical_ir:
        return None
    return {s.get("node_id") for s in logical_ir.get("sections", [])
            if s.get("intent") not in ("preserve", "remove")}


def aligns_to_content(text: str, titles: list[str]) -> bool:
    """True when a paragraph's text matches a content section title (exact, or a
    shared prefix ≥ 10 chars for truncated/variant form labels)."""
    n = _norm(text)
    if len(n) < 3:
        return False
    for ct in titles:
        if not ct:
            continue
        if n == ct:
            return True
        k = min(len(n), len(ct))
        if k >= 10 and n[:k] == ct[:k]:
            return True
    return False


# ── direct /body children, with table positions reconstructed ──────────────

def body_children(body_sequence: list[dict]) -> list[dict]:
    """Ordered direct children of /body as elements.

    body_sequence lists paragraphs in document order (including paragraphs that
    live inside tables / notes, flagged via their path). A table's position is
    the position of its first cell paragraph (path '/body/tbl[N]/...'). Footnote
    / endnote definitions ('.../footnotes...' or 'note[' paths) are NOT body
    children and are skipped.

    Returns [{kind:'p'|'tbl', pos, para_id?, text?, has_text?, is_heading?,
    tbl_index?}] — pos is the index among direct children.
    """
    children: list[dict] = []
    seen_tables: set[int] = set()
    for p in body_sequence:
        path = p.get("path") or ""
        m = re.match(r"/body/tbl\[(\d+)\]", path)
        if m:                                # a cell paragraph of a body table
            idx = int(m.group(1))
            if idx not in seen_tables:
                seen_tables.add(idx)
                children.append({"kind": "tbl", "tbl_index": idx})
            continue
        if p.get("in_table"):                # footnote/endnote/non-body — skip
            continue
        children.append({
            "kind": "p",
            "para_id": p.get("para_id"),
            "text": p.get("text", ""),
            "has_text": p.get("has_text", bool((p.get("text") or "").strip())),
            "is_heading": p.get("is_heading", False),
        })
    for i, c in enumerate(children):
        c["pos"] = i
    return children


def _anchors(children: list[dict], titles: list[str]) -> list[int]:
    """Slot-span anchor positions, chosen by the strongest structural signal.

    Heading-styled paragraphs are the precise content-region boundary when a
    template has them, so we use headings (+ intrinsic placeholders) and DELIBER-
    ATELY ignore content-title alignment there (it would match cover / TOC lines
    and swallow the front matter). Content alignment is the fallback ONLY for
    style-less templates with no heading anchors (admin letters / forms)."""
    heading = [c["pos"] for c in children
               if c["kind"] == "p" and c.get("is_heading")]
    placeholder = [c["pos"] for c in children
                   if c["kind"] == "p" and is_placeholder(c.get("text", ""))]
    if heading:
        return sorted(set(heading + placeholder))
    aligned = [c["pos"] for c in children
               if c["kind"] == "p" and aligns_to_content(c.get("text", ""), titles)]
    return sorted(set(placeholder + aligned))


def classify(body_sequence: list[dict], body_tables: list[dict],
             content_ir: dict, emitted_tags: "set | None" = None,
             front_matter_strategy: str = "preserve") -> dict:
    """Classify every direct body child as slot or furniture.

    `emitted_tags` (from logical IR) restricts content-alignment matching to
    sections the planner actually emits. `front_matter_strategy` controls the
    pre-span front region: "preserve" (default) keeps cover/TOC as furniture;
    "replace" absorbs it into the slot span (content supplies its own).

    Returns:
      slots             — para_ids to REMOVE (rebuilt from content).
      slot_tables       — tbl_index of every IN-SPAN table to REMOVE (example /
                          placeholder tables the content replaces).
      furniture_paras   — para_ids to PRESERVE.
      furniture_tables  — tbl_index of every preserved (out-of-span) table.
      trailing          — furniture AFTER the slot span, in document order, each
                          {kind, pos, para_id|tbl_index}; the planner moves these
                          to /body end so they sit after the appended content.
      kept_tables_before_trailing — # of preserved tables that are NOT trailing
                          (used to address each trailing table positionally).
      span              — (lo, hi) child positions of the slot span, or None.
    """
    children = body_children(body_sequence)
    titles = _content_titles(content_ir, emitted_tags)

    result = {
        "slots": [], "slot_tables": [], "furniture_paras": [],
        "furniture_tables": [], "trailing": [],
        "kept_tables_before_trailing": 0, "span": None,
    }

    anchors = _anchors(children, titles)

    if not anchors:
        # No positive slot evidence → preserve everything (safe degenerate case).
        for c in children:
            if c["kind"] == "p":
                result["furniture_paras"].append(c.get("para_id"))
            else:
                result["furniture_tables"].append(c["tbl_index"])
        return result

    lo, hi = min(anchors), max(anchors)
    # "replace": the content supplies its own front matter → the pre-span front
    # region (cover/TOC) is part of what gets rebuilt, not preserved.
    if front_matter_strategy == "replace":
        lo = 0
        # Content supplies its own full document (title, sections, references).
        # Extend the slot span to the end so template content after the last
        # anchor (e.g. reference entries following a "References" heading) is
        # also removed rather than preserved as furniture.
        hi = len(children) - 1
    result["span"] = (lo, hi)
    trailing_tables = 0
    for c in children:
        pos = c["pos"]
        in_span = lo <= pos <= hi
        if c["kind"] == "p":
            if in_span:
                if c.get("para_id"):
                    result["slots"].append(c["para_id"])
            else:
                if c.get("para_id"):
                    result["furniture_paras"].append(c["para_id"])
                if pos > hi and c.get("para_id"):
                    result["trailing"].append(
                        {"kind": "p", "pos": pos, "para_id": c["para_id"]})
        else:  # table
            if in_span:
                # Example/placeholder table inside the content region → remove
                # (the content's real tables are appended in its place). Tables
                # OUTSIDE the span (letterhead, signature grids) stay furniture.
                result["slot_tables"].append(c["tbl_index"])
            else:
                result["furniture_tables"].append(c["tbl_index"])
                if pos > hi:
                    trailing_tables += 1
                    result["trailing"].append(
                        {"kind": "tbl", "pos": pos, "tbl_index": c["tbl_index"]})

    result["kept_tables_before_trailing"] = (
        len(result["furniture_tables"]) - trailing_tables)
    result["trailing"].sort(key=lambda x: x["pos"])
    return result


def furniture_paraids(template_ir: dict, content_ir: dict,
                      emitted_tags: "set | None" = None,
                      front_matter_strategy: str = "preserve") -> set:
    """The set of preserved-furniture para_ids — for validator checks that must
    judge the OUTPUT's content paragraphs without flagging template furniture."""
    cls = classify(template_ir.get("body_sequence", []),
                   template_ir.get("body_tables", []), content_ir or {},
                   emitted_tags=emitted_tags,
                   front_matter_strategy=front_matter_strategy)
    return {pid for pid in cls["furniture_paras"] if pid}
