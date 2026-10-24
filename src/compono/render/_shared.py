"""Cross-cutting helpers every `_render_<primitive>` function and the two
public verbs (`validate`/`render_deck`) lean on: font-size constants,
shape-kind/alignment lookup tables, font resolution for overflow
measurement, and the small drawing helpers (`_set_font`, `_lighten`,
`_apply_shape_gradient`) shared across more than one primitive's renderer.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Pt
from pydantic import ValidationError
from pydantic_core import ErrorDetails

from compono.resolver import Template
from compono.schema import Deck
from compono.validator import resolve_safe_font

from .types import DeckValidationError

HEADER_FONT_SIZE_PT = 28
BODY_FONT_SIZE_PT = 18
STAT_VALUE_FONT_SIZE_PT = 36
STAT_LABEL_FONT_SIZE_PT = 14
TABLE_FONT_SIZE_PT = 14
CAPTION_FONT_SIZE_PT = 12

# Last-resort fallback if the bundled reference font (validator.SAFE_FONTS)
# somehow fails to load in a given environment. Overflow validation is
# skipped, not faked, when none of these are found either.
_FALLBACK_SYSTEM_FONTS = [
    Path("C:/Windows/Fonts/arial.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/System/Library/Fonts/Supplemental/Arial.ttf"),  # macOS
]

_SHAPE_KIND_TO_MSO = {
    "rect": MSO_SHAPE.RECTANGLE,
    "rounded_rect": MSO_SHAPE.ROUNDED_RECTANGLE,
    "oval": MSO_SHAPE.OVAL,
}
_ALIGN_TO_PP = {
    "left": PP_ALIGN.LEFT,
    "center": PP_ALIGN.CENTER,
    "right": PP_ALIGN.RIGHT,
}
_VALIGN_TO_MSO = {
    "top": MSO_ANCHOR.TOP,
    "middle": MSO_ANCHOR.MIDDLE,
    "bottom": MSO_ANCHOR.BOTTOM,
}
_CHART_TYPE_TO_XL = {
    "bar": XL_CHART_TYPE.COLUMN_CLUSTERED,
    "line": XL_CHART_TYPE.LINE,
    "pie": XL_CHART_TYPE.PIE,
}


def _resolve_font_path(template: Template) -> Path | None:
    """Pick the font file overflow validation should measure against, for
    *this* deck's template. v1 decks have exactly one template, so this is a
    single lookup per validate()/render_deck() call, not per-slide — a future
    per-slide-template feature would need to move this inside the slide loop
    instead.
    """
    path = resolve_safe_font(template.font_family)
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
        raise DeckValidationError(
            [_pydantic_error_to_dict(e) for e in exc.errors()]
        ) from exc


def _unknown_template_error(detail: str) -> dict[str, Any]:
    return {
        "slide": None,
        "primitive": "template",
        "field": "template",
        "error": "unknown_template",
        "detail": detail,
        "fix": "Use one of the available template names listed above, or omit `template` for the default.",
    }


def resolve_deck_template(deck: Deck, template: Template | None) -> Template:
    """An explicit `template=` kwarg always wins; otherwise resolve the name the
    spec itself asked for (`Deck.template`, schema.py) — previously unwired,
    every render silently used the hardcoded default regardless of this field.
    Raises ValueError (from Template.from_name) on an unknown name — shared by
    validate/render_deck/review, each of which reports it in their own shape.
    """
    if template is not None:
        return template
    return Template.from_name(deck.template)


def _set_font(
    font: Any, template: Template, size_pt: float, *, bold: bool = False
) -> None:
    """One shared point that applies both size and typeface to a run/paragraph
    font — `template.font_family` is the agent's choice (via `Deck.template`,
    schema.py), never hardcoded per primitive.
    """
    font.size = Pt(size_pt)
    font.name = template.font_family
    if bold:
        font.bold = True


def _lighten(hex_color: str, factor: float) -> RGBColor:
    """Blend a hex color toward white by `factor` (0=unchanged, 1=white)."""
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
    return RGBColor(
        round(r + (255 - r) * factor),
        round(g + (255 - g) * factor),
        round(b + (255 - b) * factor),
    )


def _apply_shape_gradient(sp: Any, hex_color: str) -> None:
    """Blend a light tint of `hex_color` into the color itself, top to bottom.

    Only used when a shape explicitly opts in via `fill_style="gradient"` —
    the fill style is the agent's choice, not something render.py imposes.
    """
    base = hex_color.lstrip("#")
    sp.fill.gradient()
    sp.fill.gradient_angle = 90
    stops = sp.fill.gradient_stops
    stops[0].color.rgb = _lighten(base, 0.45)
    stops[1].color.rgb = RGBColor.from_string(base)
