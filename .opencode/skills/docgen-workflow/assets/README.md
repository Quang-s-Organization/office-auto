# Design Assets

## Batch Operation IR (Design for v5)

Future optimization: compose the entire document as a batch of operations
and execute via `officecli batch` in a single save cycle.

### Current Problem

```
v4 (sequential):  add → query (per-para) → set → query → add → ...
                  N operations → ~N * 3 officecli calls
                  Each call opens/saves the document → ~1-2s overhead per call
```

### Proposed Solution (Batch Operation IR)

```json
{
  "operations": [
    {"op": "add", "from": "proto_id_1", "after": "anchor_id", "to": "/body"},
    {"op": "set", "target": "/body/p[last()]", "prop": "text=Content..."},
    {"op": "set", "target": "/body/p[last()]", "prop": "outlineLevel=1"},
    {"op": "add", "from": "proto_id_2", "after": "/body/p[last()]", "to": "/body"},
    {"op": "set", "target": "/body/p[last()]", "prop": "text=Body content..."},
    {"op": "remove", "target": "/body/p[@paraId=cleanup_1]" },
    {"op": "remove", "target": "/body/p[@paraId=cleanup_2]" }
  ]
}
```

### Execution Model

```bash
officecli batch report.docx --ops batch_ir.json
```

### Expected Gains

- Single open/save cycle instead of N cycles
- Eliminates per-operation ~1-2s overhead
- Estimated: ~400s → ~15-30s for 63 paragraphs
- O(N²) → O(N) complexity

### Status

- [ ] Design Batch IR schema
- [ ] Implement `doc_composer_batch.py` (v5)
- [ ] Test with `officecli batch` API
