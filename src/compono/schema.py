"""Pydantic models for each primitive -> JSON Schema.

Malformed input is rejected structurally here, not caught visually later
(COMPONO_PLAN.md section 1, item 1). Field descriptions are written as
instructions to the calling agent, not type labels (section 8, item 2) —
the schema doubles as in-context documentation.

v1 slice: header, text, grid, shape (COMPONO_PLAN.md section 14, step 2).
The remaining primitives (image, stat, table, sequence, chart) are added
in a later step without changing the shape of this module.
"""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field

Align = Literal["start", "center", "end", "stretch"]
Justify = Literal["start", "center", "end", "space-between"]


class PrimitiveBase(BaseModel):
    """Shared fields every primitive accepts (COMPONO_PLAN.md section 5, final paragraph)."""

    model_config = ConfigDict(extra="forbid")

    id: str | None = Field(
        default=None,
        description=(
            "Stable identifier for this primitive. Required if another primitive "
            "needs to reference its resolved position (e.g. a shape connector)."
        ),
    )
    notes: str | None = Field(
        default=None,
        description="Speaker notes for this primitive/slide. Not rendered on the slide itself.",
    )


class Header(PrimitiveBase):
    primitive: Literal["header"] = "header"
    title: str = Field(
        ...,
        description="Keep under ~60 characters — longer titles will be shrunk by the resolver.",
    )
    subtitle: str | None = Field(
        default=None,
        description="Optional supporting line under the title. Keep under ~80 characters.",
    )
    eyebrow: str | None = Field(
        default=None,
        description="Optional small label above the title (e.g. a section tag or date).",
    )
    align: Literal["left", "center", "right"] = Field(
        default="left",
        description="Horizontal alignment of the header block within its region.",
    )


class Text(PrimitiveBase):
    primitive: Literal["text"] = "text"
    mode: Literal["paragraph", "bullets"] = Field(
        default="paragraph",
        description="'paragraph' renders content as flowing prose; 'bullets' renders each list item as a bullet.",
    )
    content: str | list[str] = Field(
        ...,
        description=(
            "A single string for paragraph mode, or a list of strings for bullets mode. "
            "Keep bullet items short (under ~100 characters) so they fit without shrinking."
        ),
    )
    columns: int = Field(
        default=1,
        ge=1,
        description="Number of layout columns to split content across. Defaults to 1 (single column).",
    )
    emphasis_indices: list[int] | None = Field(
        default=None,
        description="Indices (0-based) of bullet items or sentences to visually emphasize.",
    )


class ShapeText(BaseModel):
    """Text-in-shape (COMPONO_PLAN.md section 5, item 9). Shares the fit routine with Text/Stat."""

    model_config = ConfigDict(extra="forbid")

    content: str = Field(..., description="Text to render inside the shape.")
    align: Literal["left", "center", "right"] = Field(
        default="left", description="Horizontal alignment of the text within the shape."
    )
    valign: Literal["top", "middle", "bottom"] = Field(
        default="middle", description="Vertical alignment of the text within the shape."
    )
    autofit: bool = Field(
        default=True,
        description="If true, the shared shrink-to-fit routine reduces font size to avoid overflow.",
    )


class ShapeConnects(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_id: str = Field(..., description="id of the primitive this connector originates from.")
    to_id: str = Field(..., description="id of the primitive this connector points to.")


class Shape(PrimitiveBase):
    primitive: Literal["shape"] = "shape"
    kind: Literal["rect", "rounded_rect", "oval", "line", "arrow", "connector"] = Field(
        ..., description="Shape geometry to render."
    )
    fill: str | None = Field(
        default=None, description="Fill color, e.g. a hex string. Omit for no fill / template default."
    )
    border: str | None = Field(
        default=None, description="Border color, e.g. a hex string. Omit for no border."
    )
    connects: ShapeConnects | None = Field(
        default=None,
        description=(
            "Only valid when kind='connector'. References two other primitives by id; "
            "the resolver draws the connector between their resolved rects."
        ),
    )
    text: ShapeText | None = Field(
        default=None, description="Optional text rendered inside the shape."
    )


PrimitiveSpec = Annotated[
    Union[Header, Text, "Grid", Shape],
    Field(discriminator="primitive"),
]


class Grid(PrimitiveBase):
    primitive: Literal["grid"] = "grid"
    items: list[PrimitiveSpec] = Field(
        ...,
        description=(
            "Nested primitive specs, in the same shape as a slide's top-level primitives — "
            "grids can contain any primitive, including other grids."
        ),
    )
    columns: int | Literal["auto"] = Field(
        default="auto",
        description="Number of columns, or 'auto' to let the resolver infer from item count.",
    )
    direction: Literal["row", "column"] = Field(
        default="row", description="Main-axis direction items are laid out along."
    )
    align: Align = Field(
        default="stretch", description="Cross-axis alignment of items within the grid."
    )
    justify: Justify = Field(
        default="start", description="Main-axis alignment/distribution of items within the grid."
    )


Grid.model_rebuild()
