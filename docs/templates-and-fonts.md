# Templates and fonts

## Fonts and templates

A deck's typeface comes from its **template**, not a per-primitive field —
`Deck.template` (default `"default"`) picks a `.yaml` file under
`src/compono/templates/`. compono currently includes these templates (more
can be added — see below):

| Template | `font_family` |
|---|---|
| `default` | Calibri |
| `modern` | Georgia |
| `classic` | Times New Roman |
| `clean` | Arial |

```json
{ "template": "modern", "slides": [ ... ] }
```

or via the CLI: `compono render spec.json --template modern -o deck.pptx`
(a CLI/kwarg `template` always overrides the spec's own `template` field).
An unknown name is a structured `unknown_template` error (validate/render
alike), not a crash — the `fix` lists what's available.

**If a user asks the agent for a font that isn't already bundled:**
there is no schema field to smuggle an arbitrary typeface through a single
render call — that's deliberate (see [Core concepts](getting-started.md#core-concepts)); fonts
live in a reviewed template file, not agent-request data. So:
- **A coding agent with write access to this repo** (e.g. Claude Code
  working on `compono` itself) can add a new
  `src/compono/templates/<name>.yaml` — copy `default.yaml`'s page/margin
  values, set the requested `font_family` — then use `{"template": "<name>"}`
  going forward. This is a one-time, reviewed, host-side change, the same as
  adding `modern.yaml` was.
- **An agent that only has `render_deck`/`validate` as tools** (e.g. over
  MCP, no filesystem access to `compono`'s own package) **cannot** invent a
  template on the fly. It should tell the user the requested font isn't
  available, list the templates that are, and either fall back to one of
  them or ask a human to add the template file.

Overflow checking (`validate`'s layout errors, and the "shrink text on
overflow" behavior it protects against) reads real glyph advance widths via
`fonttools` — no rendering required, and it needs a real font file to read
those widths from. compono bundles **Open Sans** (SIL OFL 1.1,
`src/compono/fonts/OpenSans-Regular.ttf` + `OFL.txt`) for exactly this
purpose. Every stock template's `font_family` (Calibri/Georgia/Times New
Roman/Arial) resolves to this one bundled file when measuring overflow —
it's the one real font shipped with the package, used as a glyph-metrics
approximation across templates.

**This bundled font is never written into the output `.pptx`/`.docx`.**
What actually renders in the deck is controlled solely by the template's
`font_family` string (e.g. `"Georgia"`) — a plain OOXML font-name reference,
resolved by whatever opens the file (PowerPoint, LibreOffice, Word) against
whatever's installed on *that* machine, exactly like any other font name in
an Office document. Neither `python-pptx` nor `python-docx` embeds font
files, and compono doesn't either — bundling Open Sans only gives the
overflow validator real glyph data to measure against, independent of what
name ends up in the file. If the bundled file somehow fails to load,
validation falls back to a system font if one is found, and is skipped —
never faked — with a warning if none is available either.


