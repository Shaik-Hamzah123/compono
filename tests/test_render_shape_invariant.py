"""Golden/invariant tests: render an example spec, reopen the .pptx with
python-pptx, and assert real structural properties — never pixel-diffing.

Covers the non-negotiable invariant (COMPONO_PLAN.md section 3): every
primitive renders as a genuine, editable OOXML object (p:sp, p:pic,
p:graphicFrame) — never a flattened image or embedded video/audio. Also
checks that resolved rects don't overlap their non-descendant siblings, and
that real text/table/chart data round-trips into the file rather than being
rasterized.
"""

import json
from itertools import combinations
from pathlib import Path

import pytest
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

from compono.render import render_deck
from compono.resolver import Rect

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"

# Shape types this library is allowed to ever produce. Anything else appearing
# in a rendered slide is itself a test failure — new render code must map
# onto one of these, never a rasterized picture.
_ALLOWED_SHAPE_TYPES = {
    MSO_SHAPE_TYPE.TEXT_BOX,
    MSO_SHAPE_TYPE.AUTO_SHAPE,
    MSO_SHAPE_TYPE.TABLE,
    MSO_SHAPE_TYPE.CHART,
    MSO_SHAPE_TYPE.LINE,
}
_FORBIDDEN_SHAPE_TYPES = {
    MSO_SHAPE_TYPE.PICTURE,
    MSO_SHAPE_TYPE.MEDIA,
    MSO_SHAPE_TYPE.EMBEDDED_OLE_OBJECT,
}


def _example_specs() -> list[tuple[str, dict]]:
    return [
        (path.name, json.loads(path.read_text(encoding="utf-8")))
        for path in sorted(EXAMPLES_DIR.glob("*.json"))
    ]


def _rects_overlap(a: Rect, b: Rect) -> bool:
    return a.x < b.x + b.w and b.x < a.x + a.w and a.y < b.y + b.h and b.y < a.y + a.h


def _is_ancestor(parents: dict[str, str], parent_id: str, other_id: str) -> bool:
    """Walk other_id's real parent chain (resolver.LayoutResult.parents) — never guess
    from id string shape, since an explicit `id` override breaks any prefix convention.
    """
    current = other_id
    while True:
        if current == parent_id:
            return True
        next_parent = parents.get(current)
        if next_parent is None:
            return False
        current = next_parent


@pytest.mark.parametrize(
    "name,spec", _example_specs(), ids=[n for n, _ in _example_specs()]
)
def test_every_shape_is_a_real_editable_object(
    name: str, spec: dict, tmp_path: Path
) -> None:
    """Non-negotiable invariant: real shapes only, never a picture/video (COMPONO_PLAN.md section 3)."""
    output = tmp_path / f"{name}.pptx"
    render_deck(spec, output)

    prs = Presentation(str(output))
    for slide in prs.slides:
        shape_types = {shape.shape_type for shape in slide.shapes}
        assert not (shape_types & _FORBIDDEN_SHAPE_TYPES), (
            f"{name}: found forbidden shape type(s) {shape_types & _FORBIDDEN_SHAPE_TYPES}"
        )
        assert shape_types <= _ALLOWED_SHAPE_TYPES, (
            f"{name}: unexpected shape type(s) {shape_types - _ALLOWED_SHAPE_TYPES}"
        )


@pytest.mark.parametrize(
    "name,spec", _example_specs(), ids=[n for n, _ in _example_specs()]
)
def test_resolved_rects_do_not_overlap_non_descendants(
    name: str, spec: dict, tmp_path: Path
) -> None:
    """A grid's own rect legitimately contains its children's rects — that's containment,
    not overlap. Only non-ancestor/descendant pairs must be disjoint.
    """
    output = tmp_path / f"{name}.pptx"
    report = render_deck(spec, output)

    for layout in report.actual_layout:
        ids = list(layout.rects.keys())
        for id_a, id_b in combinations(ids, 2):
            if _is_ancestor(layout.parents, id_a, id_b) or _is_ancestor(
                layout.parents, id_b, id_a
            ):
                continue
            assert not _rects_overlap(layout.rects[id_a], layout.rects[id_b]), (
                f"{name}: {id_a!r} and {id_b!r} overlap and are not nested"
            )


def test_header_title_text_round_trips_as_real_text(tmp_path: Path) -> None:
    spec = json.loads((EXAMPLES_DIR / "full_catalog.json").read_text(encoding="utf-8"))
    output = tmp_path / "full_catalog.pptx"
    render_deck(spec, output)

    prs = Presentation(str(output))
    slide = next(iter(prs.slides))
    all_text = " ".join(
        run.text
        for shape in slide.shapes
        if shape.has_text_frame
        for paragraph in shape.text_frame.paragraphs
        for run in paragraph.runs
    )
    assert spec["slides"][0]["header"]["title"] in all_text


def test_table_data_round_trips_into_a_real_table(tmp_path: Path) -> None:
    spec = json.loads((EXAMPLES_DIR / "full_catalog.json").read_text(encoding="utf-8"))
    output = tmp_path / "full_catalog.pptx"
    render_deck(spec, output)

    table_spec = next(
        p
        for slide in spec["slides"]
        for p in slide["body"]
        if p["primitive"] == "table"
    )

    prs = Presentation(str(output))
    table_shape = next(
        shape for slide in prs.slides for shape in slide.shapes if shape.has_table
    )
    table = table_shape.table

    header_row = [table.cell(0, c).text for c in range(len(table_spec["headers"]))]
    assert header_row == table_spec["headers"]

    for r, expected_row in enumerate(table_spec["rows"], start=1):
        actual_row = [table.cell(r, c).text for c in range(len(expected_row))]
        assert actual_row == expected_row


def test_chart_data_round_trips_into_a_real_chart(tmp_path: Path) -> None:
    spec = json.loads((EXAMPLES_DIR / "full_catalog.json").read_text(encoding="utf-8"))
    output = tmp_path / "full_catalog.pptx"
    render_deck(spec, output)

    chart_spec = next(
        p
        for slide in spec["slides"]
        for p in slide["body"]
        if p["primitive"] == "chart"
    )

    prs = Presentation(str(output))
    chart_shape = next(
        shape for slide in prs.slides for shape in slide.shapes if shape.has_chart
    )
    chart = chart_shape.chart

    assert list(chart.plots[0].categories) == chart_spec["categories"]
    series = list(chart.series)
    assert [s.name for s in series] == [s["name"] for s in chart_spec["series"]]
    for s, expected in zip(series, chart_spec["series"], strict=True):
        assert list(s.values) == expected["values"]
