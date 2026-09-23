# `shape`

A freeform shape, optionally with text inside — or a connector between
two other primitives by `id`.

## Fields

| Field | Type | Notes |
|---|---|---|
| `kind` | `"rect" \| "rounded_rect" \| "oval" \| "line" \| "arrow" \| "connector"` | Required. |
| `fill` | `str \| null` | Fill color, e.g. a hex string. Omit for no fill / template default. |
| `fill_style` | `"solid" \| "gradient"` | Default `"solid"`. `"gradient"` blends a lighter tint of `fill` top to bottom — explicit, not automatic. |
| `border` | `str \| null` | Border color. Omit for no border. |
| `connects` | `{from_id, to_id} \| null` | Only valid when `kind="connector"`. |
| `text` | `{content, align, valign, autofit, color?} \| null` | Optional text rendered inside the shape. |

## Example: a filled card with text

```json
{
  "id": "card-a",
  "primitive": "shape",
  "kind": "rounded_rect",
  "fill": "#4F46E5",
  "text": { "content": "Card A", "align": "center", "valign": "middle" }
}
```

## Example: a connector between two shapes

```json
{
  "primitive": "shape",
  "kind": "connector",
  "connects": { "from_id": "card-a", "to_id": "card-b" }
}
```

A connector routes around any box in between automatically, ends in an
arrowhead, and stops just short of the shape rather than touching it —
the same obstacle-avoiding routing [`diagram`](diagram.md)'s edges reuse.
A connector shape draws nothing at its own position; it consumes no
layout slot, so it never needs a `grid`/stack slot of its own alongside
the shapes it connects.

## Contrast

Set `text.color` explicitly against a dark `fill` — `review()`'s contrast
check (WCAG-style ratio) can only evaluate legibility when both `fill`
and `text.color` are set; it never guesses a color that wasn't provided.

## When to reach for `diagram` instead

Hand-placing several shapes plus one connector per edge is exactly what
[`diagram`](diagram.md) automates — reach for it once you have more than
a couple of connected nodes.
