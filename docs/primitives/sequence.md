# `sequence`

A row (or column) of connected step boxes — process/timeline diagrams.
Compiles internally to shapes, text, and connectors, not a bespoke
render path.

## Fields

| Field | Type | Notes |
|---|---|---|
| `steps` | `list[{label, description?}]` | Required, non-empty. Ordered steps, rendered left-to-right or top-to-bottom. |
| `orientation` | `"horizontal" \| "vertical"` | Default `"horizontal"`. |

## Example

```json
{
  "primitive": "sequence",
  "orientation": "horizontal",
  "steps": [
    { "label": "Discover", "description": "Understand the problem" },
    { "label": "Design", "description": "Sketch options" },
    { "label": "Ship", "description": "Release to users" }
  ]
}
```

Steps connect edge-to-edge through the gutter between them — never
through box centers, which would draw the connector across a step's own
label text. If the active template sets `colors.accent`, each step's
shape fills with that color (see [templates-and-fonts.md](../templates-and-fonts.md));
otherwise it uses PowerPoint's own default shape fill.

For a step sequence with real branching (not a straight line) or a
graph of many-to-many connections, use [`diagram`](diagram.md) instead —
`sequence` is specifically the single-line-of-steps case.
