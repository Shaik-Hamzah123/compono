# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.2] - 2026-09-12

### Changed
- `shape.fill_style` (`"solid" | "gradient"`, default `"solid"`) replaces the
  automatic gradient every filled shape got in 0.1.1. Gradients looked good
  in our own example decks, but imposing one on every agent-filled shape
  took away a real design decision that belongs to the agent — a shape
  with `fill` now renders flat unless `fill_style: "gradient"` is set
  explicitly. Every example deck that previously relied on the automatic
  look now sets `fill_style: "gradient"` explicitly instead.
- Enriched every example deck's data volume (`text` bullets, `chart`
  categories/series, `table` rows, `grid` items — including a nested
  grid-of-grids and an 8-node architecture diagram) so they read as
  realistic agent output rather than thin smoke-test fixtures.
- `examples/minimal.json` removed as a showcase example — every remaining
  example deck is now genuinely representative reference material. The
  equivalent spec is kept inline in `tests/test_render.py` as a smoke-test
  fixture, so no test coverage was lost.

## [0.1.1] - 2026-09-12

A visual-quality pass, prompted by rendering every example deck to a real
screenshot and judging the result honestly rather than just checking it
didn't crash.

### Added
- Genre-spanning example decks (`client_proposal`, `college_presentation`,
  `conference_talk`, `research_talk`, `fun_explainer`,
  `architecture_diagram`), each validated and rendered to real `.pptx` →
  PNG screenshots embedded in the README.
- A consistent footer on every rendered slide: a small, gray "N / total"
  page number. The footer's space was reserved since Step 2 but nothing
  was ever drawn into it — every slide looked unfinished at the bottom.
- Filled `shape` primitives now render with a deliberate top-to-bottom
  gradient (a light tint of the given color down to the color itself)
  instead of a flat solid fill — consistent with the polished look
  `sequence` step boxes already had by accident from PowerPoint's default
  theme gradient, rather than that being inconsistent with plain flat
  shapes everywhere else.

### Fixed
- A slide with only a `header` (a title/section/closing slide) rendered
  its title pinned to a short strip at the top of an otherwise-blank page.
  The resolver now gives a header-only slide the full content area, and
  `render.py` vertically centers it — a real title slide, not a title
  stranded at the top of empty space.
- `header`, `text`, and `stat` primitives didn't vertically center their
  content within a tall assigned box (only `shape.text` and `sequence`
  steps did) — every single-item slide (a lone stat, a bullet list, a
  closing slide) rendered top-heavy with dead space below. All now use
  `MSO_ANCHOR.MIDDLE`.
- Image placeholder captions were nearly invisible on some renderers (no
  explicit font color) — now explicitly gray.
- Shape connectors joined rect *centers*, cutting straight across any text
  centered in either shape. Now clipped to each rect's actual boundary
  along the line between centers, for both the `sequence` primitive and
  the general `shape.kind="connector"` case.
- Connector shapes were incorrectly counted toward a body/grid's
  equal-height slot split, even though they render nothing at their own
  position — could visibly starve real siblings of space when a diagram
  had several connectors. They're now excluded from slot counting
  entirely.

### Known limitations (new)
- Connectors route as straight lines with no obstacle avoidance — if an
  unrelated sibling sits directly between two connected primitives, the
  line will cross through it. Lay out diagrams so connected primitives
  don't have another primitive directly in between (see
  `examples/architecture_diagram.json` for a layout that avoids this).
- `table` rows are explicitly stretched to fill their assigned box height
  in the written `.pptx` (verified in the file's own XML), but LibreOffice
  recalculates its own row heights on import/render regardless — screenshots
  taken via the LibreOffice-based `scripts/render_example_screenshots.py`
  may show dead space below a short table even though the file itself is
  correct. Not observed to affect PowerPoint itself.

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
