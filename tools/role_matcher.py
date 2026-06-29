#!/usr/bin/env python3
"""role_matcher.py — offline semantic role matching (adaptation_research.md S2).

The keyword stub only fires on exact substrings; everything else falls to the
default role and loses meaning. This is the middle path between brittle regex
and a free LLM: encode each role (its name + description + keyword terms) and
each heading as a character n-gram TF vector, then assign the role whose vector
is most cosine-similar to the heading.

Why char n-grams, not word embeddings or an LLM:
  - 100% offline, deterministic, no model download, numpy-only (no new dep);
  - language-agnostic — works for Vietnamese and English alike (the design
    docs' worry about a weak local model for Vietnamese never applies here);
  - never hallucinates a role outside the profile vocabulary (closed-set by
    construction — we only score the profile's own roles).

It is a *similarity* signal, not understanding. Use it as a fallback after the
keyword rules and gate it by a confidence threshold; below the threshold the
caller may escalate to a lazy first_paragraph read or the LLM pass.
"""

from __future__ import annotations
import math
import re
import unicodedata
from collections import Counter

_WORD = re.compile(r"\w+", re.UNICODE)


def _normalize(text: str) -> str:
    """Lowercase + strip combining marks so VN diacritics don't fragment the
    n-gram space (so 'phương pháp' and 'PHUONG PHAP' share n-grams)."""
    text = text.lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return text


def _char_ngrams(text: str, lo: int = 3, hi: int = 5) -> Counter:
    """Char n-grams over word-boundary-padded tokens (captures sub-word overlap
    across languages). Includes whole short words too."""
    grams: Counter = Counter()
    for tok in _WORD.findall(_normalize(text)):
        padded = f" {tok} "
        for n in range(lo, hi + 1):
            if len(padded) < n:
                continue
            for k in range(len(padded) - n + 1):
                grams[padded[k:k + n]] += 1
    return grams


def _cosine(a: Counter, b: Counter, idf: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    keys = set(a) & set(b)
    if not keys:
        return 0.0
    num = sum(a[k] * b[k] * idf.get(k, 1.0) ** 2 for k in keys)
    na = math.sqrt(sum((a[k] * idf.get(k, 1.0)) ** 2 for k in a))
    nb = math.sqrt(sum((b[k] * idf.get(k, 1.0)) ** 2 for k in b))
    if na == 0 or nb == 0:
        return 0.0
    return num / (na * nb)


class RoleMatcher:
    """Builds one n-gram profile per role from name + description + keyword
    terms, with IDF weighting computed across roles (rare grams discriminate)."""

    def __init__(self, profile: dict):
        self.default_role = profile.get("default_role", "generic")
        descs = profile.get("role_descriptions", {})
        kw_terms: dict[str, list[str]] = {}
        for rule in profile.get("keyword_rules", []):
            kw_terms.setdefault(rule["role"], []).extend(rule.get("keywords") or rule.get("any") or [])

        self.vectors: dict[str, Counter] = {}
        for role in profile.get("role_vocabulary", []):
            if role == self.default_role:
                continue  # generic has no positive signal; it is the fallback
            parts = [role.replace("_", " "), descs.get(role, "")]
            parts.extend(kw_terms.get(role, []))
            vec = _char_ngrams(" ".join(p for p in parts if p))
            if vec:
                self.vectors[role] = vec

        # IDF over role documents
        df: Counter = Counter()
        for vec in self.vectors.values():
            for g in vec:
                df[g] += 1
        nroles = max(1, len(self.vectors))
        self.idf = {g: math.log((nroles + 1) / (c + 1)) + 1.0 for g, c in df.items()}

    def match(self, text: str) -> tuple[str, float]:
        """Return (best_role, similarity in [0,1]). Falls back to default_role
        with score 0.0 when nothing scores above noise."""
        q = _char_ngrams(text)
        best_role, best = self.default_role, 0.0
        for role, vec in self.vectors.items():
            s = _cosine(q, vec, self.idf)
            if s > best:
                best_role, best = role, s
        return best_role, best
