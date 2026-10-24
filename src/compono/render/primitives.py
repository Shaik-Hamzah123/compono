"""Every `_render_<primitive>` function — this is the file "Adding a new
primitive" (`.claude/CLAUDE.md`) points to. Each takes
`(pptx_slide, primitive, rect, template, ...)` and must produce a real
OOXML shape (`add_textbox`, `add_shape`, `add_table`, `add_chart`,
`add_connector`, `add_picture` for real images) — never rasterize content.
"""

from __future__ import annotations

from itertools import pairwise
from typing import Any

from PIL import Image as PILImage
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.dml import MSO_LINE_DASH_STYLE
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu

from compono.resolver import ConnectorPoints, Rect, Template
from compono.schema import Chart, Header, Image, Sequence, Shape, Stat, Table, Text
from compono.validator import FontMetrics

from ._overflow import _table_column_widths_emu
from ._shared import (
    _ALIGN_TO_PP,
    _CHART_TYPE_TO_XL,
    _SHAPE_KIND_TO_MSO,
    _VALIGN_TO_MSO,
    BODY_FONT_SIZE_PT,
    CAPTION_FONT_SIZE_PT,
    HEADER_FONT_SIZE_PT,
    STAT_LABEL_FONT_SIZE_PT,
    STAT_VALUE_FONT_SIZE_PT,
    TABLE_FONT_SIZE_PT,
    _apply_shape_gradient,
    _set_font,
)


def _render_header(
    pptx_slide: Any, header: Header, rect: Rect, template: Template
) -> None:
    box = pptx_slide.shapes.add_textbox(
        Emu(rect.x), Emu(rect.y), Emu(rect.w), Emu(rect.h)
    )
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE

    first = True
    if header.eyebrow:
        p = tf.paragraphs[0]
        first = False
        p.text = header.eyebrow
        _set_font(p.font, template, 12)
        p.alignment = _ALIGN_TO_PP[header.align]

    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.text = header.title
    _set_font(p.font, template, HEADER_FONT_SIZE_PT, bold=True)
    p.alignment = _ALIGN_TO_PP[header.align]

    if header.subtitle:
        p = tf.add_paragraph()
        p.text = header.subtitle
        _set_font(p.font, template, 16)
        p.alignment = _ALIGN_TO_PP[header.align]

    if template.logo_path is not None:
        # Sized proportionally to header height, pinned to the top-right —
        # additive only: unset (the default for every stock template) means
        # byte-identical output to before this field existed.
        logo_h = int(rect.h * 0.6)
        logo_y = rect.y + (rect.h - logo_h) // 2
        with PILImage.open(template.logo_path) as img:
            aspect = img.width / img.height
        logo_w = int(logo_h * aspect)
        logo_x = rect.x + rect.w - logo_w
        pptx_slide.shapes.add_picture(
            str(template.logo_path), Emu(logo_x), Emu(logo_y), Emu(logo_w), Emu(logo_h)
        )


def _render_text(pptx_slide: Any, text: Text, rect: Rect, template: Template) -> None:
    box = pptx_slide.shapes.add_textbox(
        Emu(rect.x), Emu(rect.y), Emu(rect.w), Emu(rect.h)
    )
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE

    if text.mode == "paragraph":
        content = (
            text.content if isinstance(text.content, str) else " ".join(text.content)
        )
        tf.text = content
        _set_font(tf.paragraphs[0].font, template, BODY_FONT_SIZE_PT)
        return

    items = text.content if isinstance(text.content, list) else [text.content]
    emphasis = set(text.emphasis_indices or [])
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = f"• {item}"
        _set_font(p.font, template, BODY_FONT_SIZE_PT, bold=i in emphasis)


def _render_shape(
    pptx_slide: Any, shape: Shape, rect: Rect, template: Template
) -> None:
    # "line"/"arrow" render as a straight connector across the shape's own rect.
    if shape.kind in ("line", "arrow"):
        connector = pptx_slide.shapes.add_connector(
            MSO_CONNECTOR.STRAIGHT,
            Emu(rect.x),
            Emu(rect.y),
            Emu(rect.x + rect.w),
            Emu(rect.y + rect.h),
        )
        if shape.kind == "arrow":
            _add_arrowhead(connector)
        return

    mso_shape = _SHAPE_KIND_TO_MSO.get(shape.kind, MSO_SHAPE.RECTANGLE)
    sp = pptx_slide.shapes.add_shape(
        mso_shape, Emu(rect.x), Emu(rect.y), Emu(rect.w), Emu(rect.h)
    )

    if shape.fill and shape.fill_style == "gradient":
        _apply_shape_gradient(sp, shape.fill)
    elif shape.fill:
        sp.fill.solid()
        sp.fill.fore_color.rgb = RGBColor.from_string(shape.fill.lstrip("#"))
    else:
        sp.fill.background()

    if shape.border:
        sp.line.color.rgb = RGBColor.from_string(shape.border.lstrip("#"))
    else:
        sp.line.fill.background()

    if shape.text is not None:
        tf = sp.text_frame
        tf.word_wrap = True
        tf.text = shape.text.content
        tf.vertical_anchor = _VALIGN_TO_MSO[shape.text.valign]
        # shape.text.content may contain embedded "\n"s, which python-pptx's
        # text_frame.text setter splits into multiple paragraphs — every one
        # of them needs the same font/color/alignment, not just paragraphs[0]
        # (a bug once left every line after the first in the theme default).
        for paragraph in tf.paragraphs:
            paragraph.font.name = template.font_family
            if shape.text.color:
                paragraph.font.color.rgb = RGBColor.from_string(
                    shape.text.color.lstrip("#")
                )
            paragraph.alignment = _ALIGN_TO_PP[shape.text.align]


def _render_footer(
    pptx_slide: Any, template: Template, slide_number: int, total_slides: int
) -> None:
    """A consistent footer on every slide — a page number, small and out of
    the way. Reserved footer space existed since Step 2 but nothing was ever
    drawn into it, leaving every slide looking unfinished at the bottom.
    """
    x = template.margin_left
    y = template.page_height - template.margin_bottom - template.footer_height
    w = template.page_width - template.margin_left - template.margin_right

    box = pptx_slide.shapes.add_textbox(
        Emu(x), Emu(y), Emu(w), Emu(template.footer_height)
    )
    tf = box.text_frame
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.text = f"{slide_number} / {total_slides}"
    _set_font(tf.paragraphs[0].font, template, 10)
    tf.paragraphs[0].font.color.rgb = RGBColor(0x99, 0x99, 0x99)
    tf.paragraphs[0].alignment = PP_ALIGN.RIGHT


def _render_connector(pptx_slide: Any, points: ConnectorPoints) -> None:
    """Draw one straight segment per consecutive point pair — a direct
    connector is just (start, end); one routed around an obstacle also has
    `waypoints` bends in between. An arrowhead on the final segment's end
    shows the relationship's direction, which a bare line otherwise doesn't.
    """
    path = [points.start, *points.waypoints, points.end]
    last_index = len(path) - 2
    for i, ((x1, y1), (x2, y2)) in enumerate(pairwise(path)):
        connector = pptx_slide.shapes.add_connector(
            MSO_CONNECTOR.STRAIGHT, Emu(x1), Emu(y1), Emu(x2), Emu(y2)
        )
        if i == last_index:
            _add_arrowhead(connector)


def _add_arrowhead(connector: Any) -> None:
    """python-pptx's LineFormat has no high-level arrowhead API — this is
    the minimal raw-XML equivalent of PowerPoint's own "Arrow" line-end
    style.
    """
    ln = connector.line._get_or_add_ln()
    ln.append(
        ln.makeelement(qn("a:tailEnd"), {"type": "triangle", "w": "med", "len": "med"})
    )


def _render_image(
    pptx_slide: Any,
    image: Image,
    rect: Rect,
    slide_index: int,
    item_id: str,
    manifest: list[dict[str, Any]],
    template: Template,
) -> None:
    if image.placeholder or not image.src:
        _render_image_placeholder(
            pptx_slide, image, rect, slide_index, item_id, manifest, template
        )
        return

    if image.fit == "cover":
        pptx_slide.shapes.add_picture(
            image.src, Emu(rect.x), Emu(rect.y), width=Emu(rect.w), height=Emu(rect.h)
        )
        return

    # contain: preserve aspect ratio, center within rect.
    with PILImage.open(image.src) as im:
        img_w, img_h = im.size
    img_ratio = img_w / img_h
    box_ratio = rect.w / rect.h
    if img_ratio > box_ratio:
        draw_w, draw_h = rect.w, round(rect.w / img_ratio)
    else:
        draw_h, draw_w = rect.h, round(rect.h * img_ratio)
    x = rect.x + (rect.w - draw_w) // 2
    y = rect.y + (rect.h - draw_h) // 2
    pptx_slide.shapes.add_picture(
        image.src, Emu(x), Emu(y), width=Emu(draw_w), height=Emu(draw_h)
    )


def _render_image_placeholder(
    pptx_slide: Any,
    image: Image,
    rect: Rect,
    slide_index: int,
    item_id: str,
    manifest: list[dict[str, Any]],
    template: Template,
) -> None:
    """A first-class placeholder (COMPONO_PLAN.md section 5): dashed border + caption,
    plus a manifest entry a later image-fill pass can use without re-laying-out.
    """
    sp = pptx_slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, Emu(rect.x), Emu(rect.y), Emu(rect.w), Emu(rect.h)
    )
    sp.fill.background()
    sp.line.color.rgb = RGBColor(0x99, 0x99, 0x99)
    sp.line.dash_style = MSO_LINE_DASH_STYLE.DASH

    if image.caption:
        tf = sp.text_frame
        tf.word_wrap = True
        tf.text = image.caption
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        tf.paragraphs[0].alignment = PP_ALIGN.CENTER
        _set_font(tf.paragraphs[0].font, template, CAPTION_FONT_SIZE_PT)
        # Auto-shapes with no fill otherwise inherit a near-invisible theme text
        # color on some renderers (observed as near-white on white) — match the
        # dashed border's gray explicitly so the caption is always legible.
        tf.paragraphs[0].font.color.rgb = RGBColor(0x66, 0x66, 0x66)

    manifest.append(
        {
            "slide": slide_index,
            "primitive": item_id,
            "rect": {"x": rect.x, "y": rect.y, "w": rect.w, "h": rect.h},
            "caption": image.caption,
        }
    )


def _render_stat(pptx_slide: Any, stat: Stat, rect: Rect, template: Template) -> None:
    box = pptx_slide.shapes.add_textbox(
        Emu(rect.x), Emu(rect.y), Emu(rect.w), Emu(rect.h)
    )
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE

    p_value = tf.paragraphs[0]
    p_value.text = stat.value
    _set_font(p_value.font, template, STAT_VALUE_FONT_SIZE_PT, bold=True)
    p_value.alignment = PP_ALIGN.CENTER

    p_label = tf.add_paragraph()
    p_label.text = stat.label
    _set_font(p_label.font, template, STAT_LABEL_FONT_SIZE_PT)
    p_label.alignment = PP_ALIGN.CENTER

    if stat.trend:
        p_trend = tf.add_paragraph()
        p_trend.text = stat.trend
        _set_font(p_trend.font, template, STAT_LABEL_FONT_SIZE_PT)
        p_trend.alignment = PP_ALIGN.CENTER


def _render_table(
    pptx_slide: Any,
    table: Table,
    rect: Rect,
    template: Template,
    font_metrics: FontMetrics | None = None,
) -> None:
    n_rows = len(table.rows) + 1
    n_cols = len(table.headers)
    graphic_frame = pptx_slide.shapes.add_table(
        n_rows, n_cols, Emu(rect.x), Emu(rect.y), Emu(rect.w), Emu(rect.h)
    )
    tbl = graphic_frame.table

    # add_table's graphicFrame reports height=rect.h, but individual row
    # heights default to a content-based minimum, leaving visible dead space
    # below the table when it has few rows. Stretch rows to fill rect.h.
    row_h = rect.h // n_rows
    for row in tbl.rows:
        row.height = Emu(row_h)

    # Column widths proportional to content when a font is available to
    # measure with (_table_column_widths_emu); otherwise leave python-pptx's
    # own even default, exactly as before this existed.
    col_widths = _table_column_widths_emu(table.headers, table.rows, rect, font_metrics)
    if col_widths is not None:
        for c, width in enumerate(col_widths):
            tbl.columns[c].width = Emu(width)

    for c, header_text in enumerate(table.headers):
        cell = tbl.cell(0, c)
        cell.text = header_text
        _set_font(
            cell.text_frame.paragraphs[0].font, template, TABLE_FONT_SIZE_PT, bold=True
        )
        if template.primary_color is not None:
            # Additive only — unset (every stock template today) leaves the
            # header row at python-pptx's own default table styling.
            cell.fill.solid()
            cell.fill.fore_color.rgb = RGBColor.from_string(
                template.primary_color.lstrip("#")
            )
            cell.text_frame.paragraphs[0].font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)

    cell_fills = {(cf.row, cf.col): cf.fill for cf in table.cell_fills or []}

    for r, row in enumerate(table.rows, start=1):
        for c, value in enumerate(row):
            cell = tbl.cell(r, c)
            cell.text = value
            is_emphasis = (
                table.emphasis_row is not None and r - 1 == table.emphasis_row
            ) or (table.emphasis_col is not None and c == table.emphasis_col)
            _set_font(
                cell.text_frame.paragraphs[0].font,
                template,
                TABLE_FONT_SIZE_PT,
                bold=is_emphasis,
            )
            fill = cell_fills.get((r - 1, c))
            if fill is not None:
                # Additive, coexists with is_emphasis's bold styling on the
                # same cell — a cell can be both bold and colored.
                cell.fill.solid()
                cell.fill.fore_color.rgb = RGBColor.from_string(fill.lstrip("#"))

    # Merges last, after every cell already has its own text/font/fill.
    # python-pptx's cell.merge() concatenates every merged cell's existing
    # text into the origin cell (confirmed via manual testing — not "keeps
    # the origin, discards the rest" as its own docs might suggest) — so
    # every non-origin cell in the range must be cleared first, or a table
    # spec with real (often duplicate) row data merges into a garbled
    # "North\nNorth"-style origin cell instead of a clean "North".
    for merge in table.merges or []:
        for r in range(merge.row1, merge.row2 + 1):
            for c in range(merge.col1, merge.col2 + 1):
                if (r, c) != (merge.row1, merge.col1):
                    tbl.cell(r + 1, c).text = ""
        tbl.cell(merge.row1 + 1, merge.col1).merge(tbl.cell(merge.row2 + 1, merge.col2))


def _render_sequence(
    pptx_slide: Any, sequence: Sequence, rect: Rect, template: Template
) -> None:
    """Compiles internally to shape + text + connectors (COMPONO_PLAN.md section 5), not a bespoke render path."""
    steps = sequence.steps
    n = len(steps)
    if n == 0:
        return

    gutter = max(1, min(rect.w, rect.h) // 20)

    if sequence.orientation == "horizontal":
        step_w = (rect.w - gutter * (n - 1)) // n
        positions = [
            Rect(rect.x + i * (step_w + gutter), rect.y, step_w, rect.h)
            for i in range(n)
        ]
    else:
        step_h = (rect.h - gutter * (n - 1)) // n
        positions = [
            Rect(rect.x, rect.y + i * (step_h + gutter), rect.w, step_h)
            for i in range(n)
        ]

    for step, step_rect in zip(steps, positions, strict=True):
        sp = pptx_slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            Emu(step_rect.x),
            Emu(step_rect.y),
            Emu(step_rect.w),
            Emu(step_rect.h),
        )
        if template.accent_color is not None:
            # Additive only — unset (every stock template today) leaves the
            # step shape at python-pptx's own default shape fill.
            sp.fill.solid()
            sp.fill.fore_color.rgb = RGBColor.from_string(
                template.accent_color.lstrip("#")
            )
        tf = sp.text_frame
        tf.word_wrap = True
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        tf.text = step.label
        _set_font(tf.paragraphs[0].font, template, BODY_FONT_SIZE_PT, bold=True)
        tf.paragraphs[0].alignment = PP_ALIGN.CENTER
        if step.description:
            p = tf.add_paragraph()
            p.text = step.description
            _set_font(p.font, template, CAPTION_FONT_SIZE_PT)
            p.alignment = PP_ALIGN.CENTER

    # Connect box *edges* through the gutter only — never box centers, which
    # would draw the connector across the step's own label text.
    for rect_a, rect_b in pairwise(positions):
        if sequence.orientation == "horizontal":
            x1, y1 = rect_a.x + rect_a.w, rect_a.y + rect_a.h // 2
            x2, y2 = rect_b.x, rect_b.y + rect_b.h // 2
        else:
            x1, y1 = rect_a.x + rect_a.w // 2, rect_a.y + rect_a.h
            x2, y2 = rect_b.x + rect_b.w // 2, rect_b.y
        pptx_slide.shapes.add_connector(
            MSO_CONNECTOR.STRAIGHT, Emu(x1), Emu(y1), Emu(x2), Emu(y2)
        )


def _render_chart(
    pptx_slide: Any, chart: Chart, rect: Rect, template: Template
) -> None:
    chart_data = CategoryChartData()
    chart_data.categories = chart.categories
    for series in chart.series:
        chart_data.add_series(series.name, series.values)

    graphic_frame = pptx_slide.shapes.add_chart(
        _CHART_TYPE_TO_XL[chart.chart_type],
        Emu(rect.x),
        Emu(rect.y),
        Emu(rect.w),
        Emu(rect.h),
        chart_data,
    )
    _apply_chart_font(graphic_frame.chart, template)
    _apply_chart_colors(graphic_frame.chart, chart.chart_type, template)


def _chart_color_palette(template: Template) -> list[str] | None:
    """`[primary_color, accent_color]`, either/both filtered out if unset.
    `None` (both unset) means "don't touch chart colors at all" — gated,
    additive, same as every other branding field.
    """
    colors = [c for c in (template.primary_color, template.accent_color) if c]
    return colors or None


def _apply_chart_colors(pptx_chart: Any, chart_type: str, template: Template) -> None:
    """Cycles `template.primary_color`/`accent_color` across series (bar/
    line) or data points (pie — one series, N slices, a different
    python-pptx API than bar/line's per-series coloring). A chart with more
    series/slices than colors set just repeats the cycle
    (primary, accent, primary, accent, ...) rather than falling back to
    PowerPoint's default palette partway through.
    """
    palette = _chart_color_palette(template)
    if palette is None:
        return

    plot = pptx_chart.plots[0]
    if chart_type == "pie":
        for i, point in enumerate(plot.series[0].points):
            point.format.fill.solid()
            point.format.fill.fore_color.rgb = RGBColor.from_string(
                palette[i % len(palette)].lstrip("#")
            )
    else:
        for i, series in enumerate(plot.series):
            series.format.fill.solid()
            series.format.fill.fore_color.rgb = RGBColor.from_string(
                palette[i % len(palette)].lstrip("#")
            )


def _apply_chart_font(pptx_chart: Any, template: Template) -> None:
    """Typeface only (`template.font_family`) — chart text has no existing
    FONT_SIZE_PT constant of its own, so this leaves size at python-pptx's/
    PowerPoint's defaults rather than inventing one.

    A pie chart has neither a category nor a value axis (python-pptx raises
    ValueError for both) — skip rather than force one into existing. Data
    labels are similarly opt-in: `has_data_labels` defaults to False, and
    turning them on here would change what actually renders, not just its
    font, so only style them if the deck already enabled them.
    """
    try:
        pptx_chart.category_axis.tick_labels.font.name = template.font_family
    except ValueError:
        pass
    try:
        pptx_chart.value_axis.tick_labels.font.name = template.font_family
    except ValueError:
        pass
    if pptx_chart.has_legend:
        pptx_chart.legend.font.name = template.font_family
    plot = pptx_chart.plots[0]
    if plot.has_data_labels:
        plot.data_labels.font.name = template.font_family
