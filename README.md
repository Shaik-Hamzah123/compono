# compono

**Agent-oriented, code-based PPTX generation.** Describe a deck as typed
primitives — an LLM agent never writes raw coordinates or touches OOXML.

compono lets an LLM agent (or a human) describe a slide deck as data —
headers, bullet text, stats, tables, charts, images, process sequences,
shapes — and get back a real, editable `.pptx` file. The agent never writes
raw `x`/`y`/`w`/`h` coordinates: a constraint-based layout resolver computes
every position from a small set of typed primitives.

Every rendered element is a genuine, editable native shape (`p:sp`, `p:pic`,
`p:graphicFrame`) — never a flattened image or embedded video. Open the
result in PowerPoint and drag a box around; it's a real object, not a
picture of one.

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

Three verbs in total — `render_deck`, `validate` (cheap, no file write,
run it first), and `review` (design-quality suggestions, never blocking).
See [docs/](docs/) for everything past this point.

## Documentation

- [Getting started](docs/getting-started.md) — install, quickstart, core concepts
- [API reference](docs/api-reference.md) — verbs, error shape, the feedback loop, design review
- [Primitives](docs/primitives.md) — full catalog, image placeholders, worked examples
- [Templates and fonts](docs/templates-and-fonts.md) — `Deck.template`, `font_family`
- [CLI](docs/cli.md)
- [MCP server](docs/mcp.md) — `compono-mcp`, and what to do when compono has no context
- [Claude Code plugin](docs/claude-code-plugin.md)
- [Examples](docs/examples.md) — rendered screenshots across genres, from real `examples/*.json` specs

Agents: the full reference in one file is `compono reference` /
`compono.reference()`, or `skills/compono/SKILL.md` — that's the doc
written for you, not this page.

## Contributing

See `CONTRIBUTING.md` for dev setup, branching, and code style. If you're
using Claude Code, `.claude/README.md` describes the build-workflow skill,
review subagent, and commit/format hooks set up for this repo.
