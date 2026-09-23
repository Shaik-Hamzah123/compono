# `diagram`

A node-graph flowchart — the resolver places nodes automatically and
routes edges between them, instead of hand-placing every node as a
[`shape`](shape.md) with a manual `id` plus one connector per edge.

Architecturally, a diagram's nodes are synthesized internally as
ordinary `shape` primitives, and its edges routed via the exact same
obstacle-avoiding connector routing `shape(kind="connector")` uses — so
rendering and overflow checking need zero new code, the same "reuse, not
reimplement" trick [`gantt`](gantt.md) uses on top of `table`.

## Fields

| Field | Type | Notes |
|---|---|---|
| `nodes` | `list[{id?, label, kind?, fill?}]` | Required, non-empty. In `orientation` order. `kind`/`fill` override the diagram-level `node_kind`/`node_fill` for that node only. |
| `edges` | `list[{from, to}] \| null` | Omit for an auto-connected linear chain (`nodes[0] -> nodes[1] -> ...`). `from`/`to` reference a node's `id`, or its 0-based position in `nodes` if it has none. |
| `orientation` | `"vertical" \| "horizontal"` | Default `"vertical"`. |
| `node_kind` | `"rect" \| "rounded_rect" \| "oval"` | Default `"rounded_rect"`. Default shape kind for nodes without their own `kind`. |
| `node_fill` | `str \| null` | Default fill color for nodes without their own `fill`. |

## Example: auto-connected linear chain

```json
{
  "primitive": "diagram",
  "node_fill": "#4F46E5",
  "nodes": [
    { "label": "User" },
    { "label": "Router" },
    { "label": "Retriever", "fill": "#059669" },
    { "label": "LLM" },
    { "label": "Memory", "kind": "oval", "fill": "#F59E0B" }
  ]
}
```

Omitting `edges` auto-connects nodes in order — the common case.

## Example: explicit edges (a branch or skip-ahead)

```json
{
  "primitive": "diagram",
  "orientation": "horizontal",
  "node_fill": "#8B5CF6",
  "nodes": [
    { "id": "query", "label": "Query" },
    { "id": "embed", "label": "Embed" },
    { "id": "vector-db", "label": "Vector DB", "fill": "#059669" },
    { "id": "rerank", "label": "Rerank" }
  ],
  "edges": [
    { "from": "query", "to": "embed" },
    { "from": "embed", "to": "vector-db" },
    { "from": "vector-db", "to": "rerank" },
    { "from": "query", "to": "rerank" }
  ]
}
```

For a branch or a skip-ahead edge, give `nodes` explicit `id`s and add
`edges`. An edge between non-adjacent nodes routes around whatever sits
between them — the router detours automatically. See
`examples/rag_pipeline_diagram.json` in the repo for both patterns in
full, runnable specs.

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
