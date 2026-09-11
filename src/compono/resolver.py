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
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from compono.schema import Grid, Header, PrimitiveBase, PrimitiveSpec, Shape

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
    _resolve_connectors(body, result)

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


def _iter_shapes(items: list[PrimitiveSpec]) -> list[Shape]:
    shapes: list[Shape] = []
    for item in items:
        if isinstance(item, Shape):
            shapes.append(item)
        elif isinstance(item, Grid):
            shapes.extend(_iter_shapes(item.items))
    return shapes


def _rect_boundary_point(rect: Rect, toward: tuple[int, int]) -> tuple[int, int]:
    """Where a ray from rect's center toward `toward` exits rect's boundary.

    Used so a connector's endpoint sits on the shape's edge, never its
    center — a center-to-center line would cut straight across any text
    centered inside the shape.
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

    return (round(cx + t * dx), round(cy + t * dy))


def _resolve_connectors(body: list[PrimitiveSpec], result: LayoutResult) -> None:
    """Second pass: connectors reference other primitives' already-resolved rects by id."""
    for shape in _iter_shapes(body):
        if shape.kind != "connector" or shape.connects is None:
            continue
        from_id, to_id = shape.connects.from_id, shape.connects.to_id
        if from_id not in result.rects or to_id not in result.rects:
            raise ValueError(
                f"Connector references unknown id(s): {from_id!r}, {to_id!r}"
            )
        from_rect, to_rect = result.rects[from_id], result.rects[to_id]
        from_center = (from_rect.x + from_rect.w // 2, from_rect.y + from_rect.h // 2)
        to_center = (to_rect.x + to_rect.w // 2, to_rect.y + to_rect.h // 2)
        connector_id = shape.id or f"connector[{from_id}->{to_id}]"
        result.connectors[connector_id] = ConnectorPoints(
            start=_rect_boundary_point(from_rect, to_center),
            end=_rect_boundary_point(to_rect, from_center),
        )
