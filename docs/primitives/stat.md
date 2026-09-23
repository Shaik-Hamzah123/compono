# `stat`

A headline number with a label — renders large, meant to draw the eye.

## Fields

| Field | Type | Notes |
|---|---|---|
| `value` | `str` | The headline number/value, e.g. `"42%"`. Keep short — it renders large. |
| `label` | `str` | Short label under the value, e.g. `"YoY growth"`. |
| `trend` | `str \| null` | Optional trend indicator, e.g. `"+12% vs last quarter"`. |

## Example

```json
{ "primitive": "stat", "value": "42%", "label": "YoY growth", "trend": "+12% vs Q2" }
```

## Common pattern: a stat row

Three stats side by side in a `grid`:

```json
{
  "primitive": "grid",
  "columns": 3,
  "items": [
    { "primitive": "stat", "value": "2,000", "label": "Employees trained" },
    { "primitive": "stat", "value": "94%", "label": "Completion rate" },
    { "primitive": "stat", "value": "4.8/5", "label": "Satisfaction" }
  ]
}
```

A single `stat` alone in a tall body (no supporting content alongside it)
is flagged by `review()`'s `whitespace` check as likely more empty space
than the content needs — pair it with other content in a `grid`, or use a
header-only slide if a lone big number really is the whole point.

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
