# compono-js

A TypeScript port of compono core, for agent harnesses that write/call JS
rather than Python. Same schema → resolver → validator → render pipeline,
same `review()`/Inspire/DOCX feature set, rendered via
[`pptxgenjs`](https://www.npmjs.com/package/pptxgenjs) instead of
`python-pptx` and [`docx`](https://www.npmjs.com/package/docx) instead of
`python-docx` — same primitive-JSON contracts, independent implementation
and version.

Why it exists: `pptxgenjs` produces higher-fidelity native `.pptx` output
than `python-pptx` for equivalent content, and some agent harnesses write
JS/TS rather than Python. compono's actual value isn't which library
writes the XML — it's the constraint-based resolver (describe intent,
never raw `x`/`y`/`w`/`h`) plus the validate/render feedback loop. This
package keeps that architecture and swaps the implementation language and
render backends.

## Install

```bash
npm install @skhamzah123/compono-js
```

## What's ported

- **pptx**: the full v1 primitive catalog (`header`, `text`, `image`,
  `stat`, `grid`, `table`, `sequence`, `chart`, `shape` including
  connector routing), same resolver algorithm (flex-equal body stacking,
  2D grid math, Liang-Barsky connector-routing with gutter-detour
  fallback), same overflow validator (real glyph advance widths via
  `fontkit` in place of `fontTools`).
- **`review()`**: same 5 categories (contrast, whitespace, image_fit,
  font_size, style), same thresholds — see [API reference](api-reference.md)
  for what each one checks; the Python and JS implementations check
  identically.
- **DOCX**: same primitive catalog as [DOCX generation](docx.md)
  (`heading`, `paragraph`, `bullet_list`, `numbered_list`, `table`,
  `image`, `chart`, `page_break`), via the `docx` npm package. `chart` is
  the same one documented exception — rasterized via
  `chart.js`/`chartjs-node-canvas` instead of matplotlib (no JS library
  builds native Word charts either).
- **Inspire**: `scanDeck`/`aggregate`/`writeSkill`, same grid-confidence
  scoring and per-deck (not per-shape) weighting as [Inspire](inspire.md).
  Since no npm package offers python-pptx's read-side object model, it
  reads a `.pptx`'s OOXML directly (`jszip` + `fast-xml-parser`) — same
  content-stripping invariant (never reads literal run text or image
  bytes).

Same structured error shape throughout:
`{slide|section, primitive, field, error, detail, fix}`.

## Quickstart

```ts
import { renderDeck } from "@skhamzah123/compono-js";

const spec = {
  slides: [
    {
      header: { title: "Q3 Results", subtitle: "Engineering team" },
      body: [
        {
          primitive: "text",
          mode: "bullets",
          content: ["Shipped the new layout resolver", "Cut render time by 40%"],
        },
      ],
    },
  ],
};

const report = await renderDeck(spec, "deck.pptx");
console.log(report.pptxPath, report.warnings);
```

## CLI

```bash
npx --package=@skhamzah123/compono-js compono-js validate spec.json
npx --package=@skhamzah123/compono-js compono-js render spec.json -o deck.pptx --template modern
npx --package=@skhamzah123/compono-js compono-js review spec.json
npx --package=@skhamzah123/compono-js compono-js docx validate doc_spec.json
npx --package=@skhamzah123/compono-js compono-js docx render doc_spec.json -o report.docx
npx --package=@skhamzah123/compono-js compono-js inspire scan decks/ -o skills/inspire-myteam/
```

Same verb-for-verb shape as the [Python CLI](cli.md).

## MCP

[`compono-js-mcp`](https://www.npmjs.com/package/@skhamzah123/compono-js-mcp)
is the TypeScript counterpart to [`compono-mcp`](mcp.md) — same 6 tools
(`validate_deck`, `render_deck_tool`, `review_deck`, `inspire_scan`,
`validate_docx_tool`, `render_docx_tool`) and `compono://reference`
resource, via `@modelcontextprotocol/sdk` instead of `fastmcp`.

```bash
npm install @skhamzah123/compono-js-mcp
```

```json
{ "mcpServers": { "compono-js": { "command": "npx", "args": ["-y", "@skhamzah123/compono-js-mcp"] } } }
```

## Relationship to Python `compono`

Same contract (the primitive JSON a spec is made of), independent
implementation, independently versioned — the two packages are not
required to stay in lockstep release-to-release. A spec written for one
renders correctly through the other. This is real TypeScript, not a
wrapper or subprocess call into Python.

Overflow checking reads real glyph advance widths via `fontkit` — no
rendering required. compono-js bundles Open Sans (SIL OFL 1.1,
`packages/compono-js/fonts/`) for this: every stock template's
`fontFamily` resolves to it when measuring overflow, the same reference
font compono's Python side bundles. This bundled font is never written
into the output file — the deck itself always renders in whatever
`fontFamily` the template names (a plain OOXML font-name reference,
resolved by whoever opens the file); compono-js does not embed font files,
only measure against one for validation. Chart axis/legend/data-label text
also picks up `template.fontFamily`. Table and sequence overflow are
checked per-cell/per-step against each cell's own sub-rect, not as one
combined block of text (previously not checked at all for these two
primitives).

## Known limitations

- Inspire's deck-scanning reads OOXML directly, so it only sees what's
  representable at the XML level (position, fill color, font
  family/size) — grouped shapes and some theme-inherited styling aren't
  resolved.
- `chart` in docx is a rasterized image, not an editable native Word
  chart (same caveat as the Python side).
