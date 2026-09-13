# compono-js

**Agent-oriented, code-based PPTX/DOCX generation for TypeScript/JS.**
Describe a deck or document as typed primitives — an LLM agent never
writes raw coordinates or touches OOXML.

You are receiving this document through the `compono-js-mcp` MCP server's
`compono://reference` resource — use its `validate_deck`/`review_deck`/
`render_deck_tool`/`inspire_scan`/`validate_docx_tool`/`render_docx_tool`
tools as described below.

`compono-js` is a TypeScript port of Python `compono`'s schema → resolver
→ validator → render pipeline, rendering `.pptx` via `pptxgenjs` instead
of `python-pptx` — same primitive-JSON contract, independent
implementation and version.

## Tools (via this MCP server)

| Tool | Input | Output | Notes |
|---|---|---|---|
| `validate_deck` | `spec: object` | `{valid, errors, warnings}` | No file write. Never errors out on malformed input — `valid: false` with structured errors instead. |
| `render_deck_tool` | `spec: object, output_path: string` | `{pptxPath, manifest, warnings}` on success, or `{valid: false, errors}` on failure | Writes a real `.pptx` at `output_path` on the machine running this server. |
| `review_deck` | `spec: object` | `{suggestions, warnings}` | Design-quality suggestions (contrast, whitespace, image fit, font-size proximity to overflow, style) — never blocking. |
| `inspire_scan` | `pptx_paths: string[], out_dir: string, name?: string, min_repeat_ratio?: number` | `{skill_md, profile_json, n_decks_scanned, warnings}` | Scans `.pptx` files someone already likes into a style profile/skill — never literal text or images. |
| `validate_docx_tool` | `spec: object` | `{valid, errors, warnings}` | Same shape as `validate_deck`, for a docx spec — errors use `"section"` in place of `"slide"`. |
| `render_docx_tool` | `spec: object, output_path: string` | `{docxPath, manifest, warnings}` on success, or `{valid: false, errors}` on failure | Writes a real `.docx`. `chart` primitives render as a rasterized image (chart.js) — every other primitive is a real, editable object. |

A `spec` (a `Deck`) is `{template?: str, slides: [Slide, ...]}`. A `Slide`
is `{header?: Header, body: [primitive, ...], notes?: str}`. `body` (and
`grid.items`) accept any primitive, keyed by its `"primitive"` field.

A docx `spec` (a `DocxDoc`) is `{title: str, sections: [Section, ...]}`.
A `Section` is `{header_text?: str, footer_text?: str, body: [primitive, ...]}`.

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

## Primitive catalog (pptx)

`header`, `text`, `image`, `stat`, `grid`, `table`, `sequence`, `chart`,
`shape` (including `kind: "connector"`, resolved via a routing pass that
avoids obstacles), `diagram` (`nodes` (`{id?, label, kind?, fill?}`),
`edges?` (`{from, to}`), `orientation` (vertical/horizontal), `node_kind`,
`node_fill`) — a node-graph flowchart whose nodes are placed automatically
and edges routed between them, reusing `shape(kind="connector")`'s own
obstacle-avoiding routing. Omit `edges` for an auto-connected linear chain;
give nodes explicit `id`s and add `edges` for a branch or a skip-ahead
edge.

## Primitive catalog (docx)

`heading`, `paragraph` (`runs: Run[]`), `bullet_list`/`numbered_list`
(`items: Run[][]`), `table`, `image` (`src|placeholder`), `chart`,
`page_break`. A `Run` is `{text, bold?, italic?, underline?, link?}`.

## Worked example (pptx)

```json
{
  "slides": [
    {
      "header": { "title": "Q3 Results", "subtitle": "Engineering team" },
      "body": [
        {
          "primitive": "text",
          "mode": "bullets",
          "content": ["Shipped the new layout resolver", "Cut render time by 40%"]
        }
      ]
    }
  ]
}
```

## Worked example (diagram)

```json
{
  "slides": [
    {
      "header": { "title": "RAG Pipeline" },
      "body": [
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
      ]
    }
  ]
}
```

Omitting `edges` auto-connects nodes in order (a linear chain). For a
branch or a skip-ahead edge, give `nodes` explicit `id`s and add
`edges: [{"from": "...", "to": "..."}]`.

## Worked example (docx)

```json
{
  "title": "Training Proposal",
  "sections": [
    {
      "header_text": "Acme Corp — Confidential",
      "body": [
        { "primitive": "heading", "text": "Overview", "level": 1 },
        { "primitive": "paragraph", "runs": [{ "text": "This is " }, { "text": "bold", "bold": true }, { "text": "." }] },
        { "primitive": "table", "headers": ["Track", "Weeks"], "rows": [["AI Foundations", "1-2"]] }
      ]
    }
  ]
}
```

compono-js bundles Open Sans (SIL OFL 1.1) purely as a glyph-metrics
reference for overflow measurement — every stock template's `fontFamily`
resolves to it for that purpose only. It is never written into the output
file; the deck itself always renders in whatever `fontFamily` the template
names. Chart axis/legend/data-label text picks up `template.fontFamily`
too, and table/sequence overflow is checked per-cell/per-step against each
cell's own sub-rect.

## Known limitations

- `chart` in docx is a rasterized image, not an editable native Word
  chart — no JS library builds native Word charts either.
- Inspire's deck-scanning reads OOXML directly (no npm equivalent to
  python-pptx's read-side object model exists), so it only sees what's
  representable at the XML level (position, fill color, font family/size)
  — grouped shapes and some theme-inherited styling aren't resolved.
