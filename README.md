# compono

**Agent-oriented, code-based PPTX/DOCX generation.** Describe a deck or
document as typed primitives — an LLM agent never writes raw coordinates or
touches OOXML.

compono lets an LLM agent (or a human) describe a slide deck as data —
headers, bullet text, stats, tables, charts, images, process sequences,
shapes — and get back a real, editable `.pptx` file. The agent never writes
raw `x`/`y`/`w`/`h` coordinates: a constraint-based layout resolver computes
every position from a small set of typed primitives.

Every rendered element is a genuine, editable native shape (`p:sp`, `p:pic`,
`p:graphicFrame`) — never a flattened image or embedded video. Open the
result in PowerPoint and drag a box around; it's a real object, not a
picture of one.

compono also generates `.docx` documents — its second output format, for
linear content (proposals, reports) rather than slides, with its own
smaller primitive set (`heading`, `paragraph`, `bullet_list`, `table`,
`image`, `chart`, ...). See [DOCX generation](docs/docx.md) for the full
write-up; the rest of this README covers the original `.pptx` path.

Building a JS/TS agent harness instead of a Python one? See
[compono-js](docs/compono-js.md) — a parallel TypeScript port of the same
schema/resolver/validator/render pipeline, plus `review()`, Inspire, and
DOCX generation, plus an MCP server — same primitive-JSON contracts,
independent implementation and version.

## Why compono

Ask an LLM to write raw `python-pptx` (or drive a browser-based renderer
like pptx.js) and you get code littered with hand-picked EMU coordinates —
the model has to simultaneously invent content *and* do pixel-perfect
layout math it's genuinely bad at. The usual failure modes: overlapping
boxes, text running off the slide, margins that drift slide to slide,
titles crammed against the edge. None of that is a content problem; it's
a coordinates problem.

compono removes coordinates from the agent's job entirely:

- **You describe intent, not geometry.** `{"primitive": "grid", "columns": 2, ...}`,
  not `left=Inches(0.6), top=Inches(1.9), width=...`. A directional,
  flexbox-style resolver computes every real position.
- **A cheap pre-flight check, before paying render cost.** `validate(spec)`
  catches schema errors, layout impossibilities, and text overflow —
  measured against real glyph metrics, not guessed — in milliseconds, with
  no file write. Bad specs get a structured `{slide, primitive, field,
  error, detail, fix}` back, not a broken `.pptx` or a stack trace.
- **A design-quality pass, still optional.** `review(spec)` — contrast,
  whitespace, image-fit, font-size-near-overflow, style — flags things a
  human designer would notice that "renders successfully" doesn't catch.
- **Nothing is ever a flattened image.** Every primitive is a real,
  editable OOXML shape or graphicFrame. A generated table is a real table;
  a generated chart has live, editable series data. Open the file and it's
  actually still a deck, not a picture of one.

The result: an agent's job shrinks to "pick the right primitives and
content," and a resolver + validator handle everything spatial.

## Install

```bash
pip install compono
# or
uv add compono
```

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

## How an agent should use this

The intended loop is **validate, fix, render** — not "render and hope":

1. Build a spec (plain `dict`/JSON — whatever your tool-calling naturally
   produces).
2. `validate(spec)` — cheap, no file write. If `.valid` is `False`, apply
   each error's `fix` field directly and re-validate.
3. Optionally `review(spec)` once it validates — apply suggestions that
   matter for this deck, ignore the rest; it never blocks anything.
4. `render_deck(spec, output_path)` — writes the real `.pptx`. It refuses
   to write anything on a validation failure, so a broken spec never
   produces a broken file.

`compono reference` (or `compono.reference()` in Python) prints the same
full reference an MCP client or Claude Code skill would get — useful if
you're wiring up a different agent framework and want the whole primitive
catalog and error shape in one shot.

## Documentation

- [Getting started](https://github.com/Shaik-Hamzah123/compono/blob/main/docs/getting-started.md) — install, quickstart, core concepts
- [API reference](https://github.com/Shaik-Hamzah123/compono/blob/main/docs/api-reference.md) — verbs, error shape, the feedback loop, design review
- [Primitives](https://github.com/Shaik-Hamzah123/compono/blob/main/docs/primitives.md) — full catalog, image placeholders, worked examples
- [Templates and fonts](https://github.com/Shaik-Hamzah123/compono/blob/main/docs/templates-and-fonts.md) — `Deck.template`, `font_family`
- [CLI](https://github.com/Shaik-Hamzah123/compono/blob/main/docs/cli.md)
- [MCP server](https://github.com/Shaik-Hamzah123/compono/blob/main/docs/mcp.md) — `compono-mcp`, and what to do when compono has no context
- [Inspire](https://github.com/Shaik-Hamzah123/compono/blob/main/docs/inspire.md) — scan liked decks into a style profile/skill, structure and style only, never literal content
- [DOCX generation](https://github.com/Shaik-Hamzah123/compono/blob/main/docs/docx.md) — compono's second output format, for linear documents rather than slides
- [compono-js](https://github.com/Shaik-Hamzah123/compono/blob/main/docs/compono-js.md) — TypeScript port (pptx via pptxgenjs, plus review/Inspire/DOCX) and its MCP server, for JS/TS agent harnesses
- [Claude Code plugin](https://github.com/Shaik-Hamzah123/compono/blob/main/docs/claude-code-plugin.md)
- [Examples](https://github.com/Shaik-Hamzah123/compono/blob/main/docs/examples.md) — rendered screenshots across genres, from real `examples/*.json` specs

(Absolute links, not relative — this README is also rendered as-is on
PyPI, which can't resolve links to other files in the repo.)

Agents: the full reference in one file is `compono reference` /
`compono.reference()`, or
[`skills/compono/SKILL.md`](https://github.com/Shaik-Hamzah123/compono/blob/main/skills/compono/SKILL.md)
— that's the doc written for you, not this page.

## Contributing

See [`CONTRIBUTING.md`](https://github.com/Shaik-Hamzah123/compono/blob/main/CONTRIBUTING.md)
for dev setup, branching, and code style. If you're using Claude Code,
[`.claude/README.md`](https://github.com/Shaik-Hamzah123/compono/blob/main/.claude/README.md)
describes the build-workflow skill, review subagent, and commit/format
hooks set up for this repo.
