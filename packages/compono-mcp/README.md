# compono-mcp

MCP server wrapper exposing [`compono`](https://pypi.org/project/compono/)'s
`render_deck`/`validate` as MCP tools, for any MCP-compatible client (not just
Claude Code).

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
- **`validate(spec)`** — schema + layout + overflow checks, no file write.
- **`render_deck(spec, output_path)`** — writes a real `.pptx` file.
- **resource `compono://reference`** — the full agent-facing reference doc
  (quickstart, primitive catalog, worked examples, error shape), for MCP
  clients that don't have Claude Code's skill system.

See the [main compono README](https://github.com/Shaik-Hamzah123/compono) for
the primitive schema and worked examples — `spec` here is the identical JSON
shape `compono.render_deck`/`validate` accept directly.
