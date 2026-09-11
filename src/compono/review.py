"""Design-quality suggestions — a third verb, separate from validate().

validate() answers "will this render without breaking" (schema/layout/text-
overflow). review() answers "does this look good" — actionable design
suggestions an agent can apply before or after rendering. Never blocking:
review() has no notion of pass/fail, only suggestions (possibly zero).

Pure function, like resolver.py/validator.py — no pptx write, no network.
Reuses resolve_slide's real rects rather than re-deriving layout, and the
validator's OverflowReport rather than a bespoke wrap routine.

Categories (in the same "errors are fixes, not diagnoses" spirit as
validate()'s structured errors):
  - contrast: shape.text.color vs shape.fill, WCAG-style ratio.
  - whitespace: a body slide whose single top-level primitive leaves a lot
    of a tall box empty. Header-only slides (no body at all) are a
    deliberate pattern (title/closing slides) and are never flagged —
    there's nothing to be "too empty" relative to. Uses
    `LayoutResult.parents` (not an id-string-prefix guess) to tell a
    top-level body item from a nested grid child, per this repo's own
    containment-check convention.
  - image_fit: a real image (not a placeholder) whose aspect ratio is far
    from its box's, under fit="cover" (crops a lot) or fit="contain"
    (leaves large empty bars).
  - font_size: text using most of its box's height without technically
    overflowing — a proactive nudge before it becomes a hard validate()
    error, not a duplicate of it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from PIL import Image as PILImage
from pptx.util import Emu

from compono.render import (
    _extract_text_fields,
    _parse_deck,
    _resolve_font_path,
    resolve_deck_template,
)
from compono.resolver import LayoutResult, Rect, Template, resolve_slide
from compono.schema import Deck, Image, Shape
from compono.validator import check_overflow, load_font_metrics

# WCAG 2.1 AA for normal-size text. Not configurable — a fixed, well-known bar.
_MIN_CONTRAST_RATIO = 4.5
# A lone top-level body item with a box taller than this reads as
# sparse-by-accident rather than sparse-by-design (a title/closing slide,
# which has no body at all, never reaches this check).
_WHITESPACE_MIN_HEIGHT_PT = 300.0
# Image aspect ratio diverging from its box by more than this fraction is a
# visibly bad crop (cover) or a visibly large letterbox (contain).
_IMAGE_ASPECT_TOLERANCE = 0.35
# Text using more than this fraction of its box's height is "cutting it
# close" even though it doesn't (yet) overflow.
_TIGHT_FIT_FRACTION = 0.85


@dataclass
class ReviewReport:
    suggestions: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _suggestion(
    slide: int,
    primitive: str,
    field_name: str | None,
    category: str,
    detail: str,
    fix: str,
) -> dict[str, Any]:
    return {
        "slide": slide,
        "primitive": primitive,
        "field": field_name,
        "category": category,
        "detail": detail,
        "fix": fix,
    }


def _rect_width_pt(rect: Rect) -> float:
    return Emu(rect.w).pt


def _rect_height_pt(rect: Rect) -> float:
    return Emu(rect.h).pt


def _relative_luminance(hex_color: str) -> float:
    r, g, b = (int(hex_color.lstrip("#")[i : i + 2], 16) / 255 for i in (0, 2, 4))

    def channel(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def _contrast_ratio(hex_a: str, hex_b: str) -> float:
    l1, l2 = sorted(
        (_relative_luminance(hex_a), _relative_luminance(hex_b)), reverse=True
    )
    return (l1 + 0.05) / (l2 + 0.05)


def _check_contrast(
    slide_index: int, item_id: str, primitive: Shape
) -> dict[str, Any] | None:
    if primitive.text is None or not primitive.text.color or not primitive.fill:
        return None  # can't compute without both colors — never guess one
    ratio = _contrast_ratio(primitive.text.color, primitive.fill)
    if ratio >= _MIN_CONTRAST_RATIO:
        return None
    return _suggestion(
        slide_index,
        item_id,
        "text.color",
        "contrast",
        f"text.color {primitive.text.color!r} against fill {primitive.fill!r} "
        f"has a contrast ratio of ~{ratio:.1f}:1 (WCAG AA wants {_MIN_CONTRAST_RATIO}:1).",
        "Pick a lighter/darker text.color for more contrast against fill, "
        "or use a lighter/darker fill.",
    )


def _check_whitespace(
    slide_index: int, item_id: str, rect: Rect, is_lone_top_level_item: bool
) -> dict[str, Any] | None:
    if not is_lone_top_level_item:
        return None
    box_height_pt = _rect_height_pt(rect)
    if box_height_pt < _WHITESPACE_MIN_HEIGHT_PT:
        return None
    return _suggestion(
        slide_index,
        item_id,
        None,
        "whitespace",
        f"This is the only item in the body and its box is ~{box_height_pt:.0f}pt "
        "tall — likely more empty space than the content needs.",
        "Add a supporting stat/bullet/image alongside it in a `grid`, or "
        "reduce the slide to a header-only title/section slide if that's the intent.",
    )


def _check_image_fit(
    slide_index: int, item_id: str, primitive: Image, rect: Rect
) -> dict[str, Any] | None:
    if primitive.placeholder or not primitive.src:
        return None  # no real pixels to measure
    try:
        with PILImage.open(primitive.src) as im:
            img_w, img_h = im.size
    except OSError:
        return None  # unreadable file is validate()'s concern, not review()'s

    img_ratio = img_w / img_h
    box_ratio = rect.w / rect.h
    diff = abs(img_ratio - box_ratio) / box_ratio
    if diff <= _IMAGE_ASPECT_TOLERANCE:
        return None

    if primitive.fit == "cover":
        detail = (
            f"Image aspect ratio ({img_ratio:.2f}) differs from its box "
            f"({box_ratio:.2f}) by {diff:.0%} under fit='cover' — likely crops "
            "a meaningful part of the image."
        )
        fix = "Use fit='contain' to avoid cropping, or choose an image closer to the box's aspect ratio."
    else:
        detail = (
            f"Image aspect ratio ({img_ratio:.2f}) differs from its box "
            f"({box_ratio:.2f}) by {diff:.0%} under fit='contain' — likely "
            "leaves large empty bars."
        )
        fix = "Use fit='cover' if cropping is acceptable, or choose an image closer to the box's aspect ratio."
    return _suggestion(slide_index, item_id, "fit", "image_fit", detail, fix)


def review(
    spec: dict[str, Any] | Deck, *, template: Template | None = None
) -> ReviewReport:
    """Design-quality suggestions. Assumes a structurally valid deck — pair
    with validate() first if the spec might not parse; a malformed spec
    still raises the same DeckValidationError _parse_deck always raises.
    """
    deck = _parse_deck(spec)
    resolved_template = resolve_deck_template(deck, template)

    font_path = _resolve_font_path()
    font_metrics = load_font_metrics(font_path) if font_path is not None else None

    suggestions: list[dict[str, Any]] = []
    warnings: list[str] = []
    skipped_font_check = False

    for slide_index, slide in enumerate(deck.slides):
        layout: LayoutResult = resolve_slide(
            resolved_template, header=slide.header, body=slide.body
        )
        # A body of exactly one primitive with no parent (i.e. not itself a
        # grid child, and not the header — excluded by object identity, never
        # an id-string-prefix guess, per this repo's own hard invariant) is
        # the "lone item in a tall box" shape whitespace cares about.
        top_level_body_ids = [
            item_id
            for item_id, primitive in layout.items.items()
            if primitive is not slide.header and item_id not in layout.parents
        ]
        lone_top_level_id = (
            top_level_body_ids[0]
            if len(slide.body) == 1 and len(top_level_body_ids) == 1
            else None
        )

        for item_id, rect in layout.rects.items():
            primitive = layout.items.get(item_id)
            if primitive is None:
                continue

            if isinstance(primitive, Shape):
                s = _check_contrast(slide_index, item_id, primitive)
                if s:
                    suggestions.append(s)

            if isinstance(primitive, Image):
                s = _check_image_fit(slide_index, item_id, primitive, rect)
                if s:
                    suggestions.append(s)

            is_lone_top_level = (
                item_id == lone_top_level_id and item_id not in layout.parents
            )
            s = _check_whitespace(slide_index, item_id, rect, is_lone_top_level)
            if s:
                suggestions.append(s)

            if font_metrics is None:
                skipped_font_check = True
                continue

            for field_name, text, font_size_pt in _extract_text_fields(primitive):
                report = check_overflow(
                    text,
                    font_metrics,
                    font_size_pt,
                    _rect_width_pt(rect),
                    _rect_height_pt(rect),
                )
                box_height_pt = _rect_height_pt(rect)
                if (
                    not report.overflow
                    and report.total_height_pt > _TIGHT_FIT_FRACTION * box_height_pt
                ):
                    suggestions.append(
                        _suggestion(
                            slide_index,
                            item_id,
                            field_name,
                            "font_size",
                            f"Text fills ~{report.total_height_pt / box_height_pt:.0%} "
                            "of its box's height — close to overflowing.",
                            "Shorten the text or reduce the font size for margin "
                            "before it overflows on a slightly longer edit.",
                        )
                    )

    if skipped_font_check:
        warnings.append("no font available — font_size proximity checks skipped.")

    return ReviewReport(suggestions=suggestions, warnings=warnings)
