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
from compono.schema import (
    Chart,
    Deck,
    Grid,
    Header,
    Image,
    Sequence,
    Shape,
    Slide,
    Stat,
    Table,
    Text,
)

__all__ = [
    "Chart",
    "Deck",
    "DeckValidationError",
    "Grid",
    "Header",
    "Image",
    "RenderReport",
    "Sequence",
    "Shape",
    "Slide",
    "Stat",
    "Table",
    "Text",
    "ValidationReport",
    "render_deck",
    "validate",
]
