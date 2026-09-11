# API reference

## API reference

```python
from compono import (
    render_deck, validate, review, reference,
    Deck, Slide, Header, Text, Image, Stat, Grid, Table, Sequence, Chart, Shape,
    DeckValidationError,
)
```

| Symbol | Signature | Notes |
|---|---|---|
| `render_deck` | `render_deck(spec, output_path, *, template=None) -> RenderReport` | Validates, resolves layout, writes a real `.pptx`. Raises `DeckValidationError` on any error — nothing is written on failure. |
| `validate` | `validate(spec, *, template=None) -> ValidationReport` | Schema + layout + text-overflow checks. No file I/O. Never raises — check `.valid`/`.errors`. |
| `review` | `review(spec, *, template=None) -> ReviewReport` | Design-quality suggestions (contrast, whitespace, image fit, font-size proximity to overflow). Never blocking — no valid/invalid, only `.suggestions` (possibly empty) and `.warnings`. Complements `validate`, doesn't replace it. |
| `reference` | `reference() -> str` | The full agent-facing reference doc (this file's content), packaged inside `compono` itself — for an agent with only shell/code-exec access, no MCP connection or Claude Code skill loaded. Also `compono reference` on the CLI. |
| `DeckValidationError` | `exc.errors -> list[dict]` | The one exception type. Carries the structured error list below. |

A `Deck` is `{template?: str, slides: [Slide, ...]}`. A `Slide` is
`{header?: Header, body: [primitive, ...], notes?: str}`. `body` (and
`grid.items`) accept any primitive, keyed by its `"primitive"` field.

### Error shape

```json
{
  "slide": 3,
  "primitive": "grid.items[1]",
  "field": "content",
  "error": "overflow",
  "detail": "Text is ~14pt too tall for the box at font size 18pt (6 lines).",
  "fix": "Shorten the text, reduce bullet/line count, or split into two slides."
}
```

### The feedback loop in practice

This is the actual point of `validate()` being cheap and separate from
`render_deck()` — an agent runs it first, gets back something it can act
on, and only pays render cost once the spec is clean. No new API for
this, just the two verbs above used the way they're meant to be:

**1st pass** — a real spec, sharing a slide with two stats, packs in
three long bullets:

```python
spec = {
    "slides": [{
        "header": {"title": "Q3 Roadmap"},
        "body": [
            {"primitive": "text", "mode": "bullets", "content": [
                "Ship onboarding redesign across web, iOS, and Android, "
                "with full localization support for every launch market",
                "Migrate billing to the new usage-based pricing engine, "
                "including proration, credits, and dunning retries",
                "Roll out SSO and SCIM provisioning for enterprise "
                "customers across every supported identity provider",
            ]},
            {"primitive": "stat", "value": "42%", "label": "YoY revenue growth"},
            {"primitive": "stat", "value": "99.97%", "label": "platform uptime"},
        ],
    }]
}
validate(spec).errors
```

```json
[{
  "slide": 0, "primitive": "body[0]", "field": "content", "error": "overflow",
  "detail": "Text is ~22pt too tall for the box at font size 18pt (6 lines).",
  "fix": "Shorten the text, reduce bullet/line count, or split into two slides."
}]
```

**2nd pass** — the agent applies the `fix` verbatim (shortens the
bullets), nothing else about the spec changes:

```python
spec["slides"][0]["body"][0]["content"] = [
    "Ship onboarding redesign across web, iOS, and Android",
    "Migrate billing to usage-based pricing",
    "Roll out SSO and SCIM for enterprise customers",
]
validate(spec).valid  # True
render_deck(spec, "q3-roadmap.pptx")  # now succeeds
```

`render_deck` would have raised `DeckValidationError` on the 1st-pass
spec instead of writing a broken file — the loop above is what an agent
actually runs, not a hypothetical.

### Design review (`review()`)

`validate()` answers "will this render without breaking." `review()`
answers "does this look good" — a separate, never-blocking verb: no
`.valid`, just `.suggestions` (possibly empty) and `.warnings`. Pair the
two — `review()` assumes a structurally valid deck.

```python
spec = {
    "slides": [{
        "header": {"title": "Architecture"},
        "body": [{
            "primitive": "shape", "kind": "rounded_rect", "fill": "#111827",
            "text": {"content": "Gateway", "color": "#1F2937"},
        }],
    }]
}
review(spec).suggestions
```

```json
[{
  "slide": 0, "primitive": "body[0]", "field": "text.color", "category": "contrast",
  "detail": "text.color '#1F2937' against fill '#111827' has a contrast ratio of ~1.2:1 (WCAG AA wants 4.5:1).",
  "fix": "Pick a lighter/darker text.color for more contrast against fill, or use a lighter/darker fill."
}]
```

Four categories today:

| Category | Checks | Requires |
|---|---|---|
| `contrast` | WCAG-style ratio between `shape.text.color` and `shape.fill` | Both set explicitly — never guesses a color that wasn't given. |
| `whitespace` | A body of exactly one primitive left alone in a tall box | Nothing — but **never fires on a header-only slide** (no `body` at all). A title/closing slide being sparse is the deliberate pattern that fix shipped in 0.1.1; there's nothing to be "too empty" relative to. |
| `image_fit` | A real image (not a placeholder) whose aspect ratio diverges a lot from its box, under `fit="cover"` (crops) or `fit="contain"` (large empty bars) | A real `src`, not a placeholder — nothing to measure otherwise. |
| `font_size` | Text using most of its box's height without (yet) overflowing | A font (same fallback as overflow validation) — skipped, not faked, otherwise. |


