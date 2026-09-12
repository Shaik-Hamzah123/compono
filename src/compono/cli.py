"""Console-script entry point mirroring the render_deck/validate/review verbs.

compono validate spec.json
compono review spec.json
compono render spec.json --template modern -o deck.pptx
compono reference
compono inspire scan decks/ -o skills/inspire-myteam/
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from compono.inspire import aggregate, write_skill
from compono.reference import reference
from compono.render import DeckValidationError, render_deck, validate
from compono.resolver import Template
from compono.review import review


def _load_spec(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="compono")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser(
        "validate", help="Validate a deck spec without rendering."
    )
    validate_parser.add_argument("spec", help="Path to a JSON deck spec.")

    review_parser = subparsers.add_parser(
        "review", help="Design-quality suggestions for a deck spec (never blocking)."
    )
    review_parser.add_argument("spec", help="Path to a JSON deck spec.")

    subparsers.add_parser(
        "reference",
        help=(
            "Print compono's full agent-facing reference (quickstart, primitive "
            "catalog, error shape) — for any agent with shell access but no MCP "
            "or Claude Code skill loaded."
        ),
    )

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

    inspire_parser = subparsers.add_parser(
        "inspire", help="Scan liked decks into a style profile/skill."
    )
    inspire_subparsers = inspire_parser.add_subparsers(
        dest="inspire_command", required=True
    )
    scan_parser = inspire_subparsers.add_parser(
        "scan", help="Scan a folder of .pptx files into skills/inspire-<name>/."
    )
    scan_parser.add_argument("folder", help="Folder containing .pptx files to scan.")
    scan_parser.add_argument(
        "-o",
        "--output",
        required=True,
        help="Output folder for SKILL.md + profile.json.",
    )
    scan_parser.add_argument(
        "--name", default="custom", help="Name used in SKILL.md's frontmatter."
    )
    scan_parser.add_argument(
        "--min-repeat-ratio",
        type=float,
        default=0.5,
        help="Fraction of decks a fact must appear in to count as recurring.",
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

    if args.command == "review":
        spec = _load_spec(args.spec)
        try:
            review_report = review(spec)
        except DeckValidationError as exc:
            print(
                json.dumps({"valid": False, "errors": exc.errors}, indent=2),
                file=sys.stderr,
            )
            return 1
        print(
            json.dumps(
                {
                    "suggestions": review_report.suggestions,
                    "warnings": review_report.warnings,
                },
                indent=2,
            )
        )
        return 0

    if args.command == "reference":
        print(reference())
        return 0

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

    if args.command == "inspire" and args.inspire_command == "scan":
        pptx_paths = sorted(Path(args.folder).glob("*.pptx"))
        if not pptx_paths:
            print(
                json.dumps({"error": f"No .pptx files found under {args.folder!r}."}),
                file=sys.stderr,
            )
            return 1
        profile = aggregate(pptx_paths, min_repeat_ratio=args.min_repeat_ratio)
        files = write_skill(profile, args.output, name=args.name)
        print(
            json.dumps(
                {
                    "skill_md": str(files.skill_md),
                    "profile_json": str(files.profile_json),
                    "n_decks_scanned": profile["n_example_decks"],
                    "warnings": profile["warnings"],
                },
                indent=2,
            )
        )
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
