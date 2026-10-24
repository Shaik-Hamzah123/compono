"""`diagram` layout: nodes synthesized as real `shape` primitives, edges
routed via the same obstacle-avoiding router `shape(kind="connector")`
uses (`connectors.py`'s `_route_connector`).
"""

from __future__ import annotations

from compono.schema import Diagram, Grid, Shape, ShapeText

from .connectors import _route_connector
from .template import Template
from .types import ConnectorPoints, LayoutResult, Rect


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
    # Deferred import: `layout.py` imports this module (to dispatch to
    # `_layout_diagram` from `_place_item`), so importing `_place_item` at
    # this module's top would be circular. Safe here since both modules
    # are fully loaded by the time this function actually runs.
    from .layout import _place_item

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
