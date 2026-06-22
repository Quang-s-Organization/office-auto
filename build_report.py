#!/usr/bin/env python3
"""Build report.docx from noidung.md content + format_template.docx template."""
import subprocess
import json

DOCX = "report.docx"

# Prototype paraIds from template query
H2_PROTOTYPE = "05E2D782"   # Heading2 prototype
H3_PROTOTYPE = "15D7D3CD"   # Heading3 prototype
NORMAL_PROTOTYPE = "3B91656F"  # Normal body prototype

# Read content from IR
with open("content.ir.json", "r") as f:
    ir = json.load(f)

# Helper functions
def add_paragraph(prototype_paraId, after_paraId):
    cmd = f'officecli add {DOCX} /body --from /body/p[@paraId={prototype_paraId}] --after /body/p[@paraId={after_paraId}]'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    # Extract the new paraId from output
    output = result.stdout.strip()
    if "Added paragraph at" in output:
        new_para = output.split("Added paragraph at ")[1].strip()
        return new_para
    return None

def set_text(path, text):
    cmd = f'officecli set {DOCX} {path} --prop "text={text}"'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout.strip()

def set_body(path, text):
    """Set body text on a Normal paragraph (preserves style)."""
    cmd = f'officecli set {DOCX} {path} --prop "text={text}"'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout.strip()

def get_last_para():
    """Get current last paragraph paraId."""
    cmd = f'officecli get {DOCX} /body/p[last()] --json'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    try:
        data = json.loads(result.stdout)
        return data.get("paraId", "")
    except:
        return ""

# H1 anchors (existing in template)
H1_1_paraId = "04C2E2D0"  # CƠ SỞ LÝ THUYẾT (was GIỚI THỚI)
H1_2_paraId = "051169A1"  # ỨNG DỤNG VÀ ĐỊNH HƯỚNG PHÁT TRIỂN AI (was CƠ SỞ LÝ THUYẾT)
H1_3_paraId = "37D21BE6"  # TÀI LIỆU THAM KHẢO (was KẾT LUẬN)
H1_4_paraId = "7FA7A178"  # KẾT LUẬN (was TÀI LIỆU THAM KHẢO)

current_anchor = H1_1_paraId
operations = []

for section in ir["sections"]:
    tag = section["tag"]
    stype = section["type"]
    title = section["title"]
    body = section["body_paragraphs"]

    if stype == "heading1":
        # Already replaced, find the paraId
        if tag == "h1_1":
            anchor = H1_1_paraId
        elif tag == "h1_2":
            anchor = H1_2_paraId
        elif tag == "h1_3":
            anchor = H1_3_paraId
        elif tag == "h1_4":
            anchor = H1_4_paraId
        else:
            anchor = current_anchor
        current_anchor = anchor
        continue

    if stype == "heading2":
        # Clone H2 after current H1 or H2
        new_h2 = add_paragraph(H2_PROTOTYPE, current_anchor)
        set_text(f"/body/p[last()]", title)
        operations.append(("H2", title, new_h2))
        current_anchor = new_h2

    elif stype == "heading3":
        # Clone H3 after current H2
        new_h3 = add_paragraph(H3_PROTOTYPE, current_anchor)
        set_text(f"/body/p[last()]", title)
        operations.append(("H3", title, new_h3))
        current_anchor = new_h3

    # Add body paragraphs after current heading
    for para_text in body:
        new_body = add_paragraph(NORMAL_PROTOTYPE, current_anchor)
        set_body(f"/body/p[last()]", para_text)
        operations.append(("body", para_text[:40] + "..." if len(para_text) > 40 else para_text, new_body))

print(f"Total operations: {len(operations)}")
for i, (op_type, label, path) in enumerate(operations):
    print(f"  [{i+1}] {op_type}: {label} → {path}")
