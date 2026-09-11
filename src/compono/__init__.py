"""compono — agent-oriented, code-based PPTX generation library.

Public exports ONLY (COMPONO_PLAN.md section 10) — resolver/validator/template
loader stay internal, reached only through render_deck/validate.
"""

from compono.render import (
    DeckValidationError,
    RenderReport,
    ValidationReport,
    render_deck,
    validate,
)
from compono.schema import Deck, Grid, Header, Shape, Slide, Text

__all__ = [
    "Deck",
    "DeckValidationError",
    "Grid",
    "Header",
    "RenderReport",
    "Shape",
    "Slide",
    "Text",
    "ValidationReport",
    "render_deck",
    "validate",
]
