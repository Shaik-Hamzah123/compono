"""The exception type and report dataclasses shared across the render
package — kept separate from `deck.py` (the public verbs) so that
`_shared.py` (which raises `DeckValidationError` from `_parse_deck`) can
depend on them without an import cycle.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from compono.resolver import LayoutResult


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
