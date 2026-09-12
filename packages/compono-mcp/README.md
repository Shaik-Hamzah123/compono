# compono-mcp

MCP server wrapper exposing [`compono`](https://pypi.org/project/compono/)'s
`render_deck`/`validate`/`review`/`inspire_scan`/`render_docx`/`validate_docx`
as MCP tools, for any MCP-compatible client (not just Claude Code).

## Install

```bash
pip install compono-mcp
# or
uv add compono-mcp
```

## Usage

Add to your MCP client config (Claude Desktop / Claude Code style):

```json
{ "mcpServers": { "compono": { "command": "compono-mcp" } } }
```

Exposes:
- **`validate_deck(spec)`** — schema + layout + overflow checks, no file write.
- **`render_deck_tool(spec, output_path)`** — writes a real `.pptx` file.
- **`review_deck(spec)`** — design-quality suggestions (contrast, whitespace,
  image fit, font-size proximity to overflow), never blocking.
- **`inspire_scan(pptx_paths, out_dir, name, min_repeat_ratio)`** — scans
  `.pptx` files someone already likes into a style profile/skill.
- **`validate_docx_tool(spec)`** / **`render_docx_tool(spec, output_path)`**
  — compono's second output format, `.docx` documents (linear content
  rather than slides).
- **resource `compono://reference`** — the full agent-facing reference doc
  (quickstart, primitive catalogs for both formats, worked examples, error
  shape), for MCP clients that don't have Claude Code's skill system.

See the [main compono README](https://github.com/Shaik-Hamzah123/compono) for
the primitive schemas and worked examples — `spec` here is the identical JSON
shape `compono.render_deck`/`validate`/`compono.render_docx`/`validate_docx`
accept directly.
