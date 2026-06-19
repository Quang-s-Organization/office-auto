# Audit Guide — Troubleshooting & Migration

## Audit Process

The `write_manifest` tool (manifest-server MCP) calls officecli to query the template structure:

1. Query all SDT (Structured Document Tag) elements: `officecli query <template> sdt`
2. For each SDT with a tag: create a scalar field entry
3. If no SDT tags found: fall back to legacy-anchor mode
4. Legacy mode: scan headings followed by placeholder paragraphs

## Common Audit Failures

### Empty Manifest (legacy-anchor, no fields detected)

**Cause**: Template uses text-based placeholders (e.g., "Nội dung", "…") but the heading→placeholder heuristic failed to match any pairs.

**Symptoms**:
```json
{ "fields": {}, "repeaters": {}, "tables": {}, "mode": "legacy-anchor" }
```

**Recovery**:
1. Open the template in Word
2. Enable Developer tab (File → Options → Customize Ribbon → Developer)
3. Insert Plain Text Content Controls for each placeholder
4. Set Tag property to a descriptive field name (lowercase, underscores)
5. Save and re-audit

### Missing SDT Tags

**Cause**: SDT elements exist but have no Tag property set.

**Recovery**: Open each content control in Word, Properties → Tag → set a unique name.

### Stale Manifest

**Cause**: Template was modified after audit. The SHA hash in manifest no longer matches.

The `loadManifest()` function (in auditor.ts) prints a warning. Re-audit by calling `write_manifest` again.

## Converting Legacy-Anchor to Strict-SDT

1. Open template in Word
2. For each placeholder paragraph (marked by "Nội dung" or "…"):
   - Select the placeholder text
   - Developer tab → Controls → Plain Text Content Control
   - Right-click → Properties → Tag: set a field name
   - Optional: set placeholder text to describe the field
3. Save template
4. Re-audit: `write_manifest` with updated template path
5. Verify manifest.fields is now populated with SDT-based entries
