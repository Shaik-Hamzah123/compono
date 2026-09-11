"""Self-serve documentation for any agent with code-exec/shell access but no
MCP connection or Claude Code skill loaded (COMPONO_PLAN.md section 8, item
6 — "one reference doc, dual-purpose"). `pip install compono` alone gets an
agent none of SKILL.md or compono-mcp's `reference()` MCP resource — this is
the one channel that works regardless: `import compono; compono.reference()`
or `compono reference` on the command line.
"""

from __future__ import annotations

import importlib.resources


def reference() -> str:
    """The same reference content as README.md/SKILL.md/compono-mcp's
    reference.md (kept in sync by convention, see .claude/CLAUDE.md) —
    packaged inside compono itself so it ships with a plain `pip install`.
    """
    return (
        importlib.resources.files("compono")
        .joinpath("reference.md")
        .read_text(encoding="utf-8")
    )
