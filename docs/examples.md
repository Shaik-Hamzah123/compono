# Examples

## See it in action

compono isn't scoped to one deck genre — the same primitives compose into
client proposals, conference talks, research talks, college presentations,
or a lighter explainer. Every image below is rendered directly from the
matching `../examples/*.json` spec (`.pptx` → PNG via LibreOffice, see
`../scripts/render_example_screenshots.py`) — nothing here is a mockup:

| Client proposal | Conference talk |
|---|---|
| ![KPI grid](../assets/screenshots/client_proposal/slide-2.png) | ![Planner/Executor architecture](../assets/screenshots/conference_talk/slide-4.png) |

| Research talk | Fun explainer |
|---|---|
| ![Loss curves](../assets/screenshots/research_talk/slide-4.png) | ![Roast levels](../assets/screenshots/fun_explainer/slide-3.png) |

`shape` + `connector` compose into real diagrams, not just colored boxes —
a layered system architecture, built entirely from `../examples/architecture_diagram.json`:

![Layered architecture: client → gateway → services → queue → database](../assets/screenshots/architecture_diagram/slide-1.png)

See `../examples/` for the full specs (`client_proposal.json`,
`conference_talk.json`, `research_talk.json`, `college_presentation.json`,
`fun_explainer.json`, `architecture_diagram.json`, and `full_catalog.json`).


