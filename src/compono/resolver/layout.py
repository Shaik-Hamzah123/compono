"""The core layout engine: `resolve_slide`'s directional box model, body
stacking, and `grid`'s 2D layout. Dispatches to `diagram.py`/`gantt.py` for
those two primitives' own layout (see `_place_item`), and to
`connectors.py` for the second-pass connector-routing calls `resolve_slide`
makes once every rect is final.
"""

from __future__ import annotations

import math

from compono.schema import Diagram, Gantt, Grid, Header, PrimitiveSpec, Shape

from .connectors import _resolve_connectors
from .diagram import _layout_diagram, _resolve_diagram_connectors
from .gantt import _layout_gantt
from .template import Template
from .types import LayoutResult, Rect


def resolve_slide(
    template: Template,
    header: Header | None = None,
    body: list[PrimitiveSpec] | None = None,
) -> LayoutResult:
    """Resolve one slide: header region top, footer pinned bottom, body fills the remainder."""
    body = body or []
    result = LayoutResult(
        page_width=template.page_width, page_height=template.page_height
    )

    content_x = template.margin_left
    content_w = template.page_width - template.margin_left - template.margin_right
    cursor_y = template.margin_top
    footer_top = template.page_height - template.margin_bottom - template.footer_height

    if header is not None:
        header_id = header.id or "header"
        # A header-only slide (no body) is a title/section/closing slide —
        # give it the full content area instead of the fixed header band, so
        # render.py can vertically center it on the page like a real title
        # slide, rather than pinning it to a short strip at the top with a
        # mostly-empty page below.
        header_height = (footer_top - cursor_y) if not body else template.header_height
        result.rects[header_id] = Rect(content_x, cursor_y, content_w, header_height)
        result.items[header_id] = header
        cursor_y += header_height

    body_height = footer_top - cursor_y
    if body_height < 0:
        raise ValueError(
            "Template margins/header/footer leave no room for body content — "
            "reduce header/footer height or margins."
        )

    _layout_stack(
        body,
        Rect(content_x, cursor_y, content_w, body_height),
        template,
        result,
        prefix="body",
    )
    _resolve_connectors(body, result, template)
    _resolve_diagram_connectors(result, template)

    return result


def _is_connector_shape(item: PrimitiveSpec) -> bool:
    """A connector shape draws nothing at its own position — only
    layout.connectors (computed from the *other* primitives it references)
    gets rendered. It must never consume a body/grid slot's shared space.
    """
    return isinstance(item, Shape) and item.kind == "connector"


def _layout_stack(
    items: list[PrimitiveSpec],
    rect: Rect,
    template: Template,
    result: LayoutResult,
    prefix: str,
) -> None:
    """Lay out primitives top-to-bottom, sharing rect height equally (flex-equal fallback)."""
    real_items = [item for item in items if not _is_connector_shape(item)]
    n = len(real_items)
    if n == 0:
        return

    slot_h = (rect.h - template.gutter * (n - 1)) // n if n > 1 else rect.h
    y = rect.y
    for i, item in enumerate(real_items):
        item_id = item.id or f"{prefix}[{i}]"
        item_rect = Rect(rect.x, y, rect.w, slot_h)
        _place_item(item, item_rect, template, result, item_id)
        y += slot_h + template.gutter


def _place_item(
    item: PrimitiveSpec,
    rect: Rect,
    template: Template,
    result: LayoutResult,
    item_id: str,
) -> None:
    result.rects[item_id] = rect
    result.items[item_id] = item
    if isinstance(item, Grid):
        _layout_grid(item, rect, template, result, item_id)
    elif isinstance(item, Diagram):
        _layout_diagram(item, rect, template, result, item_id)
    elif isinstance(item, Gantt):
        _layout_gantt(item, rect, template, result, item_id)


def _resolve_grid_columns(grid: Grid, n: int) -> int:
    if grid.columns != "auto":
        return grid.columns
    if grid.direction == "column":
        return 1
    return max(1, n)


def _layout_grid(
    grid: Grid,
    rect: Rect,
    template: Template,
    result: LayoutResult,
    prefix: str,
) -> None:
    """True 2D layout: row/column count, gutter, equal-fr distribution (COMPONO_PLAN.md section 6)."""
    real_items = [item for item in grid.items if not _is_connector_shape(item)]
    n = len(real_items)
    if n == 0:
        return

    columns = max(1, min(_resolve_grid_columns(grid, n), n))
    rows = math.ceil(n / columns)

    col_w = (rect.w - template.gutter * (columns - 1)) // columns
    row_h = (rect.h - template.gutter * (rows - 1)) // rows

    for i, item in enumerate(real_items):
        r, c = divmod(i, columns)
        x = rect.x + c * (col_w + template.gutter)
        y = rect.y + r * (row_h + template.gutter)
        item_id = item.id or f"{prefix}.items[{i}]"
        result.parents[item_id] = prefix
        _place_item(item, Rect(x, y, col_w, row_h), template, result, item_id)
