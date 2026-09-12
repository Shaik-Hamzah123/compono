# @skhamzah123/compono-js-mcp

MCP server wrapper exposing
[`@skhamzah123/compono-js`](https://www.npmjs.com/package/@skhamzah123/compono-js)'s
`render_deck`/`validate`/`review`/`inspire_scan`/`render_docx`/`validate_docx`
as MCP tools, for any MCP-compatible client (not just Claude Code) —
TypeScript port of [`compono-mcp`](https://pypi.org/project/compono-mcp/).

## Install

```bash
npm install @skhamzah123/compono-js-mcp
```

## Usage

Add to your MCP client config (Claude Desktop / Claude Code style):

```json
{ "mcpServers": { "compono-js": { "command": "npx", "args": ["-y", "@skhamzah123/compono-js-mcp"] } } }
```

Exposes:
- **`validate_deck(spec)`** — schema + layout + overflow checks, no file write.
- **`render_deck_tool(spec, output_path)`** — writes a real `.pptx` file.
- **`review_deck(spec)`** — design-quality suggestions (contrast,
  whitespace, image fit, font-size proximity to overflow, style), never
  blocking.
- **`inspire_scan(pptx_paths, out_dir, name, min_repeat_ratio)`** — scans
  `.pptx` files someone already likes into a style profile/skill.
- **`validate_docx_tool(spec)`** / **`render_docx_tool(spec, output_path)`**
  — compono's second output format, `.docx` documents.
- **resource `compono://reference`** — the full agent-facing reference doc.

See [`compono-js`](https://www.npmjs.com/package/@skhamzah123/compono-js)
for the primitive schemas and worked examples — `spec` here is the
identical JSON shape its functions accept directly.
