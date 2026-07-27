# probing — the probe.lua template + the three AST shapes of a heading

> PROBE is **low-freedom**: run the commands as written, generate `probe.lua` from the
> template below, collect evidence. No judgement here — that is INDUCE's job.

## The three AST shapes of a heading (check ALL THREE)
`docx+styles` still surfaces a "heading" in one of three different ways. A single-signal
detector misses levels. Probe for all three:

1. **`Header(level, attr, inlines)`** — a proper Word heading (style named `"Heading N"` with
   a space, or with an outline level). `signal.via = header_style`.
2. **`Div{custom-style="…"}`** wrapping a `Para` — a custom paragraph style (e.g. `Chuong`,
   `Dieu`). `signal.via = custom_style`.
3. **plain `Para`** whose leading text is the ordinal ("Điều 1.", "Chương I") — manual
   numbering, no style signal. `signal.via = ordinal_text`.

Plus auto-numbered items appear as **`OrderedList`** carrying `ListAttributes`
(`signal.via = ordered_list`).

> ⚠️ Verified trap: officecli writes `styleId=Heading1` (no space); pandoc reads that as a
> plain `Para`, **not** a `Header`, and emits no custom-style div. So never trust one signal.

## probe.lua (generate this at runtime; do not ship it)
Emits one JSON object `{blocks:[…]}` to **stderr**, one row per structural block in document
order, with nesting `depth`. Verified on pandoc 3.8.

```lua
-- probe.lua : emit ONE structural-evidence report (JSON) from a docx AST.
local rows = {}
local idx = 0
local function lead(inlines) return pandoc.utils.stringify(inlines):sub(1, 40) end

-- match a leading ordinal in plain text (manual numbering)
local function ordinal_of(text)
  local w, rom = text:match("^(%a[%a]*)%s+([IVXLCDM]+)%f[%W]")
  if rom then return w.." "..rom, "roman-word" end
  local dec = text:match("^(%d+)%.")
  if dec then return dec..".", "decimal" end
  local al = text:match("^(%a)%)")
  if al then return al..")", "alpha-paren" end
  local w2, d2 = text:match("^(%a[%a]*)%s+(%d+)%.?")
  if d2 then return w2.." "..d2, "word-decimal" end
  return nil, nil
end

local function push(row) idx = idx + 1; row.i = idx; rows[#rows+1] = row end

local function walk(blocks, depth, liststyle, listdelim)
  for _, b in ipairs(blocks) do
    local t = b.t or b.tag
    if t == "OrderedList" then
      local la = b.listAttributes or {}
      local scheme = tostring(la.style or "DefaultStyle")
      local delim  = tostring(la.delimiter or "DefaultDelim")
      push{kind="OrderedList", depth=depth, scheme=scheme, delim=delim,
           start=(la.start or 1), items=#b.content}
      for _, item in ipairs(b.content) do walk(item, depth+1, scheme, delim) end
    elseif t == "BulletList" then
      push{kind="BulletList", depth=depth, items=#b.content}
      for _, item in ipairs(b.content) do walk(item, depth+1, nil, nil) end
    elseif t == "Header" then
      local ot, otk = ordinal_of(pandoc.utils.stringify(b.content))
      push{kind="Header", depth=depth, level=b.level,
           style=(b.classes[1] or b.attributes["custom-style"] or nil),
           text=lead(b.content), ordinal=ot, ordinal_kind=otk}
    elseif t == "Div" then
      local cs = b.attributes["custom-style"]
      if cs then push{kind="Div", depth=depth, style=cs, text=lead(b.content)} end
      walk(b.content, depth, liststyle, listdelim)
    elseif t == "Para" or t == "Plain" then
      local s = pandoc.utils.stringify(b.content)
      local ot, otk = ordinal_of(s)
      push{kind="Para", depth=depth, text=lead(b.content),
           ordinal=ot, ordinal_kind=otk,
           in_list_scheme=liststyle, in_list_delim=listdelim}
    end
  end
end

function Pandoc(doc)
  walk(doc.blocks, 0, nil, nil)
  io.stderr:write(pandoc.json.encode({blocks=rows}))
  io.stderr:write("\n")
  return doc
end
```

Run:
```bash
pandoc -f docx+styles "$F" -L probe.lua -t native >/dev/null 2> evidence.json
python3 -m json.tool evidence.json | head -40   # eyeball it
```

## What each row gives you
| field | meaning |
|---|---|
| `kind` | `OrderedList` / `BulletList` / `Header` / `Div` / `Para` |
| `depth` | nesting depth (0 = top). Disambiguates levels pandoc splits into sibling lists. |
| `scheme`,`delim` | pandoc `ListNumberStyle`/`ListNumberDelim` on an `OrderedList` (auto) |
| `style` | Word style name on a `Header`/`Div` |
| `ordinal`,`ordinal_kind` | leading ordinal detected in text (manual numbering) |
| `in_list_scheme`/`in_list_delim` | for a `Para`, the enclosing list's scheme/delim (its own number) |

Map pandoc tokens → IR canonical values using the tables in **grammar-schema.md §5**. Do NOT
write raw pandoc tokens into the spec.

## Extending the ordinal detector
`ordinal_of` is a starting point, not law. If `human.md` shows an ordinal shape it misses
(e.g. `Điều 1a`, `§ 3`, `1.1`), add a `text:match(...)` branch and re-run. The document tells
you which patterns exist — read `human.md` first.
