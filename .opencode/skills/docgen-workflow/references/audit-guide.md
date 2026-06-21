# Audit Guide — Troubleshooting & Migration

## Audit Process

Audit the template directly with officecli:

1. Query all SDT (Structured Document Tag) elements: `officecli query <template> sdt`
2. For each SDT with a tag: create a scalar field entry in manifest
3. Build manifest JSON manually and write to `manifests/<template_id>.manifest.json`
4. If no SDT tags found: the template is in legacy-anchor mode — run `sdt-migration` skill

## Common Audit Failures

### Empty Manifest (legacy-anchor, no fields detected)

**Cause**: Template uses text-based placeholders (e.g., "Noi dung", "...") without SDT tags.

**Symptoms**:
```json
{ "fields": {}, "repeaters": {}, "tables": {}, "mode": "legacy-anchor" }
```

**Recovery**:
Load the `sdt-migration` skill and run the migration procedure:
1. `officecli add <file> /body --type sdt --prop type=richtext --prop tag=<field_name> --after <heading_path>`
2. `officecli set <file> <sdt_path> --prop text="<placeholder>"`
3. `officecli remove <file> <original_placeholder_path>`
4. Re-audit with `officecli query sdt`
5. Write new manifest

### Missing SDT Tags

**Cause**: SDT elements exist but have no Tag property set.

**Recovery**: Use `officecli set` to set tag on each SDT, or recreate via `officecli add`.

### Stale Manifest

**Cause**: Template was modified after audit. The SHA hash in manifest no longer matches.

**Recovery**: Re-audit: `officecli query <template> sdt`, rebuild manifest, write new file.

## Converting Legacy-Anchor to Strict-SDT

Use the `sdt-migration` skill, which provides a complete officecli-only procedure:
1. Audit structure: `officecli query <file> paragraph --json`
2. For each heading→placeholder pair: `add sdt`, `set text`, `remove placeholder`
3. Re-audit, write manifest, validate: `officecli validate <file>`
