# MCP server

## MCP server

[`compono-mcp`](packages/compono-mcp) exposes `validate`/`review`/`render_deck`
as MCP tools, for any MCP-compatible client — not just Claude Code.

```bash
pip install compono-mcp
# or
uv add compono-mcp
```

Add to your MCP client config (Claude Desktop / Claude Code style):

```json
{ "mcpServers": { "compono": { "command": "compono-mcp" } } }
```

Exposes `validate_deck`/`review_deck`/`render_deck_tool` tools (identical
`spec` shape to the Python API), `validate_docx_tool`/`render_docx_tool`
(see [DOCX generation](docx.md) — compono's second output format),
`inspire_scan` (see [Inspire](inspire.md) — scan liked decks into a style
profile/skill), and a `compono://reference` resource carrying the full
agent-facing reference doc, for clients without Claude Code's skill
system.

### When compono has no context

Two channels put this reference in front of an agent automatically:
Claude Code with this skill installed, and an MCP client that fetches the
`compono://reference` resource above. A bare `pip install compono` and
"write me code using this" to a generic LLM gets **neither** — that LLM
has no built-in knowledge of compono's primitives or conventions.

Two ways it can still self-serve, depending on what access it has:
- **Code-exec access**: the schema is deliberately self-documenting — every
  field's `description` is agent-facing prose, not a bare type label (see
  [Primitives](primitives.md)). `Deck.model_json_schema()` or
  `help(compono.Header)` gets real guidance without needing this file at all.
- **Shell access, no code-exec**: `compono reference` (or
  `python -c "import compono; print(compono.reference())"`) prints this
  exact content — the same reason it's packaged inside `compono` itself
  rather than only living in `SKILL.md`/`compono-mcp`.

An LLM with neither (pure text generation, no tools) has nothing beyond
whatever it can recall from training data, or the PyPI/GitHub README page
if it happens to search for it.


