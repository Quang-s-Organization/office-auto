-- probe.lua : emit ONE structural-evidence report (JSON) from a docx AST.
-- No judgement here — just faithful signals for the agent to induce from.
-- Run: pandoc -f docx+styles FILE -L probe.lua -t native >/dev/null
-- Report is written to stderr as a single JSON object.

local rows = {}          -- ordered list of evidence rows (document order)
local idx = 0

local function lead(inlines)
  local s = pandoc.utils.stringify(inlines)
  return s:sub(1, 40)
end

-- match a leading ordinal in plain text (manual numbering)
local function ordinal_of(text)
  -- roman-word forms: "Chương I", "Phần II"
  local w, rom = text:match("^(%a[%a]*)%s+([IVXLCDM]+)%f[%W]")
  if rom then return w.." "..rom, "roman-word" end
  -- decimal "1." or "12."
  local dec = text:match("^(%d+)%.")
  if dec then return dec..".", "decimal" end
  -- alpha paren "a)" "b)"
  local al = text:match("^(%a)%)")
  if al then return al..")", "alpha-paren" end
  -- word + decimal "Điều 1." "Article 3."
  local w2, d2 = text:match("^(%a[%a]*)%s+(%d+)%.?")
  if d2 then return w2.." "..d2, "word-decimal" end
  return nil, nil
end

local function push(row) idx = idx + 1; row.i = idx; rows[#rows+1] = row end

-- recursive walk keeps nesting depth that element callbacks lose
local function walk(blocks, depth, liststyle, listdelim)
  for _, b in ipairs(blocks) do
    local t = b.t or b.tag
    if t == "OrderedList" then
      local la = b.listAttributes or {}
      local scheme = tostring(la.style or "DefaultStyle")
      local delim  = tostring(la.delimiter or "DefaultDelim")
      local start  = la.start or 1
      push{kind="OrderedList", depth=depth, scheme=scheme, delim=delim,
           start=start, items=#b.content}
      for _, item in ipairs(b.content) do
        walk(item, depth+1, scheme, delim)   -- item = list of blocks
      end
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
