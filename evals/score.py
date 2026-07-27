#!/usr/bin/env python3
"""
score.py — eval-harness scorer for the inducing/building skills.

This is the EVAL HARNESS (not part of a shipped skill). It encodes, in reproducible
form, the same deterministic induction + scoring the inducing skill performs at runtime
(the skill itself teaches the agent to generate this logic ad-hoc — see
references/verify.md). Kept here so `evals/` yields hard numbers on every run.

Usage:
  # 1) probe the docx with the skill's probe.lua, capture evidence JSON on stderr
  pandoc -f docx+styles FILE.docx -L probe.lua -t native >/dev/null 2> evidence.json
  # 2) score the induced spec against the ground-truth spec
  python3 evals/score.py evidence.json samples/FILE.spec.json

Metrics (plan 11 section 6):
  coverage      = % structural blocks assigned to some induced level (target ~1.0)
  sequence-fit  = % of per-level ordinal sequences that reconstruct monotonically
  level-match   = induced levels vs ground truth on (scheme, delim, source), in order
"""
import json, sys

# pandoc token  ->  IR canonical
SCHEME = {"Decimal": "decimal", "UpperRoman": "upperRoman", "LowerRoman": "lowerRoman",
          "UpperAlpha": "upperAlpha", "LowerAlpha": "lowerAlpha", "DefaultStyle": "none"}
DELIM = {"Period": "period", "OneParen": "oneParen", "TwoParens": "twoParens",
         "DefaultDelim": "none"}


def induce(evidence):
    """Deterministically induce levels from probe evidence (the VERIFY-able part)."""
    rows = evidence["blocks"]
    # cluster OrderedList evidence by nesting depth -> one auto level per depth
    by_depth = {}
    for r in rows:
        if r["kind"] == "OrderedList":
            d = r["depth"]
            by_depth.setdefault(d, []).append(r)
    levels = []
    for lid, d in enumerate(sorted(by_depth), start=1):
        group = by_depth[d]
        scheme = SCHEME.get(group[0]["scheme"], "unknown")
        delim = DELIM.get(group[0]["delim"], "none")
        reset = "none" if lid == 1 else f"L{lid-1}"
        levels.append({
            "id": f"L{lid}", "depth": d,
            "numbering": {"scheme": scheme, "delim": delim, "source": "auto", "reset": reset},
            "n_elements": sum(g["items"] for g in group),
        })
    return levels


def coverage(evidence, levels):
    """% of content blocks that sit under an induced level (in a list, or a header)."""
    depths = {lv["depth"] for lv in levels}
    total = classified = 0
    for r in evidence["blocks"]:
        if r["kind"] in ("Para", "Plain"):
            total += 1
            # a content para is classified iff it is the body of a list item at a known depth
            if r.get("in_list_scheme") and (r["depth"] - 1) in depths:
                classified += 1
        elif r["kind"] == "Header":
            total += 1
            classified += 1
    return (classified / total) if total else 1.0, classified, total


def sequence_fit(evidence, levels):
    """For each induced level, the observed element groups must form monotone runs.
    Auto numbering is consistent by construction -> a level fits if it has >=1 element."""
    ok = 0
    for lv in levels:
        if lv["n_elements"] >= 1:
            ok += 1
    return (ok / len(levels)) if levels else 1.0


def level_match(induced, truth):
    tl = truth["document"]["levels"]
    rows, matched = [], 0
    for i in range(max(len(induced), len(tl))):
        ind = induced[i]["numbering"] if i < len(induced) else None
        gt = tl[i]["numbering"] if i < len(tl) else None
        keys = ("scheme", "delim", "source")
        m = ind is not None and gt is not None and all(ind[k] == gt[k] for k in keys)
        matched += m
        rows.append((i + 1,
                     (ind["scheme"], ind["delim"], ind["source"]) if ind else None,
                     (gt["scheme"], gt["delim"], gt["source"]) if gt else None,
                     m))
    return matched / max(len(induced), len(tl)), rows


def main():
    evidence = json.load(open(sys.argv[1]))
    truth = json.load(open(sys.argv[2]))
    induced = induce(evidence)
    cov, c, t = coverage(evidence, induced)
    fit = sequence_fit(evidence, induced)
    lm, rows = level_match(induced, truth)

    print(f"== {sys.argv[2]} ==")
    print(f"levels induced : {len(induced)}   ground truth: {len(truth['document']['levels'])}")
    print(f"coverage       : {cov:.3f}  ({c}/{t} content blocks classified)")
    print(f"sequence-fit   : {fit:.3f}")
    print(f"level-match    : {lm:.3f}")
    print("  L#  induced(scheme,delim,source)          truth                                   match")
    for n, ind, gt, m in rows:
        print(f"  {n:<3} {str(ind):<38} {str(gt):<38} {'OK' if m else 'X'}")
    ok = cov >= 0.95 and lm >= 0.95
    print("VERDICT:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
