"""Console-script entry point mirroring the render_deck/validate verbs.

compono validate spec.json
compono render spec.json --template modern -o deck.pptx
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from compono.render import DeckValidationError, render_deck, validate
from compono.resolver import Template


def _load_spec(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="compono")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser(
        "validate", help="Validate a deck spec without rendering."
    )
    validate_parser.add_argument("spec", help="Path to a JSON deck spec.")

    render_parser = subparsers.add_parser(
        "render", help="Render a deck spec to a .pptx file."
    )
    render_parser.add_argument("spec", help="Path to a JSON deck spec.")
    render_parser.add_argument(
        "-o", "--output", default="deck.pptx", help="Output .pptx path."
    )
    render_parser.add_argument(
        "--template",
        default=None,
        help=(
            "Template name under templates/ (e.g. 'default', 'modern'). "
            "Overrides the spec's own `template` field if both are given."
        ),
    )

    args = parser.parse_args(argv)

    if args.command == "validate":
        spec = _load_spec(args.spec)
        validation_report = validate(spec)
        print(
            json.dumps(
                {
                    "valid": validation_report.valid,
                    "errors": validation_report.errors,
                    "warnings": validation_report.warnings,
                },
                indent=2,
            )
        )
        return 0 if validation_report.valid else 1

    if args.command == "render":
        spec = _load_spec(args.spec)
        try:
            cli_template = Template.from_name(args.template) if args.template else None
        except ValueError as exc:
            print(
                json.dumps({"valid": False, "error": str(exc)}, indent=2),
                file=sys.stderr,
            )
            return 1
        try:
            render_report = render_deck(spec, args.output, template=cli_template)
        except DeckValidationError as exc:
            print(
                json.dumps({"valid": False, "errors": exc.errors}, indent=2),
                file=sys.stderr,
            )
            return 1
        print(
            json.dumps(
                {
                    "pptx_path": str(render_report.pptx_path),
                    "warnings": render_report.warnings,
                },
                indent=2,
            )
        )
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
