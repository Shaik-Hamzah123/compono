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
`fonttools` — no rendering required. As of this release, no font is bundled
into the package yet (`src/compono/fonts/` is a placeholder); validation
falls back to a system font if one is found (e.g. `arial.ttf` on Windows),
and is skipped — not faked — with a warning if none is available. This is
independent of `font_family` above — overflow metrics don't yet reflect the
template's chosen typeface (known limitation, see CHANGELOG). A bundled,
OFL-licensed safe-font list is planned before the first tagged release; this
section will list it once shipped.


