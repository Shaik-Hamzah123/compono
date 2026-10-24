"""Pre-render text-extraction and overflow-checking — the concern parallel
to `validator.py`'s role, distinct from `primitives.py`'s "write real
OOXML" concern. `_extract_text_fields` is the single place that maps each
primitive type to its text-bearing field(s) and font size; every entry it
yields still goes through the one shared `validator.check_overflow` call,
never a bespoke wrap implementation.
"""

from __future__ import annotations

from typing import Any

from pptx.util import Emu

from compono.resolver import LayoutResult, Rect, Template, resolve_slide
from compono.schema import (
    Header,
    Image,
    PrimitiveBase,
    Sequence,
    Shape,
    Slide,
    Stat,
    Table,
    Text,
)
from compono.validator import (
    FontMetrics,
    build_overflow_error,
    check_overflow,
    measure_text_width_pt,
)

from ._shared import (
    BODY_FONT_SIZE_PT,
    CAPTION_FONT_SIZE_PT,
    HEADER_FONT_SIZE_PT,
    STAT_LABEL_FONT_SIZE_PT,
    STAT_VALUE_FONT_SIZE_PT,
    TABLE_FONT_SIZE_PT,
)

_TABLE_MIN_COL_WIDTH_PT = 40.0


def _table_column_widths_emu(
    headers: list[str],
    rows: list[list[str]],
    rect: Rect,
    font_metrics: FontMetrics | None,
) -> list[int] | None:
    """Column widths (EMU, summing exactly to `rect.w`) proportional to each
    column's longest measured cell, clamped to `_TABLE_MIN_COL_WIDTH_PT` so
    no column collapses to nothing. Returns `None` when no font is available
    to measure with — the caller falls back to an even split rather than
    faking a proportional one (same "never fakes" pattern as overflow
    validation itself).
    """
    if font_metrics is None:
        return None

    num_cols = len(headers)
    raw_widths_pt = []
    for c in range(num_cols):
        candidates = [headers[c]] + [row[c] for row in rows]
        raw_widths_pt.append(
            max(
                measure_text_width_pt(text, font_metrics, TABLE_FONT_SIZE_PT)
                for text in candidates
            )
        )
    clamped_pt = [max(_TABLE_MIN_COL_WIDTH_PT, w) for w in raw_widths_pt]
    total_pt = sum(clamped_pt)

    widths_emu = [round(w / total_pt * rect.w) for w in clamped_pt]
    # Floor/round drift must not change the total — the last column absorbs
    # it rather than leaving a gap or overrunning rect.w.
    widths_emu[-1] += rect.w - sum(widths_emu)
    return widths_emu


def _table_cell_rects(
    rect: Rect,
    num_cols: int,
    num_rows: int,
    col_widths: list[int] | None = None,
) -> list[list[Rect]]:
    """Split the table's overall rect into per-cell boxes — row 0 is the
    header row. `col_widths` (EMU, one per column, summing to `rect.w`) come
    from `_table_column_widths_emu` when a font is available; `None` falls
    back to an even, floor-divided split (the original v1 approximation),
    with any leftover EMUs from that floor division left as unassigned
    padding, not distributed to any particular cell.
    """
    if col_widths is None:
        col_w = rect.w // num_cols
        col_widths = [col_w] * num_cols
    col_x = [rect.x]
    for w in col_widths[:-1]:
        col_x.append(col_x[-1] + w)

    row_h = rect.h // num_rows
    return [
        [
            Rect(x=col_x[c], y=rect.y + r * row_h, w=col_widths[c], h=row_h)
            for c in range(num_cols)
        ]
        for r in range(num_rows)
    ]


def _sequence_step_rects(rect: Rect, num_steps: int) -> list[Rect]:
    """Even, floor-divided split of the sequence's overall rect into one box
    per step, left-to-right — same accepted v1 approximation as table cells.
    """
    step_w = rect.w // num_steps
    return [
        Rect(x=rect.x + i * step_w, y=rect.y, w=step_w, h=rect.h)
        for i in range(num_steps)
    ]


def _extract_text_fields(
    primitive: PrimitiveBase | None,
    rect: Rect,
    font_metrics: FontMetrics | None = None,
) -> list[tuple[str, str, float, Rect | None]]:
    """(field_name, text, font_size_pt, sub_rect) for every text-bearing field
    on a primitive. `sub_rect` is None when the field should be checked
    against the primitive's own full rect (every primitive below except
    Table/Sequence); Table/Sequence instead emit one entry per cell/step,
    each with its own sub-rect, so a single overlong cell/step is caught even
    when the combined text would have fit the overall box.

    `font_metrics`, when given, sizes a Table's column sub-rects
    proportionally to content (`_table_column_widths_emu`) — the same
    widths `_render_table` actually draws — instead of an even split, so
    overflow checking matches what's rendered. `None` (the default) falls
    back to the even split, same as before this parameter existed.

    Every entry is still checked through the same shared check_overflow/
    wrap_lines routine (validator.py) — primitives never grow their own wrap
    logic (COMPONO_PLAN.md section 5, "Text-in-shape").
    """
    if isinstance(primitive, Header):
        return [("title", primitive.title, HEADER_FONT_SIZE_PT, None)]
    if isinstance(primitive, Text):
        content = (
            primitive.content
            if isinstance(primitive.content, str)
            else " ".join(primitive.content)
        )
        return [("content", content, BODY_FONT_SIZE_PT, None)]
    if isinstance(primitive, Shape) and primitive.text is not None:
        return [("text.content", primitive.text.content, BODY_FONT_SIZE_PT, None)]
    if isinstance(primitive, Stat):
        return [
            ("value", primitive.value, STAT_VALUE_FONT_SIZE_PT, None),
            ("label", primitive.label, STAT_LABEL_FONT_SIZE_PT, None),
        ]
    if isinstance(primitive, Table):
        num_cols = len(primitive.headers)
        num_rows = 1 + len(primitive.rows)  # row 0 = headers
        col_widths = _table_column_widths_emu(
            primitive.headers, primitive.rows, rect, font_metrics
        )
        cell_rects = _table_cell_rects(rect, num_cols, num_rows, col_widths)
        fields: list[tuple[str, str, float, Rect | None]] = [
            (f"headers[{c}]", header, TABLE_FONT_SIZE_PT, cell_rects[0][c])
            for c, header in enumerate(primitive.headers)
        ]
        fields.extend(
            (f"rows[{r}][{c}]", cell, TABLE_FONT_SIZE_PT, cell_rects[r + 1][c])
            for r, row in enumerate(primitive.rows)
            for c, cell in enumerate(row)
        )
        return fields
    if isinstance(primitive, Sequence):
        step_rects = _sequence_step_rects(rect, len(primitive.steps))
        return [
            (
                f"steps[{i}]",
                f"{step.label}: {step.description}" if step.description else step.label,
                BODY_FONT_SIZE_PT,
                step_rects[i],
            )
            for i, step in enumerate(primitive.steps)
        ]
    if isinstance(primitive, Image) and primitive.caption:
        return [("caption", primitive.caption, CAPTION_FONT_SIZE_PT, None)]
    return []


def _check_slide(
    slide_index: int,
    slide: Slide,
    template: Template,
    font_metrics: FontMetrics | None,
) -> tuple[LayoutResult | None, list[dict[str, Any]], list[str]]:
    errors: list[dict[str, Any]] = []
    warnings: list[str] = []

    try:
        layout = resolve_slide(template, header=slide.header, body=slide.body)
    except ValueError as exc:
        errors.append(
            {
                "slide": slide_index,
                "primitive": "slide",
                "field": None,
                "error": "layout",
                "detail": str(exc),
                "fix": "Adjust the template margins/header/footer heights, or reduce body item count.",
            }
        )
        return None, errors, warnings

    if font_metrics is None:
        warnings.append(
            f"slide {slide_index}: no font available — overflow validation skipped."
        )
        return layout, errors, warnings

    for item_id, rect in layout.rects.items():
        for field_name, text, font_size_pt, sub_rect in _extract_text_fields(
            layout.items.get(item_id), rect, font_metrics
        ):
            check_rect = sub_rect if sub_rect is not None else rect
            box_width_pt = Emu(check_rect.w).pt
            box_height_pt = Emu(check_rect.h).pt
            report = check_overflow(
                text, font_metrics, font_size_pt, box_width_pt, box_height_pt
            )
            if report.overflow:
                errors.append(
                    build_overflow_error(
                        slide_index, item_id, field_name, report, font_size_pt
                    )
                )

    return layout, errors, warnings
