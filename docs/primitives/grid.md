# `grid`

The one primitive doing true 2D layout — everything else stacks
top-to-bottom, sharing height equally. `items` can be any primitive,
including other grids.

## Fields

| Field | Type | Notes |
|---|---|---|
| `items` | `list[PrimitiveSpec]` | Required. Nested primitive specs, in the same shape as a slide's top-level `body`. |
| `columns` | `int \| "auto"` | Default `"auto"` — infers from item count. |
| `direction` | `"row" \| "column"` | Default `"row"`. Main-axis direction items are laid out along. |
| `align` | `"start" \| "center" \| "end" \| "stretch"` | Default `"stretch"`. Cross-axis alignment. |
| `justify` | `"start" \| "center" \| "end" \| "space-between"` | Default `"start"`. Main-axis alignment/distribution. |

## Example: 2-column comparison with a connector

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

## Example: nested grids (a 2x2 card layout)

```json
{
  "primitive": "grid",
  "columns": 2,
  "items": [
    { "primitive": "stat", "value": "1", "label": "one" },
    { "primitive": "stat", "value": "2", "label": "two" },
    {
      "primitive": "grid",
      "columns": 1,
      "items": [
        { "primitive": "stat", "value": "3a", "label": "three-a" },
        { "primitive": "stat", "value": "3b", "label": "three-b" }
      ]
    },
    { "primitive": "stat", "value": "4", "label": "four" }
  ]
}
```

A `grid` has no visual of its own — only its flattened children render.
`review()` treats a lone top-level grid with more than one child as a
deliberate, already-full layout (a card grid, a stat row), never flagged
as sparse whitespace even though it's the only item in `body`.

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
