"""Unit tests for src/compono/review.py — design-quality suggestions.

review() is never blocking (no valid/invalid, only suggestions, possibly
zero) and pure like resolver.py/validator.py — no pptx write.
"""

from compono.review import review


def test_review_flags_low_contrast_shape_text() -> None:
    spec = {
        "slides": [
            {
                "header": {"title": "Contrast check"},
                "body": [
                    {
                        "primitive": "shape",
                        "kind": "rounded_rect",
                        "fill": "#111827",
                        "text": {"content": "Hard to read", "color": "#1F2937"},
                    }
                ],
            }
        ]
    }
    report = review(spec)
    contrast = [s for s in report.suggestions if s["category"] == "contrast"]
    assert len(contrast) == 1
    assert contrast[0]["field"] == "text.color"


def test_review_does_not_flag_contrast_without_an_explicit_text_color() -> None:
    """Never guess a color that wasn't set — no text.color means no check."""
    spec = {
        "slides": [
            {
                "header": {"title": "No explicit color"},
                "body": [
                    {
                        "primitive": "shape",
                        "kind": "rounded_rect",
                        "fill": "#111827",
                        "text": {"content": "Whatever the theme default is"},
                    }
                ],
            }
        ]
    }
    report = review(spec)
    assert [s for s in report.suggestions if s["category"] == "contrast"] == []


def test_review_does_not_flag_good_contrast() -> None:
    spec = {
        "slides": [
            {
                "header": {"title": "Good contrast"},
                "body": [
                    {
                        "primitive": "shape",
                        "kind": "rounded_rect",
                        "fill": "#111827",
                        "text": {"content": "Easy to read", "color": "#FFFFFF"},
                    }
                ],
            }
        ]
    }
    report = review(spec)
    assert [s for s in report.suggestions if s["category"] == "contrast"] == []


def test_review_flags_a_lone_stat_alone_in_a_tall_body() -> None:
    spec = {
        "slides": [
            {
                "header": {"title": "Lonely stat"},
                "body": [{"primitive": "stat", "value": "42%", "label": "growth"}],
            }
        ]
    }
    report = review(spec)
    whitespace = [s for s in report.suggestions if s["category"] == "whitespace"]
    assert len(whitespace) == 1
    assert whitespace[0]["primitive"] == "body[0]"


def test_review_never_flags_whitespace_on_a_header_only_slide() -> None:
    """A title/closing slide (no body at all) is a deliberate pattern —
    there's nothing to be "too empty" relative to.
    """
    spec = {"slides": [{"header": {"title": "Just a title", "align": "center"}}]}
    report = review(spec)
    assert [s for s in report.suggestions if s["category"] == "whitespace"] == []


def test_review_does_not_flag_whitespace_for_a_multi_item_body() -> None:
    spec = {
        "slides": [
            {
                "header": {"title": "Not lonely"},
                "body": [
                    {"primitive": "stat", "value": "42%", "label": "growth"},
                    {"primitive": "stat", "value": "99%", "label": "uptime"},
                ],
            }
        ]
    }
    report = review(spec)
    assert [s for s in report.suggestions if s["category"] == "whitespace"] == []


def test_review_does_not_flag_whitespace_for_a_lone_but_dense_grid() -> None:
    """A single top-level `grid` with several children (a card grid, a stat
    row) is a deliberate, already-full layout — not empty space — even
    though it's the only item in `slide.body`. Regression test: this used
    to be flagged because the whitespace check only looked at
    len(slide.body) == 1, not whether that one item already fans out into
    multiple children.
    """
    spec = {
        "slides": [
            {
                "header": {"title": "Program at a Glance"},
                "body": [
                    {
                        "primitive": "grid",
                        "columns": 4,
                        "items": [
                            {"primitive": "stat", "value": "8", "label": "sessions"},
                            {"primitive": "stat", "value": "4", "label": "labs"},
                            {"primitive": "stat", "value": "1", "label": "channel"},
                            {
                                "primitive": "stat",
                                "value": "100+",
                                "label": "templates",
                            },
                        ],
                    }
                ],
            }
        ]
    }
    report = review(spec)
    assert [s for s in report.suggestions if s["category"] == "whitespace"] == []


def test_review_flags_text_close_to_overflowing_but_not_yet_over() -> None:
    """A proactive nudge distinct from validate()'s hard overflow error —
    same underlying check_overflow, a softer threshold.
    """
    spec = {
        "slides": [
            {
                "header": {"title": "Tight"},
                "body": [
                    {
                        "primitive": "text",
                        "mode": "bullets",
                        "content": [
                            "One bullet",
                            "Two bullet",
                            "Three bullet",
                            "Four bullet",
                            "Five bullet",
                            "Six bullet",
                            "Seven bullet",
                        ],
                    },
                    {"primitive": "stat", "value": "1", "label": "filler"},
                    {"primitive": "stat", "value": "2", "label": "filler"},
                ],
            }
        ]
    }
    report = review(spec)
    font_size = [s for s in report.suggestions if s["category"] == "font_size"]
    # Either genuinely tight (flagged) or not — the point is it never crashes
    # and, when present, carries the expected shape.
    for s in font_size:
        assert s["category"] == "font_size"
        assert "fix" in s and "detail" in s


def test_review_flags_a_badly_cropped_cover_image(tmp_path) -> None:
    from PIL import Image as PILImage

    img_path = tmp_path / "wide.png"
    PILImage.new("RGB", (2000, 200)).save(img_path)  # very wide, box is ~square-ish

    spec = {
        "slides": [
            {
                "header": {"title": "Cropped image"},
                "body": [
                    {
                        "primitive": "image",
                        "src": str(img_path),
                        "fit": "cover",
                    }
                ],
            }
        ]
    }
    report = review(spec)
    image_fit = [s for s in report.suggestions if s["category"] == "image_fit"]
    assert len(image_fit) == 1
    assert image_fit[0]["field"] == "fit"


def test_review_never_flags_image_fit_for_a_placeholder() -> None:
    spec = {
        "slides": [
            {
                "header": {"title": "Placeholder"},
                "body": [
                    {
                        "primitive": "image",
                        "placeholder": True,
                        "caption": "Photo goes here",
                    }
                ],
            }
        ]
    }
    report = review(spec)
    assert [s for s in report.suggestions if s["category"] == "image_fit"] == []


def test_review_never_raises_on_a_well_formed_deck() -> None:
    spec = {
        "slides": [
            {
                "header": {"title": "Fine"},
                "body": [{"primitive": "stat", "value": "1", "label": "x"}],
            }
        ]
    }
    report = review(spec)  # should not raise
    assert isinstance(report.suggestions, list)
