# officecli Error & Warning Codes

## Error Codes (E_*)

Errors indicate structural problems. The document is corrupted or invalid.
**Never deliver a document with E_* errors.**

| Code | Meaning | Recovery |
|------|---------|----------|
| `E_CORRUPT` | OOXML structure is broken | Stop immediately. Template may be corrupted. Re-download or re-create template. |
| `E_SCHEMA` | Document fails OOXML schema validation | Stop. The batch operations introduced invalid XML. Review batch.json ops for structural issues (e.g., cloning into wrong parent). |
| `E_PATH` | Referenced path does not exist in document | Re-query document structure. Path may have changed or was guessed. Never retry with guessed paths. |
| `E_BATCH` | Batch execution failed mid-way | Check which op caused failure. All prior ops in batch are rolled back. Fix the failing op and retry entire batch. |

## Warning Codes (W_*)

Warnings indicate non-critical issues. The document is still valid but has quality problems.

| Code | Meaning | Recovery |
|------|---------|----------|
| `W_LEFTOVER` | Placeholder field was not replaced | Identify which field by its path. Add or fix the corresponding batch op. Re-execute batch with corrected op. |
| `W_STYLE` | Style mismatch or missing style reference | Usually cosmetic. Can ignore if output looks correct. |
| `W_EMPTY` | Field is empty (may be intentional) | Verify if the field is optional in manifest. If required, add content. If optional, can ignore. |
| `W_FORMAT` | Number/date format does not match locale | Re-format the value according to manifest locale rules before re-executing. |
