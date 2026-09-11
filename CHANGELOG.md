# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-09-12

First tagged release: the full v1 primitive catalog, working end-to-end
against a real `.pptx` file.

### Added
- Repo scaffold: package layout, CI/release workflow skeletons, contribution
  docs, MIT license.
- Full v1 primitive schema (pydantic): `header`, `text`, `image`, `stat`,
  `grid`, `table`, `sequence`, `chart`, `shape` — malformed input rejected
  structurally, every field description written as agent-facing guidance.
- Directional box-model layout resolver: header/body/footer regions, `grid`
  2D row/column layout, shape connectors resolved by id in a second pass.
  The agent never writes raw coordinates.
- `fonttools`-based overflow validator: real glyph advance widths, greedy
  line-wrap, structured `{slide, primitive, field, error, detail, fix}`
  errors — a pure function, independently unit-tested.
- `render_deck`/`validate` public API, `DeckValidationError`, and a `compono
  validate`/`compono render` CLI mirroring the same two verbs.
- Every primitive renders as a real, editable OOXML shape (`p:sp`, `p:pic`,
  `p:graphicFrame`) — never a flattened image or embedded video. Table and
  chart render as native `graphicFrame` objects with live, editable data.
  Image placeholders render as an intentional design element and record a
  manifest entry (`{slide, primitive, rect, caption}`) for a later fill pass.
- README.md and `skills/compono/SKILL.md` reference docs: quickstart, full
  API reference, primitive catalog, 4 worked examples, error shape, and
  image-placeholder workflow.
- Golden/invariant test suite: every `examples/*.json` spec is rendered and
  checked for real shape types only, non-overlapping resolved rects, and
  round-tripped text/table/chart data.
- `.claude/` developer tooling: a build-workflow skill, a project-specific
  review subagent, and commit-blocking lint/type/test hooks.
- A `Makefile` wrapping `install`/`lint`/`format`/`typecheck`/`test`/`check`/
  `build`.

### Known limitations
- No font is bundled yet (`src/compono/fonts/` is a placeholder) — overflow
  validation falls back to a system font if found, and is skipped (not
  faked) with a warning otherwise. An OFL-licensed bundled font is planned
  for a follow-up release.
- `shape.kind` "line"/"arrow" render as a plain straight connector —
  arrowhead styling is not yet implemented.
- `table`/`sequence` overflow checking uses a combined-text heuristic, not
  true per-cell/per-step measurement.
- Not yet published to PyPI.
