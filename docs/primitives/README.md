# Primitives

Every slide's `body` (and an optional `header`) is built from primitives —
typed, declarative JSON objects. The resolver computes real EMU positions
from them; you never write raw `x`/`y`/`w`/`h` coordinates. Every primitive
accepts an optional `id` (needed if another primitive references it, e.g. a
connector) and an optional `notes` (speaker notes).

There is no separate "title slide" / "content slide" / "thank-you slide"
taxonomy — a slide is just `{header?, body: [...]}`, and genre/density/tone
decisions (what kind of slide this is, how much goes on it) are yours to
make by composing primitives, not a schema type to pick.

## Index

| Primitive | Purpose |
|---|---|
| [`header`](header.md) | Slide title region. |
| [`text`](text.md) | Prose or a bullet list. |
| [`image`](image.md) | A real picture, or a first-class placeholder. |
| [`stat`](stat.md) | A headline number with a label. |
| [`grid`](grid.md) | The one primitive with true 2D layout — items can be any other primitive, including nested grids. |
| [`table`](table.md) | A real OOXML table, with per-cell fills and merges. |
| [`sequence`](sequence.md) | A row/column of connected step boxes — process/timeline diagrams. |
| [`chart`](chart.md) | A real, editable native chart (bar/line/pie). |
| [`shape`](shape.md) | A freeform shape, optionally with text, or a connector between two other primitives. |
| [`diagram`](diagram.md) | A node-graph flowchart — nodes placed and edges routed automatically. |
| [`gantt`](gantt.md) | A Gantt/timeline chart, built internally on `table`. |

Every schema field's description is written as an instruction (e.g. "Keep
under ~60 characters — longer titles will be shrunk by the resolver"), not
a bare type label — call `Header.model_json_schema()` (or any primitive
class) to get the full JSON Schema with these descriptions inline.

Every page's spec is plain JSON — each ends with a "Using this spec"
section showing the exact same object passed to Python's `render_deck`
and JS/TS's `renderDeck` (`@skhamzah123/compono-js`), since the two
implementations share one primitive-JSON contract.

See `examples/full_catalog.json` in the repo for a complete, runnable spec
touching every primitive (also used as a test fixture).
