"""Unit tests for src/compono/resolver.py — pure functions, no rendering."""

import pytest

from compono.resolver import (
    DEFAULT_TEMPLATE_PATH,
    Rect,
    Template,
    resolve_slide,
)
from compono.schema import Grid, Header, Shape, Text


@pytest.fixture
def template() -> Template:
    return Template.from_yaml(DEFAULT_TEMPLATE_PATH)


def test_template_loads_from_default_yaml(template: Template) -> None:
    assert template.page_width == round(13.333 * 914400)
    assert template.page_height == 7.5 * 914400
    assert template.gutter == round(0.2 * 914400)


def test_template_loads_font_family_from_default_yaml(template: Template) -> None:
    assert template.font_family == "Calibri"


def test_template_from_name_resolves_a_bundled_template() -> None:
    assert Template.from_name("default").font_family == "Calibri"
    assert Template.from_name("modern").font_family == "Georgia"


def test_template_from_name_raises_on_unknown_name() -> None:
    with pytest.raises(ValueError, match="No template named 'nonexistent'"):
        Template.from_name("nonexistent")


def test_resolve_slide_with_header_places_header_above_body(template: Template) -> None:
    header = Header(title="Q3 Results")
    body = [Text(content="Body copy")]

    result = resolve_slide(template, header=header, body=body)

    header_rect = result.rects["header"]
    body_rect = result.rects["body[0]"]
    assert header_rect.y == template.margin_top
    assert body_rect.y == header_rect.y + header_rect.h
    assert header_rect.x == body_rect.x == template.margin_left


def test_resolve_slide_without_header_starts_body_at_margin(template: Template) -> None:
    body = [Text(content="Only content")]
    result = resolve_slide(template, header=None, body=body)
    assert "header" not in result.rects
    assert result.rects["body[0]"].y == template.margin_top


def test_resolve_slide_body_items_share_height_with_gutter(template: Template) -> None:
    body = [Text(content="A"), Text(content="B"), Text(content="C")]
    result = resolve_slide(template, body=body)

    r0, r1, r2 = (result.rects[f"body[{i}]"] for i in range(3))
    assert r0.h == r1.h == r2.h
    assert r1.y == r0.y + r0.h + template.gutter
    assert r2.y == r1.y + r1.h + template.gutter


def test_resolve_slide_raises_when_no_room_for_body() -> None:
    tiny = Template(
        page_width=100,
        page_height=100,
        margin_top=40,
        margin_right=10,
        margin_bottom=40,
        margin_left=10,
        header_height=30,
        footer_height=30,
        gutter=5,
    )
    with pytest.raises(ValueError, match="no room for body"):
        resolve_slide(tiny, body=[Text(content="x")])


def test_grid_row_layout_auto_columns(template: Template) -> None:
    grid = Grid(items=[{"primitive": "shape", "kind": "rect"} for _ in range(4)])
    result = resolve_slide(template, body=[grid])

    rects = [result.rects[f"body[0].items[{i}]"] for i in range(4)]
    # auto columns in row direction => all 4 side by side, same row
    assert all(r.y == rects[0].y for r in rects)
    assert all(r.h == rects[0].h for r in rects)
    assert rects[1].x > rects[0].x


def test_grid_explicit_columns_wraps_rows(template: Template) -> None:
    grid = Grid(
        columns=2,
        items=[{"primitive": "shape", "kind": "rect"} for _ in range(4)],
    )
    result = resolve_slide(template, body=[grid])

    top_row = [result.rects[f"body[0].items[{i}]"] for i in (0, 1)]
    bottom_row = [result.rects[f"body[0].items[{i}]"] for i in (2, 3)]
    assert top_row[0].y == top_row[1].y
    assert bottom_row[0].y == bottom_row[1].y
    assert bottom_row[0].y > top_row[0].y
    assert top_row[0].x == bottom_row[0].x


def test_nested_grid_ids_are_prefixed(template: Template) -> None:
    grid = Grid(
        items=[
            {"primitive": "grid", "items": [{"primitive": "shape", "kind": "rect"}]},
        ]
    )
    result = resolve_slide(template, body=[grid])
    assert "body[0].items[0].items[0]" in result.rects


def test_layout_result_items_pair_id_with_originating_primitive(
    template: Template,
) -> None:
    header = Header(title="Q3 Results")
    body_text = Text(content="Body copy")
    result = resolve_slide(template, header=header, body=[body_text])

    assert result.items["header"] is header
    assert result.items["body[0]"] is body_text


def test_explicit_id_overrides_generated_id(template: Template) -> None:
    body = [Text(id="my-text", content="Hello")]
    result = resolve_slide(template, body=body)
    assert "my-text" in result.rects
    assert "body[0]" not in result.rects


def test_parents_records_real_containment_even_with_explicit_ids(
    template: Template,
) -> None:
    grid = Grid(
        id="my-grid",
        items=[
            {"primitive": "shape", "id": "box-a", "kind": "rect"},
            {"primitive": "shape", "kind": "rect"},
        ],
    )
    result = resolve_slide(template, body=[grid])
    assert result.parents["box-a"] == "my-grid"
    assert result.parents["my-grid.items[1]"] == "my-grid"
    assert "body[0]" not in result.parents  # top-level items have no parent


def test_connector_resolves_start_and_end_points(template: Template) -> None:
    body = [
        Shape(id="box-a", kind="rect"),
        Shape(id="box-b", kind="rect"),
        Shape(kind="connector", connects={"from_id": "box-a", "to_id": "box-b"}),
    ]
    result = resolve_slide(template, body=body)

    connector = result.connectors["connector[box-a->box-b]"]
    a, b = result.rects["box-a"], result.rects["box-b"]
    # box-a sits above box-b (stacked vertically, same width) — the connector
    # must join their *edges* (a's bottom, b's top), never their centers,
    # since a center-to-center line would cut across any text inside either.
    assert connector.start == (a.x + a.w // 2, a.y + a.h)
    assert connector.end == (b.x + b.w // 2, b.y)


def test_connector_between_side_by_side_shapes_joins_vertical_edges(
    template: Template,
) -> None:
    """Reproduces the real bug found via screenshot review: two shapes side by
    side (via a grid) with a connector must join their facing vertical
    edges — not their centers, which would cut through each shape's own text.
    """
    grid = Grid(
        columns=2,
        items=[
            {"primitive": "shape", "id": "left-box", "kind": "rect"},
            {"primitive": "shape", "id": "right-box", "kind": "rect"},
        ],
    )
    body = [
        grid,
        Shape(kind="connector", connects={"from_id": "left-box", "to_id": "right-box"}),
    ]
    result = resolve_slide(template, body=body)

    left, right = result.rects["left-box"], result.rects["right-box"]
    connector = result.connectors["connector[left-box->right-box]"]

    assert connector.start == (left.x + left.w, left.y + left.h // 2)
    assert connector.end == (right.x, right.y + right.h // 2)


def test_connector_shapes_do_not_consume_a_body_slot(template: Template) -> None:
    """A connector draws nothing at its own position — only layout.connectors
    (computed from the *other* primitives it references) gets rendered. Mixing
    several connectors in with real body items must not shrink those items'
    share of the available height, the way an extra real sibling would.
    """
    without_connectors = [Shape(id="a", kind="rect"), Shape(id="b", kind="rect")]
    baseline = resolve_slide(template, body=without_connectors)

    with_connectors = [
        Shape(id="a", kind="rect"),
        Shape(id="b", kind="rect"),
        Shape(kind="connector", connects={"from_id": "a", "to_id": "b"}),
        Shape(kind="connector", connects={"from_id": "a", "to_id": "b"}),
        Shape(kind="connector", connects={"from_id": "a", "to_id": "b"}),
    ]
    result = resolve_slide(template, body=with_connectors)

    # Adding 3 more connector siblings must not change "a"/"b"'s height at
    # all — if connectors wrongly counted toward the slot split, 5 siblings
    # would give each real item 2/5 the height instead of 1/2.
    assert result.rects["a"].h == baseline.rects["a"].h
    assert result.rects["b"].h == baseline.rects["b"].h


def test_connector_unknown_id_raises(template: Template) -> None:
    body = [
        Shape(
            kind="connector", connects={"from_id": "missing", "to_id": "also-missing"}
        )
    ]
    with pytest.raises(ValueError, match="unknown id"):
        resolve_slide(template, body=body)


def test_rect_is_a_plain_value_object() -> None:
    r = Rect(1, 2, 3, 4)
    assert (r.x, r.y, r.w, r.h) == (1, 2, 3, 4)
