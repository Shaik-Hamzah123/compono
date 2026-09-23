# `chart`

A real, editable native chart with live data — never a picture of a
chart.

## Fields

| Field | Type | Notes |
|---|---|---|
| `chart_type` | `"bar" \| "line" \| "pie"` | Required. Deliberately scoped to these three — not an exhaustive chart-type catalog. |
| `categories` | `list[str]` | Required. Category labels along the axis (or pie slice labels). |
| `series` | `list[{name, values}]` | Required. One or more data series; `values` must have one entry per category. A pie chart must have exactly one series. |

## Example: bar chart

```json
{
  "primitive": "chart",
  "chart_type": "bar",
  "categories": ["Q1", "Q2", "Q3", "Q4"],
  "series": [
    { "name": "Revenue", "values": [10, 14, 16, 21] },
    { "name": "Costs", "values": [7, 8, 9, 11] }
  ]
}
```

## Example: pie chart

```json
{
  "primitive": "chart",
  "chart_type": "pie",
  "categories": ["North America", "EMEA", "APAC"],
  "series": [{ "name": "Revenue share", "values": [52, 31, 17] }]
}
```

Axis/legend/data-label text picks up the active template's `font_family`
automatically. There is no chart-color theming from `template.primary_color`/
`accent_color` yet (tracked in NEXT-STEPS.md) — chart series use
PowerPoint's own default palette regardless of the active template.

For a Gantt/timeline chart, `chart_type` has no dedicated type — see
[`gantt`](gantt.md), built on `table` instead.

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
