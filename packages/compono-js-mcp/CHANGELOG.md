# Changelog

All notable changes to `@skhamzah123/compono-js-mcp` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Tracked independently from the root `CHANGELOG.md` and `packages/compono-js/CHANGELOG.md`.

## [0.1.0] - 2026-09-12

First release.

### Added
- MCP server (stdio transport, via `@modelcontextprotocol/sdk`) exposing
  `compono-js`'s six verbs as tools: `validate_deck`, `render_deck_tool`,
  `review_deck`, `inspire_scan`, `validate_docx_tool`, `render_docx_tool`
  — same param names and return shapes as Python `compono-mcp`.
- `compono://reference` resource: the full agent-facing reference doc.
- `compono-js-mcp` console script entry point.

### Known limitations
- stdio transport only — no HTTP/SSE.
