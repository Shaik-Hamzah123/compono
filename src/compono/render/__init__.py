"""Orchestrates validate -> resolve -> write pptx.

Exposes the two public verbs (COMPONO_PLAN.md sections 8-9): render_deck(spec)
and validate(spec). No client objects, no session lifecycle — both are pure
functions over a Deck spec (raw dict or a typed Deck).

Full v1 primitive catalog: header, text, image, stat, grid, table, sequence,
chart, shape (COMPONO_PLAN.md section 5); plus `diagram`, added post-v1
(a node-graph flowchart whose nodes/edges are synthesized as `shape`
primitives at layout time — see resolver's `diagram.py`); plus `gantt`,
also post-v1 (a Gantt/timeline chart that fully collapses into a
synthesized `table` at layout time — see resolver's `gantt.py` — needing
zero code in this package at all).

Split into submodules, one per concern, since the original flat
`render.py` grew with every new primitive:
- `_shared.py` — font-size constants, shape-kind/alignment lookup tables,
  font resolution, and small drawing helpers shared across more than one
  primitive's renderer.
- `_overflow.py` — pre-render text-extraction/overflow-checking
  (`_extract_text_fields`, `_check_slide`), parallel to `validator.py`'s
  role, distinct from the "write real OOXML" concern below.
- `primitives.py` — every `_render_<primitive>` function — the file
  "Adding a new primitive" (`.claude/CLAUDE.md`) points to.
- `deck.py` — `validate`/`render_deck`, the two public verbs, plus the
  per-slide/per-primitive dispatch that ties `primitives.py`'s functions
  together.
- `types.py` — `DeckValidationError`/`ValidationReport`/`RenderReport`,
  kept separate so `_shared.py` can raise `DeckValidationError` without an
  import cycle with `deck.py`.

This `__init__.py` re-exports every name the rest of the codebase (and
`tests/`) imports from `compono.render` today, so `from compono.render
import validate` etc. is unaffected by the split.
"""

from __future__ import annotations

from ._overflow import (
    _extract_text_fields,
    _sequence_step_rects,
    _table_cell_rects,
    _table_column_widths_emu,
)
from ._shared import _parse_deck, _resolve_font_path, resolve_deck_template
from .deck import render_deck, validate
from .types import DeckValidationError, RenderReport, ValidationReport

__all__ = [
    "DeckValidationError",
    "RenderReport",
    "ValidationReport",
    "_extract_text_fields",
    "_parse_deck",
    "_resolve_font_path",
    "_sequence_step_rects",
    "_table_cell_rects",
    "_table_column_widths_emu",
    "render_deck",
    "resolve_deck_template",
    "validate",
]
