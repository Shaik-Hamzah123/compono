"""Obstacle-avoiding connector routing, shared by `shape(kind="connector")`
resolution (`_resolve_connectors`, used from `layout.py`) and `diagram`'s
edge routing (`diagram.py`'s `_resolve_diagram_connectors`, which imports
`_route_connector` from here). A leaf module within the package — it does
not import `layout.py` or `diagram.py`, so both can safely depend on it.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from compono.schema import Grid, PrimitiveSpec, Shape

from .template import Template
from .types import ConnectorPoints, LayoutResult, Rect

# A connector stopping exactly on a shape's edge reads as glued to it —
# a small visible gap first is the more common diagram convention.
_CONNECTOR_GAP_EMU = 50800  # 4pt


def _iter_shapes(items: list[PrimitiveSpec]) -> list[Shape]:
    shapes: list[Shape] = []
    for item in items:
        if isinstance(item, Shape):
            shapes.append(item)
        elif isinstance(item, Grid):
            shapes.extend(_iter_shapes(item.items))
    return shapes


def _rect_boundary_point(
    rect: Rect, toward: tuple[int, int], gap: float = _CONNECTOR_GAP_EMU
) -> tuple[int, int]:
    """Where a ray from rect's center toward `toward` exits rect's boundary,
    then pulled back `gap` further outward so the connector doesn't touch
    the shape.

    Landing on the shape's edge rather than its center is what stops a
    connector cutting straight across any text centered inside the shape;
    the extra `gap` on top of that is purely a visual nicety.
    """
    cx, cy = rect.x + rect.w / 2, rect.y + rect.h / 2
    dx, dy = toward[0] - cx, toward[1] - cy

    if dx == 0 and dy == 0:
        return (round(cx), round(cy))

    half_w, half_h = rect.w / 2, rect.h / 2
    t_candidates = []
    if dx != 0:
        t_candidates.append(half_w / abs(dx))
    if dy != 0:
        t_candidates.append(half_h / abs(dy))
    t = min(t_candidates)

    dist = math.hypot(dx, dy)
    bx, by = cx + t * dx, cy + t * dy
    ux, uy = dx / dist, dy / dist
    return (round(bx + ux * gap), round(by + uy * gap))


def _rect_bounds(rect: Rect) -> tuple[float, float, float, float]:
    return (rect.x, rect.y, rect.x + rect.w, rect.y + rect.h)


def _segment_crosses_rect(
    p1: tuple[float, float], p2: tuple[float, float], rect: Rect
) -> bool:
    """True if the open segment p1->p2 passes *through* rect's interior
    (Liang-Barsky clipping) — merely touching an edge/corner doesn't count,
    only a real crossing does, so a connector landing exactly on another
    shape's boundary isn't flagged as an obstruction.
    """
    rx0, ry0, rx1, ry1 = _rect_bounds(rect)
    x1, y1 = p1
    x2, y2 = p2
    dx, dy = x2 - x1, y2 - y1
    p = (-dx, dx, -dy, dy)
    q = (x1 - rx0, rx1 - x1, y1 - ry0, ry1 - y1)
    u1, u2 = 0.0, 1.0
    for pi, qi in zip(p, q):
        if pi == 0:
            if qi < 0:
                return False  # parallel to this edge and entirely outside it
            continue
        t = qi / pi
        if pi < 0:
            u1 = max(u1, t)
        else:
            u2 = min(u2, t)
    return u1 < u2


def _path_crosses_any(
    points: Sequence[tuple[float, float]], obstacles: list[Rect]
) -> bool:
    return any(
        _segment_crosses_rect(points[i], points[i + 1], rect)
        for i in range(len(points) - 1)
        for rect in obstacles
    )


def _route_connector(
    from_rect: Rect,
    to_rect: Rect,
    obstacles: list[Rect],
    page_width: int,
    page_height: int,
    gutter: int,
) -> list[tuple[int, int]]:
    """Points a connector should pass through, `from_rect` to `to_rect`.

    Tries the direct edge-to-edge line first (today's behavior, and still
    the common case for two adjacent boxes); if that would visibly cut
    through some other primitive's box, falls back to an orthogonal detour
    through empty gutter space instead — a horizontal or vertical jog that
    routes *around* the obstacle rather than across it. Purely geometric
    (uses only resolved rects), so it applies to any layout, not just a
    grid-shaped diagram.
    """
    fx0, fy0, fx1, fy1 = _rect_bounds(from_rect)
    tx0, ty0, tx1, ty1 = _rect_bounds(to_rect)
    from_center = ((fx0 + fx1) / 2, (fy0 + fy1) / 2)
    to_center = ((tx0 + tx1) / 2, (ty0 + ty1) / 2)

    direct = [
        _rect_boundary_point(from_rect, (round(to_center[0]), round(to_center[1]))),
        _rect_boundary_point(to_rect, (round(from_center[0]), round(from_center[1]))),
    ]
    if not _path_crosses_any(direct, obstacles):
        return direct

    margin = max(1, gutter // 2)
    gap = _CONNECTOR_GAP_EMU

    # Vertical-gutter detours: drop/rise from each box into a shared
    # horizontal strip, slide across, then into the other box. Each edge
    # carries a sign so the stub stops `gap` short of the box, same as the
    # direct-line case, instead of touching it.
    y_candidates: list[tuple[float, float, int, float, int]] = []
    if fy1 <= ty0:
        y_candidates.append(((fy1 + ty0) / 2, fy1, 1, ty0, -1))
    elif ty1 <= fy0:
        y_candidates.append(((ty1 + fy0) / 2, fy0, -1, ty1, 1))
    y_candidates.append((min(fy0, ty0) - margin, fy0, -1, ty0, -1))
    y_candidates.append((max(fy1, ty1) + margin, fy1, 1, ty1, 1))

    for gutter_y, f_edge_y, f_sign, t_edge_y, t_sign in y_candidates:
        if gutter_y < 0 or gutter_y > page_height:
            continue
        path = [
            (from_center[0], f_edge_y + f_sign * gap),
            (from_center[0], gutter_y),
            (to_center[0], gutter_y),
            (to_center[0], t_edge_y + t_sign * gap),
        ]
        if not _path_crosses_any(path, obstacles):
            return [(round(x), round(y)) for x, y in path]

    # Horizontal-gutter detours: same idea, sideways.
    x_candidates: list[tuple[float, float, int, float, int]] = []
    if fx1 <= tx0:
        x_candidates.append(((fx1 + tx0) / 2, fx1, 1, tx0, -1))
    elif tx1 <= fx0:
        x_candidates.append(((tx1 + fx0) / 2, fx0, -1, tx1, 1))
    x_candidates.append((min(fx0, tx0) - margin, fx0, -1, tx0, -1))
    x_candidates.append((max(fx1, tx1) + margin, fx1, 1, tx1, 1))

    for gutter_x, f_edge_x, f_sign, t_edge_x, t_sign in x_candidates:
        if gutter_x < 0 or gutter_x > page_width:
            continue
        path = [
            (f_edge_x + f_sign * gap, from_center[1]),
            (gutter_x, from_center[1]),
            (gutter_x, to_center[1]),
            (t_edge_x + t_sign * gap, to_center[1]),
        ]
        if not _path_crosses_any(path, obstacles):
            return [(round(x), round(y)) for x, y in path]

    # Nothing clean found (dense/unusual layout) — direct line is still the
    # best available fallback rather than raising.
    return direct


def _resolve_connectors(
    body: list[PrimitiveSpec], result: LayoutResult, template: Template
) -> None:
    """Second pass: connectors reference other primitives' already-resolved rects by id."""
    # Every resolved box except grid containers (which draw nothing of their
    # own) is a potential obstacle a connector should route around.
    obstacles_by_id = {
        item_id: rect
        for item_id, rect in result.rects.items()
        if not isinstance(result.items.get(item_id), Grid)
    }

    for shape in _iter_shapes(body):
        if shape.kind != "connector" or shape.connects is None:
            continue
        from_id, to_id = shape.connects.from_id, shape.connects.to_id
        if from_id not in result.rects or to_id not in result.rects:
            raise ValueError(
                f"Connector references unknown id(s): {from_id!r}, {to_id!r}"
            )
        from_rect, to_rect = result.rects[from_id], result.rects[to_id]
        obstacles = [
            rect
            for obstacle_id, rect in obstacles_by_id.items()
            if obstacle_id not in (from_id, to_id)
        ]
        path = _route_connector(
            from_rect,
            to_rect,
            obstacles,
            result.page_width,
            result.page_height,
            template.gutter,
        )
        connector_id = shape.id or f"connector[{from_id}->{to_id}]"
        result.connectors[connector_id] = ConnectorPoints(
            start=path[0], end=path[-1], waypoints=tuple(path[1:-1])
        )
