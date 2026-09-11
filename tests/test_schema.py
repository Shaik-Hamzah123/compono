"""Unit tests for src/compono/schema.py — header, text, grid, shape primitives."""

import pytest
from pydantic import ValidationError

from compono.schema import Grid, Header, Shape, Text


def test_header_minimal() -> None:
    h = Header(title="Q3 Results")
    assert h.primitive == "header"
    assert h.align == "left"
    assert h.subtitle is None


def test_header_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        Header(title="Q3 Results", subtitel="typo")  # type: ignore[call-arg]


def test_header_requires_title() -> None:
    with pytest.raises(ValidationError):
        Header()  # type: ignore[call-arg]


def test_text_paragraph_mode() -> None:
    t = Text(content="Some prose.")
    assert t.mode == "paragraph"
    assert t.columns == 1


def test_text_bullets_mode() -> None:
    t = Text(mode="bullets", content=["one", "two"], emphasis_indices=[0])
    assert t.content == ["one", "two"]
    assert t.emphasis_indices == [0]


def test_text_columns_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        Text(content="x", columns=0)


def test_shape_minimal() -> None:
    s = Shape(kind="rect", fill="#FFFFFF")
    assert s.primitive == "shape"
    assert s.connects is None


def test_shape_with_text() -> None:
    s = Shape(kind="oval", text={"content": "Hello"})
    assert s.text is not None
    assert s.text.content == "Hello"
    assert s.text.align == "left"
    assert s.text.autofit is True


def test_shape_connector() -> None:
    s = Shape(kind="connector", connects={"from_id": "a", "to_id": "b"})
    assert s.connects is not None
    assert s.connects.from_id == "a"
    assert s.connects.to_id == "b"


def test_grid_recursive_items() -> None:
    g = Grid(
        items=[
            {"primitive": "header", "title": "Nested header"},
            {"primitive": "text", "content": "Nested text"},
            {"primitive": "grid", "items": [{"primitive": "shape", "kind": "rect"}]},
        ]
    )
    assert g.primitive == "grid"
    assert len(g.items) == 3
    assert isinstance(g.items[0], Header)
    assert isinstance(g.items[1], Text)
    assert isinstance(g.items[2], Grid)
    assert isinstance(g.items[2].items[0], Shape)


def test_grid_defaults() -> None:
    g = Grid(items=[{"primitive": "shape", "kind": "rect"}])
    assert g.columns == "auto"
    assert g.direction == "row"
    assert g.align == "stretch"
    assert g.justify == "start"


def test_grid_rejects_unknown_primitive_type() -> None:
    with pytest.raises(ValidationError):
        Grid(items=[{"primitive": "not_a_real_primitive"}])


def test_json_schema_generation() -> None:
    schema = Header.model_json_schema()
    assert schema["properties"]["title"]["description"].startswith("Keep under")
