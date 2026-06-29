#!/usr/bin/env python3
"""Semantic classifier (v6) — document_tree → semantic.ir.json.

LAYER: Semantic tier (the only tier allowed to be non-deterministic).
It assigns each heading node a `semantic_role` from the active profile's
vocabulary — "what this node *is*", independent of any template style.

Two ways to produce semantic.ir.json:

  1. Deterministic stub (this script, default). Rule-based keyword matching
     against the profile's `keyword_rules` over the heading titles. Adds real
     value for standard Vietnamese headings (references/conclusion/appendix…)
     and is the guaranteed fallback. Runs offline, no model.

  2. LLM (the OpenCode/Qwen agent). For ambiguous or non-standard headings the
     agent may write semantic.ir.json by hand, reading ONLY the heading tree
     (titles + levels + word_count from content.ir.json `document_tree`), never
     the full body. Same schema as below. `--check` validates that file.

Hard rule: semantic_role MUST be in the profile vocabulary. Unknown roles are
clamped to the profile default (never flow downstream). Style/section/paraId do
NOT belong here — that is the deterministic logical/physical tiers' job.

Usage:
    python3 tools/semantic_classifier.py \\
        --content content.ir.json \\
        --profile profiles/vn-thesis.json \\
        --output semantic.ir.json
    python3 tools/semantic_classifier.py --check semantic.ir.json \\
        --profile profiles/vn-thesis.json
"""

from __future__ import annotations
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import contracts
from role_matcher import RoleMatcher

# confidence assigned by the deterministic stub
CONF_KEYWORD = 0.9     # matched a profile keyword rule
CONF_FALLBACK = 0.3    # nothing matched → default role (LLM stage-2 candidate)
LOW_CONF = 0.7         # below this → flagged for lazy stage-2 (heading+summary)

# router (offline char-ngram) thresholds
TAU_MATCH = 0.16       # min cosine to accept an n-gram match over the default role
CONF_NGRAM_BASE = 0.5  # n-gram confidence = base + similarity, capped below keyword


def _load_json(path: str, label: str):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[semantic] ERROR: cannot load {label}: {e}", file=sys.stderr)
        sys.exit(1)


def _iter_tree(nodes: list[dict]):
    """Yield every node in document_tree, depth-first (document order)."""
    for n in nodes:
        yield n
        yield from _iter_tree(n.get("children", []))


def _tree_index(tree: list[dict]) -> dict:
    """node_id -> {title, level, first_paragraph} for enriching a stage-2 worklist."""
    idx: dict[str, dict] = {}
    for n in _iter_tree(tree):
        idx[n["node_id"]] = {
            "title": n.get("title", ""),
            "level": n.get("level"),
            "first_paragraph": n.get("first_paragraph", ""),
        }
    return idx


def classify_stub(content_ir: dict, profile: dict) -> list[dict]:
    """Rule-based role assignment from heading titles (deterministic)."""
    rules = profile.get("keyword_rules", [])
    default_role = profile.get("default_role", "generic")
    tree = content_ir.get("document_tree")
    if not tree:
        print("[semantic] ERROR: content IR has no document_tree (re-run the "
              "parser; P0 adds it)", file=sys.stderr)
        sys.exit(1)

    out: list[dict] = []
    for node in _iter_tree(tree):
        title_u = node["title"].upper()
        role = default_role
        evidence = "fallback"
        conf = CONF_FALLBACK
        for rule in rules:
            if any(kw.upper() in title_u for kw in (rule.get("keywords") or rule.get("any") or [])):
                role = rule["role"]
                evidence = "heading"
                conf = CONF_KEYWORD
                break
        out.append({
            "node_id": node["node_id"],
            "semantic_role": role,
            "confidence": conf,
            "evidence": evidence,
        })
    return out


def classify_router(content_ir: dict, profile: dict, lazy: bool = False) -> list[dict]:
    """Confidence-routed role assignment (adaptation_research.md S2 + S5).

    Tier 1: profile keyword rules (exact, conf 0.9). Tier 2: offline char-ngram
    cosine to each role (RoleMatcher) — catches paraphrases the keywords miss,
    language-agnostically. Tier 3 (lazy, opt-in): for headings that stay below
    TAU_MATCH, re-score using title + the node's first_paragraph. Nothing ever
    leaves the profile vocabulary; low scores fall back to the default role."""
    rules = profile.get("keyword_rules", [])
    default_role = profile.get("default_role", "generic")
    tree = content_ir.get("document_tree")
    if not tree:
        print("[semantic] ERROR: content IR has no document_tree", file=sys.stderr)
        sys.exit(1)
    matcher = RoleMatcher(profile)

    out: list[dict] = []
    for node in _iter_tree(tree):
        title = node["title"]
        title_u = title.upper()
        # tier 1: keyword rules
        role, evidence, conf = default_role, "fallback", CONF_FALLBACK
        for rule in rules:
            if any(kw.upper() in title_u for kw in (rule.get("keywords") or rule.get("any") or [])):
                role, evidence, conf = rule["role"], "heading", CONF_KEYWORD
                break
        # tier 2: n-gram similarity
        if evidence == "fallback":
            r2, sim = matcher.match(title)
            # tier 3: lazy first_paragraph escalation
            if sim < TAU_MATCH and lazy and node.get("first_paragraph"):
                r3, sim3 = matcher.match(title + " " + node["first_paragraph"])
                if sim3 > sim:
                    r2, sim, evidence = r3, sim3, "ngram+summary"
            if sim >= TAU_MATCH:
                role = r2
                conf = round(min(0.85, CONF_NGRAM_BASE + sim), 2)
                evidence = evidence if evidence == "ngram+summary" else "ngram"
        out.append({"node_id": node["node_id"], "semantic_role": role,
                    "confidence": conf, "evidence": evidence})
    return out


def validate_roles(nodes: list[dict], profile: dict) -> tuple[list[dict], list[str]]:
    """Clamp unknown roles to the profile default; return (clean, warnings)."""
    vocab = set(profile.get("role_vocabulary", []))
    default_role = profile.get("default_role", "generic")
    warnings: list[str] = []
    clean: list[dict] = []
    for n in nodes:
        role = n.get("semantic_role")
        if role not in vocab:
            warnings.append(f"node {n.get('node_id')}: role '{role}' not in "
                            f"profile vocabulary → clamped to '{default_role}'")
            n = {**n, "semantic_role": default_role, "confidence": CONF_FALLBACK,
                 "evidence": "clamped"}
        clean.append(n)
    return clean, warnings


def quality_gate(nodes: list[dict], profile: dict) -> list[str]:
    """Soft warnings (not fatal): high generic ratio / low mean confidence
    suggest the heading set is unusual for this profile → consider the LLM
    path or a different profile."""
    if not nodes:
        return ["no nodes classified"]
    default_role = profile.get("default_role", "generic")
    generic = sum(1 for n in nodes if n["semantic_role"] == default_role)
    mean_conf = sum(n["confidence"] for n in nodes) / len(nodes)
    warns: list[str] = []
    if generic / len(nodes) > 0.6:
        warns.append(f"{generic}/{len(nodes)} nodes are '{default_role}' "
                     f"(>60%): headings may not match profile '{profile.get('id')}'")
    if mean_conf < 0.5:
        warns.append(f"mean confidence {mean_conf:.2f} is low: consider the "
                     f"LLM semantic pass or a different profile")
    return warns


def build_ir(nodes: list[dict], profile: dict, model: str) -> dict:
    low = sum(1 for n in nodes if n["confidence"] < LOW_CONF)
    return {
        "model": model,
        "profile": profile.get("id"),
        "evidence_budget": {
            "heading_only": len(nodes) - low,
            "needs_stage2": low,
        },
        "nodes": nodes,
    }


def main():
    ap = argparse.ArgumentParser(description="Semantic classifier v6 (stub + validator)")
    ap.add_argument("--content", help="content.ir.json (with document_tree)")
    ap.add_argument("--profile", required=True, help="profiles/<id>.json")
    ap.add_argument("--output", "-o", default="semantic.ir.json")
    ap.add_argument("--check", metavar="SEMANTIC_IR",
                    help="validate an existing semantic.ir.json (e.g. LLM-written) "
                         "against the profile vocabulary, rewrite it clamped, and exit")
    ap.add_argument("--emit-worklist", metavar="PATH",
                    help="classify mode: ALSO write the low-confidence nodes "
                         "(title+level+first_paragraph + legal roles) here, for a "
                         "SELECTIVE LLM stage-2 pass (the escalation worklist)")
    ap.add_argument("--merge", metavar="ANSWERS",
                    help="merge an LLM stage-2 answers file "
                         "(nodes[].{node_id,semantic_role[,confidence]}) into the "
                         "semantic.ir.json at --output; validate+clamp; rewrite & exit")
    ap.add_argument("--backend", choices=["keyword", "router"], default="keyword",
                    help="keyword = exact substring stub (default, parity); "
                         "router = keyword + offline char-ngram similarity (S2)")
    ap.add_argument("--lazy", action="store_true",
                    help="router only: escalate low-similarity headings with the "
                         "node's first_paragraph (S5)")
    args = ap.parse_args()

    profile = contracts.resolve_profile(args.profile)

    if args.merge:
        # Stage-2 escalation: overlay the LLM's answers for the (low-confidence)
        # nodes it was asked to reconsider onto the deterministic semantic.ir.json.
        # Only listed node_ids change; everything else keeps its stage-1 role.
        target = args.output
        ir = _load_json(target, "semantic IR (--output target)")
        answers = _load_json(args.merge, "stage-2 answers")
        by_id = {a["node_id"]: a for a in answers.get("nodes", []) if a.get("node_id")}
        patched = 0
        for n in ir.get("nodes", []):
            a = by_id.get(n["node_id"])
            if a and a.get("semantic_role"):
                n["semantic_role"] = a["semantic_role"]
                n["confidence"] = a.get("confidence", CONF_KEYWORD)
                n["evidence"] = a.get("evidence", "llm-stage2")
                patched += 1
        nodes, warns = validate_roles(ir.get("nodes", []), profile)
        for w in warns:
            print(f"[semantic] WARN: {w}", file=sys.stderr)
        ir["nodes"] = nodes
        ir["profile"] = profile.get("id")
        low = sum(1 for n in nodes if n["confidence"] < LOW_CONF)
        ir["evidence_budget"] = {"heading_only": len(nodes) - low, "needs_stage2": low}
        with open(target, "w", encoding="utf-8") as f:
            json.dump(ir, f, ensure_ascii=False, indent=2)
        print(f"[semantic] merged {patched} stage-2 answers into {target} "
              f"({len(warns)} clamped, {low} still low-confidence)", file=sys.stderr)
        return

    if args.check:
        ir = _load_json(args.check, "semantic IR")
        nodes, warns = validate_roles(ir.get("nodes", []), profile)
        for w in warns:
            print(f"[semantic] WARN: {w}", file=sys.stderr)
        for w in quality_gate(nodes, profile):
            print(f"[semantic] GATE: {w}", file=sys.stderr)
        ir["nodes"] = nodes
        ir["profile"] = profile.get("id")
        with open(args.check, "w", encoding="utf-8") as f:
            json.dump(ir, f, ensure_ascii=False, indent=2)
        print(f"[semantic] checked {args.check}: {len(nodes)} nodes, "
              f"{len(warns)} clamped", file=sys.stderr)
        return

    if not args.content:
        ap.error("--content is required unless --check is used")
    content_ir = contracts.load_and_validate(args.content, "content.ir", "content IR")
    if args.backend == "router":
        nodes = classify_router(content_ir, profile, lazy=args.lazy)
        model = "ngram-router" + ("+lazy" if args.lazy else "")
    else:
        nodes = classify_stub(content_ir, profile)
        model = "deterministic-stub"
    nodes, warns = validate_roles(nodes, profile)
    for w in warns:
        print(f"[semantic] WARN: {w}", file=sys.stderr)
    for w in quality_gate(nodes, profile):
        print(f"[semantic] GATE: {w}", file=sys.stderr)

    ir = build_ir(nodes, profile, model=model)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(ir, f, ensure_ascii=False, indent=2)
    matched = sum(1 for n in nodes if n["evidence"] == "heading")
    print(f"[semantic] Wrote {args.output}: {len(nodes)} nodes "
          f"({matched} keyword-matched, {ir['evidence_budget']['needs_stage2']} "
          f"low-confidence)", file=sys.stderr)

    # Selective-escalation worklist: the nodes the deterministic pass was unsure
    # about, enriched with what the LLM needs to decide (title, level, first
    # paragraph) + the legal roles. The LLM reconsiders ONLY these, then `--merge`.
    if args.emit_worklist:
        idx = _tree_index(content_ir.get("document_tree", []))
        work = [
            {"node_id": n["node_id"], "current_role": n["semantic_role"],
             "confidence": n["confidence"], **idx.get(n["node_id"], {})}
            for n in nodes if n["confidence"] < LOW_CONF
        ]
        worklist = {
            "profile": profile.get("id"),
            "role_vocabulary": profile.get("role_vocabulary", []),
            "role_descriptions": profile.get("role_descriptions", {}),
            "instructions": ("Assign each node a semantic_role from role_vocabulary "
                             "(meanings in role_descriptions). Reply as "
                             "{\"nodes\":[{\"node_id\",\"semantic_role\",\"confidence\"}]} "
                             "then run semantic_classifier --merge."),
            "nodes": work,
        }
        with open(args.emit_worklist, "w", encoding="utf-8") as f:
            json.dump(worklist, f, ensure_ascii=False, indent=2)
        print(f"[semantic] Wrote stage-2 worklist {args.emit_worklist}: "
              f"{len(work)} low-confidence node(s) for the LLM", file=sys.stderr)


if __name__ == "__main__":
    main()
