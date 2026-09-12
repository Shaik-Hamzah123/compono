# Changelog

All notable changes to `compono-js` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Tracked independently from the root `CHANGELOG.md`, which covers `compono` core.

## [0.2.0] - 2026-09-12

### Added
- `review()`: TypeScript port of Python `review()`'s 5 design-quality
  categories (contrast, whitespace, image_fit, font_size, style), same
  thresholds, reusing `resolveSlide`'s own maps and `checkOverflow`.
- DOCX generation (`docx_schema.ts`/`docx.ts`): same primitive catalog as
  Python's `docx_schema.py`/`docx.py` (`heading`, `paragraph`,
  `bullet_list`, `numbered_list`, `table`, `image`, `chart`,
  `page_break`), rendered via the `docx` npm package. `chart` is the one
  documented exception, rasterized via `chart.js`/`chartjs-node-canvas`
  (no native Word chart API exists in any JS library either). New
  `compono-js docx validate`/`compono-js docx render` CLI subcommands.
- Inspire (`inspire.ts`): `scanDeck`/`aggregate`/`writeSkill`, same
  grid-confidence scoring and per-deck weighting as Python's
  `inspire.py`. Reads a `.pptx`'s OOXML directly (`jszip` +
  `fast-xml-parser`), since no npm package offers python-pptx's read-side
  object model — same content-stripping invariant (never reads literal
  run text or image bytes). New `compono-js inspire scan` CLI subcommand.

### Fixed
- `renderShape`: a shape with `text` set drew the fill and the text as
  two separate stacked `<p:sp>` elements at the identical rect, instead
  of one shape with text inside it. Harmless to look at, but it broke
  Inspire's row-grouping/grid-detection math when scanning a rendered
  deck back (found via `inspire.test.ts` against real rendered output,
  not a hypothetical). Fixed via pptxgenjs's `addText(text, {shape: ...})`.
- `docx.ts`: tables defaulted to ~100 twips (an invisible sliver) with no
  explicit width; hyperlink runs had no explicit color/underline and
  rendered invisible in some viewers even though the XML and relationship
  were both correct. Both found by rendering a real spec and viewing the
  output, not just unit tests.

## [0.1.0] - 2026-09-12

First release.

### Added
- TypeScript port of `compono`'s schema → resolver → validator → render
  pipeline, rendering via `pptxgenjs` instead of `python-pptx`. Full v1
  primitive catalog (`header`, `text`, `image`, `stat`, `grid`, `table`,
  `sequence`, `chart`, `shape` including connector routing) — ported
  algorithm-for-algorithm, including the resolver's flex-equal body
  stacking, 2D grid math, and Liang-Barsky connector-routing with
  gutter-detour fallback.
- `validate(spec)`/`renderDeck(spec, outputPath)` — same public shape
  and structured `{slide, primitive, field, error, detail, fix}` error
  convention as the Python `validate()`/`render_deck()`.
- Overflow detection via real glyph advance widths, using `fontkit` in
  place of `fontTools`.
- `compono-js validate`/`compono-js render` CLI, mirroring `compono
  validate`/`compono render`.

### Known limitations
- Inspire, `review()`, and DOCX generation are not ported — Python
  `compono` core only, for now.
- No MCP server for this package yet.
- No bundled font (matches Python `compono`'s current state) — overflow
  validation falls back to a system font if found, and is skipped (never
  faked) with a warning otherwise.
