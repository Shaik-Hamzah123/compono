"""Console-script entry point mirroring the render_deck/validate/review verbs.

compono validate spec.json
compono review spec.json
compono render spec.json --template modern -o deck.pptx
compono reference
compono inspire scan decks/ -o skills/inspire-myteam/
compono docx validate doc_spec.json
compono docx render doc_spec.json -o report.docx
compono template extract corporate_master.pptx acme -o src/compono/templates/
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from compono.docx import DocxValidationError, render_docx, validate_docx
from compono.inspire import aggregate, write_skill
from compono.reference import reference
from compono.render import DeckValidationError, render_deck, validate
from compono.resolver import Template
from compono.review import review
from compono.template_authoring import extract_template_data, write_extracted_template


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

    docx_parser = subparsers.add_parser(
        "docx", help="Validate/render a docx document spec."
    )
    docx_subparsers = docx_parser.add_subparsers(dest="docx_command", required=True)
    docx_validate_parser = docx_subparsers.add_parser(
        "validate", help="Validate a docx document spec without rendering."
    )
    docx_validate_parser.add_argument("spec", help="Path to a JSON docx spec.")
    docx_render_parser = docx_subparsers.add_parser(
        "render", help="Render a docx document spec to a .docx file."
    )
    docx_render_parser.add_argument("spec", help="Path to a JSON docx spec.")
    docx_render_parser.add_argument(
        "-o", "--output", default="document.docx", help="Output .docx path."
    )

    template_parser = subparsers.add_parser(
        "template", help="Developer-side template tooling (not agent-facing)."
    )
    template_subparsers = template_parser.add_subparsers(
        dest="template_command", required=True
    )
    template_extract_parser = template_subparsers.add_parser(
        "extract",
        help=(
            "Draft a new templates/<name>.yaml from an existing .pptx's page "
            "size, theme accent colors, theme font, and master logo. Best-"
            "effort — review the written yaml before committing it, same as "
            "any hand-authored template."
        ),
    )
    template_extract_parser.add_argument("source", help="Path to the source .pptx.")
    template_extract_parser.add_argument("name", help="Name for the new template.")
    template_extract_parser.add_argument(
        "-o",
        "--output-dir",
        default=str(Path(__file__).parent / "templates"),
        help="Directory to write <name>.yaml (and assets/<name>-logo.* if a "
        "logo was found) into. Defaults to compono's own bundled templates/.",
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

    if args.command == "docx" and args.docx_command == "validate":
        spec = _load_spec(args.spec)
        docx_validation_report = validate_docx(spec)
        print(
            json.dumps(
                {
                    "valid": docx_validation_report.valid,
                    "errors": docx_validation_report.errors,
                    "warnings": docx_validation_report.warnings,
                },
                indent=2,
            )
        )
        return 0 if docx_validation_report.valid else 1

    if args.command == "docx" and args.docx_command == "render":
        spec = _load_spec(args.spec)
        try:
            docx_render_report = render_docx(spec, args.output)
        except DocxValidationError as exc:
            print(
                json.dumps({"valid": False, "errors": exc.errors}, indent=2),
                file=sys.stderr,
            )
            return 1
        print(
            json.dumps(
                {
                    "docx_path": str(docx_render_report.docx_path),
                    "manifest": docx_render_report.manifest,
                    "warnings": docx_render_report.warnings,
                },
                indent=2,
            )
        )
        return 0

    if args.command == "template" and args.template_command == "extract":
        data = extract_template_data(Path(args.source))
        yaml_path = write_extracted_template(data, args.name, Path(args.output_dir))
        print(
            json.dumps(
                {
                    "template_yaml": str(yaml_path),
                    "font_family": data.font_family,
                    "primary_color": data.primary_color,
                    "accent_color": data.accent_color,
                    "logo_found": data.logo_bytes is not None,
                },
                indent=2,
            )
        )
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
