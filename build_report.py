#!/usr/bin/env python3
"""Build script for report.docx"""
import subprocess, json, shutil, time

src_template = "/home/minhquang/office-auto/templates/format_template.docx"
output = "/home/minhquang/office-auto/report.docx"
content_file = "/home/minhquang/office-auto/content.ir.json"

shutil.copy2(src_template, output)
print(f"Copied template to {output}")

H1_2 = "557EE3B3"
H1_4 = "63DE7EE1"
H1_REF = "18DC5A4B"
NORM_SRC = "63CF449C"
INITIAL_ANCHOR = "074DDEE4"
CLEANUP_IDS = [
    "6B73A0C1","4DEAF1F1","49507EB2","30194BD4",
    "0714B04C","3FBC18C5","2E0F0A25","1204F959"
]

def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return r.stdout.strip()

def all_paras():
    out = run(["officecli","query",output,"p","--json"])
    if not out: return set()
    try:
        return {x["format"]["paraId"] for x in json.loads(out)["data"]["results"]}
    except: return set()

def new_pid(before):
    time.sleep(0.3)
    after = all_paras()
    diff = after - before
    print(f"    [debug] before={len(before)} after={len(after)} diff_count={len(diff)} diff={diff}")
    if len(diff)==1: return list(diff)[0]
    if len(diff)>1: return sorted(diff)[-1]
    return None

def add(proto, after_pid):
    before = all_paras()
    res = run(["officecli","add",output,"/body",
               "--from",f"/body/p[@paraId={proto}]",
               "--after",f"/body/p[@paraId={after_pid}]"])
    ok = "Copied to" in res
    print(f"  add(proto={proto}, after={after_pid}) res_ok={ok} res='{res[:50]}'")
    if not ok: return None
    return new_pid(before)

def stxt(pid, text):
    run(["officecli","set",output,f"/body/p[@paraId={pid}]","--prop",f"text={text}"])

def sprp(pid, key, val):
    run(["officecli","set",output,f"/body/p[@paraId={pid}]","--prop",f"{key}={val}"])

def remv(pid):
    run(["officecli","remove",output,f"/body/p[@paraId={pid}]"])

# OPEN
print("=== Opening ===")
run(["officecli","open",output])

# CLONE PROTOTYPES BEFORE CLEANUP
print("=== Cloning prototypes ===")
H2 = add("6B73A0C1", "5DFFF610")  # after SUPERVISOR'S COMMENTS
NORM = add(NORM_SRC, H2) if H2 else None
print(f"  => H2={H2}, NORM={NORM}")

# CLEANUP
print("=== Cleanup ===")
for p in CLEANUP_IDS: remv(p)
print(f"  Removed {len(CLEANUP_IDS)}")

# LOAD CONTENT
data = json.load(open(content_file))
sections = data["sections"]
h1_idx = 0

# BUILD
print("=== Building ===")
total = 0
anchor = INITIAL_ANCHOR

for i, sec in enumerate(sections):
    if not sec.get("verbatim", True): continue
    stype, title = sec["type"], sec["title"]
    body = sec.get("body_paragraphs", [])
    
    if stype == "heading1":
        if h1_idx == 0: proto = H1_2
        elif h1_idx == 1: proto = H1_4
        else: proto = H1_REF
        h1_idx += 1
    elif stype in ("heading2","heading3"):
        proto = H2
    else: continue
    
    pid = add(proto, anchor)
    if not pid:
        print(f"  SKIP heading: {title[:50]}")
        continue
    
    stxt(pid, title)
    if stype == "heading1":
        sprp(pid,"outlineLevel","1"); sprp(pid,"size","16pt"); sprp(pid,"font.ea","Calibri")
    elif stype == "heading2":
        sprp(pid,"outlineLevel","2"); sprp(pid,"size","14pt"); sprp(pid,"font.ea","Calibri")
    elif stype == "heading3":
        sprp(pid,"outlineLevel","3"); sprp(pid,"size","14pt"); sprp(pid,"font.ea","Calibri")
    
    anchor = pid; total += 1
    
    for txt in body:
        pid = add(NORM, anchor)
        if not pid:
            print(f"  SKIP body"); continue
        stxt(pid, txt)
        sprp(pid,"ind.firstLine","1.27cm"); sprp(pid,"lineSpacing","1.3x")
        anchor = pid; total += 1
    print(f"  OK: {title[:60]}")

print(f"  Total: {total}")

# CLOSE
print("=== Closing ===")
run(["officecli","close",output])
print("Done!")
