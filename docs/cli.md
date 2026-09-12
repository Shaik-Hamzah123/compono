# CLI

## CLI

```bash
compono validate spec.json
compono review spec.json
compono render spec.json --template modern -o deck.pptx
compono reference
compono inspire scan decks/ -o skills/inspire-myteam/
compono docx validate doc_spec.json
compono docx render doc_spec.json -o report.docx
```

Mirrors `validate`/`review`/`render_deck`/`inspire`/`render_docx` exactly —
useful for agent frameworks that can only shell out rather than import
Python. `reference` prints the same content as this README to stdout, for
any agent with shell access but no MCP connection or Claude Code skill
loaded (a bare `pip install compono` gets neither of those automatically —
see [When compono has no context](mcp.md#when-compono-has-no-context)
below). See [Inspire](inspire.md) and [DOCX generation](docx.md) for the
`inspire`/`docx` subcommands.


