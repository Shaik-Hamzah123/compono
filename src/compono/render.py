"""Orchestrates validate -> resolve -> write pptx.

Exposes the two public verbs (COMPONO_PLAN.md sections 8-9): render_deck(spec)
and validate(spec). No client objects, no session lifecycle — both are pure
functions over a Deck spec (raw dict or a typed Deck).

v1 slice: header, text, grid, shape (Step 4). Image/stat/table/sequence/chart
render support lands in Step 5 without changing this module's shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Pt
from pydantic import ValidationError
from pydantic_core import ErrorDetails

from compono.resolver import (
    ConnectorPoints,
    LayoutResult,
    Rect,
    Template,
    resolve_slide,
)
from compono.schema import Deck, Header, PrimitiveBase, Shape, Slide, Text
from compono.validator import (
    SAFE_FONTS,
    FontMetrics,
    build_overflow_error,
    check_overflow,
    load_font_metrics,
    resolve_safe_font,
)

HEADER_FONT_SIZE_PT = 28
BODY_FONT_SIZE_PT = 18

# Fallback system fonts used only until a real font ships in src/compono/fonts/
# (SAFE_FONTS in validator.py is still empty). Overflow validation is skipped,
# not faked, when none of these are found either.
_FALLBACK_SYSTEM_FONTS = [
    Path("C:/Windows/Fonts/arial.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
]

_SHAPE_KIND_TO_MSO = {
    "rect": MSO_SHAPE.RECTANGLE,
    "rounded_rect": MSO_SHAPE.ROUNDED_RECTANGLE,
    "oval": MSO_SHAPE.OVAL,
}
_ALIGN_TO_PP = {"left": PP_ALIGN.LEFT, "center": PP_ALIGN.CENTER, "right": PP_ALIGN.RIGHT}
_VALIGN_TO_MSO = {"top": MSO_ANCHOR.TOP, "middle": MSO_ANCHOR.MIDDLE, "bottom": MSO_ANCHOR.BOTTOM}


class DeckValidationError(Exception):
    """The one exception type. Carries the structured list of per-field errors."""

    def __init__(self, errors: list[dict[str, Any]]) -> None:
        super().__init__(f"{len(errors)} validation error(s)")
        self.errors = errors


@dataclass
class ValidationReport:
    valid: bool
    errors: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class RenderReport:
    """render_deck returns this, not just a file — a feedback channel (COMPONO_PLAN.md section 8, item 5)."""

    pptx_path: Path
    manifest: list[dict[str, Any]]
    warnings: list[str]
    actual_layout: list[LayoutResult]


def _resolve_font_path() -> Path | None:
    for name in SAFE_FONTS:
        path = resolve_safe_font(name)
        if path is not None and path.exists():
            return path
    return next((p for p in _FALLBACK_SYSTEM_FONTS if p.exists()), None)


def _pydantic_error_to_dict(err: ErrorDetails) -> dict[str, Any]:
    loc = ".".join(str(part) for part in err["loc"]) or "<deck>"
    return {
        "slide": None,
        "primitive": loc,
        "field": err["loc"][-1] if err["loc"] else None,
        "error": err["type"],
        "detail": err["msg"],
        "fix": "Check the field against the schema description and correct the value/type.",
    }


def _parse_deck(spec: dict[str, Any] | Deck) -> Deck:
    if isinstance(spec, Deck):
        return spec
    try:
        return Deck.model_validate(spec)
    except ValidationError as exc:
        raise DeckValidationError([_pydantic_error_to_dict(e) for e in exc.errors()]) from exc


def _extract_text_and_font_size(primitive: PrimitiveBase | None) -> tuple[str, float] | None:
    if isinstance(primitive, Header):
        return primitive.title, HEADER_FONT_SIZE_PT
    if isinstance(primitive, Text):
        content = primitive.content if isinstance(primitive.content, str) else " ".join(primitive.content)
        return content, BODY_FONT_SIZE_PT
    if isinstance(primitive, Shape) and primitive.text is not None:
        return primitive.text.content, BODY_FONT_SIZE_PT
    return None


def _check_slide(
    slide_index: int,
    slide: Slide,
    template: Template,
    font_metrics: FontMetrics | None,
) -> tuple[LayoutResult | None, list[dict[str, Any]], list[str]]:
    errors: list[dict[str, Any]] = []
    warnings: list[str] = []

    try:
        layout = resolve_slide(template, header=slide.header, body=slide.body)
    except ValueError as exc:
        errors.append(
            {
                "slide": slide_index,
                "primitive": "slide",
                "field": None,
                "error": "layout",
                "detail": str(exc),
                "fix": "Adjust the template margins/header/footer heights, or reduce body item count.",
            }
        )
        return None, errors, warnings

    if font_metrics is None:
        warnings.append(f"slide {slide_index}: no font available — overflow validation skipped.")
        return layout, errors, warnings

    for item_id, rect in layout.rects.items():
        text_and_size = _extract_text_and_font_size(layout.items.get(item_id))
        if text_and_size is None:
            continue
        text, font_size_pt = text_and_size
        box_width_pt = Emu(rect.w).pt
        box_height_pt = Emu(rect.h).pt
        report = check_overflow(text, font_metrics, font_size_pt, box_width_pt, box_height_pt)
        if report.overflow:
            errors.append(build_overflow_error(slide_index, item_id, "content", report, font_size_pt))

    return layout, errors, warnings


def validate(spec: dict[str, Any] | Deck, *, template: Template | None = None) -> ValidationReport:
    """Cheap and separate from render — no pptx write, no image render (COMPONO_PLAN.md section 8, item 4)."""
    resolved_template = template or Template.from_yaml()

    try:
        deck = _parse_deck(spec)
    except DeckValidationError as exc:
        return ValidationReport(valid=False, errors=exc.errors)

    font_path = _resolve_font_path()
    font_metrics = load_font_metrics(font_path) if font_path is not None else None

    all_errors: list[dict[str, Any]] = []
    all_warnings: list[str] = []
    for i, slide in enumerate(deck.slides):
        _, errors, warnings = _check_slide(i, slide, resolved_template, font_metrics)
        all_errors.extend(errors)
        all_warnings.extend(warnings)

    return ValidationReport(valid=not all_errors, errors=all_errors, warnings=all_warnings)


def render_deck(
    spec: dict[str, Any] | Deck,
    output_path: str | Path,
    *,
    template: Template | None = None,
) -> RenderReport:
    resolved_template = template or Template.from_yaml()
    output_path = Path(output_path)

    deck = _parse_deck(spec)

    font_path = _resolve_font_path()
    font_metrics = load_font_metrics(font_path) if font_path is not None else None

    layouts: list[LayoutResult] = []
    errors: list[dict[str, Any]] = []
    warnings: list[str] = []

    for i, slide in enumerate(deck.slides):
        layout, slide_errors, slide_warnings = _check_slide(i, slide, resolved_template, font_metrics)
        errors.extend(slide_errors)
        warnings.extend(slide_warnings)
        layouts.append(layout)  # type: ignore[arg-type]  # None only paired with an error, checked below

    if errors:
        raise DeckValidationError(errors)

    prs = Presentation()
    prs.slide_width = Emu(resolved_template.page_width)
    prs.slide_height = Emu(resolved_template.page_height)
    blank_layout = prs.slide_layouts[6]

    manifest: list[dict[str, Any]] = []
    for layout in layouts:
        pptx_slide = prs.slides.add_slide(blank_layout)
        _render_slide(pptx_slide, layout)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(output_path))

    return RenderReport(pptx_path=output_path, manifest=manifest, warnings=warnings, actual_layout=layouts)


def _render_slide(pptx_slide: Any, layout: LayoutResult) -> None:
    for item_id, rect in layout.rects.items():
        primitive = layout.items.get(item_id)
        if primitive is None:
            continue
        if isinstance(primitive, Shape) and primitive.kind == "connector":
            continue  # drawn below from layout.connectors, not from its own rect
        _render_primitive(pptx_slide, primitive, rect)

    for points in layout.connectors.values():
        _render_connector(pptx_slide, points)


def _render_primitive(pptx_slide: Any, primitive: PrimitiveBase, rect: Rect) -> None:
    if isinstance(primitive, Header):
        _render_header(pptx_slide, primitive, rect)
    elif isinstance(primitive, Text):
        _render_text(pptx_slide, primitive, rect)
    elif isinstance(primitive, Shape):
        _render_shape(pptx_slide, primitive, rect)
    # Grid has no visual of its own — only its (already-flattened) children render.


def _render_header(pptx_slide: Any, header: Header, rect: Rect) -> None:
    box = pptx_slide.shapes.add_textbox(Emu(rect.x), Emu(rect.y), Emu(rect.w), Emu(rect.h))
    tf = box.text_frame
    tf.word_wrap = True

    first = True
    if header.eyebrow:
        p = tf.paragraphs[0]
        first = False
        p.text = header.eyebrow
        p.font.size = Pt(12)
        p.alignment = _ALIGN_TO_PP[header.align]

    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.text = header.title
    p.font.size = Pt(HEADER_FONT_SIZE_PT)
    p.font.bold = True
    p.alignment = _ALIGN_TO_PP[header.align]

    if header.subtitle:
        p = tf.add_paragraph()
        p.text = header.subtitle
        p.font.size = Pt(16)
        p.alignment = _ALIGN_TO_PP[header.align]


def _render_text(pptx_slide: Any, text: Text, rect: Rect) -> None:
    box = pptx_slide.shapes.add_textbox(Emu(rect.x), Emu(rect.y), Emu(rect.w), Emu(rect.h))
    tf = box.text_frame
    tf.word_wrap = True

    if text.mode == "paragraph":
        content = text.content if isinstance(text.content, str) else " ".join(text.content)
        tf.text = content
        tf.paragraphs[0].font.size = Pt(BODY_FONT_SIZE_PT)
        return

    items = text.content if isinstance(text.content, list) else [text.content]
    emphasis = set(text.emphasis_indices or [])
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = f"\u2022 {item}"
        p.font.size = Pt(BODY_FONT_SIZE_PT)
        p.font.bold = i in emphasis


def _render_shape(pptx_slide: Any, shape: Shape, rect: Rect) -> None:
    # "line"/"arrow" render as a straight connector across the shape's own rect;
    # arrowhead styling is a known gap, left for a follow-up once needed.
    if shape.kind in ("line", "arrow"):
        pptx_slide.shapes.add_connector(
            MSO_CONNECTOR.STRAIGHT, Emu(rect.x), Emu(rect.y), Emu(rect.x + rect.w), Emu(rect.y + rect.h)
        )
        return

    mso_shape = _SHAPE_KIND_TO_MSO.get(shape.kind, MSO_SHAPE.RECTANGLE)
    sp = pptx_slide.shapes.add_shape(mso_shape, Emu(rect.x), Emu(rect.y), Emu(rect.w), Emu(rect.h))

    if shape.fill:
        sp.fill.solid()
        sp.fill.fore_color.rgb = RGBColor.from_string(shape.fill.lstrip("#"))
    else:
        sp.fill.background()

    if shape.border:
        sp.line.color.rgb = RGBColor.from_string(shape.border.lstrip("#"))
    else:
        sp.line.fill.background()

    if shape.text is not None:
        tf = sp.text_frame
        tf.word_wrap = True
        tf.text = shape.text.content
        tf.vertical_anchor = _VALIGN_TO_MSO[shape.text.valign]
        tf.paragraphs[0].alignment = _ALIGN_TO_PP[shape.text.align]


def _render_connector(pptx_slide: Any, points: ConnectorPoints) -> None:
    x1, y1 = points.start
    x2, y2 = points.end
    pptx_slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Emu(x1), Emu(y1), Emu(x2), Emu(y2))
