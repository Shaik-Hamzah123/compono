# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.8] - 2026-09-12

### Added
- `compono.inspire`: `scan_deck(path)`, `aggregate(paths, *,
  min_repeat_ratio=0.5)`, and `write_skill(profile, out_dir, *, name)` —
  scan a folder of `.pptx` files someone already likes into a
  structural/style profile (palette, fonts, spacing, grid patterns with
  a confidence score) and package it as a `skills/inspire-<name>/`
  folder (`SKILL.md` + `profile.json`) an agent can read before
  generating a *new* deck, so it adopts similar practices loosely
  rather than copying any source deck literally. Hard invariant: never
  serializes a scanned deck's literal text or image bytes into the
  profile — only measurable structure. `aggregate()` separates a
  recurring practice (seen in at least `min_repeat_ratio` of the
  scanned decks) from a one-off quirk, weighted per-deck (not per-slide
  or per-shape) so a many-slide deck can't dominate an aggregate of
  otherwise-small decks. A low-confidence grid detection is omitted
  entirely rather than reported as a guess.
- `compono inspire scan <folder> -o <out_dir> [--name NAME]
  [--min-repeat-ratio R]` CLI subcommand wrapping `aggregate` +
  `write_skill`; a `.pptx` file that fails to open is skipped with a
  warning, not a crash.

### Fixed
- `shape.text.content` with embedded `\n`s (a multi-line label, e.g.
  `"Track 1\nAI Foundations"`) only applied `font_family`/`color`/`align`
  to the first line — python-pptx's `text_frame.text` setter splits on
  `\n` into separate paragraphs, and only `paragraphs[0]` was being
  formatted. Every line after the first silently fell back to the theme
  default (visibly wrong text color on multi-line shape cards). Found via
  a real end-to-end test (Inspire-informed proposal deck with 4-line
  shape cards), fixed by applying font/color/alignment to every
  paragraph in the text frame.
- `review()`'s whitespace check flagged a lone top-level `grid` with
  several children (a card grid, a stat row) as "empty space", even
  though that's a deliberate, already-full layout — the check only
  looked at `len(slide.body) == 1`, not whether that one item already
  fans out into multiple children. Found on the same real deck: 13 of 14
  slides were false-positively flagged before the fix, 3 genuinely sparse
  slides after it.

### Known limitations (new)
- Grid detection is a naive geometric heuristic (row-clustering by
  y-position, near-equal widths, evenly spaced gaps) — reliable against
  clean/grid-based layouts (including anything `compono` itself
  rendered), noisier against genuinely irregular hand-authored decks.
  "No confident pattern found" is a valid, expected outcome there, not
  a bug.
- `SKILL.md`'s prose is templated directly from the structural facts,
  not an LLM-generated summary — it can only state what the numbers
  support (no visual-density judgment from an actually rendered slide).
- Not yet exposed as an MCP tool in `compono-mcp` — it's a
  filesystem-scanning verb, a different shape from that server's
  spec-in/spec-out tools.

## [0.1.7] - 2026-09-12

### Fixed
- Connector routing (`shape.kind="connector"`) could draw a straight line
  right through an unrelated shape's label whenever the two connected
  shapes weren't directly adjacent (e.g. a fan-out/fan-in diagram, or any
  connection skipping over a box in between). `resolver.py` now checks
  whether the direct edge-to-edge line would cross any other resolved box
  and, if so, routes an orthogonal detour through empty gutter space
  around it instead — purely geometric (uses only resolved rects, no
  spec-specific assumptions), so it applies to any layout. Found via a
  hands-on visual stress test rendering a 10-shape/11-connector
  architecture-diagram deck to PNG, not by reading the code.

### Added
- Connectors (`shape.kind="connector"`) and the `"arrow"` line-shape kind
  now render with a real arrowhead at the target end, instead of a bare
  line with no indication of direction.
- A small visual gap (4pt) between a connector's endpoint and the shape it
  connects to, instead of touching the shape's edge flush — the more
  common diagram convention.
- `review()` gains a fifth suggestion category, `style`: flags an em dash
  (`—`) in any text-bearing field and proposes the mechanical fix (a plain
  hyphen). Narrow and precise by design — just the one character, not a
  broader "AI writing tell" pass — since many readers flag em dashes
  specifically as a sign of AI-generated text.

## [0.1.6] - 2026-09-12

### Changed
- `requires-python` lowered from `>=3.13` to `>=3.11` — the `>=3.13` floor
  wasn't backed by any actual 3.13-only language feature in the codebase.
  Verified by actually installing and running the full test suite against
  real 3.11 and 3.12 interpreters (not just relaxing the metadata) — 102/102
  pass on both, no compatibility issues found.

## [0.1.5] - 2026-09-12

### Added
- Two more bundled templates, covering commonly-requested fonts:
  `classic` (Times New Roman) and `clean` (Arial), alongside `default`
  (Calibri) and `modern` (Georgia). No cap on how many templates can
  exist — `Deck.template` resolves any `.yaml` file under
  `src/compono/templates/`.

### Changed
- Root `README.md` is now a slim landing page (install, quickstart,
  links) instead of a fourth full copy of the reference doc — the
  screenshot gallery and full section content moved into `docs/*.md`.
  `skills/compono/SKILL.md` and both `reference.md` copies
  (`src/compono/reference.md`, `packages/compono-mcp/.../reference.md`)
  are unchanged and remain the complete, single-file reference an agent
  gets (Claude Code skill / `compono.reference()` / MCP resource).

## [0.1.4] - 2026-09-12

### Added
- `review(spec, *, template=None) -> ReviewReport` — a third public verb,
  separate from `validate()`: design-quality suggestions, never blocking
  (no `.valid`, only `.suggestions` — possibly empty — and `.warnings`).
  Four categories: `contrast` (WCAG-style ratio between `shape.text.color`
  and `shape.fill`, only when both are set — never guesses a color),
  `whitespace` (a lone top-level body primitive left alone in a tall box —
  uses `LayoutResult.parents` for real containment, and **never fires on a
  header-only slide**, since a sparse title/closing slide is the
  deliberate pattern the 0.1.1 fix shipped, not a defect), `image_fit` (a
  real image, not a placeholder, whose aspect ratio diverges a lot from
  its box), and `font_size` (text using most of its box's height without
  yet overflowing — a proactive nudge distinct from `validate()`'s hard
  error, reusing the same `check_overflow`).
- `ShapeText.color` (schema.py): explicit text color for `shape.text`,
  needed for `review()`'s contrast check to have something concrete to
  measure — previously shape text always used the theme default with no
  way to set it.
- `reference() -> str` (and `compono reference` on the CLI): the same
  reference content as README/SKILL.md, packaged inside `compono` itself
  so a bare `pip install compono` — no MCP connection, no Claude Code
  skill loaded — still gives an agent with shell/code-exec access a way
  to self-serve the documentation.
- `compono review spec.json` CLI subcommand, mirroring `validate`/`render`.
- `compono-mcp` gains a `review_deck` tool (its own CHANGELOG/version).

## [0.1.3] - 2026-09-12

### Added
- A deck's typeface is now a real, working choice: `templates/*.yaml`
  gained a `font_family` key, applied via one shared `_set_font` helper
  everywhere text is rendered (header, text, stat, shape text, table,
  sequence, footer, image caption). A second bundled template,
  `templates/modern.yaml` (Georgia), proves it end-to-end alongside
  `default.yaml` (Calibri).
- `Deck.template` (schema.py) — present in the schema since the first
  release but never actually wired to anything — now really selects a
  template: `Template.from_name(name)` resolves it, both `validate()` and
  `render_deck()` use it when no explicit `template=` kwarg is given, and
  the CLI's `--template` flag (previously a documented no-op) now works,
  overriding the spec's own field when both are given. An unknown
  template name is a structured `unknown_template` error, not a crash.

### Known limitations (new)
- `font_family` is a name written into the file, not an embedded font —
  PowerPoint resolves it against whatever's installed on the viewer's
  machine; compono does not embed font files.
- Overflow validation's glyph metrics don't yet reflect a template's
  chosen `font_family` — wrap/overflow math still measures off whichever
  bundled/system font `_resolve_font_path` finds, regardless of what the
  deck actually renders in.
- Chart category/series labels are not yet threaded through
  `font_family` — python-pptx's chart font API is a separate surface not
  otherwise touched in this codebase; they still use the theme default.

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
