# `table`

Renders as a real OOXML table (`p:graphicFrame`) — never an image.
Column widths auto-fit to content when a font is available to measure
with (falling back to an even split otherwise, never a crash).

## Fields

| Field | Type | Notes |
|---|---|---|
| `headers` | `list[str]` | Required, non-empty. Column headers, in order. |
| `rows` | `list[list[str]]` | Required, non-empty. Each row must have the same length as `headers`. |
| `emphasis_row` | `int \| null` | 0-based index into `rows` of a row to bold. |
| `emphasis_col` | `int \| null` | 0-based index into `headers` of a column to bold. |
| `cell_fills` | `list[{row, col, fill}] \| null` | Per-body-cell fill color overrides. |
| `merges` | `list[{row1, col1, row2, col2}] \| null` | Rectangular ranges of body cells to merge into one. |

`row`/`row1`/`row2` in `cell_fills`/`merges` are 0-based indices into
`rows` (never the header row — same convention as `emphasis_row`). `col`/
`col1`/`col2` are 0-based indices into `headers` (same convention as
`emphasis_col`).

## Basic example

```json
{ "primitive": "table", "headers": ["Quarter", "Revenue"], "rows": [["Q1", "10"], ["Q2", "14"]] }
```

## Highlighting specific cells

```json
{
  "primitive": "table",
  "headers": ["Metric", "Q1", "Q2"],
  "rows": [
    ["Revenue", "$10M", "$14M"],
    ["Churn", "4.2%", "2.1%"]
  ],
  "cell_fills": [
    { "row": 1, "col": 2, "fill": "#22C55E" }
  ]
}
```

`cell_fills` is additive to (not a replacement for) `emphasis_row`/
`emphasis_col`'s bold styling — a cell can be both bold and colored.

## Merging cells

```json
{
  "primitive": "table",
  "headers": ["Region", "Q1", "Q2"],
  "rows": [
    ["North", "10", "12"],
    ["North", "11", "13"],
    ["South", "5", "6"]
  ],
  "merges": [
    { "row1": 0, "col1": 0, "row2": 1, "col2": 0 }
  ]
}
```

Only the merge range's **top-left cell**'s text survives — every other
cell in the range is cleared automatically, so it's fine (as above) if
`rows` repeats the same value across the cells you intend to merge; you
don't need to blank them out yourself. `merges` ranges may not overlap
each other — validated at the schema level.

## Building a Gantt/timeline chart

A Gantt chart is `cell_fills` used to color a task's active span of
columns — see [`gantt`](gantt.md), which does exactly this internally.
You can build the same thing by hand with a plain `table` if you want
more control than `gantt`'s schema exposes (e.g. per-cell text inside the
span, not just a solid fill).

## Density

`review()` flags a table whose resolved row height or column width is
already cramped for its box (`table_density` category) — before any cell's
text technically overflows. Fix by reducing rows/columns, shrinking the
table's font, or splitting the data across two tables/slides.

## Using this spec

**Python:**

```python
from compono import render_deck
render_deck(spec, "deck.pptx")
```

**JS/TS:**

```ts
import { renderDeck } from "@skhamzah123/compono-js";
await renderDeck(spec, "deck.pptx");
```

Same JSON, same result — `merges` renders identically either way, even
though the two implementations get there differently under the hood
(python-pptx's `cell.merge()` vs. compono-js expressing the merge as
`colspan`/`rowspan` on the origin cell).
