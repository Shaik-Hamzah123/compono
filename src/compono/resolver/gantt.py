"""`gantt` layout: fully collapses into a synthesized `table`."""

from __future__ import annotations

from compono.schema import Gantt, Table, TableCellFill

from .template import Template
from .types import LayoutResult, Rect


def _layout_gantt(
    gantt: Gantt,
    rect: Rect,
    template: Template,
    result: LayoutResult,
    item_id: str,
) -> None:
    """A Gantt/timeline chart collapses into a single synthesized `table`
    at the gantt's own id — one row per task, one column per time unit
    (plus a leading task-label column), with each task's active span
    colored via `table.cell_fills`. Unlike `_layout_diagram` (which places
    several *child* shapes under the diagram's id), this fully replaces
    the `Gantt` entry in `result.items[item_id]` with the synthesized
    `Table` — real-shape invariant applies unchanged, and render.py never
    needs to know `gantt` exists at all.
    """
    # Deferred import: `layout.py` imports this module (to dispatch to
    # `_layout_gantt` from `_place_item`), so importing `_place_item` at
    # this module's top would be circular. Safe here since both modules
    # are fully loaded by the time this function actually runs.
    from .layout import _place_item

    headers = ["Task", *gantt.unit_labels]
    rows = [[task.label, *([""] * len(gantt.unit_labels))] for task in gantt.tasks]
    cell_fills = [
        TableCellFill(row=r, col=c + 1, fill=task.fill or gantt.task_fill)
        for r, task in enumerate(gantt.tasks)
        for c in range(task.start_unit, task.start_unit + task.duration_units)
    ]
    synthetic_table = Table(headers=headers, rows=rows, cell_fills=cell_fills)
    _place_item(synthetic_table, rect, template, result, item_id)
