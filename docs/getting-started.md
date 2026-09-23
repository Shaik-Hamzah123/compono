# Getting started

## Install

```bash
pip install compono
# or
uv add compono
```

For local development, see `../CONTRIBUTING.md`.

## Quickstart

```python
from compono import render_deck

spec = {
    "slides": [
        {
            "header": {"title": "Q3 Results", "subtitle": "Engineering team"},
            "body": [
                {
                    "primitive": "text",
                    "mode": "bullets",
                    "content": [
                        "Shipped the new layout resolver",
                        "Cut render time by 40%",
                        "Zero overflow bugs in production",
                    ],
                    "emphasis_indices": [1],
                }
            ],
        }
    ]
}

report = render_deck(spec, "deck.pptx")
print(report.pptx_path, report.warnings)
```

Or from the command line:

```bash
compono validate spec.json
compono render spec.json -o deck.pptx
```


## Core concepts

- **Two required verbs, one optional third.** `render_deck(spec, output_path)`
  and `validate(spec)` are the core loop — `validate` is cheap, no pptx
  write, millisecond-scale, so an agent can iterate on a spec before paying
  render cost. `review(spec)` is a separate, never-blocking third verb for
  design-quality suggestions (contrast, whitespace, image fit, style) — pair it
  with the other two, it doesn't replace either.
- **A spec is plain data.** Either a raw `dict`/JSON (what an agent's
  tool-calling naturally produces) or the typed builder classes
  (`Deck`, `Header`, `Text`, ...) — both serialize to the identical shape.
  There's no divergence between the two paths.
- **You never write coordinates.** Every primitive claims space in a slide;
  the resolver (a CSS-flexbox-style directional box model) computes real
  EMU positions. `grid` is the one primitive that does true 2D
  row/column math.
- **Errors are fixes, not diagnoses.** Every validation/render failure is
  `{slide, primitive, field, error, detail, fix}` — see
  [Error shape](api-reference.md#error-shape) below.
- **render_deck returns a report, not just a file** —
  `{pptx_path, manifest, warnings, actual_layout}` — so an agent can reason
  about what happened without reopening the file.


See [API reference](api-reference.md) for the full verb signatures and error
shape, [Primitives](primitives/README.md) for the full catalog, and
[Templates and fonts](templates-and-fonts.md) for `template`/`font_family`.
