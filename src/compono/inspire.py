"""Inspire: scan liked decks into a structural/style profile.

Point Inspire at a folder of `.pptx` files someone already likes and it
extracts structural/style facts — palette, fonts, spacing, grid
patterns — never the literal text or images, aggregates those facts
across every scanned deck to separate a recurring habit from a one-off
quirk, and packages the result as a skill folder
(`skills/inspire-<name>/{SKILL.md, profile.json}`) an agent can read
before generating a *new* deck with `compono`, so the new deck adopts
similar practices loosely rather than copying any source deck literally.

Hard invariant, same weight as render.py's "always a real shape, never a
flattened image": `scan_deck`/`aggregate` must never serialize a source
deck's literal text strings or image bytes into the profile. Only
measurable structure (colors, font family/size, positions, sizes) is
ever extracted. This is what makes scanning someone's own old decks safe
by default, and what makes sharing the resulting skill folder with
teammates low-risk — the profile never carried the original content in
the first place.

Two public verbs, mirroring compono's own validate/render/review
pattern: `scan_deck(path) -> dict` (one deck), `aggregate(paths) -> dict`
(many decks -> recurring vs. one-off facts), plus `write_skill(profile,
out_dir, name=...)` to emit the skill folder. `compono inspire scan` on
the CLI wraps `aggregate` + `write_skill` together.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pptx import Presentation

EMU_PER_IN = 914400

# A detected grid row must clear this confidence before it's reported as a
# fact at all — never let a shaky guess masquerade as a real pattern.
_MIN_GRID_CONFIDENCE = 0.6
_MIN_GRID_MEMBERS = 3


def _in(emu: float | None) -> float:
    return round((emu or 0) / EMU_PER_IN, 3)


def _grid_confidence(members: list[tuple[float, float, float, float]]) -> float:
    """0..1 confidence that `members` (same-row shapes) form a real grid.

    Based on how tightly widths cluster (a real grid's columns are close to
    equal width) and how evenly the gaps between them are spaced (a real
    grid has a consistent gutter, not arbitrary leftover whitespace).
    """
    widths = [w for _, _, w, _ in members]
    max_w = max(widths)
    if max_w <= 0:
        return 0.0
    width_spread = (max(widths) - min(widths)) / max_w
    width_score = max(0.0, 1.0 - width_spread / 0.3)

    members_sorted = sorted(members)
    gaps = [
        members_sorted[i + 1][0] - (members_sorted[i][0] + members_sorted[i][2])
        for i in range(len(members_sorted) - 1)
    ]
    if not gaps:
        gap_score = 1.0
    else:
        avg_gap = sum(gaps) / len(gaps)
        if avg_gap <= 0:
            gap_score = 0.5
        else:
            gap_spread = (max(gaps) - min(gaps)) / max(abs(avg_gap), 1e-6)
            gap_score = max(0.0, 1.0 - gap_spread / 0.5)

    return round(min(width_score, gap_score), 2)


def scan_deck(path: str | Path) -> dict[str, Any]:
    """Extract a structural/style profile from one `.pptx` file.

    Never reads or returns literal run text, table cell text, or image
    bytes — only measurable structure: fill colors, font family/size,
    shape-type mix, spacing, and grid patterns (each with a confidence
    score; low-confidence rows are omitted, never reported as a guess).
    """
    prs = Presentation(str(path))
    slide_w_in = _in(prs.slide_width)
    slide_h_in = _in(prs.slide_height)

    palette: Counter[str] = Counter()
    fonts: Counter[tuple[str, float | str]] = Counter()
    shape_mix: Counter[str] = Counter()
    all_gaps: list[float] = []
    all_margins: list[float] = []
    grids_detected: list[dict[str, Any]] = []

    for slide_i, slide in enumerate(prs.slides):
        rects: list[tuple[float, float, float, float]] = []
        for shp in slide.shapes:
            shape_mix[str(shp.shape_type)] += 1

            try:
                if shp.fill.type is not None and shp.fill.fore_color.type is not None:
                    palette[str(shp.fill.fore_color.rgb)] += 1
            except Exception:  # noqa: BLE001, S110 - shp.fill raises on shapes with no fill API
                pass

            if getattr(shp, "has_text_frame", False):
                for para in shp.text_frame.paragraphs:
                    for run in para.runs:
                        fam = run.font.name or "?"
                        size = run.font.size.pt if run.font.size else "?"
                        fonts[(fam, size)] += 1

            left, top = _in(shp.left), _in(shp.top)
            w, h = _in(shp.width), _in(shp.height)
            rects.append((left, top, w, h))
            all_margins.append(
                min(left, top, slide_w_in - (left + w), slide_h_in - (top + h))
            )

        by_row: dict[float, list[tuple[float, float, float, float]]] = {}
        for l, t, w, h in rects:
            by_row.setdefault(round(t, 1), []).append((l, t, w, h))
        for members in by_row.values():
            if len(members) < _MIN_GRID_MEMBERS:
                continue
            confidence = _grid_confidence(members)
            if confidence < _MIN_GRID_CONFIDENCE:
                continue
            members_sorted = sorted(members)
            gaps = [
                round(
                    members_sorted[i + 1][0]
                    - (members_sorted[i][0] + members_sorted[i][2]),
                    2,
                )
                for i in range(len(members_sorted) - 1)
            ]
            grids_detected.append(
                {
                    "slide": slide_i,
                    "columns": len(members),
                    "avg_gap_in": round(sum(gaps) / len(gaps), 2) if gaps else 0.0,
                    "confidence": confidence,
                }
            )
            all_gaps.extend(gaps)

    return {
        "slide_size_in": [slide_w_in, slide_h_in],
        "n_slides": len(prs.slides),
        "palette_top": [{"hex": c, "count": n} for c, n in palette.most_common(6)],
        "fonts_top": [
            {"family": f, "size_pt": s, "count": n}
            for (f, s), n in fonts.most_common(6)
        ],
        "shape_mix": dict(shape_mix),
        "avg_margin_in": round(sum(all_margins) / len(all_margins), 2)
        if all_margins
        else None,
        "avg_gap_in": round(sum(all_gaps) / len(all_gaps), 2) if all_gaps else None,
        "grids_detected": grids_detected,
    }


def aggregate(
    paths: Sequence[str | Path], *, min_repeat_ratio: float = 0.5
) -> dict[str, Any]:
    """Scan multiple decks and separate a recurring practice from a one-off.

    Every counter below is incremented at most once per deck (not once per
    shape), so a single deck with unusually heavy use of a color/font/grid
    can't outweigh several decks that use it more sparingly, and a deck
    with many slides can't dominate an aggregate of otherwise-small decks.
    """
    profiles: list[dict[str, Any]] = []
    skipped: list[str] = []
    for p in paths:
        try:
            profiles.append(scan_deck(p))
        except Exception as exc:  # noqa: BLE001 - isolate one bad file from the batch
            skipped.append(f"Skipped {p}: {exc}")
    n = len(profiles)
    if n == 0:
        raise ValueError(
            "aggregate() found no scannable deck among the given paths."
            + (f" ({'; '.join(skipped)})" if skipped else "")
        )

    palette_counter: Counter[str] = Counter()
    font_counter: Counter[tuple[str, float | str]] = Counter()
    grid_column_counts: Counter[int] = Counter()
    margins: list[float] = []
    gaps: list[float] = []
    total_grids = 0

    for profile in profiles:
        for entry in profile["palette_top"]:
            palette_counter[entry["hex"]] += 1
        for entry in profile["fonts_top"]:
            # "?" means no run in that slide set an explicit font override
            # (it's inherited from the layout/master/theme instead) — that's
            # common across almost every deck regardless of what font it
            # actually renders in, so counting it would let "no override"
            # crowd out a real, recurring font choice in the vote below.
            if entry["family"] == "?":
                continue
            font_counter[(entry["family"], entry["size_pt"])] += 1
        for g in profile["grids_detected"]:
            grid_column_counts[g["columns"]] += 1
        total_grids += len(profile["grids_detected"])
        if profile["avg_margin_in"] is not None:
            margins.append(profile["avg_margin_in"])
        if profile["avg_gap_in"] is not None:
            gaps.append(profile["avg_gap_in"])

    def is_recurring(count: int) -> bool:
        return count / n >= min_repeat_ratio

    recurring_colors = [c for c, cnt in palette_counter.items() if is_recurring(cnt)]
    one_off_colors = [c for c, cnt in palette_counter.items() if not is_recurring(cnt)]
    recurring_fonts = [
        {"family": f, "size_pt": s}
        for (f, s), cnt in font_counter.items()
        if is_recurring(cnt)
    ]
    avg_grids_per_deck = round(total_grids / n, 2)
    avg_margin = round(sum(margins) / len(margins), 2) if margins else None
    avg_gap = round(sum(gaps) / len(gaps), 2) if gaps else None

    style_note = (
        f"Across {n} example deck{'s' if n != 1 else ''}: "
        + (
            f"recurring palette colors are {recurring_colors}; "
            if recurring_colors
            else "no single color recurred across decks; "
        )
        + (
            f"grids appear on average {avg_grids_per_deck:.1f} time(s) per deck "
            f"(column counts seen: {dict(grid_column_counts)}); "
            if total_grids
            else "grids were rarely or never used; "
        )
        + (
            f"typical margin ~{avg_margin}in, gap ~{avg_gap}in."
            if avg_margin is not None and avg_gap is not None
            else "not enough spacing data to draw a margin/gap conclusion."
        )
    )

    return {
        "n_example_decks": n,
        "recurring_palette": recurring_colors,
        "one_off_palette": one_off_colors,
        "recurring_fonts": recurring_fonts,
        "avg_margin_in": avg_margin,
        "avg_gap_in": avg_gap,
        "grid_column_counts_seen": dict(grid_column_counts),
        "avg_grids_per_deck": avg_grids_per_deck,
        "style_note": style_note,
        "warnings": skipped,
    }


@dataclass(frozen=True)
class SkillFiles:
    """Paths written by `write_skill()`."""

    skill_md: Path
    profile_json: Path


def _skill_md_body(profile: dict[str, Any], name: str) -> str:
    palette = profile.get("recurring_palette") or []
    fonts = profile.get("recurring_fonts") or []
    note = profile.get("style_note", "")

    lines = [
        "---",
        f"name: inspire-{name}",
        (
            f"description: Style practices learned from "
            f"{profile.get('n_example_decks', '?')} example decks, for compono "
            "to adopt loosely (not literally) on new decks."
        ),
        "---",
        "",
        f"# inspire-{name}",
        "",
        (
            "Practices extracted from a set of example decks the user already "
            "likes. This is guidance for `compono` deck generation, not a "
            "template to copy literally — apply what fits the new deck's own "
            "content, ignore what doesn't. None of the original decks' text or "
            "images are represented here; only measurable structure/style facts."
        ),
        "",
        f"{note}",
        "",
    ]
    if palette:
        lines += [
            "## Recurring palette",
            "",
            (
                "Reuse these colors by default for "
                "`shape.fill`/`ShapeText.color` unless the requested deck "
                "specifies otherwise:"
            ),
            "",
            *(f"- `{c}`" for c in palette),
            "",
        ]
    if fonts:
        lines += [
            "## Recurring fonts",
            "",
            (
                "Prefer a `Template`/`font_family` matching one of these when "
                "the deck has no other font requirement:"
            ),
            "",
            *(f"- {f['family']} ({f['size_pt']}pt)" for f in fonts),
            "",
        ]
    if profile.get("grid_column_counts_seen"):
        lines += [
            "## Layout habits",
            "",
            (
                f"Grid column counts seen across the example decks: "
                f"{profile['grid_column_counts_seen']}. Prefer `grid` over a "
                "long `text` bullet wall where the content naturally splits "
                "into cards."
            ),
            "",
        ]
    lines += [
        "## Full structural profile",
        "",
        (
            "See `profile.json` in this folder for the complete structural "
            "facts (palette/font frequency, spacing, per-slide grid "
            "detections with confidence scores) this summary was generated "
            "from."
        ),
        "",
    ]
    return "\n".join(lines)


def write_skill(
    profile: dict[str, Any], out_dir: str | Path, *, name: str
) -> SkillFiles:
    """Emit a `skills/inspire-<name>/` folder: `SKILL.md` + `profile.json`.

    `SKILL.md` is templated directly from the aggregated structural facts
    (no LLM call) — its prose is written as agent instructions, the same
    voice as `schema.py`'s `Field(description=...)` text.
    """
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    skill_md = out_path / "SKILL.md"
    profile_json = out_path / "profile.json"
    skill_md.write_text(_skill_md_body(profile, name), encoding="utf-8")
    profile_json.write_text(
        json.dumps(profile, indent=2, sort_keys=True), encoding="utf-8"
    )
    return SkillFiles(skill_md=skill_md, profile_json=profile_json)
