---
name: compono
description: Build PowerPoint (.pptx) decks or Word (.docx) documents as data — typed primitives (header, text, image, stat, grid, table, sequence, chart, shape for pptx; heading, paragraph, bullet_list, table, image, chart for docx) rendered via a constraint-based layout resolver (pptx) or Word's own flow (docx), with real editable shapes (never flattened images/video, except docx charts — see below). Use when asked to create, generate, or edit a slide deck/presentation or a Word document programmatically.
---

# compono

**Agent-oriented, code-based PPTX/DOCX generation.** Describe a deck or
document as typed primitives — an LLM agent never writes raw coordinates
or touches OOXML.

compono lets you describe a slide deck as data — headers, bullet text,
stats, tables, charts, images, process sequences, shapes — and get back a
real, editable `.pptx` file. You never write raw `x`/`y`/`w`/`h`
coordinates: a constraint-based layout resolver computes every position
from a small set of typed primitives.

Every rendered element is a genuine, editable native shape (`p:sp`, `p:pic`,
`p:graphicFrame`) — never a flattened image or embedded video. Opening the
result in PowerPoint and dragging a box around works; it's a real object,
not a picture of one.

compono also generates `.docx` documents — its second output format, for
linear content (proposals, reports) rather than slides, with its own
smaller primitive set. See the "DOCX" section below.

This is the packaged, agent-facing version of the project's README — see
the repo root `README.md` for the human-facing copy (kept in sync).

## Quickstart

```python
from compono import render_deck

spec = {
    "slides": [
        {
            "header": {"title": "Q3 Results", "subtitle": "Engineering team"},
            "body": [
                {
                    "primitive": "text",
                    "mode": "bullets",
                    "content": [
                        "Shipped the new layout resolver",
                        "Cut render time by 40%",
                        "Zero overflow bugs in production",
                    ],
                    "emphasis_indices": [1],
                }
            ],
        }
    ]
}

report = render_deck(spec, "deck.pptx")
print(report.pptx_path, report.warnings)
```

Or from the command line:

```bash
compono validate spec.json
compono render spec.json -o deck.pptx
```

## Core concepts

- **Two required verbs, one optional third.** `render_deck(spec, output_path)`
  and `validate(spec)` are the core loop — `validate` is cheap, no pptx
  write, millisecond-scale, so iterate on a spec before paying render cost.
  `review(spec)` is a separate, never-blocking third verb for design-quality
  suggestions (contrast, whitespace, image fit, style) — pair it with the other
  two, it doesn't replace either.
- **A spec is plain data.** A raw `dict`/JSON (what tool-calling naturally
  produces) is all you need — pass it straight to `render_deck`/`validate`.
  Typed builder classes (`Deck`, `Header`, `Text`, ...) exist for human
  code and serialize to the identical shape.
- **You never write coordinates.** Every primitive claims space in a slide;
  the resolver (a CSS-flexbox-style directional box model) computes real
  EMU positions. `grid` is the one primitive that does true 2D
  row/column math.
- **Errors are fixes, not diagnoses.** Every validation/render failure is
  `{slide, primitive, field, error, detail, fix}` — see
  [Error shape](#error-shape) below. Act on `fix`, don't just retry blindly.
- **render_deck returns a report, not just a file** —
  `{pptx_path, manifest, warnings, actual_layout}` — reason about what
  happened without reopening the file.

## API reference

```python
from compono import (
    render_deck, validate, review, reference,
    Deck, Slide, Header, Text, Image, Stat, Grid, Table, Sequence, Chart, Shape,
    DeckValidationError,
)
```

| Symbol | Signature | Notes |
|---|---|---|
| `render_deck` | `render_deck(spec, output_path, *, template=None) -> RenderReport` | Validates, resolves layout, writes a real `.pptx`. Raises `DeckValidationError` on any error — nothing is written on failure. |
| `validate` | `validate(spec, *, template=None) -> ValidationReport` | Schema + layout + text-overflow checks. No file I/O. Never raises — check `.valid`/`.errors`. |
| `review` | `review(spec, *, template=None) -> ReviewReport` | Design-quality suggestions (contrast, whitespace, image fit, font-size proximity to overflow, style). Never blocking — only `.suggestions` (possibly empty) and `.warnings`. Complements `validate`, doesn't replace it. |
| `reference` | `reference() -> str` | The full agent-facing reference doc, packaged inside `compono` itself — also `compono reference` on the CLI. |
| `DeckValidationError` | `exc.errors -> list[dict]` | The one exception type. Carries the structured error list below. |

A `Deck` is `{template?: str, slides: [Slide, ...]}`. A `Slide` is
`{header?: Header, body: [primitive, ...], notes?: str}`. `body` (and
`grid.items`) accept any primitive, keyed by its `"primitive"` field.

**Prefer `validate` before `render_deck` when iterating** — it's cheap and
gives you the same structured errors without writing a file.

### Error shape

```json
{
  "slide": 3,
  "primitive": "grid.items[1]",
  "field": "content",
  "error": "overflow",
  "detail": "Text is ~14pt too tall for the box at font size 18pt (6 lines).",
  "fix": "Shorten the text, reduce bullet/line count, or split into two slides."
}
```

### The feedback loop in practice

This is the actual point of `validate()` being cheap and separate from
`render_deck()` — an agent runs it first, gets back something it can act
on, and only pays render cost once the spec is clean. No new API for
this, just the two verbs above used the way they're meant to be:

**1st pass** — a real spec, sharing a slide with two stats, packs in
three long bullets:

```python
spec = {
    "slides": [{
        "header": {"title": "Q3 Roadmap"},
        "body": [
            {"primitive": "text", "mode": "bullets", "content": [
                "Ship onboarding redesign across web, iOS, and Android, "
                "with full localization support for every launch market",
                "Migrate billing to the new usage-based pricing engine, "
                "including proration, credits, and dunning retries",
                "Roll out SSO and SCIM provisioning for enterprise "
                "customers across every supported identity provider",
            ]},
            {"primitive": "stat", "value": "42%", "label": "YoY revenue growth"},
            {"primitive": "stat", "value": "99.97%", "label": "platform uptime"},
        ],
    }]
}
validate(spec).errors
```

```json
[{
  "slide": 0, "primitive": "body[0]", "field": "content", "error": "overflow",
  "detail": "Text is ~22pt too tall for the box at font size 18pt (6 lines).",
  "fix": "Shorten the text, reduce bullet/line count, or split into two slides."
}]
```

**2nd pass** — the agent applies the `fix` verbatim (shortens the
bullets), nothing else about the spec changes:

```python
spec["slides"][0]["body"][0]["content"] = [
    "Ship onboarding redesign across web, iOS, and Android",
    "Migrate billing to usage-based pricing",
    "Roll out SSO and SCIM for enterprise customers",
]
validate(spec).valid  # True
render_deck(spec, "q3-roadmap.pptx")  # now succeeds
```

`render_deck` would have raised `DeckValidationError` on the 1st-pass
spec instead of writing a broken file — the loop above is what an agent
actually runs, not a hypothetical.

### Design review (`review()`)

`validate()` answers "will this render without breaking." `review()`
answers "does this look good" — a separate, never-blocking verb: no
`.valid`, just `.suggestions` (possibly empty) and `.warnings`. Pair the
two — `review()` assumes a structurally valid deck.

```python
spec = {
    "slides": [{
        "header": {"title": "Architecture"},
        "body": [{
            "primitive": "shape", "kind": "rounded_rect", "fill": "#111827",
            "text": {"content": "Gateway", "color": "#1F2937"},
        }],
    }]
}
review(spec).suggestions
```

```json
[{
  "slide": 0, "primitive": "body[0]", "field": "text.color", "category": "contrast",
  "detail": "text.color '#1F2937' against fill '#111827' has a contrast ratio of ~1.2:1 (WCAG AA wants 4.5:1).",
  "fix": "Pick a lighter/darker text.color for more contrast against fill, or use a lighter/darker fill."
}]
```

Four categories today:

| Category | Checks | Requires |
|---|---|---|
| `contrast` | WCAG-style ratio between `shape.text.color` and `shape.fill` | Both set explicitly — never guesses a color that wasn't given. |
| `whitespace` | A body of exactly one primitive left alone in a tall box | Nothing — but **never fires on a header-only slide** (no `body` at all). A title/closing slide being sparse is the deliberate pattern that fix shipped in 0.1.1; there's nothing to be "too empty" relative to. |
| `image_fit` | A real image (not a placeholder) whose aspect ratio diverges a lot from its box, under `fit="cover"` (crops) or `fit="contain"` (large empty bars) | A real `src`, not a placeholder — nothing to measure otherwise. |
| `font_size` | Text using most of its box's height without (yet) overflowing | A font (same fallback as overflow validation) — skipped, not faked, otherwise. |
| `style` | An em dash (—) in any text-bearing field | Nothing — purely a text-content scan, runs even when overflow/font-size checks are skipped for lack of a font. Narrow by design: just the one character, not a broader "AI writing tell" pass. |

## Primitive catalog

Every primitive accepts an optional `id` (needed if another primitive
references it, e.g. a connector) and an optional `notes` (speaker notes).
There is no separate "title slide" / "content slide" / "thank-you slide"
taxonomy — a slide is just `{header?, body: [...]}`, and genre/density/tone
decisions (what kind of slide this is, how much goes on it) are yours to
make by composing primitives, not a schema type to pick.

| Primitive | Key fields | Purpose |
|---|---|---|
| `header` | `title`, `subtitle?`, `eyebrow?`, `align` | Slide title region. |
| `text` | `mode` (paragraph/bullets), `content`, `columns?`, `emphasis_indices?` | Prose or bullet list. |
| `image` | `src?`, `placeholder`, `caption?`, `fit` (cover/contain) | A real picture, or a first-class placeholder — see below. |
| `stat` | `value`, `label`, `trend?` | A headline number with a label. |
| `grid` | `items`, `columns`, `direction`, `align`, `justify` | The one primitive with true 2D layout. Items can be any primitive, including nested grids. |
| `table` | `headers`, `rows`, `emphasis_row?`, `emphasis_col?` | Renders as a real OOXML table (`p:graphicFrame`), not an image. |
| `sequence` | `steps` (`{label, description?}`), `orientation` | A row/column of connected step boxes — process/timeline diagrams. |
| `chart` | `chart_type` (bar/line/pie), `categories`, `series` | A real, editable native chart with live data — not a picture of a chart. |
| `shape` | `kind` (rect/rounded_rect/oval/line/arrow/connector), `fill`, `fill_style` (solid default, or gradient), `border`, `connects?`, `text?` (`content`, `align`, `valign`, `autofit`, `color?`) | Freeform shape, optionally with text inside, or a connector between two other primitives by `id` (routes around any box in between automatically, ends in an arrowhead, and stops just short of the shape rather than touching it). Set `text.color` explicitly against a dark `fill` — `review()`'s contrast check can only evaluate it when both are given. |
| `diagram` | `nodes` (`{id?, label, kind?, fill?}`), `edges?` (`{from, to}`), `orientation` (vertical/horizontal), `node_kind`, `node_fill` | A node-graph flowchart — nodes are placed automatically and edges routed between them (reusing `shape(kind="connector")`'s own obstacle-avoiding routing). Omit `edges` for an auto-connected linear chain; give nodes explicit `id`s and add `edges` for a branch or a skip-ahead edge. |

Every schema field's description is written as an instruction (e.g. "Keep
under ~60 characters — longer titles will be shrunk by the resolver"), not
a bare type label — call `Header.model_json_schema()` (or any primitive
class) to get the full JSON Schema with these descriptions inline.

### Image placeholders

Set `"placeholder": true` (with an optional `caption`) instead of `src` when
you don't have a real image yet. It renders as an intentional design
element — dashed border, centered caption — and `render_deck`'s
`RenderReport.manifest` gets one entry per placeholder:
`{slide, primitive, rect: {x, y, w, h}, caption}`. A later pass (image
search/generation/human upload) can fill each reserved rect directly from
the manifest EMU rect — no re-layout needed, and you don't need
image-generation capability just to build the deck.

## Worked examples

### 1. Title slide

```json
{
  "slides": [
    { "header": { "title": "2026 Roadmap", "subtitle": "Platform team", "eyebrow": "Q1 Kickoff" } }
  ]
}
```

### 2. Two-column comparison with a connector

```json
{
  "slides": [{
    "header": { "title": "Before vs. After" },
    "body": [
      {
        "primitive": "grid",
        "columns": 2,
        "items": [
          { "id": "before", "primitive": "shape", "kind": "rounded_rect", "fill": "#EF4444",
            "text": { "content": "Manual layout" } },
          { "id": "after", "primitive": "shape", "kind": "rounded_rect", "fill": "#10B981",
            "text": { "content": "Resolver-computed layout" } }
        ]
      },
      { "primitive": "shape", "kind": "connector", "connects": { "from_id": "before", "to_id": "after" } }
    ]
  }]
}
```

### 3. Stat + table + chart dashboard

```json
{
  "slides": [{
    "header": { "title": "Q3 Metrics" },
    "body": [
      { "primitive": "stat", "value": "42%", "label": "YoY growth", "trend": "+12% vs Q2" },
      { "primitive": "table", "headers": ["Quarter", "Revenue"], "rows": [["Q1", "10"], ["Q2", "14"]] },
      { "primitive": "chart", "chart_type": "bar", "categories": ["Q1", "Q2"],
        "series": [{ "name": "Revenue", "values": [10, 14] }] }
    ]
  }]
}
```

### 4. Process sequence

```json
{
  "slides": [{
    "header": { "title": "Our Process" },
    "body": [{
      "primitive": "sequence",
      "orientation": "horizontal",
      "steps": [
        { "label": "Discover", "description": "Understand the problem" },
        { "label": "Design", "description": "Sketch options" },
        { "label": "Ship", "description": "Release to users" }
      ]
    }]
  }]
}
```

### 5. Diagram (auto-connected node graph)

```json
{
  "slides": [{
    "header": { "title": "RAG Pipeline" },
    "body": [{
      "primitive": "diagram",
      "node_fill": "#4F46E5",
      "nodes": [
        { "label": "User" },
        { "label": "Router" },
        { "label": "Retriever", "fill": "#059669" },
        { "label": "LLM" },
        { "label": "Memory", "kind": "oval", "fill": "#F59E0B" }
      ]
    }]
  }]
}
```

Omitting `edges` auto-connects nodes in order (a linear chain). For a
branch or a skip-ahead edge, give `nodes` explicit `id`s and add
`edges: [{"from": "...", "to": "..."}]` — see
`examples/rag_pipeline_diagram.json` for both.

See `examples/full_catalog.json` in the repo for a complete, runnable spec.

## Fonts and templates

A deck's typeface comes from its **template**, not a per-primitive field —
`Deck.template` (default `"default"`) names a config file under
`src/compono/templates/`. compono currently includes these templates
(more can be added — see below): `default` (Calibri), `modern`
(Georgia), `classic` (Times New Roman), and `clean` (Arial).
`{"template": "modern", "slides": [...]}` is a real, visible choice.
An unknown name is a structured `unknown_template` error, not a crash.

**If asked for a font that isn't already bundled:** there is no
schema field to smuggle an arbitrary typeface through a render call —
fonts live in a reviewed template file, not per-request data.
- With filesystem access to this repo: add a new
  `src/compono/templates/<name>.yaml` (copy `default.yaml`'s page/margin
  values, set `font_family`), then use `{"template": "<name>"}`.
- With only `render_deck`/`validate` as tools (e.g. over MCP, no
  filesystem access): you cannot invent a template on the fly. Tell the
  user the font isn't available, list what is, and fall back or ask a
  human to add the template file.

Overflow checking (`validate`'s layout errors, and the "shrink text on
overflow" behavior it protects against) reads real glyph advance widths via
`fonttools` — no rendering required. compono bundles **Open Sans** (SIL OFL
1.1, `src/compono/fonts/`) for this: every stock template's `font_family`
resolves to it when measuring overflow, as a glyph-metrics approximation.
This bundled font is never written into the output file — the deck itself
always renders in whatever `font_family` the template names (a plain OOXML
font-name reference, resolved by the viewer's own installed fonts). Chart
axis/legend/data-label text also picks up `template.font_family`. Table and
sequence overflow are checked per-cell/per-step against each cell's own
sub-rect, not as one combined block of text against the whole box — a
single overlong cell trips a structured error even if the rest of the
table/sequence is short.

## Inspire

`scan_deck`/`aggregate`/`write_skill` (also `compono.inspire`) scan a
folder of `.pptx` files someone already likes into a style
profile/skill — palette, fonts, spacing, grid patterns — **never**
literal text or images. Aggregating across multiple decks separates a
recurring practice (seen in most decks) from a one-off quirk; low-
confidence grid patterns are omitted rather than guessed. The result is
a `skills/inspire-<name>/{SKILL.md, profile.json}` folder an agent can
read before generating a *new* deck, so it adopts similar practices
loosely rather than copying any source deck literally. See
`docs/inspire.md` for the full write-up.

## DOCX

`render_docx`/`validate_docx` (also `compono.docx`) generate `.docx`
documents — compono's second output format, for linear content (proposals,
reports) rather than slides. It has its own smaller primitive set
(`heading`, `paragraph`, `bullet_list`, `numbered_list`, `table`, `image`,
`chart`, `page_break`) since a document flows top-to-bottom on its own —
no resolver/EMU layout math needed. Every primitive renders as a real,
editable python-docx object **except `chart`**, which is rasterized via
matplotlib and embedded as a picture (`python-docx` has no native chart
API, unlike `python-pptx`) — the one deliberate, documented exception to
compono's usual "always a real object" preference. See `docs/docx.md` for
the full write-up.

## CLI

```bash
compono validate spec.json
compono review spec.json
compono render spec.json --template modern -o deck.pptx
compono reference
compono inspire scan decks/ -o skills/inspire-myteam/
compono docx validate doc_spec.json
compono docx render doc_spec.json -o report.docx
```

Mirrors `validate`/`review`/`render_deck`/`inspire`/`render_docx` exactly —
useful when you can only shell out rather than import Python. `reference`
prints this same document to stdout — useful if this skill isn't loaded
and there's no MCP connection either.
