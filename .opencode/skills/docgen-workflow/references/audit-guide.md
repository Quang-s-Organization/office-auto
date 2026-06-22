# Prototype Discovery Guide

With the Clone DOM Builder approach, "audit" means discovering style prototypes in the template.

## Discover Style Prototypes

Query the template to find one representative paragraph per style:

```bash
officecli query <file> "p[style=Heading1]" --json   # → capture paraId
officecli query <file> "p[style=Heading2]" --json   # → capture paraId
officecli query <file> "p[style=Heading3]" --json   # → capture paraId
officecli query <file> "p[style=Normal and text!='']" --json  # → capture paraId
```

These paraIds are used as `--from` sources in `add --from` operations.

## Verify Prototypes

For each prototype, verify it has the expected formatting:

```bash
officecli query <file> "/body/p[@paraId=<id>]" --json
```

Check: `style`, `effective.bold`, `effective.alignment`, `effective.size`, `effective.font.ascii`.

## When Template Has No Suitable Prototype

If a style is missing from the template:
1. The `officecli query p[style=X]` returns empty → use the closest available style
2. Or create a new paragraph with the desired style via `officecli add <file> /body --type paragraph --prop text="" --prop style="X"`
3. Then use THAT paragraph as the prototype for future clones
