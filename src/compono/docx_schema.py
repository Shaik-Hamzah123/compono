"""Pydantic models for compono's docx primitive catalog -> JSON Schema.

A Word document flows top-to-bottom on its own — there is no spatial
layout problem to solve here the way there is for slides, so this is a
deliberately separate, smaller catalog from `schema.py`'s pptx
primitives, not a reuse of them. Field descriptions are still written as
instructions to the calling agent, not type labels, matching schema.py's
convention.

v1 docx catalog: heading, paragraph, bullet_list, numbered_list, table,
image, chart, page_break.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DocxPrimitiveBase(BaseModel):
    """Shared fields every docx primitive accepts (mirrors schema.py's PrimitiveBase)."""

    model_config = ConfigDict(extra="forbid")

    id: str | None = Field(
        default=None,
        description="Stable identifier for this primitive. Optional — nothing in the "
        "docx renderer currently needs to reference it back, but kept for symmetry "
        "with the pptx primitive catalog and future use.",
    )
    notes: str | None = Field(
        default=None,
        description="Internal note about this primitive. Not rendered into the document.",
    )


class Run(BaseModel):
    """One inline styled span of text within a Paragraph or a list item."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(..., description="The run's literal text.")
    bold: bool = Field(default=False, description="Render this run in bold.")
    italic: bool = Field(default=False, description="Render this run in italics.")
    underline: bool = Field(default=False, description="Render this run underlined.")
    link: str | None = Field(
        default=None,
        description="If set, this run becomes a clickable hyperlink to this URL.",
    )


class Heading(DocxPrimitiveBase):
    primitive: Literal["heading"] = "heading"
    text: str = Field(..., description="Heading text. Keep short — one line.")
    level: int = Field(
        default=1,
        ge=1,
        le=4,
        description="Heading level 1-4, mapped to Word's built-in Heading 1-4 styles. "
        "Use level 1 sparingly (usually once per document, as the title of a major "
        "section) and go deeper for subsections.",
    )


class Paragraph(DocxPrimitiveBase):
    primitive: Literal["paragraph"] = "paragraph"
    runs: list[Run] = Field(
        ...,
        description="One or more styled spans of text, concatenated in order to form "
        "the paragraph. Use multiple runs only where inline styling (bold/italic/"
        "underline/link) actually changes mid-sentence — a plain paragraph is a "
        "single run with no styling flags set.",
    )


class BulletList(DocxPrimitiveBase):
    primitive: Literal["bullet_list"] = "bullet_list"
    items: list[list[Run]] = Field(
        ...,
        description="One list of runs per bullet item, same run-styling rules as "
        "Paragraph. Keep each item under ~100 characters so it reads as a bullet, "
        "not a paragraph.",
    )


class NumberedList(DocxPrimitiveBase):
    primitive: Literal["numbered_list"] = "numbered_list"
    items: list[list[Run]] = Field(
        ...,
        description="One list of runs per numbered item, same run-styling rules as "
        "Paragraph. Word numbers items automatically in document order.",
    )


class DocTable(DocxPrimitiveBase):
    primitive: Literal["table"] = "table"
    headers: list[str] = Field(..., description="Column headers, in order.")
    rows: list[list[str]] = Field(
        ..., description="Row values. Each row must have the same length as headers."
    )

    @model_validator(mode="after")
    def _rows_match_header_length(self) -> DocTable:
        bad = [i for i, row in enumerate(self.rows) if len(row) != len(self.headers)]
        if bad:
            raise ValueError(
                f"rows {bad} do not have the same length as headers ({len(self.headers)} columns)."
            )
        return self


class DocImage(DocxPrimitiveBase):
    primitive: Literal["image"] = "image"
    src: str | None = Field(
        default=None, description="Path to the image file. Omit when placeholder=True."
    )
    placeholder: bool = Field(
        default=False,
        description="If true, renders a bordered placeholder paragraph with the "
        "caption text instead of a real image, for a later fill pass (e.g. a "
        "company logo the agent doesn't have yet).",
    )
    caption: str | None = Field(
        default=None,
        description="Caption shown under the image (or inside a placeholder).",
    )
    width_in: float = Field(
        default=4.0,
        gt=0,
        description="Image width in inches. Height scales automatically to preserve "
        "the source image's aspect ratio.",
    )

    @model_validator(mode="after")
    def _require_src_or_placeholder(self) -> DocImage:
        if not self.placeholder and not self.src:
            raise ValueError("image requires either 'src' or 'placeholder=True'.")
        return self


class DocChartSeries(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., description="Series name, shown in the chart legend.")
    values: list[float] = Field(
        ..., description="One value per category, same length and order as categories."
    )


class DocChart(DocxPrimitiveBase):
    """Renders as a static image, not a native Word chart object.

    `python-docx` has no chart API — a native Word chart is a whole
    embedded-package format (chart XML + an embedded worksheet) that no
    current Python library builds. This primitive is rasterized via
    matplotlib and embedded as a picture: real, but not editable in Word
    the way a pptx chart is. Documented explicitly, not hidden.
    """

    primitive: Literal["chart"] = "chart"
    chart_type: Literal["bar", "line", "pie"] = Field(
        ...,
        description="Chart type to render. Same scoped catalog as compono's pptx chart.",
    )
    categories: list[str] = Field(
        ..., description="Category labels along the axis (or pie slice labels)."
    )
    series: list[DocChartSeries] = Field(
        ...,
        description="One or more data series. A pie chart should have exactly one series.",
    )
    width_in: float = Field(
        default=5.5, gt=0, description="Rendered chart image width in inches."
    )

    @model_validator(mode="after")
    def _series_match_category_length(self) -> DocChart:
        bad = [s.name for s in self.series if len(s.values) != len(self.categories)]
        if bad:
            raise ValueError(
                f"series {bad} do not have one value per category ({len(self.categories)} categories)."
            )
        if self.chart_type == "pie" and len(self.series) != 1:
            raise ValueError("a pie chart must have exactly one series.")
        return self


class PageBreak(DocxPrimitiveBase):
    primitive: Literal["page_break"] = "page_break"


DocxPrimitiveSpec = Annotated[
    Heading | Paragraph | BulletList | NumberedList | DocTable | DocImage | DocChart | PageBreak,
    Field(discriminator="primitive"),
]


class Section(BaseModel):
    """One document section: optional running header/footer text, and body
    primitives stacked top-to-bottom in order — Word's section concept,
    replacing pptx's per-slide model.
    """

    model_config = ConfigDict(extra="forbid")

    header_text: str | None = Field(
        default=None,
        description="Optional running header text repeated on every page of this section.",
    )
    footer_text: str | None = Field(
        default=None,
        description="Optional running footer text repeated on every page of this section.",
    )
    body: list[DocxPrimitiveSpec] = Field(
        default_factory=list, description="Body primitives, in document order."
    )


class DocxDoc(BaseModel):
    """Top-level spec passed to render_docx/validate_docx."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(
        ..., description="Document title. Used as the .docx core-properties title."
    )
    sections: list[Section] = Field(..., description="Sections, in document order.")
