# @skhamzah123/compono-js

**Agent-oriented, code-based PPTX/DOCX generation for TypeScript/JS.**
Describe a deck or document as typed primitives — an LLM agent never
writes raw coordinates or touches OOXML.

A TypeScript port of [`compono`](https://pypi.org/project/compono/)'s
full pipeline — schema → resolver → validator → render, `review()`,
Inspire, and DOCX generation — rendering pptx via
[`pptxgenjs`](https://www.npmjs.com/package/pptxgenjs) instead of
`python-pptx`, and docx via [`docx`](https://www.npmjs.com/package/docx)
instead of `python-docx`. Same primitive-JSON contracts as the Python
package, same "validate → fix → render" feedback loop, independent
implementation and independent version — for agent harnesses that
write/call JS rather than Python. An MCP server is available separately
as [`compono-js-mcp`](https://www.npmjs.com/package/@skhamzah123/compono-js-mcp).

Why this exists: `pptxgenjs` produces higher-fidelity native `.pptx`
output than `python-pptx` for equivalent content. compono's actual value
isn't which library writes the XML — it's the constraint-based resolver
(you describe intent, never raw `x`/`y`/`w`/`h`) plus the validate/render
feedback loop. This package keeps that architecture and swaps the render
backend.

## Install

```bash
npm install @skhamzah123/compono-js
```

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

Or from the command line:

```bash
npx --package=@skhamzah123/compono-js compono-js validate spec.json
npx --package=@skhamzah123/compono-js compono-js render spec.json -o deck.pptx --template modern
```

## What's ported

**pptx**: full v1 primitive catalog (`header`, `text`, `image`, `stat`,
`grid`, `table`, `sequence`, `chart`, `shape` including connector
routing) — same resolver algorithm (flex-equal body stacking, 2D grid
math, Liang-Barsky connector-routing with gutter-detour fallback), same
overflow validator (real glyph advance widths via `fontkit` in place of
`fontTools`), same structured error shape
(`{slide, primitive, field, error, detail, fix}`).

**`review()`**: same 5 categories (contrast, whitespace, image_fit,
font_size, style), same thresholds, via `imageSize` for real image
dimensions instead of `PIL.Image.open`.

**DOCX**: same primitive catalog (`heading`, `paragraph`, `bullet_list`,
`numbered_list`, `table`, `image`, `chart`, `page_break`) via the `docx`
npm package. `chart` is the one documented exception — rasterized via
`chart.js`/`chartjs-node-canvas`, same as Python's matplotlib approach
(no JS library builds native Word charts either).

**Inspire**: `scanDeck`/`aggregate`/`writeSkill`, same grid-confidence
scoring and per-deck (not per-shape) weighting. Since no npm package
offers python-pptx's read-side object model, it reads the `.pptx`'s
OOXML directly (`jszip` + `fast-xml-parser`) — same content-stripping
invariant (never reads literal run text or image bytes).

Not yet available: an MCP server bundled *into* this package — see the
separate [`compono-js-mcp`](https://www.npmjs.com/package/@skhamzah123/compono-js-mcp)
package instead.

## Relationship to Python `compono`

Same contract (the primitive JSON a spec is made of), independent
implementation, independently versioned. A spec written for one renders
correctly through the other — that's the point. This package is not a
wrapper or a subprocess call into Python; it's real TypeScript.
