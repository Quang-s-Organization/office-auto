# Structure-Spec IR contract (grammar-schema ≡ spec-schema)

> **This is the central contract between the two skills.** `inducing-doc-structure`
> WRITES it; `building-docx-from-structure` READS it. It is the *Format IR*: it captures
> the **format grammar an agent induced from a document plus its evidence and
> confidence** — never rules a human imposed.
>
> ⚠️ **MIRROR FILES — MUST stay byte-for-byte identical:**
> `inducing-doc-structure/references/grammar-schema.md` and
> `building-docx-from-structure/references/spec-schema.md` are two copies of THIS file.
> If you edit one, edit the other; verify with `diff` (must be empty). A drift here silently
> breaks the whole system (the builder reads fields the inducer never wrote, or vice-versa).

## 0. Two artifacts, one grammar (decision D1)

The inducer emits **twins**:

- **`structure-spec.json`** — the machine source of truth. The **builder reads only this.**
- **`structure-spec.md`** — the human-readable rendering (outline + evidence table) for QA
  and for reporting to the professor. **No tool parses the `.md`.**

Both encode the same grammar defined below. When they disagree, the `.json` wins.

## 1. Top-level shape

```json
{
  "spec_version": "1.0",
  "meta": {
    "source_file": "samples/sample-01-legal-auto.docx",
    "source": "synth | real",
    "generated_by": "inducing-doc-structure",
    "pandoc_version": "3.8",
    "notes": "free text, optional"
  },
  "document": {
    "detected_type": "vn-legal-thongtu | contract | standard | unknown | <agent label>",
    "confidence": 0.0,
    "header_block": { "...": "see §3, optional, may be null" },
    "levels": [ { "...": "see §4" } ],
    "anomalies": [ "block #57 matched no level" ]
  }
}
```

- `spec_version` — bump when the schema changes; both skills check it.
- `meta` — provenance only; never drives the build. `source` ∈ `synth | real`.
- `document.detected_type` — the label the agent **induced**, or `"unknown"` when unsure.
  It is a *hint* for the builder (e.g. to pick Path C), never a rule.
- `document.confidence` — overall induction confidence `0.0–1.0`. **Never hide a low value.**
- `document.header_block` — optional (decision D2); see §3.
- `document.levels[]` — the induced hierarchy, **ordered shallow → deep** (index 0 = top
  level). See §4. This array is the core of the contract.
- `document.anomalies[]` — every structural block that fit no level, stated honestly.

## 2. Canonical vocabulary (the enums)

The IR uses **one canonical vocabulary**, independent of either tool. Each skill maps it to
its own tool. **Never** write a raw pandoc token (`UpperRoman`) or a raw officecli token
(`upperRoman`) into the JSON — always the IR canonical value below.

| Field | Allowed values |
|---|---|
| `signal.via` | `header_style` · `custom_style` · `ordinal_text` · `ordered_list` |
| `numbering.scheme` | `decimal` · `upperRoman` · `lowerRoman` · `upperAlpha` · `lowerAlpha` · `none` |
| `numbering.delim` | `period` · `oneParen` · `twoParens` · `none` |
| `numbering.source` | `auto` · `manual` |
| `numbering.reset` | `none` · `per_parent` · `<level id>` (e.g. `"L1"`) |
| `format.align` | `left` · `center` · `right` · `justify` |
| `format.bold` / `format.all_caps` | `true` · `false` |
| `format.indent` | integer twips, or `null` when not observed |

## 3. `header_block` (optional, decision D2)

Vietnamese legal documents open with a National-heading / doc-number block ("Quốc hiệu",
"Số: …/…"). It is a **signal of document type** and helps the builder render a document that
"looks real", but it is **not** a structural level. Kept as a **separate optional block** so
generality is preserved — it may be `null` for documents that have none.

```json
"header_block": {
  "present": true,
  "lines": [
    { "text": "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM", "align": "center", "bold": true, "all_caps": true },
    { "text": "Độc lập - Tự do - Hạnh phúc",        "align": "center", "bold": true },
    { "text": "Số: 01/2026/TT-BXD",                  "align": "left" }
  ]
}
```

`present: false` (or `header_block: null`) → the builder skips it. The builder reproduces
`lines[]` verbatim as literal paragraphs; it does **not** treat them as levels.

## 4. A `level` object (the heart)

Each entry of `document.levels[]` has **exactly these five keys**: `id`, `signal`,
`numbering`, `format`, `examples`. All five are **required** (use `null`/`false` for
"not observed", never omit a key — omission is how contracts drift).

```json
{
  "id": "L2",
  "signal": {
    "via": "ordinal_text",
    "style": "Heading 2",
    "ordinal_regex": "^Điều\\s+(\\d+)"
  },
  "numbering": {
    "scheme": "decimal",
    "delim": "period",
    "source": "manual",
    "reset": "none"
  },
  "format": {
    "bold": true,
    "all_caps": false,
    "align": "left",
    "indent": null
  },
  "examples": ["Điều 1.", "Điều 2.", "Điều 3."]
}
```

### 4.1 `id`
Stable within this spec: `L1`, `L2`, … in depth order. Other levels reference it in
`numbering.reset` (e.g. L2 resets `per_parent` of `L1`).

### 4.2 `signal` — how the inducer *recognized* this level
- `via` — which of the three heading shapes (§ pandoc doc 04) fired:
  - `header_style` — pandoc emitted a `Header(level, …)`.
  - `custom_style` — a `Div`/`Span` with `custom-style="…"`.
  - `ordinal_text` — a plain `Para` whose leading text is the ordinal (manual numbering).
  - `ordered_list` — a pandoc `OrderedList` carrying `ListAttributes` (auto numbering).
- `style` — the Word style name observed (`"Heading 2"`, `"Chuong"`), or `null`.
- `ordinal_regex` — a regex (JSON-escaped) that matches this level's ordinal prefix and
  **captures the ordinal in group 1**. Drives sequence-fit verification. `null` if the level
  carries no ordinal (e.g. a title).

### 4.3 `numbering` — the numbering rule (the double-number trap lives here)
- `scheme` — canonical scheme (§2).
- `delim` — canonical delimiter (§2).
- `source` — **`auto`** (Word renders the number; the text does NOT contain it) or
  **`manual`** (the number is literal text). ⚠️ **This single field prevents double-numbering
  on rebuild.** Get it from the probe: `ordered_list` ⇒ `auto`; ordinal-in-text ⇒ `manual`.
- `reset` — `none` (never resets), `per_parent` (restarts under each parent), or a level id.

### 4.4 `format` — reproducible visual signals
`bold`, `all_caps` (booleans), `align` (§2), `indent` (twips or `null`). These are the only
format fields round-trip parity scores (decision D3). Cosmetic details pandoc drops (exact
font px, colour) are intentionally **not** in the contract.

### 4.5 `examples`
2–5 observed instances, verbatim. Human QA + a witness for the induced rule.

## 5. Cross-tool mapping tables (normative)

These tables are **the contract's teeth**: they pin how each canonical value is read from
pandoc (inducer) and written by officecli (builder). Neither skill may improvise a mapping.

### 5.1 `numbering.scheme`
| IR canonical | pandoc `ListNumberStyle` | officecli abstractnum `format` | renders as |
|---|---|---|---|
| `decimal`    | `Decimal`    | `decimal`     | 1, 2, 3 |
| `upperRoman` | `UpperRoman` | `upperRoman`  | I, II, III |
| `lowerRoman` | `LowerRoman` | `lowerRoman`  | i, ii, iii |
| `upperAlpha` | `UpperAlpha` | `upperLetter` | A, B, C |
| `lowerAlpha` | `LowerAlpha` | `lowerLetter` | a, b, c |
| `none`       | `DefaultStyle` | *(n/a — manual/text)* | — |

> ⚠️ Alpha mismatch across tools: pandoc says `UpperAlpha`/`LowerAlpha`, officecli says
> `upperLetter`/`lowerLetter`. The IR hides this behind `upperAlpha`/`lowerAlpha`.

### 5.2 `numbering.delim`
| IR canonical | pandoc `ListNumberDelim` | officecli `lvlText` pattern (level N) |
|---|---|---|
| `period`    | `Period`      | `%N.`  |
| `oneParen`  | `OneParen`    | `%N)`  |
| `twoParens` | `TwoParens`   | `(%N)` |
| `none`      | `DefaultDelim`| `%N`   |

### 5.3 `numbering.source`
| IR | pandoc evidence | officecli build action |
|---|---|---|
| `auto`   | block is `OrderedList` with `ListAttributes` | define `abstractnum`+`num`, set `numId`+`ilvl` on the paragraph — Word renders the ordinal |
| `manual` | ordinal appears as `Str` text in a `Para`/`Header` | write the ordinal as literal `text=`; do **NOT** also set `numId` (would double-number) |

## 6. Validation rules (both skills enforce)

A spec is **valid** iff:
1. `spec_version` present and understood.
2. `document.levels` is a non-empty array, each element has **all five** keys.
3. Every `numbering.source` ∈ `{auto, manual}` (never absent — the double-number guard).
4. Every enum value is drawn from §2 (no raw pandoc/officecli tokens).
5. `confidence` ∈ `[0,1]`; `anomalies` is an array (possibly empty).
6. Any `numbering.reset` that names a level id references an **existing** shallower level.

The inducer must emit a valid spec; the builder must **reject** an invalid one (fail loud,
don't guess).

## 7. Minimal valid example

See `samples/example.spec.json` — a hand-written, schema-valid spec used as a fixture to test
the builder **before** the inducer can produce one. Keep it in sync with this schema.
