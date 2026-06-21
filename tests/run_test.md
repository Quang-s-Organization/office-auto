# Test: Run Pipeline with Sample Content

## Steps

1. Delete any old output
   ```bash
   rm -f out/report_test*.docx
   ```

2. Create output directory
   ```bash
   mkdir -p out
   ```

3. Load skills
   - `docgen-workflow` (v2)
   - `officecli`
   - `manifest`

4. Run pipeline (docgen-workflow Steps 0-8):
   - Step 0: manifests/format_template.manifest.json EXISTS + fields non-empty → skip to Step 2
   - Step 2: Validate manifest → 10 fields
   - Step 3: Coverage check → verify source chapters match template slots
   - Step 4: Extract content verbatim from tests/sample_noidung.md
   - Step 5: Construct batch.json to out/report_test.json
   - Step 6: Execute batch → out/report_test.docx
   - Step 7: Structural validation (S1-S6)
   - Step 8: Report result

5. Verify output:
   - 5 H1 headings in correct order
   - Chương 2 content present
   - No W_LEFTOVER
   - No caption-heading misassignment
