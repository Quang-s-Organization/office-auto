# inventories — the three no-judgement inventories

> Built from `ast.json` (pandoc `-t json`) + `evidence.json` (probe.lua). **Descriptive
> only** — you are cataloguing signals, NOT yet deciding what is a level. Judgement is INDUCE.

You do not need `jq`. Use `python3` to walk `evidence.json`/`ast.json`, or read `human.md`
by eye for small files.

## 1. Style inventory
Every distinct style signal + how often it occurs.
- From `evidence.json`: count `Header` rows by `(level, style)`, and `Div` rows by `style`.
- From `ast.json`: distinct `custom-style` attribute values and Header levels.

Output shape (example):
```
style              kind    count
Heading 1          Header  3
Heading 2          Header  12
Chuong (div)       Div     3
(none)             Para    40
```
A style that appears a handful of times at a consistent depth is a level candidate; a style
used everywhere (e.g. body `Normal`) is not.

## 2. Numbering inventory
Two independent sources — record BOTH, because one document can mix them:
- **auto** — every `OrderedList` row: `(depth, scheme, delim, items)`. The number is rendered
  by Word, NOT in the text.
- **manual** — every `ordinal`/`ordinal_kind` detected on `Header`/`Para` rows: the leading
  ordinal text (`"Điều 1"`, `"Chương I"`, `"a)"`).

Output shape:
```
source  depth  scheme      delim      kind/example         count
auto     0     UpperRoman  Default    (list)               1
auto     1     Decimal     Period     (list)               5
manual   -     -           -          "Điều 1." word-decimal 12
manual   -     -           -          "a)"     alpha-paren   30
```
> This inventory is where `numbering.source` is decided per level. Getting it wrong ⇒ the
> builder double-numbers. When in doubt, open `human.md` and look: is the number in the text?

## 3. Ordered sequence
The `evidence.json` rows already come **in document order** with `depth`. This IS the
sequence. Keep it as-is; VERIFY replays it. Note runs and resets you can see:
```
i  depth kind         scheme/ordinal
1  0     OrderedList  UpperRoman        <- L1 run starts
2  1     Para         "Scope..."         (I)
3  1     OrderedList  Decimal            <- L2 run under I
...
9  1     Para         "Obligations..."   (II)  <- L1 continues
```

## Map tokens to IR
When you carry these into a grammar hypothesis, convert pandoc tokens to IR canonical with
**grammar-schema.md §5** (`UpperRoman`→`upperRoman`, `Period`→`period`, `LowerAlpha`→
`lowerAlpha`, `DefaultDelim`→`none`, …). Never put a raw pandoc token in the spec.
