"""Layout resolver: directional box model (CSS-flexbox mental model).

Computes real EMU positions from primitive specs so the agent never writes
raw x/y/w/h coordinates (COMPONO_PLAN.md section 6).

Split into submodules, one per concern, since the original flat
`resolver.py` grew with every new primitive:
- `template.py` — `Template` (page size, margins, header/footer heights,
  gutter, optional `colors`/`logo` branding fields) and its loaders.
- `types.py` — `Rect`, `ConnectorPoints`, `LayoutResult`.
- `layout.py` — `resolve_slide`'s directional box model, body stacking,
  and `grid`'s 2D layout; dispatches to `diagram.py`/`gantt.py` for those
  primitives' own layout.
- `diagram.py` — `diagram` layout: nodes synthesized as real `shape`
  primitives, edges routed via `connectors.py`'s router.
- `gantt.py` — `gantt` layout: fully collapses into a synthesized `table`.
- `connectors.py` — the obstacle-avoiding connector router shared by plain
  `shape(kind="connector")` resolution and `diagram`'s edges.

This `__init__.py` re-exports every name the rest of the codebase (and
`tests/`) imports from `compono.resolver` today, so `from compono.resolver
import Template` etc. is unaffected by the split.
"""

from __future__ import annotations

from .connectors import _CONNECTOR_GAP_EMU
from .layout import resolve_slide
from .template import DEFAULT_TEMPLATE_PATH, EMU_PER_INCH, Template
from .types import ConnectorPoints, LayoutResult, Rect

__all__ = [
    "DEFAULT_TEMPLATE_PATH",
    "EMU_PER_INCH",
    "_CONNECTOR_GAP_EMU",
    "ConnectorPoints",
    "LayoutResult",
    "Rect",
    "Template",
    "resolve_slide",
]
