# Changelog

All notable changes to `compono-mcp` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Tracked independently from the root `CHANGELOG.md`, which covers `compono` core.

## [Unreleased]

### Added
- MCP server (stdio transport, via `fastmcp`) exposing `compono`'s two verbs
  as tools: `validate_deck` and `render_deck_tool`. Both are thin proxies —
  `spec` parameters are typed as plain `dict`, so malformed input reaches
  `compono.validate`/`render_deck` itself and comes back as compono's own
  structured `{slide, primitive, field, error, detail, fix}` errors, never a
  generic MCP schema-rejection error.
- `compono://reference` resource: the full agent-facing reference doc
  (quickstart, primitive catalog, worked examples, error shape), for MCP
  clients without Claude Code's skill system.
- `compono-mcp` console script entry point.

### Known limitations
- stdio transport only — no HTTP/SSE.
- Not yet published to PyPI.
