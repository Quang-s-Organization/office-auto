# Validation Guide

## Validation Steps

After batch rendering, run two officecli operations on the output file:

### 1. Schema Validation
```
officecli validate <output.docx>
```
Returns:
```json
{ "ok": true/false, "issues": [...] }
```
If `ok: false` with `E_*` errors: the document is structurally corrupted. Stop. Do not deliver.

### 2. View Issues
```
officecli view <output.docx> issues
```
Returns human-readable list of all warnings and errors.

## Leftover Placeholder Detection

Query for common placeholder patterns in the output:
```
officecli query <output.docx> ':contains("{{") or :contains("__") or :contains("Nội dung")'
```

If results are non-empty: some fields were not filled. Cross-reference with batch.json.

## Interpretation

### W_LEFTOVER warnings
A field was declared in manifest but the batch did not set it.

**Recovery**:
1. Identify the path from the warning
2. Check if the field has a corresponding op in batch.json
3. If missing: add the op with the correct value
4. If present but wrong path: re-query document to find correct path
5. Re-execute batch with corrected batch.json

### E_CORRUPT or E_SCHEMA errors
The document structure was broken by the batch operations.

**Recovery**:
1. Review the batch ops for structural issues
2. Common cause: `clone` op with wrong parent, or `add` to non-existent path
3. Re-audit the template to get fresh paths
4. Reconstruct batch.json from scratch
5. Do NOT attempt to patch a corrupted document

### E_PATH errors
A path in batch.json does not exist in the document.

**Recovery**:
1. Query the document to find the actual path
2. Update the batch op with the correct path
3. Re-execute batch

## Pass Criteria

A document is ready for delivery when:
- `validate` returns `ok: true` (or `success: true`)
- `view issues` returns empty array
- Leftover placeholder query returns empty array
- Structural invariants check passes (if applicable)
