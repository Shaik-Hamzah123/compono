# `header`

The slide's title region — a distinct field on `Slide` (`{header?, body}`),
not a body primitive, since a slide has at most one.

## Fields

| Field | Type | Notes |
|---|---|---|
| `title` | `str` | Required. Keep under ~60 characters — longer titles will be shrunk by the resolver. |
| `subtitle` | `str \| null` | Optional supporting line under the title. |
| `eyebrow` | `str \| null` | Optional small label above the title (e.g. a section tag or date). |
| `align` | `"left" \| "center" \| "right"` | Default `"left"`. |

## Example

```json
{
  "slides": [
    {
      "header": {
        "eyebrow": "Q1 Kickoff",
        "title": "2026 Roadmap",
        "subtitle": "Platform team"
      }
    }
  ]
}
```

A header-only slide (no `body`) gets the *entire* content area instead of
the fixed header band, so it renders as a real title/section/closing
slide — vertically centered on the page — rather than a mostly-empty page
with a short strip of text at the top.

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

## Branding

If the active template sets a `logo` (see [templates-and-fonts.md](../templates-and-fonts.md)),
a real logo picture is placed in the header's top-right corner
automatically — no schema field needed on `header` itself.
