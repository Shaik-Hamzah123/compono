# `image`

A real embedded picture, or a first-class placeholder for one you don't
have yet.

## Fields

| Field | Type | Notes |
|---|---|---|
| `src` | `str \| null` | Path or URL to the image. Omit when `placeholder: true`. |
| `placeholder` | `bool` | Default `false`. See below. |
| `caption` | `str \| null` | Shown on placeholders; also usable as alt text on a real image. |
| `fit` | `"cover" \| "contain"` | Default `"contain"`. `"contain"` preserves aspect ratio within the box; `"cover"` fills the box exactly (may crop). |

Requires either `src` or `placeholder: true` — validated at the schema
level, not left to fail at render time.

## Example: a real image

```json
{ "primitive": "image", "src": "diagrams/architecture.png", "fit": "contain", "caption": "System architecture" }
```

## Example: a placeholder

```json
{ "primitive": "image", "placeholder": true, "caption": "Team photo goes here" }
```

Set `"placeholder": true` instead of `src` when you don't have a real
image yet. It renders as an intentional design element — dashed border,
centered caption — never a blank gap or a broken-image icon. `render_deck`'s
`RenderReport.manifest` gets one entry per placeholder:

```json
{ "slide": 2, "primitive": "photo", "rect": { "x": 685800, "y": 1143000, "w": 4572000, "h": 2743200 }, "caption": "Team photo goes here" }
```

A later pass (image search/generation/human upload) can fill each
reserved rect directly from the manifest's EMU rect — no re-layout
needed, and the deck-building agent itself never needs image-generation
capability just to build the deck's structure.

`review()` flags a real image (not a placeholder) whose aspect ratio
diverges sharply from its resolved box under the chosen `fit` — a likely
bad crop (`cover`) or large empty bars (`contain`).

## Using this spec

Reading `report.manifest`/`report.pptx_path` (Python) or
`report.manifest`/`report.pptxPath` (JS/TS) is how a later pass locates
each placeholder's reserved rect:

**Python:**

```python
from compono import render_deck
report = render_deck(spec, "deck.pptx")
for entry in report.manifest:
    print(entry["slide"], entry["rect"], entry["caption"])
```

**JS/TS:**

```ts
import { renderDeck } from "@skhamzah123/compono-js";
const report = await renderDeck(spec, "deck.pptx");
for (const entry of report.manifest) {
  console.log(entry.slide, entry.rect, entry.caption);
}
```
