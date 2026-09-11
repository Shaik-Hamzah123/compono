# Compono — Project Plan

*An agent-oriented, code-based PPTX generation library — "Manim, but for PowerPoint." This file is meant to be handed to Claude Code (or another engineering agent) as the working spec for scaffolding and building the repo.*

## 1. Vision

An open-source, code-based tool that lets LLM agents build genuinely good `.pptx` decks reliably — not scoped to one company's deck genre, but usable for college presentations, research talks, client proposals, conference talks, or explainers. Distributed as a Python library (`pip install compono`), adoptable by any agent framework, not Claude-specific.

## 2. Prior art and why this is different

- `manim-slides` / `manim-pptx` produce decks by pre-rendering each slide as a video clip embedded as an autoplay placeholder. PowerPoint does no animation — it just plays a video per slide.
- PowerPoint's real animation system (`<p:timing>` in OOXML) is unsupported for *writing* by both `python-pptx` and `pptxgenjs`, and every existing tool routes around it via the video-embed trick instead of solving native layout/animation.
- **Verdict:** video-embedded slides aren't editable afterward, bloat file size, and have no real text layer — disqualifying as the default engine. Could remain a manual escape hatch for a single special slide, never the default path.
- **This project's bet:** the real leverage isn't a big component catalog — it's a **constraint-based layout resolver** so the agent never writes raw `x/y/w/h` coordinates. The agent describes intent; deterministic code computes real EMU positions. This is the single highest-value, most novel piece of the project.

## 3. Architecture — four parts

1. **Primitive schema** — typed spec (pydantic → JSON Schema) per primitive; malformed input rejected structurally, not caught visually later.
2. **Template as data, not code** — palette, fonts, logo assets, motifs, footer, title/closing layout live in a config file (YAML). A new brand/style = a new config file, not new code.
3. **Layout resolver** — the constraint solver. Where most engineering effort goes.
4. **Validator** — two layers:
   - (a) analytical pre-render check using real font-metric/glyph-width tables (via `fonttools`, reading actual advance widths — not PIL) to predict overflow before any rendering.
   - (b) render-to-image visual QA as a backstop.

### Non-negotiable invariant: everything is a real, editable native shape

Every primitive must render as a genuine OOXML object (`p:sp`, `p:pic`, `p:graphicFrame`) — never a flattened image, never embedded video. Enforced by an automated post-render test that opens the `.pptx` and asserts shape-type composition matches expectations. This is what structurally rules out the manim-slides approach and guarantees "client opens it in PowerPoint and drags a box around" holds.

## 4. Scope discipline: genre reasoning belongs to the agent

The tool stays completely genre-agnostic. It enforces only mechanical correctness (no overlap, no overflow, no misalignment, consistent template application) and reserving/tracking placeholders. It does **not** bake in "conference vs. college vs. proposal" density presets — the agent already reasons about deck genre, density, pacing, and tone. Baking genre logic into the tool is scope creep it shouldn't own.

## 5. Primitive catalog (v1 — 9 primitives)

Small and generic, not a large named catalog (rejected reusing a 24-component genre-scoped catalog from an earlier internal project — genre-specific "looks" are skins on these same primitives, not separate things the tool needs to know about).

1. **header** — `title`, `subtitle?`, `eyebrow?`, `align`
2. **text** — `mode` (paragraph/bullets), `content`, `columns?` (int, default 1, for multi-column layout), `emphasis_indices?`
3. **image** — `src?`, `placeholder` (bool), `caption?`, `fit` (cover/contain) — see placeholder design below
4. **stat** — `value`, `label`, `trend?`
5. **grid** — `items` (recursive: list of nested primitive specs), `columns` (int or "auto"), `direction` (row/column), `align`, `justify` (see alignment below)
6. **table** — `headers`, `rows`, `emphasis_row?`/`emphasis_col?`
7. **sequence** — `steps` (list of {label, description}), `orientation` (horizontal/vertical) — may compile internally to `shape` + `text` + connectors rather than a bespoke render path
8. **chart** — `chart_type` (bar/line/pie), `categories`, `series`
9. **shape** — `kind` (rect/rounded_rect/oval/line/arrow/connector), `fill`, `border`, `id?`, `connects?` ({from_id, to_id}), `text?` (nested object — see below)

All primitives accept an optional shared `notes` field (speaker notes) and an optional `id` (needed for shape connectors to reference other primitives' resolved positions).

### Text-in-shape

```
shape.text: { content, align (left/center/right), valign (top/middle/bottom), autofit (bool, default true) }
```
Uses the *same* shrink-to-fit routine as the `text` primitive and `stat` — one shared "fit text into this rectangle" function, not three separate implementations, so overflow-logic fixes apply everywhere at once.

### Image placeholders — first-class, not a broken state

- Renders as an intentional design element (dashed border, small icon, caption describing what should go there).
- Renderer emits a manifest alongside the `.pptx`: one entry per placeholder with slide number, exact EMU rect, and caption text.
- A later pass (image search/gen/human) fills each reserved rect directly from the manifest — no re-layout needed. The deck-building agent itself never needs image capability.

## 6. Layout resolver — constraint model

Directional box model (CSS-flexbox mental model), not a general constraint solver (avoid `kiwisolver`/Cassowary-style complexity unless real cases demand escalation):

- Each slide: fixed page margins (from template config) → vertical stack of regions (header region top, footer pinned bottom, body fills remainder).
- Within body: primitives lay out top-to-bottom by default, each claiming height explicitly, by content-based estimate (via the font-metric table), or as a flex weight when multiple primitives share a slide.
- `grid` is the one primitive doing true 2D math — row/column count, gutter size, equal-fr distribution unless a child requests a weight.
- `shape` connectors resolve in a second pass, after all positions are final (a connector references another primitive's resolved rect via `id`).

### Alignment

Direct CSS parallel, deliberately reused mental model:
- **Container-level** (on `grid` / slide body region): `align` (start/center/end/stretch — cross-axis), `justify` (start/center/end/space-between — main-axis).
- **Per-item override**: `align_self` (start/center/end/stretch) on any child inside a grid.
- Peer-to-peer alignment across unrelated shapes (not sharing a container) is explicitly **out of scope for v1** — container-based alignment covers the large majority of real cases; add only if a real deck needs it.

### Auto-reshaping (shrink-to-fit, bounded and reported — never silent)

- Each primitive has a defined safe shrink range (font size within a bounded band, slightly tighter line-height).
- If content overflows past the band's floor: hard validation error with a fix-suggestion (see error shape below), never a silently added slide or truncated text.
- Any shrink that *does* happen is reported in the render output: `{slide, primitive, shrunk_from, shrunk_to}` — visible and reversible, like PowerPoint's own "shrink text on overflow," never invisible.

## 7. Validator — overflow detection

- Use `fonttools` to read real glyph advance widths directly from font files at a given size — no rendering required, works headlessly in CI.
- Maintain a small allowlist of "safe" fonts (bundled or verified present); anything outside it is substituted or flagged.
- Algorithm: greedy line-wrap using measured advance widths → count resulting lines × line-height → compare to box height → flag overflow with the specific primitive/slide index, before any pptx rendering happens.
- This is a pure function, independently unit-testable with zero rendering involved.

## 8. Agent ergonomics — design principles

1. **One entry point, not a library of methods** — `render_deck(spec)` and `validate(spec)` are the only two verbs. Resolver/validator/template loader stay internal.
2. **The schema *is* the documentation** — every JSON Schema field's `description` is written as an instruction, not a type label (e.g. "Keep under 60 characters — longer titles will be shrunk by the resolver").
3. **Errors are fixes, not diagnoses** — structured, localized, actionable:
   ```json
   {"slide": 3, "primitive": "grid.items[1]", "field": "content",
    "error": "overflow",
    "detail": "Text is ~14pt too tall for the box at font size 18pt.",
    "fix": "Shorten to under ~40 characters, or drop to 2 bullet items, or split into two slides."}
   ```
4. **`validate` is cheap and separate from `render`** — no pptx write, no image render, millisecond-scale — so an agent can iterate tightly before paying render cost.
5. **`render_deck` returns a report, not just a file** — `{pptx_path, manifest, warnings, actual_layout}` — a feedback channel so the agent can reason about what happened without opening the file.
6. **Recursive primitives, recursive reasoning** — `grid.items` accepts the same primitive specs as a slide's top level; no separate "grid-item" schema.
7. **Generous defaults, minimal required fields** — e.g. `grid` needs only `items`; columns/gutter/alignment default from the template. Layout minutiae shouldn't need explicit specification in the common case.
8. **Ship a single reference doc that's both the README and the agent's in-context reference** — schema + 3-4 worked examples + the safe-font list, one file, dual-purpose.
9. **Never silently guess in ways that hide a mistake** — safe normalization (trimming whitespace, coercing types) is fine if reported back; anything that changes intent (auto-truncating text, dropping a field) is a validation error instead.

## 9. API surface

```python
from compono import render_deck, validate, Deck, Header, Text, Image, Stat, Grid, Table, Sequence, Chart, Shape
```

- **Agent path** — raw dict/JSON straight into `render_deck`/`validate` (matches tool-calling shape natively, no object construction).
- **Human path** — typed builder classes (`Deck`, `Header`, ...), pure sugar that serializes to the *identical* dict shape the agent path uses. No divergence between the two — if they ever differ, that's a bug.
- Primitive class names are the schema type strings, 1:1 (`"primitive": "header"` ↔ `Header`).
- No client objects, no session lifecycle — `render_deck`/`validate` are pure functions.
- **CLI mirrors the same two verbs** exactly, for agent frameworks that can only shell out:
  ```
  compono validate spec.json
  compono render spec.json --template fractal -o deck.pptx
  ```
- **One exception type** — `DeckValidationError`, carrying the structured list of per-field errors (the shape above). No exception hierarchy to memorize.

## 10. Repo structure

```
compono/
├── pyproject.toml            # PEP 621 packaging, no setup.py
├── README.md                 # quickstart + doubles as agent-facing reference
├── LICENSE                   # MIT
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md        # Contributor Covenant
├── CHANGELOG.md              # Keep a Changelog format
├── src/compono/
│   ├── __init__.py           # public exports ONLY
│   ├── primitives.py
│   ├── schema.py              # pydantic models -> JSON Schema
│   ├── resolver.py             # layout engine
│   ├── validator.py            # font-metric overflow checker
│   ├── render.py               # orchestrates validate -> resolve -> write pptx
│   ├── templates/default.yaml
│   ├── fonts/                  # bundled safe-font metrics
│   └── cli.py                  # console-script entry point
├── skills/compono/SKILL.md   # Claude Code / Cowork skill packaging
├── examples/                   # 3-4 worked specs; doubles as test fixtures
│   ├── minimal.json
│   ├── conference_talk.json
│   └── client_proposal.json
├── tests/
│   ├── test_schema.py
│   ├── test_resolver.py
│   ├── test_validator_overflow.py
│   ├── test_render_shape_invariant.py   # asserts every element is a real editable shape
│   └── fixtures/
└── .github/
    ├── workflows/
    │   ├── ci.yml               # lint + typecheck + test on push/PR
    │   └── release.yml           # publish to PyPI on version tag (trusted publishing/OIDC)
    └── ISSUE_TEMPLATE/
```

The `src/` layout is deliberate: it prevents tests from accidentally importing the local uncompiled folder instead of the actually-installed package, catching packaging mistakes before a real user hits them.

## 11. Distribution channels

1. **PyPI** (`pip install compono`) — primary channel, since the core is Python.
2. **Claude Code / Cowork skill** — `skills/compono/SKILL.md` (same content as the README, doubling as agent context). Installed either via a marketplace (`/plugin marketplace add <you>/<repo>` → `/plugin install compono`) or by copying the skill folder into a project's `.claude/skills/`.
3. **MCP server wrapper** (`compono-mcp`, v1.1) — exposes `render_deck`/`validate` as MCP tools for any MCP-compatible framework, not just Claude. Deferred past initial release, not a day-one requirement.
4. **No npx/JS path for v1** — deliberately deferred. An npx wrapper would either mean a parallel JS reimplementation (double maintenance) or a fragile shim shelling out to a Python install. Revisit only if real demand appears.

## 12. Open source practices checklist

- [ ] **License: MIT** — simplest, most permissive, maximizes adoption (no legal review needed to use it).
- [ ] **Semantic versioning** (MAJOR.MINOR.PATCH) + `CHANGELOG.md` in Keep a Changelog format.
- [ ] **Tests via pytest**:
  - Unit tests on the resolver and validator directly (pure functions — no rendering needed).
  - "Golden" tests: render an example spec, reopen the `.pptx` with `python-pptx`, assert real properties (shape count, real text elements, no overlaps) — not pixel-diffing.
- [ ] **CI via GitHub Actions**: lint + type-check + test workflow on every push/PR; a separate release workflow publishing to PyPI on a version tag using trusted publishing (GitHub OIDC), not a long-lived API token.
- [ ] **CONTRIBUTING.md**: dev setup (`pip install -e .[dev]`), how to run tests, code style expectations.
- [ ] **CODE_OF_CONDUCT.md** (Contributor Covenant template).
- [ ] Issue/PR templates.

## 13. Open questions (flagged, not decided)

- Direct-write JSON/YAML spec vs. an NL→spec translation layer: **resolved** — ship direct-write for v1; an NL layer, if built later, is a convenience wrapper compiling to the same JSON, never a replacement path.
- Peer-to-peer shape alignment (outside a shared container): deferred past v1.
- MCP server wrapper: deferred to v1.1.
- npx/JS distribution: deferred indefinitely, pending real demand.

## 14. Suggested build order

1. Scaffold repo structure + `pyproject.toml` + license/CI skeleton.
2. Define pydantic models for 3-4 primitives first (`header`, `text`, `grid`, `shape`) to prove the "agent never writes coordinates" claim before expanding to all 9.
3. Build the resolver's directional box model against those 3-4 primitives.
4. Build the `fonttools`-based overflow validator as a standalone pure function, unit-tested independently of rendering.
5. Wire `render_deck`/`validate` together, add the CLI.
6. Add the remaining primitives (`image`+placeholder manifest, `stat`, `table`, `sequence`, `chart`).
7. Write the `SKILL.md` (doubles as README) once the API surface is stable.
8. Add golden/invariant tests, CI, and cut a first PyPI release.