"""The two public verbs (COMPONO_PLAN.md sections 8-9): `render_deck(spec)`
and `validate(spec)`. No client objects, no session lifecycle — both are
pure functions over a Deck spec (raw dict or a typed Deck). Also owns the
per-slide/per-primitive write-pass orchestration (`_render_slide`,
`_render_primitive`) that dispatches to `primitives.py`'s functions.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pptx import Presentation
from pptx.util import Emu

from compono.resolver import LayoutResult, Rect, Template
from compono.schema import (
    Chart,
    Deck,
    Header,
    Image,
    PrimitiveBase,
    Sequence,
    Shape,
    Stat,
    Table,
    Text,
)
from compono.validator import FontMetrics, load_font_metrics

from . import primitives
from ._overflow import _check_slide
from ._shared import (
    _parse_deck,
    _resolve_font_path,
    _unknown_template_error,
    resolve_deck_template,
)
from .types import DeckValidationError, RenderReport, ValidationReport


def validate(
    spec: dict[str, Any] | Deck, *, template: Template | None = None
) -> ValidationReport:
    """Cheap and separate from render — no pptx write, no image render (COMPONO_PLAN.md section 8, item 4)."""
    try:
        deck = _parse_deck(spec)
    except DeckValidationError as exc:
        return ValidationReport(valid=False, errors=exc.errors)

    try:
        resolved_template = resolve_deck_template(deck, template)
    except ValueError as exc:
        return ValidationReport(valid=False, errors=[_unknown_template_error(str(exc))])

    font_path = _resolve_font_path(resolved_template)
    font_metrics = load_font_metrics(font_path) if font_path is not None else None

    all_errors: list[dict[str, Any]] = []
    all_warnings: list[str] = []
    for i, slide in enumerate(deck.slides):
        _, errors, warnings = _check_slide(i, slide, resolved_template, font_metrics)
        all_errors.extend(errors)
        all_warnings.extend(warnings)

    return ValidationReport(
        valid=not all_errors, errors=all_errors, warnings=all_warnings
    )


def render_deck(
    spec: dict[str, Any] | Deck,
    output_path: str | Path,
    *,
    template: Template | None = None,
) -> RenderReport:
    output_path = Path(output_path)

    deck = _parse_deck(spec)

    try:
        resolved_template = resolve_deck_template(deck, template)
    except ValueError as exc:
        raise DeckValidationError([_unknown_template_error(str(exc))]) from exc

    font_path = _resolve_font_path(resolved_template)
    font_metrics = load_font_metrics(font_path) if font_path is not None else None

    layouts: list[LayoutResult] = []
    errors: list[dict[str, Any]] = []
    warnings: list[str] = []

    for i, slide in enumerate(deck.slides):
        layout, slide_errors, slide_warnings = _check_slide(
            i, slide, resolved_template, font_metrics
        )
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
    for i, layout in enumerate(layouts):
        pptx_slide = prs.slides.add_slide(blank_layout)
        _render_slide(pptx_slide, layout, i, manifest, resolved_template, font_metrics)
        primitives._render_footer(pptx_slide, resolved_template, i + 1, len(layouts))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(output_path))

    return RenderReport(
        pptx_path=output_path,
        manifest=manifest,
        warnings=warnings,
        actual_layout=layouts,
    )


def _render_slide(
    pptx_slide: Any,
    layout: LayoutResult,
    slide_index: int,
    manifest: list[dict[str, Any]],
    template: Template,
    font_metrics: FontMetrics | None = None,
) -> None:
    for item_id, rect in layout.rects.items():
        primitive = layout.items.get(item_id)
        if primitive is None:
            continue
        if isinstance(primitive, Shape) and primitive.kind == "connector":
            continue  # drawn below from layout.connectors, not from its own rect
        _render_primitive(
            pptx_slide,
            primitive,
            rect,
            slide_index,
            item_id,
            manifest,
            template,
            font_metrics,
        )

    for points in layout.connectors.values():
        primitives._render_connector(pptx_slide, points)


def _render_primitive(
    pptx_slide: Any,
    primitive: PrimitiveBase,
    rect: Rect,
    slide_index: int,
    item_id: str,
    manifest: list[dict[str, Any]],
    template: Template,
    font_metrics: FontMetrics | None = None,
) -> None:
    if isinstance(primitive, Header):
        primitives._render_header(pptx_slide, primitive, rect, template)
    elif isinstance(primitive, Text):
        primitives._render_text(pptx_slide, primitive, rect, template)
    elif isinstance(primitive, Shape):
        primitives._render_shape(pptx_slide, primitive, rect, template)
    elif isinstance(primitive, Image):
        primitives._render_image(
            pptx_slide, primitive, rect, slide_index, item_id, manifest, template
        )
    elif isinstance(primitive, Stat):
        primitives._render_stat(pptx_slide, primitive, rect, template)
    elif isinstance(primitive, Table):
        primitives._render_table(pptx_slide, primitive, rect, template, font_metrics)
    elif isinstance(primitive, Sequence):
        primitives._render_sequence(pptx_slide, primitive, rect, template)
    elif isinstance(primitive, Chart):
        primitives._render_chart(pptx_slide, primitive, rect, template)
    # Grid/Diagram/Gantt have no visual of their own — only their
    # (already-flattened) children (Diagram nodes are synthesized as real
    # Shape instances; Gantt fully collapses into a real Table) render.
