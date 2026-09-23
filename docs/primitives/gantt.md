# `gantt`

A Gantt/timeline chart. Not a native chart type — `chart.chart_type` is
deliberately scoped to bar/line/pie only, and compono's resolver never
does value-proportional placement (every primitive is positioned by the
equal-split box model, not scaled against arbitrary numeric values like
dates). A `gantt` is instead synthesized internally as a
[`table`](table.md): `unit_labels` become the time-unit columns (plus a
leading task-label column), each task becomes a row, and its active span
of cells is colored via `table`'s `cell_fills` — the same "reuse, don't
reimplement" trick [`diagram`](diagram.md) uses for its nodes, taken one
step further: by the time `render.py` sees a `gantt`, it's already an
ordinary `table` it already knows how to render.

## Fields

| Field | Type | Notes |
|---|---|---|
| `tasks` | `list[{label, start_unit, duration_units, fill?}]` | Required, non-empty. One row per task, in order. `start_unit`/`duration_units` must fit within `unit_labels`. |
| `unit_labels` | `list[str]` | Required, non-empty. One header per time-unit column, e.g. `["Wk 1", "Wk 2", ...]`. Plain strings — no date math happens on compono's side. |
| `task_fill` | `str` | Default `"#2A6FDB"`. Fill color for tasks that don't set their own `fill`. |

`start_unit` is a 0-based index into `unit_labels`; `duration_units` is
how many consecutive columns the task spans. A task's `fill` overrides
`task_fill` for that task's row only.

## Example

```json
{
  "primitive": "gantt",
  "task_fill": "#2A6FDB",
  "unit_labels": ["Wk 1", "Wk 2", "Wk 3", "Wk 4", "Wk 5", "Wk 6", "Wk 7", "Wk 8"],
  "tasks": [
    { "label": "Discovery", "start_unit": 0, "duration_units": 2 },
    { "label": "Design", "start_unit": 1, "duration_units": 3, "fill": "#D9534F" },
    { "label": "Build", "start_unit": 3, "duration_units": 4 },
    { "label": "Launch", "start_unit": 7, "duration_units": 1, "fill": "#059669" }
  ]
}
```

See `examples/gantt_timeline.json` in the repo for the full, runnable
spec (with a header).

## Limitations

- `unit_labels` are plain strings, chosen and formatted by the caller —
  compono does no date arithmetic (no "8 weeks starting March 3rd"
  generation).
- No dependency arrows between tasks (a "Design blocks Build" connector)
  — each task is just a colored span in its own row.
- No chart-color theming: unlike `table`'s header row or `sequence`'s
  step shapes, `gantt`'s colors come only from `task_fill`/per-task
  `fill`, not from the active template's `colors.primary`/`accent`.

If you need per-cell text inside a task's span (not just a solid color),
or dependency arrows, build the timeline directly with a `table` +
`cell_fills`/`merges` instead — see [`table`](table.md).
