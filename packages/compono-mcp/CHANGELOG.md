# Changelog

All notable changes to `compono-mcp` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Tracked independently from the root `CHANGELOG.md`, which covers `compono` core.

## [Unreleased]

## [0.1.3] - 2026-09-12

### Added
- `validate_docx_tool(spec)`/`render_docx_tool(spec, output_path)` tools:
  proxy `compono`'s new `.docx` output format (`compono.docx`), same
  thin-proxy convention as `validate_deck`/`render_deck_tool` — errors use
  `"section"` in place of `"slide"`. `chart` primitives render as a
  rasterized image (matplotlib); every other docx primitive is a real,
  editable python-docx object.

### Changed
- `compono` dependency bumped to `>=0.2.0` (needs `compono.docx`, new in
  0.2.0).

## [0.1.2] - 2026-09-12

### Added
- `inspire_scan(pptx_paths, out_dir, name="custom", min_repeat_ratio=0.5)`
  tool: scans a set of `.pptx` files someone already likes into a style
  profile (palette, fonts, spacing, confidence-scored grid patterns) via
  `compono.inspire`, never literal text or images, and writes it as a
  `skills/inspire-<name>/{SKILL.md, profile.json}` folder. Complements
  `validate_deck`/`review_deck`/`render_deck_tool` with a filesystem-in,
  filesystem-out shape rather than spec-in/spec-out.

### Changed
- `compono` dependency bumped to `>=0.1.8` (needs `compono.inspire`, new
  in 0.1.8).

## [0.1.1] - 2026-09-12

### Added
- `review_deck` tool: design-quality suggestions (contrast, whitespace,
  image fit, font-size proximity to overflow) via `compono.review`. Never
  blocking — `{suggestions: [...], warnings: [...]}`, suggestions may be
  empty. Complements `validate_deck`, doesn't replace it.

### Changed
- `compono` dependency bumped to `>=0.1.6` (needs `review`/`reference`,
  new in 0.1.4).
- `requires-python` lowered from `>=3.13` to `>=3.11` — matches
  `fastmcp`'s own floor (`>=3.10`) and compono core's (verified against
  real 3.11/3.12 interpreters, not just relaxed metadata).

## [0.1.0] - 2026-09-12

First release.

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
