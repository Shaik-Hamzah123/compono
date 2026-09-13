"""Layout resolver: directional box model (CSS-flexbox mental model).

Computes real EMU positions from primitive specs so the agent never writes
raw x/y/w/h coordinates (COMPONO_PLAN.md section 6).

v1 slice: header, text, grid, shape. Body primitives share the available
body height equally (a flex-equal fallback) — content-based height
estimation via font metrics lands in Step 3 and will replace this fallback
for primitives that don't request an explicit weight.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from compono.schema import (
    Diagram,
    Grid,
    Header,
    PrimitiveBase,
    PrimitiveSpec,
    Shape,
    ShapeText,
)

EMU_PER_INCH = 914400

DEFAULT_TEMPLATE_PATH = Path(__file__).parent / "templates" / "default.yaml"


def _in_to_emu(value: float) -> int:
    return round(value * EMU_PER_INCH)


@dataclass(frozen=True)
class Template:
    """Resolved layout constants, in EMU, for one template config."""

    page_width: int
    page_height: int
    margin_top: int
    margin_right: int
    margin_bottom: int
    margin_left: int
    header_height: int
    footer_height: int
    gutter: int
    font_family: str = "Calibri"

    @classmethod
    def from_yaml(cls, path: Path = DEFAULT_TEMPLATE_PATH) -> Template:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        page = data["page"]
        margin = data["margin_in"]
        return cls(
            page_width=_in_to_emu(page["width_in"]),
            page_height=_in_to_emu(page["height_in"]),
            margin_top=_in_to_emu(margin["top"]),
            margin_right=_in_to_emu(margin["right"]),
            margin_bottom=_in_to_emu(margin["bottom"]),
            margin_left=_in_to_emu(margin["left"]),
            header_height=_in_to_emu(data["header"]["height_in"]),
            footer_height=_in_to_emu(data["footer"]["height_in"]),
            gutter=_in_to_emu(data["gutter_in"]),
            font_family=data.get("font_family", "Calibri"),
        )

    @classmethod
    def from_name(cls, name: str) -> Template:
        """Resolve a `Deck.template` name (schema.py) to a bundled templates/*.yaml.

        `Deck.template` has always been agent-facing in the schema, but was
        never actually wired to anything until this — every render used
        `from_yaml()`'s hardcoded default regardless of what the spec said.
        """
        path = DEFAULT_TEMPLATE_PATH.parent / f"{name}.yaml"
        if not path.exists():
            available = sorted(
                p.stem for p in DEFAULT_TEMPLATE_PATH.parent.glob("*.yaml")
            )
            raise ValueError(
                f"No template named {name!r} under templates/. "
                f"Available: {', '.join(available)}."
            )
        return cls.from_yaml(path)


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    w: int
    h: int


@dataclass(frozen=True)
class ConnectorPoints:
    start: tuple[int, int]
    end: tuple[int, int]
    # Intermediate bend points, in order from `start` to `end`, for a
    # connector routed around an obstacle (empty for a clean direct line —
    # `.start`/`.end` alone still describe that common case). render.py draws
    # one straight segment per consecutive pair in (start, *waypoints, end).
    waypoints: tuple[tuple[int, int], ...] = ()


@dataclass
class LayoutResult:
    page_width: int
    page_height: int
    rects: dict[str, Rect] = field(default_factory=dict)
    connectors: dict[str, ConnectorPoints] = field(default_factory=dict)
    # The primitive that produced each rect, keyed by the same id — a single
    # source of truth so render.py never has to re-derive the id scheme above.
    items: dict[str, PrimitiveBase] = field(default_factory=dict)
    # Real parent-child id relationships (child id -> parent grid's id), captured
    # during grid recursion — a grid's rect legitimately contains its children's
    # rects, so consumers checking for overlap need real containment, not a
    # string-prefix guess (explicit `id` overrides break any such guess).
    parents: dict[str, str] = field(default_factory=dict)


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


def _diagram_node_id(diagram: Diagram, prefix: str, index: int) -> str:
    """Same "explicit id, else synthesized from position" scheme every
    other container (grid, body stack) uses — `edges` and
    `_resolve_diagram_connectors` must derive the exact same id.
    """
    return diagram.nodes[index].id or f"{prefix}.nodes[{index}]"


def _resolve_diagram_node_ref(diagram: Diagram, prefix: str, ref: str) -> str:
    """Resolve one edge's `from`/`to` string (a node's explicit `id`, or its
    0-based index) to that node's final, resolved id. Schema.py's own
    `_edges_reference_real_nodes` validator already rejects a spec with a
    bad reference before this ever runs, but resolver.py raises its own
    clear error too, matching `_resolve_connectors`'s existing convention.
    """
    for i, node in enumerate(diagram.nodes):
        if node.id == ref:
            return _diagram_node_id(diagram, prefix, i)
    if ref.isdigit() and int(ref) < len(diagram.nodes):
        return _diagram_node_id(diagram, prefix, int(ref))
    raise ValueError(f"Diagram edge references unknown node {ref!r}.")


def _layout_diagram(
    diagram: Diagram,
    rect: Rect,
    template: Template,
    result: LayoutResult,
    prefix: str,
) -> None:
    """Places each node as a synthesized `shape` (real-shape invariant
    applies unchanged) stacked along `orientation`, evenly split — same
    col_w/row_h math as `_layout_grid`, specialized to a single row/column.
    Edges are resolved separately, in `_resolve_diagram_connectors`, once
    every slide primitive (not just this diagram's own nodes) has a
    resolved rect to route around.
    """
    n = len(diagram.nodes)
    if n == 0:
        return

    vertical = diagram.orientation == "vertical"
    columns = 1 if vertical else n
    rows = n if vertical else 1
    col_w = (rect.w - template.gutter * (columns - 1)) // columns
    row_h = (rect.h - template.gutter * (rows - 1)) // rows

    for i, node in enumerate(diagram.nodes):
        r, c = (i, 0) if vertical else (0, i)
        x = rect.x + c * (col_w + template.gutter)
        y = rect.y + r * (row_h + template.gutter)
        node_id = _diagram_node_id(diagram, prefix, i)
        result.parents[node_id] = prefix
        synthetic_shape = Shape(
            id=node_id,
            kind=node.kind or diagram.node_kind,
            fill=node.fill or diagram.node_fill,
            text=ShapeText(content=node.label),
        )
        _place_item(
            synthetic_shape, Rect(x, y, col_w, row_h), template, result, node_id
        )


def _resolve_diagram_connectors(result: LayoutResult, template: Template) -> None:
    """Second pass, run alongside `_resolve_connectors`: routes each
    diagram's edges (explicit, or a default linear chain) through the same
    obstacle-avoiding `_route_connector` used by shape(kind='connector').
    Keyed off `result.items` (post-placement) rather than the pre-layout
    body tree, since a diagram's node ids depend on its own resolved id —
    unknown until after `_layout_stack` has already run.
    """
    obstacles_by_id = {
        item_id: rect
        for item_id, rect in result.rects.items()
        if not isinstance(result.items.get(item_id), (Grid, Diagram))
    }

    for prefix, diagram in list(result.items.items()):
        if not isinstance(diagram, Diagram):
            continue
        n = len(diagram.nodes)
        edges = (
            [(edge.from_, edge.to) for edge in diagram.edges]
            if diagram.edges is not None
            else [(str(i), str(i + 1)) for i in range(n - 1)]
        )
        for i, (from_ref, to_ref) in enumerate(edges):
            from_id = _resolve_diagram_node_ref(diagram, prefix, from_ref)
            to_id = _resolve_diagram_node_ref(diagram, prefix, to_ref)
            from_rect, to_rect = result.rects[from_id], result.rects[to_id]
            obstacles = [
                obstacle_rect
                for obstacle_id, obstacle_rect in obstacles_by_id.items()
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
            edge_id = f"{prefix}.edges[{i}]"
            result.connectors[edge_id] = ConnectorPoints(
                start=path[0], end=path[-1], waypoints=tuple(path[1:-1])
            )


def _iter_shapes(items: list[PrimitiveSpec]) -> list[Shape]:
    shapes: list[Shape] = []
    for item in items:
        if isinstance(item, Shape):
            shapes.append(item)
        elif isinstance(item, Grid):
            shapes.extend(_iter_shapes(item.items))
    return shapes


# A connector stopping exactly on a shape's edge reads as glued to it —
# a small visible gap first is the more common diagram convention.
_CONNECTOR_GAP_EMU = 50800  # 4pt


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
