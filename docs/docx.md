# DOCX generation

compono's second output format, alongside `.pptx`. Where a slide deck is a
2D layout problem (the resolver's whole job), a Word document flows
top-to-bottom on its own — so DOCX has its own, smaller primitive set
(`compono.docx_schema`) and renderer (`compono.docx`), not a reuse of the
pptx primitives.

## Primitive catalog

| Primitive | What it renders |
| --- | --- |
| `heading` | A real Word `Heading 1`-`4` paragraph style. |
| `paragraph` | One or more styled `runs` (bold/italic/underline/link), concatenated. |
| `bullet_list` | Real `List Bullet`-styled paragraphs, one per item. |
| `numbered_list` | Real `List Number`-styled paragraphs, one per item. |
| `table` | A real python-docx table, header row bolded. |
| `image` | A real embedded picture, or a bordered text placeholder + caption (same manifest-entry convention as pptx's `image` placeholder) when `placeholder: true`. |
| `chart` | See "Chart caveat" below. |
| `page_break` | A real page break. |

A document is `{title, sections: [...]}`. Each `Section` carries optional
`header_text`/`footer_text` (Word's running header/footer, repeated on
every page of that section) and a `body` list of primitives in order.

## Chart caveat — the one deliberate exception

`python-pptx` has a native chart object (`add_chart`); `python-docx` does
not — a native Word chart is a whole separate embedded-package format (a
chart XML part plus an embedded Excel worksheet) that no current Python
library builds. compono's `chart` primitive is instead rasterized via
`matplotlib` and embedded as a picture.

This is the one place DOCX generation differs from compono's usual
"always a real, editable object" preference — there's no editable native
chart primitive here to be faithful to, so it's documented rather than
hidden. Every other primitive in the catalog is verified (in
`tests/test_docx_shape_invariant.py`) to produce a genuine python-docx
object.

## CLI

```bash
compono docx validate doc_spec.json
compono docx render doc_spec.json -o report.docx
```

Same two-verb, structured-error convention as the pptx CLI
([cli.md](cli.md)) — `validate` never raises; `render` raises with
`{section, primitive, field, error, detail, fix}` errors (via
`DocxValidationError`) and writes nothing on failure.

## Python API

```python
from compono import DocxDoc, render_docx, validate_docx

spec = {
    "title": "Training Proposal",
    "sections": [
        {
            "header_text": "Acme Corp — Confidential",
            "body": [
                {"primitive": "heading", "text": "Overview", "level": 1},
                {"primitive": "paragraph", "runs": [{"text": "Hello."}]},
            ],
        }
    ],
}

report = validate_docx(spec)          # ValidationReport — never raises
render_docx(spec, "report.docx")      # writes a real .docx, or raises
                                       # DocxValidationError
```

## Worked example

```json
{
  "title": "Training Proposal",
  "sections": [
    {
      "header_text": "Acme Corp — Confidential",
      "footer_text": "compono docx demo",
      "body": [
        {"primitive": "heading", "text": "Executive Summary", "level": 1},
        {
          "primitive": "paragraph",
          "runs": [
            {"text": "This proposal outlines a "},
            {"text": "14-week", "bold": true},
            {"text": " training program."}
          ]
        },
        {
          "primitive": "table",
          "headers": ["Track", "Weeks"],
          "rows": [["AI Foundations", "1-2"], ["Advanced ML", "3-6"]]
        },
        {"primitive": "image", "placeholder": true, "caption": "Company logo"},
        {
          "primitive": "chart",
          "chart_type": "bar",
          "categories": ["Q1", "Q2", "Q3"],
          "series": [{"name": "Enrolled", "values": [12, 25, 30]}]
        },
        {"primitive": "page_break"},
        {"primitive": "heading", "text": "Next Steps", "level": 1}
      ]
    }
  ]
}
```

## MCP

`compono-mcp` exposes the same two verbs as tools:
`validate_docx_tool(spec)`/`render_docx_tool(spec, output_path)` — see
[MCP server](mcp.md).

## Known limitations

- No resolver/overflow validation for text — Word wraps and paginates
  content itself, so there's nothing equivalent to pptx's font-metric
  overflow check to run here.
- `chart` is a rasterized image, not an editable native Word chart (see
  above).
- No `review()`-equivalent design-quality pass yet (contrast/whitespace
  checks are pptx-specific today).
