"""Overflow validator: fonttools-based glyph advance-width measurement.

COMPONO_PLAN.md section 7. The core measurement/wrap/overflow functions are
pure and independently unit-testable with zero rendering involved — they
operate on a `FontMetrics` table, not a font file. `load_font_metrics` is the
one function that touches a real font file (via fontTools), reading actual
advance widths directly rather than rasterizing anything.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fontTools.ttLib import TTFont  # type: ignore[import-untyped]  # no stubs published

FONTS_DIR = Path(__file__).parent / "fonts"

# Bundled/verified-present fonts this library will render text with. Anything
# outside this list is substituted for the template default or flagged.
# Empty until real font files are bundled (see fonts/.gitkeep) — resolve_safe_font
# returns None for every name until then, which is the correct/honest behavior.
SAFE_FONTS: dict[str, str] = {}


@dataclass(frozen=True)
class FontMetrics:
    """Per-character advance widths, in font units, normalized by `units_per_em`."""

    advance_widths: dict[str, int]
    units_per_em: int
    default_advance: int  # fallback for characters missing from the font's cmap


def load_font_metrics(font_path: Path) -> FontMetrics:
    """Read real glyph advance widths from a font file. No rendering required."""
    font = TTFont(font_path, lazy=True)
    try:
        cmap = font.getBestCmap()
        hmtx = font["hmtx"]
        units_per_em = font["head"].unitsPerEm

        advance_widths: dict[str, int] = {}
        for codepoint, glyph_name in cmap.items():
            advance_widths[chr(codepoint)] = hmtx[glyph_name][0]

        space_advance = advance_widths.get(" ")
        default_advance = space_advance if space_advance is not None else round(units_per_em * 0.5)

        return FontMetrics(
            advance_widths=advance_widths,
            units_per_em=units_per_em,
            default_advance=default_advance,
        )
    finally:
        font.close()


def resolve_safe_font(name: str) -> Path | None:
    """Look up a bundled/verified-present font by name. None if not in the allowlist."""
    filename = SAFE_FONTS.get(name)
    return FONTS_DIR / filename if filename else None


def _char_width_pt(char: str, metrics: FontMetrics, font_size_pt: float) -> float:
    raw = metrics.advance_widths.get(char, metrics.default_advance)
    return raw / metrics.units_per_em * font_size_pt


def measure_text_width_pt(text: str, metrics: FontMetrics, font_size_pt: float) -> float:
    """Sum measured advance widths for `text` at `font_size_pt`, in points."""
    return sum(_char_width_pt(c, metrics, font_size_pt) for c in text)


def wrap_lines(
    text: str,
    metrics: FontMetrics,
    font_size_pt: float,
    max_width_pt: float,
) -> list[str]:
    """Greedy line-wrap using measured advance widths (COMPONO_PLAN.md section 7)."""
    words = text.split()
    if not words:
        return []

    space_w = _char_width_pt(" ", metrics, font_size_pt)
    lines: list[str] = []
    current_words: list[str] = []
    current_width = 0.0

    for word in words:
        word_w = measure_text_width_pt(word, metrics, font_size_pt)
        candidate_width = word_w if not current_words else current_width + space_w + word_w
        if current_words and candidate_width > max_width_pt:
            lines.append(" ".join(current_words))
            current_words = [word]
            current_width = word_w
        else:
            current_words.append(word)
            current_width = candidate_width

    if current_words:
        lines.append(" ".join(current_words))
    return lines


@dataclass(frozen=True)
class OverflowReport:
    lines: list[str]
    line_count: int
    total_height_pt: float
    box_height_pt: float
    overflow: bool


def check_overflow(
    text: str,
    metrics: FontMetrics,
    font_size_pt: float,
    box_width_pt: float,
    box_height_pt: float,
    line_height_factor: float = 1.2,
) -> OverflowReport:
    """Greedy line-wrap -> line count * line-height -> compare to box height."""
    lines = wrap_lines(text, metrics, font_size_pt, box_width_pt)
    line_height_pt = font_size_pt * line_height_factor
    total_height_pt = len(lines) * line_height_pt
    return OverflowReport(
        lines=lines,
        line_count=len(lines),
        total_height_pt=total_height_pt,
        box_height_pt=box_height_pt,
        overflow=total_height_pt > box_height_pt,
    )


def build_overflow_error(
    slide: int,
    primitive_path: str,
    field: str,
    report: OverflowReport,
    font_size_pt: float,
) -> dict[str, object]:
    """Structured, actionable error — a fix, not just a diagnosis (COMPONO_PLAN.md section 8, item 3)."""
    excess_pt = report.total_height_pt - report.box_height_pt
    return {
        "slide": slide,
        "primitive": primitive_path,
        "field": field,
        "error": "overflow",
        "detail": (
            f"Text is ~{excess_pt:.0f}pt too tall for the box at font size {font_size_pt:g}pt "
            f"({report.line_count} lines)."
        ),
        "fix": "Shorten the text, reduce bullet/line count, or split into two slides.",
    }
