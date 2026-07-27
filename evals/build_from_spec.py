#!/usr/bin/env python3
"""
build_from_spec.py — compile a structure-spec.json into a .docx via officecli.

EVAL HARNESS (not a shipped skill). Encodes the same Path-B build the building skill performs
at runtime (numbering.md recipes). The spec is a GRAMMAR, not content: this generates a small
nested INSTANCE (N elements per level) with placeholder bodies, honoring numbering.source and
reset. Round-trip parity then scores the grammar re-induced from this instance.

Usage: python3 evals/build_from_spec.py <spec.json> <out.docx> [N_per_level]
"""
import json, subprocess, sys, os

OFFICE = os.path.expanduser("~/.local/bin/officecli")

SCHEME_TO_FMT = {"decimal": "decimal", "upperRoman": "upperRoman", "lowerRoman": "lowerRoman",
                 "upperAlpha": "upperLetter", "lowerAlpha": "lowerLetter"}
ROMAN = [(10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]
VN_LETTERS = list("abcdđe")  # Vietnamese điểm alphabet (subset)


def cli(*args):
    r = subprocess.run([OFFICE, *args], capture_output=True, text=True)
    if r.returncode != 0:
        sys.stderr.write("ERR: " + " ".join(args) + "\n" + r.stderr + "\n")
    return r


def roman(n, upper=True):
    out, x = "", n
    for v, s in ROMAN:
        while x >= v:
            out += s; x -= v
    return out if upper else out.lower()


def ordinal(scheme, i):  # i is 1-based
    if scheme == "decimal": return str(i)
    if scheme == "upperRoman": return roman(i, True)
    if scheme == "lowerRoman": return roman(i, False)
    if scheme == "upperAlpha": return chr(ord("A") + i - 1)
    if scheme == "lowerAlpha": return VN_LETTERS[(i - 1) % len(VN_LETTERS)]
    return str(i)


DELIM = {"period": ".", "oneParen": ")", "twoParens_close": ")", "none": ""}
def delim_text(scheme, i, delim):
    o = ordinal(scheme, i)
    if delim == "period": return f"{o}."
    if delim == "oneParen": return f"{o})"
    if delim == "twoParens": return f"({o})"
    return o


def lvltext(delim, n):  # officecli lvlText for ilvl n-1
    p = f"%{n}"
    return {"period": p + ".", "oneParen": p + ")", "twoParens": f"({p})", "none": p}[delim]


def main():
    spec = json.load(open(sys.argv[1]))
    out = sys.argv[2]
    N = int(sys.argv[3]) if len(sys.argv) > 3 else 2
    levels = spec["document"]["levels"]
    all_auto = all(l["numbering"]["source"] == "auto" for l in levels)

    if os.path.exists(out): os.remove(out)
    cli("create", out)

    # header block first
    hb = spec["document"].get("header_block")
    if hb and hb.get("present"):
        for ln in hb["lines"]:
            props = [f"text={ln['text']}"]
            if ln.get("bold"): props.append("bold=true")
            props.append(f"align={ln.get('align','left')}")
            args = ["add", out, "/body", "--type", "paragraph"]
            for p in props: args += ["--prop", p]
            cli(*args)

    # AUTO: one multi-level abstractnum for all levels
    if all_auto:
        args = ["add", out, "/numbering", "--type", "abstractnum"]
        for idx, l in enumerate(levels):
            n = l["numbering"]
            args += ["--prop", f"level{idx}.format={SCHEME_TO_FMT[n['scheme']]}",
                     "--prop", f"level{idx}.text={lvltext(n['delim'], idx+1)}"]
        cli(*args)
        cli("add", out, "/numbering", "--type", "num", "--prop", "abstractNumId=0")

    # recursive nested instance
    def emit(depth, counters):
        l = levels[depth]
        n = l["numbering"]
        for i in range(1, N + 1):
            body = f"Placeholder body for {l['id']} #{i}."
            if n["source"] == "auto":
                cli("add", out, "/body", "--type", "paragraph",
                    "--prop", f"text={body}", "--prop", "numId=1", "--prop", f"ilvl={depth}")
            else:
                ord_txt = delim_text(n["scheme"], i, n["delim"])
                text = f"{ord_txt} {body}"
                args = ["add", out, "/body", "--type", "paragraph", "--prop", f"text={text}"]
                if l["format"].get("bold"): args += ["--prop", "bold=true"]
                args += ["--prop", f"align={l['format'].get('align','left')}"]
                if l["format"].get("indent"): args += ["--prop", f"indent={l['format']['indent']}"]
                cli(*args)
            if depth + 1 < len(levels):
                emit(depth + 1, counters + [i])

    emit(0, [])
    cli("save", out)
    v = cli("validate", out)
    print(v.stdout.strip() or v.stderr.strip())
    print(f"built {out} from {sys.argv[1]} (N={N}/level, all_auto={all_auto})")


if __name__ == "__main__":
    main()
