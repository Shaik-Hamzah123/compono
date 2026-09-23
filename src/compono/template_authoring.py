"""Host/developer-side tool: draft a new `templates/<name>.yaml` from an
existing corporate .pptx (`compono template extract`, cli.py).

Deliberately **not** part of the five-module pipeline (schema/resolver/
validator/render/cli) — this module owns the one "read an existing .pptx
for its theme/page-size/logo, then write a template yaml (+ optional logo
asset) to disk" concern, so that neither `resolver.py` (which must stay a
pure, minimal-I/O module per CLAUDE.md — see `Template.from_yaml`'s "one
read" contract) nor `render.py` (reserved for the pptx *write* path) has
to import `pptx` for a second, unrelated reason.

Extraction is always best-effort: a missing/malformed theme part, or no
logo picture on the master, degrades to `None` fields rather than raising
— a developer running the CLI command should get a usable draft yaml to
review/edit, never a crash on an unusual source deck.

**Explicitly not attempted** (see NEXT-STEPS.md): placeholder/slide-layout
geometry inheritance (compono's resolver computes its own EMU box model
and never uses PowerPoint placeholder inheritance, so there is nowhere for
that geometry to plug in), full theme extraction beyond two accent colors
and one body typeface, and chart color theming.
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

EMU_PER_INCH = 914400

_DEFAULT_TEMPLATE_PATH = Path(__file__).parent / "templates" / "default.yaml"

_THEME_NS = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}


@dataclass(frozen=True)
class ExtractedTemplateData:
    """Best-effort data pulled from an existing corporate .pptx. Every
    field beyond page size is independently optional — a missing/malformed
    theme or no master logo just means that field comes back `None`.
    """

    page_width_in: float
    page_height_in: float
    font_family: str | None
    primary_color: str | None
    accent_color: str | None
    logo_bytes: bytes | None
    logo_ext: str | None


def _theme_xml_root(pptx_path: Path) -> Any:
    """Return the parsed `<a:theme>` root of `ppt/theme/theme1.xml`, or
    `None` if the part is missing/unreadable. Deliberately raw zip+lxml —
    python-pptx's `pptx/oxml/theme.py` has no read accessors for theme
    color/font schemes at all (it's a write-only factory for a notes-
    master default theme), so there is no object-model API to use instead.
    """
    from lxml import etree

    try:
        with zipfile.ZipFile(pptx_path) as zf:
            xml_bytes = zf.read("ppt/theme/theme1.xml")
        return etree.fromstring(xml_bytes)
    except (KeyError, zipfile.BadZipFile, etree.XMLSyntaxError, OSError):
        return None


def _theme_color(root: Any, scheme_name: str) -> str | None:
    node = root.find(f"a:themeElements/a:clrScheme/a:{scheme_name}", _THEME_NS)
    if node is None:
        return None
    srgb = node.find("a:srgbClr", _THEME_NS)
    if srgb is not None and srgb.get("val"):
        return f"#{srgb.get('val').upper()}"
    sys_clr = node.find("a:sysClr", _THEME_NS)
    if sys_clr is not None and sys_clr.get("lastClr"):
        return f"#{sys_clr.get('lastClr').upper()}"
    return None


def _theme_font(root: Any) -> str | None:
    for font_group in ("minorFont", "majorFont"):
        node = root.find(
            f"a:themeElements/a:fontScheme/a:{font_group}/a:latin", _THEME_NS
        )
        typeface = node.get("typeface") if node is not None else None
        if typeface and not typeface.startswith("+"):
            return typeface
    return None


def extract_template_data(pptx_path: Path) -> ExtractedTemplateData:
    """Best-effort extraction of a template's page size, theme accent
    colors, theme body font, and master logo from an existing .pptx.

    Margins/header/footer height/gutter are never derived here — see
    `write_extracted_template`, which fills those in from compono's own
    `default.yaml` instead, since arbitrary master placeholder geometry
    has no meaningful mapping onto compono's resolver box model.
    """
    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE_TYPE

    prs = Presentation(str(pptx_path))
    if prs.slide_width is None or prs.slide_height is None:
        raise ValueError(f"{pptx_path} has no slide size set in presentation.xml.")
    page_width_in = prs.slide_width / EMU_PER_INCH
    page_height_in = prs.slide_height / EMU_PER_INCH

    font_family: str | None = None
    primary_color: str | None = None
    accent_color: str | None = None
    theme_root = _theme_xml_root(pptx_path)
    if theme_root is not None:
        font_family = _theme_font(theme_root)
        primary_color = _theme_color(theme_root, "accent1")
        accent_color = _theme_color(theme_root, "accent2")

    logo_bytes: bytes | None = None
    logo_ext: str | None = None
    if prs.slide_masters:
        for shape in prs.slide_masters[0].shapes:
            if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                logo_bytes = shape.image.blob
                logo_ext = shape.image.ext
                break

    return ExtractedTemplateData(
        page_width_in=page_width_in,
        page_height_in=page_height_in,
        font_family=font_family,
        primary_color=primary_color,
        accent_color=accent_color,
        logo_bytes=logo_bytes,
        logo_ext=logo_ext,
    )


def write_extracted_template(
    data: ExtractedTemplateData, name: str, output_dir: Path
) -> Path:
    """Write `<output_dir>/<name>.yaml` (and, if a logo was found,
    `<output_dir>/assets/<name>-logo.<ext>`), merging the extracted page
    size/font/colors onto compono's own default margin/header/footer/
    gutter values. Returns the written yaml's path.
    """
    defaults = yaml.safe_load(_DEFAULT_TEMPLATE_PATH.read_text(encoding="utf-8"))

    doc: dict[str, Any] = {
        "name": name,
        "page": {
            "width_in": round(data.page_width_in, 3),
            "height_in": round(data.page_height_in, 3),
        },
        "margin_in": defaults["margin_in"],
        "header": defaults["header"],
        "footer": defaults["footer"],
        "gutter_in": defaults["gutter_in"],
        "font_family": data.font_family or defaults["font_family"],
    }

    colors = {}
    if data.primary_color:
        colors["primary"] = data.primary_color
    if data.accent_color:
        colors["accent"] = data.accent_color
    if colors:
        doc["colors"] = colors

    output_dir.mkdir(parents=True, exist_ok=True)
    if data.logo_bytes is not None:
        assets_dir = output_dir / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        logo_filename = f"{name}-logo.{data.logo_ext or 'png'}"
        (assets_dir / logo_filename).write_bytes(data.logo_bytes)
        doc["logo"] = f"assets/{logo_filename}"

    yaml_path = output_dir / f"{name}.yaml"
    header_comment = (
        "# Extracted via `compono template extract` from an existing .pptx.\n"
        "# Page size, font, and accent colors were parsed from its theme; margins/\n"
        "# header/footer/gutter are copied from compono's own default.yaml, since\n"
        "# arbitrary master placeholder geometry has no equivalent in compono's\n"
        "# resolver box model. Review before committing, same as any hand-authored\n"
        "# templates/*.yaml.\n\n"
    )
    yaml_path.write_text(
        header_comment + yaml.safe_dump(doc, sort_keys=False), encoding="utf-8"
    )
    return yaml_path
