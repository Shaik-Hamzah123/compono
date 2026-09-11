"""Tests for compono_mcp.server — call the underlying tool functions directly
(no live stdio transport needed) with a small inline spec, mirroring
examples/minimal.json's shape (not a cross-package file reference, since an
installed compono-mcp wheel won't carry compono's examples/ directory).
"""

from pathlib import Path

from compono_mcp.server import reference, render_deck_tool, validate_deck

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
    result = validate_deck({"slides": [{"body": [{"primitive": "header"}]}]})  # missing required title
    assert result["valid"] is False
    error = result["errors"][0]
    assert set(error.keys()) >= {"slide", "primitive", "field", "error", "detail", "fix"}


def test_render_deck_tool_writes_a_real_pptx(tmp_path: Path) -> None:
    output = tmp_path / "deck.pptx"
    result = render_deck_tool(MINIMAL_SPEC, str(output))

    assert result["pptx_path"] == str(output)
    assert output.exists()
    assert "warnings" in result


def test_render_deck_tool_returns_structured_errors_instead_of_raising(tmp_path: Path) -> None:
    output = tmp_path / "deck.pptx"
    result = render_deck_tool({"slides": [{"body": [{"primitive": "header"}]}]}, str(output))

    assert result["valid"] is False
    assert result["errors"]
    assert not output.exists()


def test_reference_resource_returns_nonempty_text_with_expected_content() -> None:
    text = reference()
    assert len(text) > 500
    assert "render_deck" in text
    assert "validate" in text
