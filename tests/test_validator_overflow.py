"""Unit tests for src/compono/validator.py.

Core measurement/wrap/overflow functions are pure and tested against a
hand-built FontMetrics table — no font file or rendering involved. A small
integration test at the bottom exercises `load_font_metrics` against the
bundled reference font (Open Sans, src/compono/fonts/) that every stock
template's `font_family` resolves to for overflow measurement.
"""

import pytest

from compono.validator import (
    FontMetrics,
    build_overflow_error,
    check_overflow,
    load_font_metrics,
    measure_text_width_pt,
    resolve_safe_font,
    wrap_lines,
)

UNITS_PER_EM = 1000


@pytest.fixture
def monospace_metrics() -> FontMetrics:
    """Every character (including space) advances 500 units — trivial to reason about."""
    return FontMetrics(advance_widths={}, units_per_em=UNITS_PER_EM, default_advance=500)


def test_measure_text_width_pt_uses_default_advance(monospace_metrics: FontMetrics) -> None:
    # 4 chars * 500/1000 * 20pt = 40pt
    assert measure_text_width_pt("abcd", monospace_metrics, font_size_pt=20) == 40


def test_measure_text_width_pt_prefers_known_advance() -> None:
    metrics = FontMetrics(advance_widths={"i": 100}, units_per_em=1000, default_advance=500)
    # "i" is narrow (100/1000), "m" falls back to default (500/1000)
    assert measure_text_width_pt("i", metrics, font_size_pt=10) == 1
    assert measure_text_width_pt("m", metrics, font_size_pt=10) == 5


def test_wrap_lines_empty_text_returns_no_lines(monospace_metrics: FontMetrics) -> None:
    assert wrap_lines("", monospace_metrics, font_size_pt=20, max_width_pt=1000) == []


def test_wrap_lines_fits_on_one_line(monospace_metrics: FontMetrics) -> None:
    lines = wrap_lines("one two three", monospace_metrics, font_size_pt=10, max_width_pt=1000)
    assert lines == ["one two three"]


def test_wrap_lines_wraps_when_too_narrow(monospace_metrics: FontMetrics) -> None:
    # each word is 3 chars * 500/1000 * 10pt = 15pt; max_width just fits one word at a time
    lines = wrap_lines("one two three", monospace_metrics, font_size_pt=10, max_width_pt=16)
    assert lines == ["one", "two", "three"]


def test_wrap_lines_never_splits_a_single_word_even_if_it_overflows(
    monospace_metrics: FontMetrics,
) -> None:
    lines = wrap_lines("supercalifragilistic", monospace_metrics, font_size_pt=10, max_width_pt=1)
    assert lines == ["supercalifragilistic"]


def test_check_overflow_fits(monospace_metrics: FontMetrics) -> None:
    report = check_overflow(
        "short text",
        monospace_metrics,
        font_size_pt=18,
        box_width_pt=500,
        box_height_pt=100,
    )
    assert report.overflow is False
    assert report.line_count == 1


def test_check_overflow_flags_overflow(monospace_metrics: FontMetrics) -> None:
    long_text = " ".join(["word"] * 50)
    report = check_overflow(
        long_text,
        monospace_metrics,
        font_size_pt=18,
        box_width_pt=100,
        box_height_pt=20,
    )
    assert report.overflow is True
    assert report.line_count > 1


def test_build_overflow_error_shape(monospace_metrics: FontMetrics) -> None:
    report = check_overflow(
        " ".join(["word"] * 50),
        monospace_metrics,
        font_size_pt=18,
        box_width_pt=100,
        box_height_pt=20,
    )
    error = build_overflow_error(
        slide=3,
        primitive_path="grid.items[1]",
        field="content",
        report=report,
        font_size_pt=18,
    )
    assert error["slide"] == 3
    assert error["primitive"] == "grid.items[1]"
    assert error["field"] == "content"
    assert error["error"] == "overflow"
    assert "too tall" in error["detail"]
    assert "fix" in error


def test_resolve_safe_font_returns_none_when_not_in_allowlist() -> None:
    assert resolve_safe_font("SomeRandomFont") is None


# --- Integration tests against the bundled reference font ---

_STOCK_TEMPLATE_FONT_NAMES = ["Calibri", "Georgia", "Times New Roman", "Arial", "Open Sans"]


@pytest.mark.parametrize("font_name", _STOCK_TEMPLATE_FONT_NAMES)
def test_resolve_safe_font_resolves_every_stock_template_font(font_name: str) -> None:
    """Every stock template's `font_family` (templates/*.yaml) must resolve to
    a real, existing bundled file — this is what backs overflow measurement
    for that template. It is never the font actually written into a deck's
    OOXML; only the template's own font_family string is (see
    docs/templates-and-fonts.md).
    """
    path = resolve_safe_font(font_name)
    assert path is not None
    assert path.exists()


def test_load_font_metrics_from_bundled_font_file() -> None:
    path = resolve_safe_font("Open Sans")
    assert path is not None
    metrics = load_font_metrics(path)
    assert metrics.units_per_em > 0
    assert " " in metrics.advance_widths
    assert metrics.advance_widths[" "] > 0
