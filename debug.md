# Identified issues in v2 pipeline

After inspecting the full log (1205 lines) of the opencode LLM session, here are the actual issues where the LLM deviated from the designed workspace architecture or behaved unexpectedly.

## 1. LLM abandoned MCP tools and scripted officecli in Python (CRITICAL)

**What happened:** The architecture expects the LLM to use only officecli MCP tools for document manipulation. In this session, the LLM made only **6 MCP tool calls total** — all for template discovery (`query`, `view`) and one `open`. The moment document building started, it switched entirely to bash commands (`$ officecli ...`), and then to a Python script that runs officecli commands via `subprocess.run()` in a loop.

**Evidence from log:**
- Lines 31-34: 4 MCP tool calls (`query` for styles) — discovery phase
- Line 77: 1 MCP tool call (`view` outline) — discovery phase
- Line 145: 1 MCP tool call (`open` report.docx) — last MCP call ever
- Everything after line 145: bash commands and Python scripts

**The Python script (build_document.py):**
```python
def run(cmd):
    result = subprocess.run(cmd, shell=True, ...)
    return result.stdout.strip()
```

Then executed inside a heredoc:
```python
$ python3 << 'PYEOF'
...
run(f"officecli add {REPORT} /body --from /body/p[@paraId={NORMAL_PROTO}] --after /body/p[@paraId={current_anchor}]")
current_anchor = find_after(current_anchor)
run(f'officecli set {REPORT} /body/p[@paraId={current_anchor}] --prop text={shlex.quote(text)}')
...
PYEOF
```

**Why this happened:** The anchor-chaining problem (add → get paraId → set → add next → get paraId → set → ...) is inherently iterative. The MCP tool interface doesn't support loops or programmatic iteration between tool calls. The LLM couldn't efficiently chain ~60+ MCP calls (add + set for each of 52 body paragraphs and 9 headings), so it fell back to scripting.

**Impact:** The entire document generation pipeline bypassed the MCP tool layer. This defeats the purpose of the tool-based architecture, which was designed to give the LLM fine-grained, observable control over each operation.

Root cause: The MCP tool interface lacks support for iterative/loop patterns. Each tool call is independent — there's no way to say "do this N times" or "for each item in this list, call add then set." When faced with 60+ repetitive operations, the LLM naturally scripted it.

## 2. `p[last()]` XPath syntax failure

**What happened:** The LLM attempted `officecli query report.docx "p[last()]" --json` and got `"success": false` with error `"Malformed filter expression: unexpected '()' in 'last()'"`.

**Impact:** This forced the LLM to switch from direct XPath queries to the `find_after()` approach that parses full `officecli get /body --depth 1` output with regex to extract the next paraId. This works but is fragile — it assumes the next paragraph in the output is always the one just added.

## 3. Fragile `find_after()` anchor chaining

**What happened:** Instead of using stable `@paraId` references, the LLM parsed the full document body output after every single `add` to find the newly created paragraph's ID:

```python
def find_after(anchor_id):
    out = run(f"officecli get {REPORT} /body --depth 1 2>&1")
    lines = out.split("\n")
    found = False
    for line in lines:
        if f"@paraId={anchor_id}" in line:
            found = True
            continue
        if found and "@paraId=" in line:
            m = re.search(r'@paraId=([A-F0-9]+)', line)
            if m:
                return m.group(1)
    return None
```

**Issue:** This assumes the newly added paragraph always appears immediately after the anchor in the `get --depth 1` output. If the body contains non-paragraph elements (tables, bookmarks, section breaks) between them, the wrong element would be returned. It happened to work in this session because the editing region only contained paragraphs.

## 4. Duplicate H2 heading — cloned instead of reused

**What happened:** The template already had H2 "Tầm quan trọng dữ liệu ảnh huấn luyện trong thị giác máy tính" under "CƠ SỞ LÝ THUYẾT". The LLM cloned it (creating paraId=7FB28FA1) instead of reusing/renaming the original. The final document has two identical H2 headings:

```
├── [46] "Tầm quan trọng dữ liệu ảnh huấn luyện..." (heading 2) — template original, untouched
├── [47] "Tầm quan trọng dữ liệu ảnh huấn luyện..." (heading 2) — cloned content
```

**Impact:** [46] remains as dead content with placeholder text, while [47] has the actual content. A cleanup step should remove [46].

## 5. H3 ordering mixed with template remnants

**What happened:** The template had an H3 "Thu thập dữ liệu ảnh thủ công" nested under the template's H2. When content H3s were inserted for the new H2 1_4, the template's original H3 stayed in place, ending up out of hierarchy:

```
├── [61] "Các phương pháp sinh dữ liệu ảnh truyền thống" (heading 2) — new
  ├── [63] "Thu thập dữ liệu ảnh thủ công" (heading 3) — new content (correct)
  ├── [67] "Tăng cường dữ liệu ảnh" (heading 3) — new content (correct)
  ├── [76] "Thu thập dữ liệu ảnh thủ công" (heading 3) — template original (out of place)
```

**Impact:** The template's original H3 at [76] sits outside the intended hierarchy, between the last H3 body paragraph and "KẾT LUẬN".

## 6. No AI fallback for "verbatim: false" sections

**What happened:** "GIỚI THIỆU" and "KẾT LUẬN" existed in the template but had no corresponding content in `noidung.md`. The LLM kept them as-is with placeholder "Nội dung..." text. The architecture describes a "verbatim: false" policy where missing sections should be AI-generated, but no generation mechanism was triggered.

**Impact:** These sections remain with template placeholder text. No LLM call was made to generate content for them.

## Summary

| # | Issue | Severity | Root cause |
|---|-------|----------|------------|
| 1 | Abandoned MCP tools, scripted officecli in Python | **CRITICAL** | MCP tools don't support iterative/loop patterns |
| 2 | `p[last()]` XPath failure | Medium | LLM assumed XPath functions work in officecli queries |
| 3 | Fragile `find_after()` regex anchor chaining | Medium | Byproduct of issue 1 — scripting avoided proper MCP chain |
| 4 | Duplicate H2 heading | Low | LLM didn't check for existing matching heading |
| 5 | H3 ordering mixed with template original | Low | Template cleanup step was missing |
| 6 | No AI fallback for missing sections | Medium | No mechanism to detect and generate missing sections |

**Key takeaway:** Issue 1 is the fundamental problem. The architecture relied on MCP tool calls, but when the task required iteration (52+ body paragraphs × add+set operations), the LLM abandoned the tool interface and scripted it directly.

**Resolution:** The pipeline has been updated (agent v9, workflow v8) to accept scripting as the correct approach. `tools/build_document.py` is now the primary execution method for full document builds. This design explicitly:
- Provides `tools/build_document.py` as the official anchor-chaining script
- Documents that scripting is the preferred approach for iterative operations
- Keeps MCP tools for small edits (1-5 ops) and template discovery
- Enforces consistent @paraId anchoring and open/close protocol in the script
