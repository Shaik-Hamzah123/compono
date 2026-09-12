"""Tests for compono_mcp.server — call the underlying tool functions directly
(no live stdio transport needed) with a small inline spec (not a
cross-package file reference, since an installed compono-mcp wheel won't
carry compono's examples/ directory).
"""

from pathlib import Path

from compono_mcp.server import (
    inspire_scan,
    reference,
    render_deck_tool,
    review_deck,
    validate_deck,
)

MINIMAL_SPEC = {
    "slides": [
        {
            "header": {"title": "Q3 Results", "subtitle": "Engineering team"},
            "body": [
                {
                    "primitive": "text",
                    "mode": "bullets",
                    "content": ["Shipped the resolver", "Cut render time by 40%"],
                }
            ],
        }
    ]
}


def test_validate_deck_accepts_valid_spec() -> None:
    result = validate_deck(MINIMAL_SPEC)
    assert result["valid"] is True
    assert result["errors"] == []


def test_validate_deck_returns_structured_errors_for_malformed_spec() -> None:
    result = validate_deck(
        {"slides": [{"body": [{"primitive": "header"}]}]}
    )  # missing required title
    assert result["valid"] is False
    error = result["errors"][0]
    assert set(error.keys()) >= {
        "slide",
        "primitive",
        "field",
        "error",
        "detail",
        "fix",
    }


def test_render_deck_tool_writes_a_real_pptx(tmp_path: Path) -> None:
    output = tmp_path / "deck.pptx"
    result = render_deck_tool(MINIMAL_SPEC, str(output))

    assert result["pptx_path"] == str(output)
    assert output.exists()
    assert "warnings" in result


def test_render_deck_tool_returns_structured_errors_instead_of_raising(
    tmp_path: Path,
) -> None:
    output = tmp_path / "deck.pptx"
    result = render_deck_tool(
        {"slides": [{"body": [{"primitive": "header"}]}]}, str(output)
    )

    assert result["valid"] is False
    assert result["errors"]
    assert not output.exists()


def test_review_deck_returns_suggestions_never_blocking() -> None:
    result = review_deck(MINIMAL_SPEC)
    assert "suggestions" in result and "warnings" in result
    assert isinstance(result["suggestions"], list)


def test_review_deck_flags_low_contrast_shape_text() -> None:
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
    result = review_deck(spec)
    assert any(s["category"] == "contrast" for s in result["suggestions"])


def test_inspire_scan_writes_skill_folder_from_real_pptx_files(
    tmp_path: Path,
) -> None:
    from compono import render_deck as _render_deck

    deck_path = tmp_path / "liked.pptx"
    _render_deck(MINIMAL_SPEC, str(deck_path))

    out_dir = tmp_path / "skills" / "inspire-team"
    result = inspire_scan([str(deck_path)], str(out_dir), name="team")

    assert result["n_decks_scanned"] == 1
    assert result["warnings"] == []
    assert Path(result["skill_md"]).exists()
    assert Path(result["profile_json"]).exists()


def test_inspire_scan_never_leaks_literal_source_text(tmp_path: Path) -> None:
    from compono import render_deck as _render_deck

    deck_path = tmp_path / "liked.pptx"
    _render_deck(MINIMAL_SPEC, str(deck_path))

    out_dir = tmp_path / "skills" / "inspire-team"
    result = inspire_scan([str(deck_path)], str(out_dir), name="team")

    profile_text = Path(result["profile_json"]).read_text(encoding="utf-8")
    assert "Shipped the resolver" not in profile_text
    assert "Q3 Results" not in profile_text


def test_reference_resource_returns_nonempty_text_with_expected_content() -> None:
    text = reference()
    assert len(text) > 500
    assert "render_deck" in text
    assert "validate" in text
