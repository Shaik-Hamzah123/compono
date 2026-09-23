"""Unit tests for src/compono/schema.py — the full v1 primitive catalog."""

import pytest
from pydantic import ValidationError

from compono.schema import (
    Chart,
    Diagram,
    Gantt,
    Grid,
    Header,
    Image,
    Sequence,
    Shape,
    Stat,
    Table,
    Text,
)


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


def test_image_placeholder() -> None:
    img = Image(placeholder=True, caption="Team photo goes here")
    assert img.src is None
    assert img.fit == "contain"


def test_image_requires_src_or_placeholder() -> None:
    with pytest.raises(ValidationError):
        Image()  # type: ignore[call-arg]


def test_image_with_src_does_not_need_placeholder() -> None:
    img = Image(src="photo.png")
    assert img.placeholder is False


def test_stat_minimal() -> None:
    s = Stat(value="42%", label="YoY growth")
    assert s.trend is None


def test_table_minimal() -> None:
    t = Table(headers=["Name", "Score"], rows=[["Alice", "90"], ["Bob", "85"]])
    assert len(t.rows) == 2


def test_table_rejects_mismatched_row_length() -> None:
    with pytest.raises(ValidationError):
        Table(headers=["Name", "Score"], rows=[["Alice"]])


def test_table_rejects_empty_headers() -> None:
    # An empty headers list would make the per-cell overflow rect math
    # (render.py's _table_cell_rects) divide by zero.
    with pytest.raises(ValidationError):
        Table(headers=[], rows=[])


def test_table_rejects_empty_rows() -> None:
    with pytest.raises(ValidationError):
        Table(headers=["Name", "Score"], rows=[])


def test_table_accepts_valid_cell_fills() -> None:
    t = Table(
        headers=["Name", "Score"],
        rows=[["Alice", "90"], ["Bob", "85"]],
        cell_fills=[{"row": 0, "col": 1, "fill": "#2A6FDB"}],
    )
    assert t.cell_fills is not None
    assert t.cell_fills[0].row == 0
    assert t.cell_fills[0].col == 1
    assert t.cell_fills[0].fill == "#2A6FDB"


def test_table_rejects_cell_fills_outside_bounds() -> None:
    with pytest.raises(ValidationError):
        Table(
            headers=["Name", "Score"],
            rows=[["Alice", "90"]],
            cell_fills=[{"row": 5, "col": 0, "fill": "#2A6FDB"}],
        )


def test_table_accepts_valid_merges() -> None:
    t = Table(
        headers=["Region", "Q1", "Q2"],
        rows=[["North", "10", "12"], ["North", "11", "13"]],
        merges=[{"row1": 0, "col1": 0, "row2": 1, "col2": 0}],
    )
    assert t.merges is not None
    assert t.merges[0].row2 == 1


def test_table_rejects_merges_outside_bounds() -> None:
    with pytest.raises(ValidationError):
        Table(
            headers=["A", "B"],
            rows=[["1", "2"]],
            merges=[{"row1": 0, "col1": 0, "row2": 5, "col2": 0}],
        )


def test_table_rejects_inverted_merge_range() -> None:
    with pytest.raises(ValidationError):
        Table(
            headers=["A", "B"],
            rows=[["1", "2"], ["3", "4"]],
            merges=[{"row1": 1, "col1": 0, "row2": 0, "col2": 0}],
        )


def test_table_rejects_overlapping_merges() -> None:
    with pytest.raises(ValidationError):
        Table(
            headers=["A", "B"],
            rows=[["1", "2"], ["3", "4"], ["5", "6"]],
            merges=[
                {"row1": 0, "col1": 0, "row2": 1, "col2": 0},
                {"row1": 1, "col1": 0, "row2": 2, "col2": 0},
            ],
        )


def test_sequence_minimal() -> None:
    seq = Sequence(
        steps=[
            {"label": "Discover"},
            {"label": "Design", "description": "Sketch options"},
        ]
    )
    assert seq.orientation == "horizontal"
    assert seq.steps[1].description == "Sketch options"


def test_sequence_rejects_empty_steps() -> None:
    # An empty steps list would make _sequence_step_rects divide by zero.
    with pytest.raises(ValidationError):
        Sequence(steps=[])


def test_chart_minimal() -> None:
    c = Chart(
        chart_type="bar",
        categories=["Q1", "Q2"],
        series=[{"name": "Revenue", "values": [10, 20]}],
    )
    assert c.series[0].values == [10, 20]


def test_chart_rejects_mismatched_series_length() -> None:
    with pytest.raises(ValidationError):
        Chart(
            chart_type="bar",
            categories=["Q1", "Q2"],
            series=[{"name": "Revenue", "values": [10]}],
        )


def test_chart_pie_requires_single_series() -> None:
    with pytest.raises(ValidationError):
        Chart(
            chart_type="pie",
            categories=["A", "B"],
            series=[
                {"name": "S1", "values": [1, 2]},
                {"name": "S2", "values": [3, 4]},
            ],
        )


def test_grid_accepts_all_new_primitive_types() -> None:
    g = Grid(
        items=[
            {"primitive": "image", "placeholder": True},
            {"primitive": "stat", "value": "1", "label": "x"},
            {"primitive": "table", "headers": ["a"], "rows": [["1"]]},
            {"primitive": "sequence", "steps": [{"label": "step"}]},
            {
                "primitive": "chart",
                "chart_type": "line",
                "categories": ["a"],
                "series": [{"name": "s", "values": [1]}],
            },
        ]
    )
    assert len(g.items) == 5


def test_diagram_minimal_defaults_to_linear_chain() -> None:
    d = Diagram(nodes=[{"label": "A"}, {"label": "B"}, {"label": "C"}])
    assert d.primitive == "diagram"
    assert d.orientation == "vertical"
    assert d.node_kind == "rounded_rect"
    assert d.edges is None


def test_diagram_accepts_explicit_edges_by_id() -> None:
    d = Diagram(
        nodes=[{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
        edges=[{"from": "a", "to": "b"}],
    )
    assert d.edges is not None
    assert d.edges[0].from_ == "a"
    assert d.edges[0].to == "b"


def test_diagram_accepts_explicit_edges_by_positional_index() -> None:
    d = Diagram(
        nodes=[{"label": "A"}, {"label": "B"}, {"label": "C"}],
        edges=[{"from": "0", "to": "2"}],
    )
    assert d.edges is not None
    assert d.edges[0].from_ == "0"


def test_diagram_per_node_style_overrides() -> None:
    d = Diagram(
        nodes=[{"label": "A", "kind": "oval", "fill": "#FF0000"}, {"label": "B"}],
        node_kind="rect",
        node_fill="#00FF00",
    )
    assert d.nodes[0].kind == "oval"
    assert d.nodes[0].fill == "#FF0000"
    assert d.nodes[1].kind is None  # falls back to node_kind at layout time
    assert d.node_kind == "rect"


def test_diagram_rejects_edge_referencing_unknown_node() -> None:
    with pytest.raises(ValidationError):
        Diagram(nodes=[{"label": "A"}], edges=[{"from": "0", "to": "does-not-exist"}])


def test_diagram_rejects_empty_nodes() -> None:
    with pytest.raises(ValidationError):
        Diagram(nodes=[])


def test_gantt_minimal() -> None:
    g = Gantt(
        unit_labels=["Wk 1", "Wk 2", "Wk 3"],
        tasks=[{"label": "Discovery", "start_unit": 0, "duration_units": 2}],
    )
    assert g.primitive == "gantt"
    assert g.task_fill == "#2A6FDB"
    assert g.tasks[0].fill is None


def test_gantt_per_task_fill_override() -> None:
    g = Gantt(
        unit_labels=["Wk 1", "Wk 2"],
        tasks=[{"label": "A", "start_unit": 0, "duration_units": 1, "fill": "#D9534F"}],
    )
    assert g.tasks[0].fill == "#D9534F"


def test_gantt_rejects_task_extending_past_unit_labels() -> None:
    with pytest.raises(ValidationError):
        Gantt(
            unit_labels=["Wk 1", "Wk 2"],
            tasks=[{"label": "Too long", "start_unit": 1, "duration_units": 2}],
        )


def test_gantt_rejects_empty_tasks() -> None:
    with pytest.raises(ValidationError):
        Gantt(unit_labels=["Wk 1"], tasks=[])


def test_gantt_rejects_empty_unit_labels() -> None:
    with pytest.raises(ValidationError):
        Gantt(
            unit_labels=[], tasks=[{"label": "A", "start_unit": 0, "duration_units": 1}]
        )
