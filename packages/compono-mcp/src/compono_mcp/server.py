"""MCP server exposing compono's render_deck/validate/review as MCP tools.

Every tool here is a thin proxy — no reimplemented logic. `spec` parameters
are typed as plain `dict`, not the `Deck` pydantic model, so malformed input
reaches compono.validate/render_deck itself and comes back as compono's own
structured {slide, primitive, field, error, detail, fix} shape, never MCP's
generic schema-rejection error (this is deliberate — see the project plan).
"""

from __future__ import annotations

import importlib.resources
from typing import Any

from fastmcp import FastMCP

from compono import (
    DeckValidationError,
    aggregate,
    render_deck,
    review,
    validate,
    write_skill,
)

mcp = FastMCP("compono")


@mcp.tool()
def validate_deck(spec: dict[str, Any]) -> dict[str, Any]:
    """Validate a compono deck spec: schema + layout + text-overflow checks, no file write.

    Cheap (millisecond-scale) — prefer this before render_deck when iterating.
    Never raises: malformed input comes back as {valid: false, errors: [...]},
    each error shaped {slide, primitive, field, error, detail, fix}.
    """
    report = validate(spec)
    return {"valid": report.valid, "errors": report.errors, "warnings": report.warnings}


@mcp.tool()
def render_deck_tool(spec: dict[str, Any], output_path: str) -> dict[str, Any]:
    """Render a compono deck spec to a real, editable .pptx file at output_path.

    On success: {pptx_path, manifest, warnings}. On any validation/layout/
    overflow error: {valid: false, errors: [...]} in the same shape as
    validate_deck — nothing is written to output_path in that case.
    """
    try:
        report = render_deck(spec, output_path)
    except DeckValidationError as exc:
        return {"valid": False, "errors": exc.errors}

    return {
        "pptx_path": str(report.pptx_path),
        "manifest": report.manifest,
        "warnings": report.warnings,
    }


@mcp.tool()
def review_deck(spec: dict[str, Any]) -> dict[str, Any]:
    """Design-quality suggestions for a compono deck spec: contrast, whitespace,
    image fit, font-size proximity to overflow. Never blocking — no valid/invalid,
    only {suggestions: [...], warnings: [...]}; suggestions may be empty.
    Complements validate_deck, doesn't replace it — pair the two.
    """
    report = review(spec)
    return {"suggestions": report.suggestions, "warnings": report.warnings}


@mcp.tool()
def inspire_scan(
    pptx_paths: list[str],
    out_dir: str,
    name: str = "custom",
    min_repeat_ratio: float = 0.5,
) -> dict[str, Any]:
    """Scan a set of .pptx files someone already likes into a style profile,
    and write it as a skills/inspire-<name>/ folder (SKILL.md + profile.json)
    at out_dir.

    Extracts only measurable structure — palette, fonts, spacing, grid
    patterns with a confidence score — never literal text or images from
    the scanned decks. A fact must recur in at least min_repeat_ratio of
    the given decks to be reported as a real practice rather than a one-off
    quirk. Returns {skill_md, profile_json, n_decks_scanned}; a .pptx that
    fails to open is skipped and named in the returned warnings, not raised.
    """
    profile = aggregate(pptx_paths, min_repeat_ratio=min_repeat_ratio)
    files = write_skill(profile, out_dir, name=name)
    return {
        "skill_md": str(files.skill_md),
        "profile_json": str(files.profile_json),
        "n_decks_scanned": profile["n_example_decks"],
        "warnings": profile["warnings"],
    }


@mcp.resource("compono://reference")
def reference() -> str:
    """The full agent-facing compono reference: quickstart, primitive catalog,
    worked examples, and error shape — for MCP clients without Claude Code's
    skill system.
    """
    return (
        importlib.resources.files("compono_mcp")
        .joinpath("reference.md")
        .read_text(encoding="utf-8")
    )


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
