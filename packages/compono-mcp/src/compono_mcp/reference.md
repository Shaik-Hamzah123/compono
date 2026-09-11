<!--
  Served verbatim as the `compono://reference` MCP resource (see server.py).
  Kept in sync with the repo root skills/compono/SKILL.md and README.md —
  same convention already used between those two files. Update all three
  together when the API surface changes.
-->

# compono

**Agent-oriented, code-based PPTX generation.** Describe a deck as typed
primitives — an LLM agent never writes raw coordinates or touches OOXML.

compono lets you describe a slide deck as data — headers, bullet text,
stats, tables, charts, images, process sequences, shapes — and get back a
real, editable `.pptx` file. You never write raw `x`/`y`/`w`/`h`
coordinates: a constraint-based layout resolver computes every position
from a small set of typed primitives.

Every rendered element is a genuine, editable native shape (`p:sp`, `p:pic`,
`p:graphicFrame`) — never a flattened image or embedded video. Opening the
result in PowerPoint and dragging a box around works; it's a real object,
not a picture of one.

You are receiving this document through the `compono-mcp` MCP server's
`compono://reference` resource — use its `validate_deck`/`review_deck`/
`render_deck_tool` tools as described below.

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

Through this MCP server, call the `validate` and `render_deck` tools with
the identical `spec` shape instead of importing Python directly.

## Core concepts

- **Two required verbs, one optional third.** `render_deck(spec, output_path)`
  and `validate(spec)` are the core loop — `validate` is cheap, no pptx
  write, millisecond-scale, so iterate on a spec before paying render cost.
  `review(spec)` is a separate, never-blocking third verb for design-quality
  suggestions (contrast, whitespace, image fit) — pair it with the other
  two, it doesn't replace either.
- **A spec is plain data.** A raw `dict`/JSON (what tool-calling naturally
  produces) is all you need — pass it straight to `render_deck`/`validate`.
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

## Tools (via this MCP server)

| Tool | Input | Output | Notes |
|---|---|---|---|
| `validate_deck` | `spec: object` | `{valid, errors, warnings}` | No file write. Never errors out on malformed input — `valid: false` with structured errors instead. |
| `review_deck` | `spec: object` | `{suggestions, warnings}` | Design-quality suggestions (contrast, whitespace, image fit, font-size proximity to overflow) — never blocking, no valid/invalid, `suggestions` may be empty. Complements `validate_deck`, doesn't replace it. |
| `render_deck_tool` | `spec: object, output_path: string` | `{pptx_path, manifest, warnings}` on success, or `{valid: false, errors}` on failure | Writes a real `.pptx` at `output_path` on the machine running this server. |

A `spec` (a `Deck`) is `{template?: str, slides: [Slide, ...]}`. A `Slide` is
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
| `shape` | `kind` (rect/rounded_rect/oval/line/arrow/connector), `fill`, `fill_style` (solid default, or gradient), `border`, `connects?`, `text?` (`content`, `align`, `valign`, `autofit`, `color?`) | Freeform shape, optionally with text inside, or a connector between two other primitives by `id`. Set `text.color` explicitly against a dark `fill` — `review_deck`'s contrast check can only evaluate it when both are given. |

### Image placeholders

Set `"placeholder": true` (with an optional `caption`) instead of `src` when
you don't have a real image yet. It renders as an intentional design
element — dashed border, centered caption — and `render_deck`'s response
gets one manifest entry per placeholder:
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

## Fonts and templates

A deck's typeface comes from its **template**, not a per-primitive field —
`Deck.template` (default `"default"`) names a config file under
`src/compono/templates/`. Two ship today: `default` (Calibri), `modern`
(Georgia). An unknown name is a structured `unknown_template` error.

A `font_family` is just a name written into the file — PowerPoint resolves
it against fonts installed on whoever opens the deck; compono does not
embed font files. If asked for a font that isn't `default`/`modern`, there
is no schema field for it — either fall back to an existing template, or
(with filesystem access to this repo) add a new `templates/<name>.yaml`.

## Fonts and overflow validation

Overflow checking reads real glyph advance widths via `fonttools` — no
rendering required. As of this release, no font is bundled yet; validation
falls back to a system font if one is found, and is skipped — not faked —
with a warning if none is available. This is independent of `font_family`
— overflow metrics don't yet reflect the template's chosen typeface.
