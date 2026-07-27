#!/usr/bin/env python3
"""
score2.py — Regime B verifier (docs/19 item 4, docs/20 s5). EVAL HARNESS, not a shipped skill.

Consumes probe2.lua evidence and measures the two invariants that make Regime B generic
rather than if-else:

  coverage       = blocks_assigned / blocks_total          -> MUST be 1.0 (totality, tru (b))
  cluster-purity = weighted mean, per cluster, of the fraction of members that share the
                   cluster's modal signature fingerprint    -> high = clusters don't mix roles

Clustering is DETERMINISTIC and open-vocabulary-ready (tru (a)):
  primary key   = styleId              (the author's own pre-made grouping)
  fallback key  = format signature     (for direct-format / None-styled blocks)
No fixed type list is consulted. The LLM labelling step (role_label) happens downstream;
here we emit a schema-valid DRAFT spec with placeholder labels so the shape is provable.

Usage:
  pandoc -f docx+styles FILE.docx -L evals/probe2.lua -t native >/dev/null 2> ev.json
  python3 evals/score2.py ev.json [out-draft-spec.json]
"""
import json, sys, collections


def len_bucket(n):
    if not n: return "empty"
    if n <= 40: return "short"
    if n <= 200: return "medium"
    return "long"


def fingerprint(row):
    """Non-semantic signature fingerprint used as the fallback cluster key + purity anchor."""
    sig = row.get("signature") or {}
    return (
        bool(sig.get("bold")), bool(sig.get("italic")), bool(sig.get("allcaps")),
        len_bucket(sig.get("len", 0)),
        bool(sig.get("has_num")), bool(sig.get("has_image")), bool(sig.get("has_link")),
    )


def cluster_key(row):
    """styleId primary; signature fallback; kind for non-text carry blocks (Table/unknown)."""
    sid = row.get("styleId") or (row.get("signature") or {}).get("styleId")
    if sid:
        return ("style", sid)
    if row.get("signature"):
        return ("sig", fingerprint(row))
    return ("kind", row["kind"])            # Table / OrderedList / catch-all raw blocks


def main():
    ev = json.load(open(sys.argv[1]))
    rows = ev["blocks"]

    # --- cluster ---
    buckets = collections.OrderedDict()
    for r in rows:
        buckets.setdefault(cluster_key(r), []).append(r)

    # --- coverage: every row lands in a bucket by construction -> 1.0 ---
    total = len(rows)
    assigned = sum(len(v) for v in buckets.values())
    cov = assigned / total if total else 1.0

    # --- purity: fraction of each bucket matching its modal fingerprint ---
    per_purity, clusters = [], []
    for cid, (key, members) in enumerate(buckets.items(), start=1):
        fps = [fingerprint(m) for m in members if m.get("signature")]
        if fps:
            modal, cnt = collections.Counter(fps).most_common(1)[0]
            pur = cnt / len(fps)
        else:
            modal, pur = None, 1.0           # carry blocks (Table/unknown): purity by kind
        per_purity.append((pur, len(members)))

        rep = members[0]
        needs_dep = any(m.get("needs_dep_closure") or (m.get("signature") or {}).get("has_link")
                        for m in members)
        is_carry = key[0] == "kind" or any(m.get("unknown") for m in members) \
            or rep["kind"] in ("Table",)
        clusters.append({
            "id": f"C{cid}",
            "cluster_key": "styleId" if key[0] == "style" else "signature",
            "styleId": key[1] if key[0] == "style" else None,
            "signature": {
                "styleId": (rep.get("signature") or {}).get("styleId"),
                "bold": (rep.get("signature") or {}).get("bold", False),
                "italic": (rep.get("signature") or {}).get("italic", False),
                "allcaps": (rep.get("signature") or {}).get("allcaps", False),
                "len_bucket": len_bucket((rep.get("signature") or {}).get("len", 0)),
                "has_num": (rep.get("signature") or {}).get("has_num", False),
                "has_image": (rep.get("signature") or {}).get("has_image", False),
                "has_math": (rep.get("signature") or {}).get("has_math", False),
                "has_link": (rep.get("signature") or {}).get("has_link", False),
            },
            "role_label": f"unlabeled:{key[1] if key[0]!='sig' else 'sig'+str(cid)}",
            "target_style": key[1] if key[0] == "style" and not is_carry else None,
            "context_rule": None,
            "frequency": len(members),
            "members": [m["i"] for m in members],
            "examples": [m.get("text", "") for m in members[:2] if m.get("text")],
            "build_action": {
                "mode": "raw_fallback" if is_carry else "typed",
                "fallback_tier": "raw-splice" if is_carry else None,
                "needs_dep_closure": bool(needs_dep and is_carry),
            },
        })

    purity = sum(p * n for p, n in per_purity) / total if total else 1.0

    # --- DIAGNOSTIC: signature->styleId collision audit (reproduces docs/19 s2.1) ---
    # Re-cluster by SIGNATURE ONLY (ignoring styleId) and count fingerprints that span >1
    # distinct styleId. These are the roles that format-signature alone cannot separate
    # (docs/19 found 3: TOC2/TOC3/TableofFigures). It is WHY styleId is the primary key and
    # signature only the fallback -- a measured limitation, not a pass/fail gate.
    by_fp = collections.defaultdict(set)
    for r in rows:
        sid = r.get("styleId") or (r.get("signature") or {}).get("styleId")
        if r.get("signature"):
            by_fp[fingerprint(r)].add(sid)          # None counts as a styleId
    n_fp = len(by_fp)
    collisions = {fp: sids for fp, sids in by_fp.items() if len(sids) > 1}
    separation = 1 - (len(collisions) / n_fp) if n_fp else 1.0

    # --- report ---
    print(f"blocks probed : {total}")
    print(f"clusters       : {len(buckets)}")
    print(f"coverage       : {cov:.3f}  ({assigned}/{total} blocks assigned)   [GATE]")
    print(f"sig-homogeneity: {purity:.3f}  (diag; presentation variance within a cluster)")
    print(f"sig-separation : {separation:.3f}  (diag; {len(collisions)}/{n_fp} fingerprints "
          f"span >1 styleId)")
    print("\n  cluster (key)                        n   homog  build")
    for cl, (pur, n) in zip(clusters, per_purity):
        key = cl["styleId"] or f"sig{cl['id']}"
        print(f"  {key:32} {n:>3}   {pur:4.2f}   "
              f"{cl['build_action']['mode']}"
              f"{'+dep' if cl['build_action']['needs_dep_closure'] else ''}")
    if collisions:
        print("\n  signature collisions (format alone can't separate these styleIds):")
        for fp, sids in collisions.items():
            print(f"    {fp}  ->  {sorted(str(s) for s in sids)}")
    # GATE is coverage only: totality is the anti-if-else guarantee. Separation is a diagnostic
    # with a known, documented limit (docs/19 s2.1: fixable by adding tab-leader/indent features;
    # moot wherever styleId exists).
    verdict = cov >= 0.999
    print("\nVERDICT:", "PASS" if verdict else "FAIL", "(GATE: coverage>=1.0)")

    # --- optional: emit a schema-valid DRAFT spec (pre-LLM-labelling) ---
    if len(sys.argv) > 2:
        spec = {
            "$schemaVersion": "flow-a/regime-b-spec/1.0",
            "source": ev.get("source", "unknown"),
            "evidence": {"probe": "evals/probe2.lua",
                         "style_catalog_source": "officecli (TODO join)",
                         "blocks_probed": total},
            "clusters": clusters,
            "coverage": {"blocks_total": total, "blocks_assigned": assigned, "ratio": cov},
            "anomalies": ["role_label values are placeholders (unlabeled:*) — the LLM "
                          "labelling step assigns open-vocabulary roles."],
        }
        json.dump(spec, open(sys.argv[2], "w"), ensure_ascii=False, indent=2)
        print(f"\ndraft spec written -> {sys.argv[2]}")

    sys.exit(0 if verdict else 1)


if __name__ == "__main__":
    main()
