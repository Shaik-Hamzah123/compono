# Primitives

## Primitive catalog

Every primitive accepts an optional `id` (needed if another primitive
references it, e.g. a connector) and an optional `notes` (speaker notes).

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
| `diagram` | `nodes` (`{id?, label, kind?, fill?}`), `edges?` (`{from, to}`), `orientation` (vertical/horizontal), `node_kind`, `node_fill` | A node-graph flowchart — the resolver places nodes automatically and routes edges between them (reusing `shape(kind="connector")`'s own obstacle-avoiding routing), instead of hand-placing every node as a `shape` with a manual `id` plus one connector per edge. See below. |

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
the manifest EMU rect — no re-layout needed, and the deck-building agent
itself never needs image-generation capability.


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

Omitting `edges` auto-connects nodes in order (a linear chain) — the
common case. For a branch or a skip-ahead edge, give `nodes` explicit
`id`s and add `edges: [{"from": "...", "to": "..."}]`; an edge between
non-adjacent nodes routes around whatever sits between them, the same
obstacle-avoiding routing `shape(kind="connector")` already uses. See
`examples/rag_pipeline_diagram.json` for both a linear chain and an
explicit-edges branch.

See `examples/full_catalog.json` for a complete, runnable spec (also used
as a test fixture).


