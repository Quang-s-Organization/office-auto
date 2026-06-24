#!/usr/bin/env python3
"""Low-level officecli operation wrappers with retry and error handling.

Provides safe wrappers for: add, set, remove, query, open, close.
Handles paraId capture via the diff pattern (before/after snapshot).
"""

from __future__ import annotations
import json
import subprocess
import sys
import time
from typing import Optional


def _run(cmd: list[str], timeout: int = 30) -> str:
    """Run an officecli command and return stdout."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if r.returncode != 0:
            msg = f"[composer] ERROR: {' '.join(cmd)}\nSTDERR: {r.stderr[:300]}"
            print(msg, file=sys.stderr)
            return ""
        return r.stdout.strip()
    except subprocess.TimeoutExpired:
        print(f"[composer] ERROR: Timed out after {timeout}s: {' '.join(cmd)}",
              file=sys.stderr)
        return ""


def _all_para_ids(filepath: str) -> set[str]:
    """Get the set of all paragraph paraIds in the document."""
    out = _run(["officecli", "query", filepath, "p", "--json"])
    if not out:
        return set()
    try:
        data = json.loads(out)
        results = data.get("data", {}).get("results", [])
        return {r["format"]["paraId"] for r in results if "format" in r}
    except (json.JSONDecodeError, KeyError, TypeError):
        return set()


def _extract_last_para_id(filepath: str) -> Optional[str]:
    """Extract paraId of last paragraph by querying ALL and taking last result."""
    out = _run(["officecli", "query", filepath, "p", "--json"])
    if not out:
        return None
    try:
        data = json.loads(out)
        results = data.get("data", {}).get("results", [])
        if not results:
            return None
        # Results are in document order; last element = last paragraph
        last = results[-1]
        return last.get("format", {}).get("paraId")
    except (json.JSONDecodeError, KeyError, IndexError):
        return None


def open_doc(filepath: str) -> bool:
    """Open a document for editing. Returns True on success."""
    out = _run(["officecli", "open", filepath])
    ok = out and "error" not in out.lower()
    if not ok:
        print(f"[composer] WARN: open may have failed: {out[:100]}", file=sys.stderr)
    return ok


def close_doc(filepath: str) -> bool:
    """Close (save) a document. Returns True on success."""
    out = _run(["officecli", "close", filepath])
    ok = "error" not in out.lower() if out else False
    return ok


def add_paragraph(
    filepath: str,
    proto_para_id: str,
    after_para_id: str,
    max_retries: int = 3
) -> Optional[str]:
    """Clone a prototype paragraph after an anchor.

    Uses diff pattern: capture all paraIds before/after, return new one.
    Optimized: no sleep, single retry only on failure.
    """
    before = _all_para_ids(filepath)

    for attempt in range(max_retries):
        _run([
            "officecli", "add", filepath, "/body",
            "--from", f"/body/p[@paraId={proto_para_id}]",
            "--after", f"/body/p[@paraId={after_para_id}]",
        ])

        after = _all_para_ids(filepath)
        diff = after - before

        if len(diff) == 1:
            new_id = list(diff)[0]
            # Quick verify it's readable
            _run([
                "officecli", "query", filepath,
                f"/body/p[@paraId={new_id}]", "--json"
            ])
            return new_id
        elif len(diff) > 1:
            new_id = sorted(diff)[-1]
            return new_id
        else:
            if attempt < max_retries - 1:
                import time
                time.sleep(0.5)

    return None


def set_text(filepath: str, para_id: str, text: str) -> bool:
    """Set the text content of a paragraph. Returns True on success."""
    out = _run([
        "officecli", "set", filepath,
        f"/body/p[@paraId={para_id}]",
        "--prop", f"text={text}",
    ])
    return "error" not in out.lower() if out else False


def set_prop(filepath: str, para_id: str, key: str, value: str) -> bool:
    """Set an OOXML property on a paragraph. Returns True on success."""
    out = _run([
        "officecli", "set", filepath,
        f"/body/p[@paraId={para_id}]",
        "--prop", f"{key}={value}",
    ])
    return "error" not in out.lower() if out else False


def remove_paragraph(filepath: str, para_id: str) -> bool:
    """Remove a paragraph from the document. Returns True on success."""
    out = _run([
        "officecli", "remove", filepath,
        f"/body/p[@paraId={para_id}]",
    ])
    return "error" not in out.lower() if out else False


def refresh_doc(filepath: str) -> bool:
    """Refresh TOC field codes. Returns True on success."""
    out = _run(["officecli", "refresh", filepath])
    ok = "error" not in out.lower() if out else False
    # Need open/close around refresh
    return ok


def get_text(filepath: str, para_id: str) -> Optional[str]:
    """Read back the text content of a paragraph."""
    out = _run([
        "officecli", "query", filepath,
        f"/body/p[@paraId={para_id}]", "--json"
    ])
    if not out:
        return None
    try:
        data = json.loads(out)
        return data["data"]["results"][0].get("text", "")
    except (json.JSONDecodeError, KeyError, IndexError):
        return None


def query_heading_info(filepath: str, style: str) -> list[dict]:
    """Query all paragraphs of a given style and return key info."""
    out = _run([
        "officecli", "query", filepath,
        f"p[style={style}]", "--json"
    ])
    if not out:
        return []
    try:
        data = json.loads(out)
        results = []
        for r in data.get("data", {}).get("results", []):
            fmt = r.get("format", {})
            results.append({
                "para_id": fmt.get("paraId"),
                "text": r.get("text", ""),
                "style": fmt.get("style"),
                "outline_level": fmt.get("outlineLevel"),
                "size": fmt.get("effective.size"),
                "font": fmt.get("effective.font.ascii"),
                "ind_first_line": fmt.get("ind.firstLine"),
            })
        return results
    except (json.JSONDecodeError, KeyError):
        return []
