# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`compono` — an agent-oriented, code-based PPTX generation library ("Manim,
but for PowerPoint"). An LLM agent describes a slide deck as typed
primitives (JSON/dict), and a constraint-based layout resolver computes
real EMU positions so the agent never writes raw coordinates. Every
rendered element must be a genuine, editable OOXML shape — never a
flattened image or embedded video. The full spec is `COMPONO_PLAN.md` at
the repo root; read it before making architectural changes.

## Commands

```
uv sync                    # install deps (dev group syncs by default)
make check                  # lint + typecheck + test (same as pre-commit hook)
make lint                   # uv run ruff check .
make format                  # uv run ruff format . && ruff check --fix .
make typecheck               # uv run mypy src
make test                    # uv run pytest -q
make build                   # uv build
```

Adding a dependency: use `uv add <package>` (and `uv add --dev <package>`
for dev-only tools) — unpinned, so it resolves to the latest version.
Don't hand-edit version pins into `pyproject.toml`; let `uv add` write them.

If `uv sync`/`uv add` fails with a TLS `UnknownIssuer` error (seen on this
machine, likely corporate proxy/VPN related), retry with `--system-certs`.

Run a single test: `uv run pytest tests/test_resolver.py::test_grid_row_layout_auto_columns -q`

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
  in `CHANGELOG.md`, Keep a Changelog format).

## Architecture

Five modules in `src/compono/`, each with a single, non-overlapping job —
new work almost always touches several of them in the same pattern:

1. **`schema.py`** — pydantic models for the primitive catalog: `header`,
   `text`, `image`, `stat`, `grid`, `table`, `sequence`, `chart`, `shape`.
   `PrimitiveSpec` is a discriminated union (`Field(discriminator="primitive")`)
   over all of them; `Grid.items` is recursively typed as `list[PrimitiveSpec]`
   (grids can contain any primitive, including other grids), which is why
   `Grid.model_rebuild()` runs once all primitive classes are defined. `Slide`
   (`{header?, body, notes?}`) and `Deck` (`{template, slides}`) sit above the
   primitives. Every `Field(description=...)` is written as an instruction to
   the calling agent ("Keep under ~60 characters — longer titles will be
   shrunk by the resolver"), not a bare type label — this is deliberate,
   since the schema doubles as in-context documentation.
2. **`resolver.py`** — the layout engine. `Template.from_yaml` loads
   `templates/default.yaml` (page size, margins, header/footer heights,
   gutter) and converts everything to EMU. `resolve_slide` does a
   directional box model: header region top, footer pinned bottom, body
   fills the remainder; body primitives currently share height equally (a
   flex-equal fallback — real content-based sizing via font metrics is a
   known future improvement, see CHANGELOG "Known limitations"). `grid` is
   the one primitive doing true 2D row/column math. Shape connectors
   resolve in a second pass, once every other rect is final, by looking up
   the referenced `id`s. **Pure function — no file I/O beyond
   `Template.from_yaml` itself, no pptx writes.**
   - `LayoutResult.items` maps each resolved id back to its originating
     primitive object — the single source of truth `render.py` uses instead
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
   so `render.py` falls back to a system font if one is found and skips
   (never fakes) overflow validation otherwise, with a warning.
4. **`render.py`** — orchestrates validate → resolve → write pptx; the only
   module allowed to import `pptx`. `validate()` and `render_deck()` are the
   two public verbs. `_extract_text_fields` is the single place that maps
   each primitive type to its text-bearing field(s) and font size for
   overflow checking — every primitive routes through the same
   `check_overflow` call, never a bespoke wrap implementation.
   `_render_<primitive>` functions each take `(pptx_slide, primitive, rect)`
   and must produce a real OOXML shape (`add_textbox`, `add_shape`,
   `add_table`, `add_chart`, `add_connector`, `add_picture` for real images)
   — never rasterize content. Image placeholders render a dashed-border box
   + caption and append a manifest entry instead.
5. **`cli.py`** — argparse wrapper exposing `validate`/`render_deck` as
   `compono validate`/`compono render`, for frameworks that can only shell
   out.

### Adding a new primitive

Touch, in order: `schema.py` (new class + add to `PrimitiveSpec` union +
re-run `Grid.model_rebuild()`) → `resolver.py`'s `_place_item` (usually
no change needed — it's already generic for leaf primitives; only grids
need special 2D handling) → `validator.py` (reuse `check_overflow`, don't
add a new wrap routine) → `render.py`'s `_render_<primitive>` +
`_extract_text_fields` → `__init__.py` exports. Extend
`tests/test_schema.py`, `tests/test_resolver.py`, `tests/test_render.py`,
`tests/test_render_shape_invariant.py` in the same style as existing
primitives — don't create a new test file per primitive.

### Hard invariants

- Every primitive renders as a real, editable OOXML shape — never a
  flattened image or embedded video. Enforced by
  `tests/test_render_shape_invariant.py`, which renders every
  `examples/*.json` spec and asserts only allowed shape types appear.
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
  it later is just adding entries to `_CHART_TYPE_TO_XL` in `render.py`, not
  a rearchitecture, but don't add types speculatively.

## Repo-specific tooling

- `.claude/skills/compono-build/SKILL.md` — the full build-workflow
  reference (build-order status, this same primitive-adding pattern, in
  more detail).
- `.claude/agents/compono-reviewer.md` — a review subagent checking changes
  against these specific invariants (not generic code review).
- `.claude/hooks/` — the commit-blocking and auto-format hooks referenced
  above.
