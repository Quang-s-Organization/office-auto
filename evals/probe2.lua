-- probe2.lua : GENERIC feature-extractor for Regime B (docs/19, docs/20).
-- Contract change vs probe.lua: this is a FEATURE-EXTRACTOR, not a kind-classifier.
--   * EVERY block emits exactly one row (incl. Table + any unknown kind) via a catch-all
--     => nothing is invisible => coverage over blocks can reach 1.0 (docs/19 tru (b)).
--   * Each row carries a NON-SEMANTIC format-signature + content-signals (image/math/link),
--     so clustering discovers roles from presentation, NOT from a fixed type list (tru (a)).
-- No judgement here. Induction/labelling happens downstream (score2.py / the agent).
-- Run: pandoc -f docx+styles FILE -L probe2.lua -t native >/dev/null   (JSON on stderr)
--
-- Honest gaps (pandoc-only): `align` and `left/first-line indent` are DROPPED by pandoc's
-- docx reader (see evals/README parity). They are recovered downstream by joining `styleId`
-- against an officecli style-catalog. `raw_pointer` is a LOGICAL hint (kind + nth-of-kind);
-- the builder resolves it to a concrete officecli path (e.g. /body/tbl[n]).

local rows = {}
local idx = 0
local nth = {}                      -- per-kind running counter for raw_pointer

local function bump(kind)
  nth[kind] = (nth[kind] or 0) + 1
  return nth[kind]
end

local function push(row)
  idx = idx + 1; row.i = idx
  rows[#rows+1] = row
end

-- leading 40 chars of stringified content (evidence sample, not used for clustering)
local function lead(x) return (pandoc.utils.stringify(x)):sub(1, 40) end

-- Manual (typed) leading ordinal — the one legitimately-semantic-free text signal.
local function ordinal_of(text)
  local w, rom = text:match("^(%a[%a]*)%s+([IVXLCDM]+)%f[%W]")
  if rom then return w .. " " .. rom, "roman-word" end
  local dec = text:match("^(%d+)%.")
  if dec then return dec .. ".", "decimal" end
  local al = text:match("^(%a)%)")
  if al then return al .. ")", "alpha-paren" end
  local w2, d2 = text:match("^(%a[%a]*)%s+(%d+)%.?")
  if d2 then return w2 .. " " .. d2, "word-decimal" end
  return nil, nil
end

-- Count inline content-signals inside ANY block (walks table cells too -> catches the
-- hyperlink-in-table case that drives the rId dependency-closure problem, docs/19 s2.2).
local function inline_signals(block)
  local n = { image = 0, math = 0, link = 0, strong = 0, emph = 0 }
  pandoc.walk_block(block, {
    Image  = function() n.image  = n.image  + 1 end,
    Math   = function() n.math   = n.math   + 1 end,
    Link   = function() n.link   = n.link   + 1 end,
    Strong = function() n.strong = n.strong + 1 end,
    Emph   = function() n.emph   = n.emph   + 1 end,
  })
  return n
end

local function utf8len(s)
  local ok, n = pcall(utf8.len, s)
  return (ok and n) and n or #s
end

-- Build the non-semantic signature for a text-bearing block.
local function signature(block, styleId, depth, list_scheme, list_delim)
  local s = pandoc.utils.stringify(block.content or block)
  local sig = inline_signals(block)
  local has_alpha = s:match("%a") ~= nil
  return {
    styleId    = styleId,
    len        = utf8len(s),
    bold       = sig.strong > 0,
    italic     = sig.emph > 0,
    allcaps    = has_alpha and (s == s:upper()),
    has_image  = sig.image > 0,
    has_math   = sig.math > 0,
    has_link   = sig.link > 0,
    n_link     = sig.link,
    has_num    = list_scheme ~= nil,
    list_scheme = list_scheme,
    list_delim  = list_delim,
  }
end

-- rows/cols of a pandoc Table, defensively.
local function table_shape(tbl)
  local rowcount, cols = 0, 0
  pcall(function()
    cols = #(tbl.colspecs or {})
    rowcount = rowcount + #((tbl.head and tbl.head.rows) or {})
    for _, body in ipairs(tbl.bodies or {}) do
      rowcount = rowcount + #(body.head or {}) + #(body.body or {})
    end
    rowcount = rowcount + #((tbl.foot and tbl.foot.rows) or {})
  end)
  return rowcount, cols
end

local function emit_para(block, kind, styleId, depth, list_scheme, list_delim, in_table)
  local text = lead(block.content or {})
  local ot, otk = ordinal_of(pandoc.utils.stringify(block.content or {}))
  local row = { kind = kind, depth = depth, styleId = styleId,
                text = text, ordinal = ot, ordinal_kind = otk,
                in_table = in_table or false,
                raw_pointer = "logical:p#" .. bump("p") }
  row.signature = signature(block, styleId, depth, list_scheme, list_delim)
  push(row)
end

-- Recursive walk. `carry` = style inherited from an enclosing custom-style Div.
local function walk(blocks, depth, list_scheme, list_delim, in_table)
  for _, b in ipairs(blocks) do
    local t = b.t or b.tag
    if t == "OrderedList" then
      local la = b.listAttributes or {}
      local scheme = tostring(la.style or "DefaultStyle")
      local delim  = tostring(la.delimiter or "DefaultDelim")
      push{ kind = "OrderedList", depth = depth, scheme = scheme, delim = delim,
            start = la.start or 1, items = #b.content, raw_pointer = "logical:ol#" .. bump("ol") }
      for _, item in ipairs(b.content) do walk(item, depth + 1, scheme, delim, in_table) end

    elseif t == "BulletList" then
      push{ kind = "BulletList", depth = depth, items = #b.content,
            raw_pointer = "logical:ul#" .. bump("ul") }
      for _, item in ipairs(b.content) do walk(item, depth + 1, nil, nil, in_table) end

    elseif t == "Header" then
      local styleId = b.classes[1] or b.attributes["custom-style"]
      local ot, otk = ordinal_of(pandoc.utils.stringify(b.content))
      local row = { kind = "Header", depth = depth, level = b.level, styleId = styleId,
                    text = lead(b.content), ordinal = ot, ordinal_kind = otk,
                    in_table = in_table or false, raw_pointer = "logical:h#" .. bump("h") }
      row.signature = signature(b, styleId, depth, nil, nil)
      push(row)

    elseif t == "Div" then
      local cs = b.attributes["custom-style"]
      local inner = b.content
      -- Collapse the common docx shape "custom-style Div wrapping ONE paragraph" into a
      -- single logical row carrying styleId=cs (avoids the Div+Para double-count of probe.lua).
      if cs and #inner == 1 and (inner[1].t == "Para" or inner[1].t == "Plain") then
        emit_para(inner[1], inner[1].t, cs, depth, nil, nil, in_table)
      else
        if cs then
          local row = { kind = "Div", depth = depth, styleId = cs, text = lead(b.content),
                        in_table = in_table or false, raw_pointer = "logical:div#" .. bump("div") }
          row.signature = signature(b, cs, depth, nil, nil)
          push(row)
        end
        walk(inner, depth, list_scheme, list_delim, in_table)
      end

    elseif t == "Para" or t == "Plain" then
      emit_para(b, t, nil, depth, list_scheme, list_delim, in_table)

    elseif t == "Table" then
      -- ONE row for the whole table (verbatim-carry unit). Count links inside for
      -- dependency-closure (hyperlink -> document.xml.rels rId that a raw splice would drop).
      local rc, cc = table_shape(b)
      local sig = inline_signals(b)
      push{ kind = "Table", depth = depth, styleId = b.attributes and b.attributes["custom-style"] or nil,
            rows = rc, cols = cc, n_link = sig.link, n_image = sig.image, has_math = sig.math > 0,
            in_table = in_table or false, raw_pointer = "logical:tbl#" .. bump("tbl"),
            needs_dep_closure = (sig.link > 0 or sig.image > 0) }
      -- do NOT recurse into cells: the table is carried as one unit.

    else
      -- CATCH-ALL: any block kind not handled above (CodeBlock, RawBlock, HorizontalRule,
      -- LineBlock, DefinitionList, Figure, or anything a future pandoc emits) still gets a row.
      local sig = inline_signals(b)
      push{ kind = t, depth = depth, unknown = true, text = lead(b),
            n_image = sig.image, n_link = sig.link, has_math = sig.math > 0,
            in_table = in_table or false, raw_pointer = "logical:raw#" .. bump("raw"),
            needs_dep_closure = (sig.link > 0 or sig.image > 0) }
    end
  end
end

function Pandoc(doc)
  walk(doc.blocks, 0, nil, nil, false)
  io.stderr:write(pandoc.json.encode({ blocks = rows }))
  io.stderr:write("\n")
  return doc
end
