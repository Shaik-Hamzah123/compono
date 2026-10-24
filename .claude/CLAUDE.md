# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`compono` — an agent-oriented, code-based PPTX/DOCX generation library
("Manim, but for PowerPoint/Word"). An LLM agent describes a slide deck (or
a Word document) as typed primitives (JSON/dict); for pptx, a
constraint-based layout resolver computes real EMU positions so the agent
never writes raw coordinates — docx has no resolver, since Word flows
content top-to-bottom on its own, and uses its own smaller primitive set
(`src/compono/docx_schema.py`/`src/compono/docx.py`, see `docs/docx.md`).
Every rendered element must be a genuine, editable OOXML shape — never a
flattened image or embedded video — with one documented exception: a docx
`chart` primitive, which `python-docx` has no native API for, is
rasterized via matplotlib. The full pptx spec is `COMPONO_PLAN.md` at the
repo root; read it before making architectural changes to the pptx path.

## Commands

```
uv sync                    # install deps (dev group syncs by default)
make check                  # lint + typecheck + test (same as pre-commit hook)
make lint                   # uv run ruff check .
make format                  # uv run ruff format . && ruff check --fix .
make typecheck               # uv run mypy src
make test                    # uv run python -m pytest -q
make build                   # uv build
```

Adding a dependency: use `uv add <package>` (and `uv add --dev <package>`
for dev-only tools) — unpinned, so it resolves to the latest version.
Don't hand-edit version pins into `pyproject.toml`; let `uv add` write them.

If `uv sync`/`uv add` fails with a TLS `UnknownIssuer` error (seen on this
machine, likely corporate proxy/VPN related), retry with `--system-certs`.

If the repo is checked out over a UNC/network path (e.g. editing a WSL
checkout from Windows) and `uv run pytest` fails importing numpy/matplotlib
with "DLL load failed" even though the same venv imports them fine in a
plain Python shell, use `uv run python -m pytest` instead — the `pytest`
console-script shim's DLL search behavior breaks over such paths; `python
-m pytest` from the same venv does not. `make test`/`make check` and the
pre-commit hook already invoke pytest this way.

Run a single test: `uv run python -m pytest tests/test_resolver.py::test_grid_row_layout_auto_columns -q`

CLI (mirrors the public API): `compono validate spec.json` /
`compono render spec.json -o deck.pptx`

A pre-commit hook (`.claude/hooks/pre_commit_check.py`) already blocks
`git commit` if ruff/mypy/pytest fail — fix the reported failure rather
than bypassing it. A post-edit hook auto-formats any `.py` file touched
under `src/`/`tests/`.

## Branching and versioning

- `main` — production; only receives merges from `dev` when release-ready.
  Tagging a version on `main` triggers `.github/workflows/release.yml`
  (PyPI trusted publishing).
- `dev` — integration branch; all day-to-day work happens here (or on a
  short-lived branch cut from `dev`).
- One commit per logical unit of work, not per file. Don't bump
  `pyproject.toml`'s version except at a real release milestone (record it
  in `CHANGELOG.md`, Keep a Changelog format) — a real bug fix or behavior
  change to `src/compono/` itself is a milestone (patch bump); a pure
  tooling/structure change (e.g. adding a workspace member) is not.
- **After any change to `compono`'s public behavior/API** (new primitive,
  changed default, new CLI/MCP surface, etc.), update the docs that claim
  to describe it in the same commit. Three files carry the **full**
  content and are kept in sync by convention (see the comment at the top
  of each): `skills/compono/SKILL.md`, `src/compono/reference.md`
  (packaged inside `compono` itself, served by `reference()`/`compono
  reference` — for an agent with only shell/code-exec access, no MCP or
  Claude Code skill), and `packages/compono-mcp/src/compono_mcp/reference.md`
  (served instead as the `compono://reference` MCP resource). Root
  `README.md` is now a slim landing page (install/quickstart/links into
  `docs/*.md`) rather than a fourth full copy — update whichever `docs/*.md`
  page and/or the README itself actually changed. A behavior change
  without a matching doc update is an incomplete change, not a follow-up.
- **A version bump is not done until it's published.** The moment
  `pyproject.toml`'s version changes, that same piece of work must merge
  `dev` → `main`, tag `vX.Y.Z`, and push the tag (triggering
  `release.yml`) before starting anything else — never leave a bumped
  version un-tagged, and never bump again while a previous bump is still
  unpublished (this slipped once already: 0.1.1 was bumped and committed
  but never tagged/released before 0.1.2 followed it). After pushing the
  tag, confirm the release actually landed — `gh run view <run-id>`
  shows `completed`/`success` and `https://pypi.org/pypi/compono/<version>/json`
  (the exact version, not the bare `/compono/json` endpoint, which can
  serve a stale cached "latest") returns that version — don't assume a
  green tag push means PyPI has it.

## Architecture

Five modules in `src/compono/`, each with a single, non-overlapping job —
new work almost always touches several of them in the same pattern:

1. **`schema.py`** — pydantic models for the primitive catalog: `header`,
   `text`, `image`, `stat`, `grid`, `table` (including `cell_fills`/`merges`
   for per-cell body styling and rectangular-range merging), `sequence`,
   `chart`, `shape`, `diagram` (a node-graph flowchart whose nodes/edges
   are synthesized as `shape` primitives at layout time by
   `resolver/diagram.py`'s `_layout_diagram` — this is why adding it
   needed no new `render/` code at all), `gantt` (a Gantt/timeline chart
   that fully collapses into a synthesized `table` at layout time via
   `resolver/gantt.py`'s `_layout_gantt` — even less new `render/` code
   than `diagram`: zero, not even a dispatch branch, since by render time
   it's already an ordinary `table`).
   `PrimitiveSpec` is a discriminated union (`Field(discriminator="primitive")`)
   over all of them; `Grid.items` is recursively typed as `list[PrimitiveSpec]`
   (grids can contain any primitive, including other grids), which is why
   `Grid.model_rebuild()` runs once all primitive classes are defined. `Slide`
   (`{header?, body, notes?}`) and `Deck` (`{template, slides}`) sit above the
   primitives. Every `Field(description=...)` is written as an instruction to
   the calling agent ("Keep under ~60 characters — longer titles will be
   shrunk by the resolver"), not a bare type label — this is deliberate,
   since the schema doubles as in-context documentation.
2. **`resolver/`** (a package, not a flat file — split 2026-10-24 once it
   grew past 600 lines; see item 4 below for the same split on `render/`)
   — the layout engine. `resolver/template.py`'s `Template.from_yaml` loads
   `templates/default.yaml` (page size, margins, header/footer heights,
   gutter, and optional `colors: {primary, accent}`/`logo:` branding
   fields — all `None` unless a template yaml sets them, so every stock
   template renders byte-identically to before these fields existed) and
   converts geometry to EMU. `resolver/types.py` holds `Rect`/
   `ConnectorPoints`/`LayoutResult`. `resolver/layout.py`'s `resolve_slide`
   does a directional box model: header region top, footer pinned bottom,
   body fills the remainder; body primitives currently share height
   equally (a flex-equal fallback — real content-based sizing via font
   metrics is a known future improvement, see CHANGELOG "Known
   limitations"). `grid` is the one primitive doing true 2D row/column
   math, also in `layout.py`. `diagram`'s layout (nodes synthesized as
   `shape`s) lives in `resolver/diagram.py`; `gantt`'s (fully collapses
   into a synthesized `table`) in `resolver/gantt.py`. Shape connectors
   (and `diagram`'s edges) resolve in a second pass, once every other rect
   is final, by looking up the referenced `id`s — the obstacle-avoiding
   router both share lives in `resolver/connectors.py`, a leaf module
   `diagram.py` imports from with no cycle. `diagram.py`/`gantt.py` each
   need `layout.py`'s `_place_item` to place their synthesized primitive,
   which would be a circular import at module-load time — both use a
   **deferred import** (`from .layout import _place_item` inside the
   function body, not at module top) to break the cycle; this is the one
   place in the package where that pattern is used, and it's commented
   at each occurrence. **Pure package — no file I/O beyond
   `Template.from_yaml` itself, no pptx writes.** `resolver/__init__.py`
   re-exports everything the rest of the codebase imports from
   `compono.resolver` today, so `from compono.resolver import Template`
   etc. is unaffected by the package split.
   - `LayoutResult.items` maps each resolved id back to its originating
     primitive object — the single source of truth `render/` uses instead
     of re-deriving the id scheme.
   - `LayoutResult.parents` maps each child id to its parent grid's id,
     captured during grid recursion. Use this (not an id-string-prefix
     guess) for any containment/ancestry check — an explicit `id` override
     on a primitive breaks any naming-convention assumption.
3. **`validator.py`** — overflow detection via real font metrics.
   `load_font_metrics` reads actual glyph advance widths from a font file
   via `fontTools` (no rendering). `measure_text_width_pt` /`wrap_lines`/
   `check_overflow` are pure functions operating on a `FontMetrics` table,
   independently unit-tested without touching a font file.
   `build_overflow_error` produces the canonical structured error shape:
   `{slide, primitive, field, error, detail, fix}`. `SAFE_FONTS` (bundled
   font allowlist) is currently empty — no font ships with the package yet,
   so `render/` falls back to a system font if one is found and skips
   (never fakes) overflow validation otherwise, with a warning.
4. **`render/`** (a package, not a flat file — split 2026-10-24 once it
   grew past 1000 lines) — orchestrates validate → resolve → write pptx;
   the only package allowed to import `pptx`. `render/deck.py`'s
   `validate()` and `render_deck()` are the two public verbs, plus the
   per-slide/per-primitive dispatch (`_render_slide`/`_render_primitive`)
   that calls into `primitives.py`. `render/_overflow.py`'s
   `_extract_text_fields` is the single place that maps each primitive
   type to its text-bearing field(s) and font size for overflow checking
   — every primitive routes through the same `check_overflow` call, never
   a bespoke wrap implementation. `render/primitives.py` holds every
   `_render_<primitive>` function — **this is the file "Adding a new
   primitive" below refers to** — each taking
   `(pptx_slide, primitive, rect, template, ...)` and producing a real
   OOXML shape (`add_textbox`, `add_shape`, `add_table`, `add_chart`,
   `add_connector`, `add_picture` for real images) — never rasterize
   content. Image placeholders render a dashed-border box + caption and
   append a manifest entry instead. `render/_shared.py` holds the
   cross-cutting constants/helpers (font sizes, `_set_font`, font
   resolution) every primitive renderer and the public verbs lean on;
   `render/types.py` holds `DeckValidationError`/`ValidationReport`/
   `RenderReport`, kept separate from `deck.py` so `_shared.py` can raise
   `DeckValidationError` without an import cycle. `render/__init__.py`
   re-exports everything the rest of the codebase (and `review.py`,
   `tests/`) imports from `compono.render` today.
5. **`cli.py`** — argparse wrapper exposing `validate`/`render_deck` as
   `compono validate`/`compono render`, for frameworks that can only shell
   out (also wires up `docx validate`/`docx render`, `inspire scan`,
   `reference`, `template extract`).

### `template_authoring.py` (host-side tool, not part of the five modules)

Backs `compono template extract SOURCE NAME` — drafts a new
`templates/<name>.yaml` from an existing corporate `.pptx`'s page size,
theme accent colors (`a:clrScheme/accent1`/`accent2`, read via raw
zip+lxml parsing of the theme XML part since python-pptx's own
`pptx/oxml/theme.py` has no read accessors for it), theme body font, and
a logo picture on the slide master, if any. Always best-effort — a
missing/malformed theme or no master logo degrades to `None` fields, never
raises. Deliberately **not** placed in `resolver/` (which must stay
import-`pptx`-free per the "only `render/` imports `pptx`" rule below —
this module imports it for read-only extraction, a distinct concern from
either `resolver/`'s pure layout math or `render/`'s pptx *write*
path). Margins/header/footer/gutter are never derived from the source
deck — they're copied from compono's own `default.yaml`, since arbitrary
master placeholder geometry has no mapping onto compono's resolver box
model (compono never uses PowerPoint placeholder inheritance). This is a
developer/host-side tool only: `Deck.template` (schema.py) still accepts
only a plain string naming a file under `templates/`, so an agent cannot
point a render at an arbitrary uploaded `.pptx` — the written yaml is a
"one-time, reviewed, host-side change" like any hand-authored template
(see `docs/templates-and-fonts.md`'s governance section).

The three new optional `Template` fields (`primary_color`, `accent_color`,
`logo_path`) are consumed additively in `render/primitives.py`: a branded table
header row fill (`_render_table`, gated on `primary_color`), branded
sequence step shape fill (`_render_sequence`, gated on `accent_color`),
branded chart series/data-point colors (`_render_chart`'s
`_apply_chart_colors`, gated on either color being set — cycles
`[primary_color, accent_color]` across series for bar/line or points for
pie, via `series.format.fill`/`point.format.fill` respectively, two
different python-pptx APIs), and a header-region logo picture
(`_render_header`, gated on `logo_path`) — each a real OOXML object
(`cell.fill`/`shape.fill`/chart `format.fill`/`add_picture`), never a
rasterized stand-in. Slide master/layout placeholder-geometry inheritance
is explicitly out of scope (see NEXT-STEPS.md if working on this area
further).

### DOCX (a separate, parallel pipeline)

`docx_schema.py`/`docx.py` are compono's second output format — `.docx`
documents, not slides — and are deliberately **not** part of the five
modules above: no resolver (Word flows content top-to-bottom on its own),
a smaller primitive set (`heading`, `paragraph`, `bullet_list`,
`numbered_list`, `table`, `image`, `chart`, `page_break`), and `docx.py` is
the only module allowed to import `docx`/`matplotlib` (mirrors `render/`'s
"only package allowed to import pptx" rule). `render_docx()`/
`validate_docx()` are its two public verbs, same shape as `render_deck()`/
`validate()`. One deliberate, documented exception to the "always a real
object" invariant below: `chart` is rasterized via matplotlib (no native
Word chart API exists in `python-docx`) — every other docx primitive is a
genuine python-docx object. See `docs/docx.md` for the full write-up.

### compono-js / compono-js-mcp (separate, parallel packages — not Python)

`packages/compono-js/` is a TypeScript port of compono core (schema →
resolver → validator → render, `review()`, Inspire, DOCX generation) —
pptx via `pptxgenjs` instead of `python-pptx`, docx via the `docx` npm
package instead of `python-docx`, chart rasterization via
`chartjs-node-canvas` instead of matplotlib, Inspire's deck-*reading* via
direct OOXML parsing (`jszip` + `fast-xml-parser`) since no npm package
offers python-pptx's read-side object model. Same primitive-JSON
contracts, same structured error shapes, independent implementation and
version (own `package.json`, own `CHANGELOG.md`, published to npm
separately from PyPI). `packages/compono-js-mcp/` is its MCP server, the
TypeScript counterpart to `compono-mcp` (same 6 tools, same
`compono://reference` resource, via `@modelcontextprotocol/sdk` instead
of `fastmcp`) — it depends on `compono-js` via a `file:../compono-js`
dependency in dev, a real published version range at publish time.

Neither is a `uv` workspace member — the root `pyproject.toml`'s
`[tool.uv.workspace]` explicitly excludes both, since neither has a
`pyproject.toml` and uv's `packages/*` glob otherwise errors on a non-
Python directory. A change to a pptx/docx primitive or algorithm on the
Python side is a candidate to port over here too, but the two
implementations are not required to stay in lockstep release-to-release
— check `docs/compono-js.md` for what's currently ported.
Real bugs surfaced *by* the port (not hypothetical) so far: a shape-with-
text drew as two stacked shapes instead of one (broke Inspire's grid
detection when scanning compono-js's own output), a docx table defaulted
to an invisible ~100-twip width, and docx hyperlink runs rendered
invisible without explicit color/underline styling — all with regression
tests.

### Adding a new primitive

Touch, in order: `schema.py` (new class + add to `PrimitiveSpec` union +
re-run `Grid.model_rebuild()`) → `resolver/layout.py`'s `_place_item`
(usually no change needed — it's already generic for leaf primitives;
only grids/diagram/gantt-style primitives that synthesize other
primitives need their own `resolver/<primitive>.py` + a dispatch branch)
→ `validator.py` (reuse `check_overflow`, don't add a new wrap routine)
→ `render/primitives.py`'s `_render_<primitive>` + `render/_overflow.py`'s
`_extract_text_fields` → `src/compono/__init__.py` exports. Extend
`tests/test_schema.py`, `tests/test_resolver.py`, `tests/test_render.py`,
`tests/test_render_shape_invariant.py` in the same style as existing
primitives — don't create a new test file per primitive.

### Hard invariants

- Every primitive renders as a real, editable OOXML shape — never a
  flattened image or embedded video. Enforced by
  `tests/test_render_shape_invariant.py`, which renders every
  `examples/*.json` spec and asserts only allowed shape types appear. The
  one documented exception is docx's `chart` primitive (see "DOCX" above),
  scoped and enforced separately by `tests/test_docx_shape_invariant.py`.
- Resolver and validator stay pure functions (no pptx writes, no network).
- One shared text-fit routine (`validator.check_overflow`/`wrap_lines`) for
  every text-bearing primitive — never a per-primitive reimplementation.
- Errors are fixes, not diagnoses: always
  `{slide, primitive, field, error, detail, fix}`.
- Never silently guess in a way that hides a mistake — safe normalization
  (whitespace trimming, type coercion) is fine; anything that changes
  intent must be a validation error instead.
- No slide-type taxonomy (title/content/thank-you slide types) — a slide is
  just `{header?, body}`; genre/density/tone composition is the caller's
  job, not a schema concept.
- `chart.chart_type` is scoped to `bar`/`line`/`pie` only (COMPONO_PLAN.md
  section 5) — deliberately not an exhaustive chart-type catalog. Extending
  it later is just adding entries to `_CHART_TYPE_TO_XL` in
  `render/_shared.py`, not a rearchitecture, but don't add types
  speculatively.

## Repo-specific tooling

- `.claude/skills/compono-build/SKILL.md` — the full build-workflow
  reference (build-order status, this same primitive-adding pattern, in
  more detail).
- `.claude/agents/compono-reviewer.md` — a review subagent checking changes
  against these specific invariants (not generic code review).
- `.claude/hooks/` — the commit-blocking and auto-format hooks referenced
  above.
