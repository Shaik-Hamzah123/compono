"""Template loading: resolved layout constants, in EMU, for one template config."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

EMU_PER_INCH = 914400

DEFAULT_TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "default.yaml"


def _in_to_emu(value: float) -> int:
    return round(value * EMU_PER_INCH)


@dataclass(frozen=True)
class Template:
    """Resolved layout constants, in EMU, for one template config."""

    page_width: int
    page_height: int
    margin_top: int
    margin_right: int
    margin_bottom: int
    margin_left: int
    header_height: int
    footer_height: int
    gutter: int
    font_family: str = "Calibri"
    primary_color: str | None = None
    accent_color: str | None = None
    logo_path: Path | None = None

    @classmethod
    def from_yaml(cls, path: Path = DEFAULT_TEMPLATE_PATH) -> Template:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        page = data["page"]
        margin = data["margin_in"]
        colors = data.get("colors") or {}
        logo = data.get("logo")
        return cls(
            page_width=_in_to_emu(page["width_in"]),
            page_height=_in_to_emu(page["height_in"]),
            margin_top=_in_to_emu(margin["top"]),
            margin_right=_in_to_emu(margin["right"]),
            margin_bottom=_in_to_emu(margin["bottom"]),
            margin_left=_in_to_emu(margin["left"]),
            header_height=_in_to_emu(data["header"]["height_in"]),
            footer_height=_in_to_emu(data["footer"]["height_in"]),
            gutter=_in_to_emu(data["gutter_in"]),
            font_family=data.get("font_family", "Calibri"),
            primary_color=colors.get("primary"),
            accent_color=colors.get("accent"),
            logo_path=(path.parent / logo) if logo else None,
        )

    @classmethod
    def from_name(cls, name: str) -> Template:
        """Resolve a `Deck.template` name (schema.py) to a bundled templates/*.yaml.

        `Deck.template` has always been agent-facing in the schema, but was
        never actually wired to anything until this — every render used
        `from_yaml()`'s hardcoded default regardless of what the spec said.
        """
        path = DEFAULT_TEMPLATE_PATH.parent / f"{name}.yaml"
        if not path.exists():
            available = sorted(
                p.stem for p in DEFAULT_TEMPLATE_PATH.parent.glob("*.yaml")
            )
            raise ValueError(
                f"No template named {name!r} under templates/. "
                f"Available: {', '.join(available)}."
            )
        return cls.from_yaml(path)
