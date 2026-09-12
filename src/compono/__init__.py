"""compono — agent-oriented, code-based PPTX/DOCX generation library.

Public exports ONLY (COMPONO_PLAN.md section 10) — resolver/validator/template
loader stay internal, reached only through render_deck/validate.
"""

from compono.docx import (
    DocxRenderReport,
    DocxValidationError,
    render_docx,
    validate_docx,
)
from compono.docx_schema import (
    BulletList,
    DocChart,
    DocImage,
    DocTable,
    DocxDoc,
    Heading,
    NumberedList,
    PageBreak,
    Paragraph,
    Run,
    Section,
)
from compono.inspire import SkillFiles, aggregate, scan_deck, write_skill
from compono.reference import reference
from compono.render import (
    DeckValidationError,
    RenderReport,
    ValidationReport,
    render_deck,
    validate,
)
from compono.review import ReviewReport, review
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
    "BulletList",
    "Chart",
    "Deck",
    "DeckValidationError",
    "DocChart",
    "DocImage",
    "DocTable",
    "DocxDoc",
    "DocxRenderReport",
    "DocxValidationError",
    "Grid",
    "Header",
    "Heading",
    "Image",
    "NumberedList",
    "PageBreak",
    "Paragraph",
    "RenderReport",
    "ReviewReport",
    "Run",
    "Section",
    "Sequence",
    "Shape",
    "SkillFiles",
    "Slide",
    "Stat",
    "Table",
    "Text",
    "ValidationReport",
    "aggregate",
    "reference",
    "render_deck",
    "render_docx",
    "review",
    "scan_deck",
    "validate",
    "validate_docx",
    "write_skill",
]
