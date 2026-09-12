"""Schema-level tests for compono's docx primitive catalog (docx_schema.py).

Mirrors tests/test_schema.py's style: pydantic validation errors, cross-
field validators, and discriminated-union dispatch.
"""

import pytest
from pydantic import ValidationError

from compono.docx_schema import (
    BulletList,
    DocChart,
    DocImage,
    DocTable,
    DocxDoc,
    Heading,
    PageBreak,
    Paragraph,
    Run,
    Section,
)


def test_heading_requires_level_between_1_and_4() -> None:
    Heading(text="Intro", level=1)
    Heading(text="Deep dive", level=4)
    with pytest.raises(ValidationError):
        Heading(text="Too deep", level=5)


def test_paragraph_accepts_multiple_styled_runs() -> None:
    p = Paragraph(runs=[Run(text="Plain. "), Run(text="Bold part.", bold=True)])
    assert p.runs[1].bold is True


def test_table_rejects_row_with_wrong_length() -> None:
    with pytest.raises(ValidationError, match="do not have the same length"):
        DocTable(headers=["A", "B"], rows=[["1", "2"], ["only-one"]])


def test_table_accepts_matching_rows() -> None:
    t = DocTable(headers=["A", "B"], rows=[["1", "2"], ["3", "4"]])
    assert len(t.rows) == 2


def test_image_requires_src_or_placeholder() -> None:
    with pytest.raises(ValidationError, match="requires either"):
        DocImage()
    DocImage(placeholder=True, caption="Company logo")
    DocImage(src="logo.png")


def test_chart_rejects_series_length_mismatch_with_categories() -> None:
    with pytest.raises(ValidationError, match="one value per category"):
        DocChart(
            chart_type="bar",
            categories=["Q1", "Q2", "Q3"],
            series=[{"name": "Revenue", "values": [1, 2]}],
        )


def test_pie_chart_rejects_more_than_one_series() -> None:
    with pytest.raises(ValidationError, match="exactly one series"):
        DocChart(
            chart_type="pie",
            categories=["A", "B"],
            series=[
                {"name": "s1", "values": [1, 2]},
                {"name": "s2", "values": [3, 4]},
            ],
        )


def test_section_and_docxdoc_dispatch_every_primitive_type() -> None:
    section = Section(
        header_text="Confidential",
        footer_text="Page footer",
        body=[
            {"primitive": "heading", "text": "Title", "level": 1},
            {"primitive": "paragraph", "runs": [{"text": "Hello"}]},
            {"primitive": "bullet_list", "items": [[{"text": "One"}]]},
            {"primitive": "numbered_list", "items": [[{"text": "Step 1"}]]},
            {"primitive": "table", "headers": ["A"], "rows": [["1"]]},
            {"primitive": "image", "placeholder": True, "caption": "Logo"},
            {
                "primitive": "chart",
                "chart_type": "bar",
                "categories": ["A"],
                "series": [{"name": "s", "values": [1]}],
            },
            {"primitive": "page_break"},
        ],
    )
    doc = DocxDoc(title="Report", sections=[section])
    kinds = [p.primitive for p in doc.sections[0].body]
    assert kinds == [
        "heading",
        "paragraph",
        "bullet_list",
        "numbered_list",
        "table",
        "image",
        "chart",
        "page_break",
    ]
    assert isinstance(doc.sections[0].body[-1], PageBreak)
    assert isinstance(doc.sections[0].body[4], DocTable)
    assert isinstance(doc.sections[0].body[2], BulletList)


def test_extra_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        Heading(text="Hi", level=1, unexpected_field="nope")
