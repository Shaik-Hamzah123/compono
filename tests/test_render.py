"""Unit/integration tests for src/compono/render.py and cli.py.

Covers the two public verbs (render_deck/validate) end-to-end for the v1
primitive slice (header, text, grid, shape), plus a CLI smoke test against
examples/minimal.json.
"""

import json
from pathlib import Path

import pytest
from pptx import Presentation

from compono.cli import main as cli_main
from compono.render import DeckValidationError, render_deck, validate
from compono.resolver import Template

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"
MINIMAL_SPEC = json.loads((EXAMPLES_DIR / "minimal.json").read_text(encoding="utf-8"))
FULL_CATALOG_SPEC = json.loads(
    (EXAMPLES_DIR / "full_catalog.json").read_text(encoding="utf-8")
)


def test_validate_accepts_minimal_spec() -> None:
    report = validate(MINIMAL_SPEC)
    assert report.valid is True
    assert report.errors == []


def test_validate_rejects_malformed_spec() -> None:
    report = validate(
        {"slides": [{"body": [{"primitive": "header"}]}]}
    )  # missing required title
    assert report.valid is False
    assert report.errors[0]["error"] is not None


def test_validate_flags_unknown_connector_id() -> None:
    spec = {
        "slides": [
            {
                "body": [
                    {
                        "primitive": "shape",
                        "kind": "connector",
                        "connects": {"from_id": "x", "to_id": "y"},
                    },
                ]
            }
        ]
    }
    report = validate(spec)
    assert report.valid is False
    assert any(e["error"] == "layout" for e in report.errors)


def test_render_deck_writes_a_real_pptx(tmp_path: Path) -> None:
    output = tmp_path / "deck.pptx"
    report = render_deck(MINIMAL_SPEC, output)

    assert report.pptx_path == output
    assert output.exists()
    assert len(report.actual_layout) == 1

    prs = Presentation(str(output))
    slides = list(prs.slides)
    assert len(slides) == 1

    slide = slides[0]
    # Non-negotiable invariant: every primitive is a real, editable shape —
    # never a picture or embedded video (COMPONO_PLAN.md section 3).
    shape_types = {shape.shape_type for shape in slide.shapes}
    from pptx.enum.shapes import MSO_SHAPE_TYPE

    assert MSO_SHAPE_TYPE.PICTURE not in shape_types
    # header textbox + bullets textbox + 2 shapes + 1 connector = 5 shapes
    assert len(slide.shapes) == 5


def test_render_deck_raises_on_invalid_spec(tmp_path: Path) -> None:
    with pytest.raises(DeckValidationError):
        render_deck(
            {"slides": [{"body": [{"primitive": "header"}]}]}, tmp_path / "out.pptx"
        )


def test_render_deck_respects_explicit_template(tmp_path: Path) -> None:
    template = Template.from_yaml()
    output = tmp_path / "deck.pptx"
    render_deck(MINIMAL_SPEC, output, template=template)
    prs = Presentation(str(output))
    assert prs.slide_width == template.page_width
    assert prs.slide_height == template.page_height


def test_cli_validate_smoke(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = cli_main(["validate", str(EXAMPLES_DIR / "minimal.json")])
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert exit_code == 0
    assert result["valid"] is True


def test_cli_render_smoke(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    output = tmp_path / "cli_deck.pptx"
    exit_code = cli_main(
        ["render", str(EXAMPLES_DIR / "minimal.json"), "-o", str(output)]
    )
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert exit_code == 0
    assert result["pptx_path"] == str(output)
    assert output.exists()


def test_validate_accepts_full_catalog_spec() -> None:
    report = validate(FULL_CATALOG_SPEC)
    assert report.valid is True
    assert report.errors == []


def test_render_deck_writes_all_primitive_types(tmp_path: Path) -> None:
    from pptx.enum.shapes import MSO_SHAPE_TYPE

    output = tmp_path / "full_catalog.pptx"
    report = render_deck(FULL_CATALOG_SPEC, output)

    prs = Presentation(str(output))
    assert len(list(prs.slides)) == 3
    shape_types = {shape.shape_type for slide in prs.slides for shape in slide.shapes}

    # Non-negotiable invariant: real, editable shapes only — table and chart
    # are real OOXML graphicFrames, never a flattened picture or video.
    assert MSO_SHAPE_TYPE.PICTURE not in shape_types
    assert MSO_SHAPE_TYPE.TABLE in shape_types
    assert MSO_SHAPE_TYPE.CHART in shape_types

    # image placeholder records a manifest entry instead of a real picture
    assert len(report.manifest) == 1
    assert report.manifest[0]["caption"] == "Team photo goes here"
    assert "rect" in report.manifest[0]


def test_image_placeholder_caption_has_a_visible_font_color(tmp_path: Path) -> None:
    from pptx.dml.color import RGBColor

    output = tmp_path / "full_catalog.pptx"
    render_deck(FULL_CATALOG_SPEC, output)

    prs = Presentation(str(output))
    placeholder = next(
        shape
        for slide in prs.slides
        for shape in slide.shapes
        if shape.has_text_frame and "Team photo goes here" in shape.text_frame.text
    )
    color = placeholder.text_frame.paragraphs[0].font.color.rgb
    assert color == RGBColor(0x66, 0x66, 0x66)


def test_render_deck_sequence_draws_connectors_between_steps(tmp_path: Path) -> None:
    from pptx.enum.shapes import MSO_SHAPE_TYPE

    output = tmp_path / "full_catalog.pptx"
    render_deck(FULL_CATALOG_SPEC, output)

    prs = Presentation(str(output))
    # 3 sequence steps -> 2 connectors between them (plus none from other primitives here)
    connectors = [
        shape
        for slide in prs.slides
        for shape in slide.shapes
        if shape.shape_type == MSO_SHAPE_TYPE.LINE
    ]
    assert len(connectors) == 2


def test_render_deck_sequence_connectors_run_through_the_gutter_not_the_boxes(
    tmp_path: Path,
) -> None:
    """Connectors must join box edges, never centers — a center-to-center line

    would cross directly over each step's own label text.
    """
    output = tmp_path / "full_catalog.pptx"
    render_deck(FULL_CATALOG_SPEC, output)

    prs = Presentation(str(output))
    step_boxes = [
        shape
        for slide in prs.slides
        for shape in slide.shapes
        if shape.has_text_frame
        and shape.text_frame.text.splitlines()[0] in ("Discover", "Design", "Ship")
    ]
    step_boxes.sort(key=lambda s: s.left)
    assert len(step_boxes) == 3

    connectors = sorted(
        (
            shape
            for slide in prs.slides
            for shape in slide.shapes
            if shape.shape_type.name == "LINE"
        ),
        key=lambda s: s.left,
    )
    assert len(connectors) == 2

    for box, connector in zip(step_boxes, connectors, strict=False):
        box_right_edge = box.left + box.width
        assert connector.left == box_right_edge
        box_vertical_center = box.top + box.height // 2
        assert connector.top == box_vertical_center
