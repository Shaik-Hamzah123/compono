"""Pydantic models for each primitive -> JSON Schema.

Malformed input is rejected structurally here, not caught visually later
(COMPONO_PLAN.md section 1, item 1). Field descriptions are written as
instructions to the calling agent, not type labels (section 8, item 2) —
the schema doubles as in-context documentation.

Full v1 catalog (COMPONO_PLAN.md section 5): header, text, image, stat, grid,
table, sequence, chart, shape; plus `diagram`, added post-v1 (a node-graph
flowchart whose nodes/edges are synthesized as `shape` primitives at
layout time, so it renders/overflow-checks through the exact same
pipeline as a hand-placed shape — no new render code needed).
"""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator

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
    color: str | None = Field(
        default=None,
        description=(
            "Text color, e.g. a hex string. Omit for the theme default. Set this "
            "explicitly on a shape with a dark `fill` — review()'s contrast check "
            "can only evaluate legibility against `fill` when this is set."
        ),
    )


class ShapeConnects(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_id: str = Field(
        ..., description="id of the primitive this connector originates from."
    )
    to_id: str = Field(..., description="id of the primitive this connector points to.")


class Shape(PrimitiveBase):
    primitive: Literal["shape"] = "shape"
    kind: Literal["rect", "rounded_rect", "oval", "line", "arrow", "connector"] = Field(
        ..., description="Shape geometry to render."
    )
    fill: str | None = Field(
        default=None,
        description="Fill color, e.g. a hex string. Omit for no fill / template default.",
    )
    fill_style: Literal["solid", "gradient"] = Field(
        default="solid",
        description=(
            "'solid' (default) is a flat fill. 'gradient' blends a lighter tint of "
            "`fill` into the color itself, top to bottom — an explicit choice, not "
            "applied automatically, so use it only where it fits the deck's look."
        ),
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


class DiagramNode(BaseModel):
    """One node in a `diagram` — synthesized into a real `shape` at layout
    time, so it renders through the exact same pipeline as a hand-placed
    shape (COMPONO_PLAN.md's real-shape invariant applies unchanged).
    """

    model_config = ConfigDict(extra="forbid")

    id: str | None = Field(
        default=None,
        description=(
            "Stable identifier for this node, for `edges` to reference and for "
            "shape(kind='connector') elsewhere on the slide to point at. If "
            "omitted, other nodes/edges must reference this node by its "
            '0-based position in `nodes` instead (e.g. "0", "1").'
        ),
    )
    label: str = Field(..., description="Text rendered inside the node's shape.")
    kind: Literal["rect", "rounded_rect", "oval"] | None = Field(
        default=None,
        description="Overrides the diagram's `node_kind` for this node only.",
    )
    fill: str | None = Field(
        default=None,
        description="Overrides the diagram's `node_fill` for this node only.",
    )


class DiagramEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_: str = Field(
        ...,
        alias="from",
        description="The edge's source node — its `id`, or its 0-based index in `nodes` if it has none.",
    )
    to: str = Field(
        ...,
        description="The edge's target node — its `id`, or its 0-based index in `nodes` if it has none.",
    )


class Diagram(PrimitiveBase):
    """A node-graph flowchart: the resolver places `nodes` automatically
    (in `orientation` order) and routes `edges` between them using the same
    obstacle-avoiding connector routing shape(kind='connector') uses —
    replaces hand-placing every node as a shape with a manual id plus one
    connector shape per edge.
    """

    primitive: Literal["diagram"] = "diagram"
    nodes: list[DiagramNode] = Field(
        ..., min_length=1, description="Nodes, in `orientation` order."
    )
    edges: list[DiagramEdge] | None = Field(
        default=None,
        description=(
            "Connections between nodes. Omit to auto-connect nodes in order "
            "as a linear chain (nodes[0] -> nodes[1] -> ...)."
        ),
    )
    orientation: Literal["vertical", "horizontal"] = Field(
        default="vertical",
        description="Layout direction of the node flow: stacked top-to-bottom, or side-by-side.",
    )
    node_kind: Literal["rect", "rounded_rect", "oval"] = Field(
        default="rounded_rect",
        description="Default shape kind for nodes that don't set their own `kind`.",
    )
    node_fill: str | None = Field(
        default=None,
        description="Default fill color for nodes that don't set their own `fill`.",
    )

    @model_validator(mode="after")
    def _edges_reference_real_nodes(self) -> Diagram:
        if self.edges is None:
            return self
        valid_refs = {str(i) for i in range(len(self.nodes))} | {
            node.id for node in self.nodes if node.id is not None
        }
        bad = [
            (edge.from_, edge.to)
            for edge in self.edges
            if edge.from_ not in valid_refs or edge.to not in valid_refs
        ]
        if bad:
            raise ValueError(
                f"edges {bad} reference node(s) not present in `nodes` "
                "(use a node's `id`, or its 0-based index if it has none)."
            )
        return self


class Image(PrimitiveBase):
    primitive: Literal["image"] = "image"
    src: str | None = Field(
        default=None,
        description="Path or URL to the image. Omit when placeholder=True.",
    )
    placeholder: bool = Field(
        default=False,
        description=(
            "If true, renders an intentional placeholder (dashed border + caption) instead of "
            "a real image, and records the exact rect in the render manifest for a later fill pass."
        ),
    )
    caption: str | None = Field(
        default=None,
        description="Caption describing the image (shown on placeholders; also usable as alt text).",
    )
    fit: Literal["cover", "contain"] = Field(
        default="contain",
        description="'contain' preserves aspect ratio within the box; 'cover' fills the box exactly.",
    )

    @model_validator(mode="after")
    def _require_src_or_placeholder(self) -> Image:
        if not self.placeholder and not self.src:
            raise ValueError("image requires either 'src' or 'placeholder=True'.")
        return self


class Stat(PrimitiveBase):
    primitive: Literal["stat"] = "stat"
    value: str = Field(
        ...,
        description="The headline number/value, e.g. '42%'. Keep short — it renders large.",
    )
    label: str = Field(
        ..., description="Short label under the value, e.g. 'YoY growth'."
    )
    trend: str | None = Field(
        default=None,
        description="Optional trend indicator, e.g. '+12% vs last quarter'.",
    )


class Table(PrimitiveBase):
    primitive: Literal["table"] = "table"
    headers: list[str] = Field(
        ..., min_length=1, description="Column headers, in order."
    )
    rows: list[list[str]] = Field(
        ...,
        min_length=1,
        description="Row values. Each row must have the same length as headers.",
    )
    emphasis_row: int | None = Field(
        default=None,
        description="0-based index (into rows) of a row to visually emphasize.",
    )
    emphasis_col: int | None = Field(
        default=None,
        description="0-based index (into headers) of a column to visually emphasize.",
    )

    @model_validator(mode="after")
    def _rows_match_header_length(self) -> Table:
        bad = [i for i, row in enumerate(self.rows) if len(row) != len(self.headers)]
        if bad:
            raise ValueError(
                f"rows {bad} do not have the same length as headers ({len(self.headers)} columns)."
            )
        return self


class SequenceStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(..., description="Short step label, e.g. 'Discovery'.")
    description: str | None = Field(
        default=None, description="Optional one-line elaboration of the step."
    )


class Sequence(PrimitiveBase):
    primitive: Literal["sequence"] = "sequence"
    steps: list[SequenceStep] = Field(
        ...,
        min_length=1,
        description="Ordered steps, rendered left-to-right or top-to-bottom.",
    )
    orientation: Literal["horizontal", "vertical"] = Field(
        default="horizontal", description="Layout direction of the step sequence."
    )


class ChartSeries(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., description="Series name, shown in the chart legend.")
    values: list[float] = Field(
        ..., description="One value per category, same length and order as categories."
    )


class Chart(PrimitiveBase):
    primitive: Literal["chart"] = "chart"
    chart_type: Literal["bar", "line", "pie"] = Field(
        ..., description="Chart type to render."
    )
    categories: list[str] = Field(
        ..., description="Category labels along the axis (or pie slice labels)."
    )
    series: list[ChartSeries] = Field(
        ...,
        description="One or more data series. A pie chart should have exactly one series.",
    )

    @model_validator(mode="after")
    def _series_match_category_length(self) -> Chart:
        bad = [s.name for s in self.series if len(s.values) != len(self.categories)]
        if bad:
            raise ValueError(
                f"series {bad} do not have one value per category ({len(self.categories)} categories)."
            )
        if self.chart_type == "pie" and len(self.series) != 1:
            raise ValueError("a pie chart must have exactly one series.")
        return self


PrimitiveSpec = Annotated[
    Union[Header, Text, Image, Stat, "Grid", Table, Sequence, Chart, Shape, Diagram],
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
        default="start",
        description="Main-axis alignment/distribution of items within the grid.",
    )


Grid.model_rebuild()


class Slide(BaseModel):
    """One slide: an optional header region, and body primitives stacked top-to-bottom by default."""

    model_config = ConfigDict(extra="forbid")

    header: Header | None = Field(
        default=None, description="Optional header region for this slide."
    )
    body: list[PrimitiveSpec] = Field(
        default_factory=list,
        description="Body primitives, laid out top-to-bottom by default.",
    )
    notes: str | None = Field(
        default=None, description="Speaker notes for the whole slide."
    )


class Deck(BaseModel):
    """Top-level spec passed to render_deck/validate (COMPONO_PLAN.md section 9)."""

    model_config = ConfigDict(extra="forbid")

    template: str = Field(
        default="default",
        description="Template name — a config file under templates/, or 'default'.",
    )
    slides: list[Slide] = Field(..., description="Slides, in presentation order.")
