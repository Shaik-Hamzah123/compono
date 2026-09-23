/**
 * Orchestrates validate -> resolve -> write pptx via pptxgenjs.
 *
 * TypeScript port of src/compono/render.py's public verbs. This is the
 * only module allowed to import `pptxgenjs` (mirrors the Python side's
 * "only module allowed to import pptx" rule). `validate()` and
 * `renderDeck()` are the two public verbs — every rendered element is a
 * genuine, editable native object, never a flattened image.
 */

// pptxgenjs ships ambient UMD-style types (`declare namespace PptxGenJS`)
// that don't resolve cleanly under `moduleResolution: NodeNext`'s default
// import interop — `PptxSlideLike` etc. isn't reachable through the
// default-imported binding. Rather than fight the library's own .d.ts,
// treat the import as untyped and describe the small surface we actually
// use ourselves (constructable, addSlide/addText/addShape/addTable/
// addChart/addImage/defineLayout/writeFile) — a structural type, not a
// reimplementation of pptxgenjs's full API.
import { readFileSync } from "node:fs";
import { imageSize } from "image-size";
import PptxGenJSImport from "pptxgenjs";
import { z } from "zod";

interface PptxSlideLike {
  addText(text: unknown, options?: Record<string, unknown>): PptxSlideLike;
  addShape(shapeName: string, options?: Record<string, unknown>): PptxSlideLike;
  addTable(rows: unknown[], options?: Record<string, unknown>): PptxSlideLike;
  addChart(type: string, data: unknown, options?: Record<string, unknown>): PptxSlideLike;
  addImage(options: Record<string, unknown>): PptxSlideLike;
}

interface PptxPresentationLike {
  layout: string;
  defineLayout(props: { name: string; width: number; height: number }): void;
  addSlide(): PptxSlideLike;
  writeFile(props: { fileName: string }): Promise<string>;
}

const PptxGenJS = PptxGenJSImport as unknown as new () => PptxPresentationLike;
import {
  loadTemplateByName,
  resolveSlide,
  EMU_PER_INCH,
  type ConnectorPoints,
  type Rect,
  type Template,
} from "./resolver.js";
import { Deck, type Chart, type Header, type PrimitiveSpecT, type Sequence, type Shape, type Stat, type Table, type Text } from "./schema.js";
import {
  buildOverflowError,
  checkOverflow,
  loadFontMetrics,
  measureTextWidthPt,
  resolveFontPath,
  type FontMetrics,
} from "./validator.js";

const HEADER_FONT_SIZE_PT = 28;
const BODY_FONT_SIZE_PT = 18;
const STAT_VALUE_FONT_SIZE_PT = 36;
const STAT_LABEL_FONT_SIZE_PT = 14;
const TABLE_FONT_SIZE_PT = 14;
const CAPTION_FONT_SIZE_PT = 12;

function emuToIn(v: number): number {
  return v / EMU_PER_INCH;
}

export class DeckValidationError extends Error {
  errors: Record<string, unknown>[];
  constructor(errors: Record<string, unknown>[]) {
    super(`${errors.length} validation error(s)`);
    this.errors = errors;
  }
}

export interface ValidationReport {
  valid: boolean;
  errors: Record<string, unknown>[];
  warnings: string[];
}

export interface RenderReport {
  pptxPath: string;
  manifest: Record<string, unknown>[];
  warnings: string[];
}

function zodErrorToDicts(error: z.ZodError): Record<string, unknown>[] {
  return error.issues.map((issue) => ({
    slide: null,
    primitive: issue.path.join(".") || "<deck>",
    field: issue.path.length ? issue.path[issue.path.length - 1] : null,
    error: issue.code,
    detail: issue.message,
    fix: "Check the field against the schema description and correct the value/type.",
  }));
}

export function parseDeck(spec: unknown): Deck {
  const result = Deck.safeParse(spec);
  if (!result.success) {
    throw new DeckValidationError(zodErrorToDicts(result.error));
  }
  return result.data;
}

const TABLE_MIN_COL_WIDTH_PT = 40.0;

/** Column widths (EMU, summing exactly to `rect.w`) proportional to each
 * column's longest measured cell, clamped to `TABLE_MIN_COL_WIDTH_PT` so no
 * column collapses to nothing. Returns `null` when no font is available to
 * measure with — the caller falls back to an even split rather than faking
 * a proportional one (same "never fakes" pattern as overflow validation).
 */
export function tableColumnWidthsEmu(
  headers: string[],
  rows: string[][],
  rect: Rect,
  fontMetrics: FontMetrics | null,
): number[] | null {
  if (!fontMetrics) return null;
  const rawWidthsPt = headers.map((header, c) => {
    const candidates = [header, ...rows.map((row) => row[c])];
    return Math.max(...candidates.map((text) => measureTextWidthPt(text, fontMetrics, TABLE_FONT_SIZE_PT)));
  });
  const clampedPt = rawWidthsPt.map((w) => Math.max(TABLE_MIN_COL_WIDTH_PT, w));
  const totalPt = clampedPt.reduce((a, b) => a + b, 0);
  const widthsEmu = clampedPt.map((w) => Math.round((w / totalPt) * rect.w));
  // Floor/round drift must not change the total — the last column absorbs
  // it rather than leaving a gap or overrunning rect.w.
  widthsEmu[widthsEmu.length - 1] += rect.w - widthsEmu.reduce((a, b) => a + b, 0);
  return widthsEmu;
}

/** Split the table's overall rect into per-cell boxes — row 0 is the
 * header row. `colWidths` (EMU, one per column, summing to `rect.w`) come
 * from `tableColumnWidthsEmu` when a font is available; omitted falls back
 * to an even, floor-divided split (the original v1 approximation), with
 * any leftover EMUs from that floor division left as unassigned padding,
 * not distributed to any particular cell.
 */
export function tableCellRects(
  rect: Rect,
  numCols: number,
  numRows: number,
  colWidths?: number[] | null,
): Rect[][] {
  const widths = colWidths ?? Array(numCols).fill(Math.trunc(rect.w / numCols));
  const colX = [rect.x];
  for (const w of widths.slice(0, -1)) colX.push(colX[colX.length - 1] + w);

  const rowH = Math.trunc(rect.h / numRows);
  return Array.from({ length: numRows }, (_, r) =>
    Array.from({ length: numCols }, (_, c) => ({
      x: colX[c],
      y: rect.y + r * rowH,
      w: widths[c],
      h: rowH,
    })),
  );
}

/** Even, floor-divided split of the sequence's overall rect into one box
 * per step, left-to-right — same accepted v1 approximation as table cells.
 */
export function sequenceStepRects(rect: Rect, numSteps: number): Rect[] {
  const stepW = Math.trunc(rect.w / numSteps);
  return Array.from({ length: numSteps }, (_, i) => ({
    x: rect.x + i * stepW,
    y: rect.y,
    w: stepW,
    h: rect.h,
  }));
}

/** (field, text, fontSizePt, subRect) for every text-bearing field on a
 * primitive. `subRect` is null when the field should be checked against the
 * primitive's own full rect (every case below except table/sequence);
 * table/sequence instead emit one entry per cell/step, each with its own
 * sub-rect, so a single overlong cell/step is caught even when the
 * combined text would have fit the overall box.
 */
export function extractTextFields(
  primitive: PrimitiveSpecT | Header,
  rect: Rect,
  fontMetrics: FontMetrics | null = null,
): [string, string, number, Rect | null][] {
  switch (primitive.primitive) {
    case "header":
      return [["title", primitive.title, HEADER_FONT_SIZE_PT, null]];
    case "text": {
      const content = Array.isArray(primitive.content) ? primitive.content.join("\n") : primitive.content;
      return [["content", content, BODY_FONT_SIZE_PT, null]];
    }
    case "stat":
      return [
        ["value", primitive.value, STAT_VALUE_FONT_SIZE_PT, null],
        ["label", primitive.label, STAT_LABEL_FONT_SIZE_PT, null],
      ];
    case "shape":
      return primitive.text ? [["text.content", primitive.text.content, BODY_FONT_SIZE_PT, null]] : [];
    case "table": {
      const table = primitive as Table;
      const numCols = table.headers.length;
      const numRows = 1 + table.rows.length; // row 0 = headers
      const colWidths = tableColumnWidthsEmu(table.headers, table.rows, rect, fontMetrics);
      const cellRects = tableCellRects(rect, numCols, numRows, colWidths);
      const fields: [string, string, number, Rect | null][] = table.headers.map((header, c) => [
        `headers[${c}]`,
        header,
        TABLE_FONT_SIZE_PT,
        cellRects[0][c],
      ]);
      table.rows.forEach((row, r) => {
        row.forEach((cell, c) => {
          fields.push([`rows[${r}][${c}]`, cell, TABLE_FONT_SIZE_PT, cellRects[r + 1][c]]);
        });
      });
      return fields;
    }
    case "sequence": {
      const sequence = primitive as Sequence;
      const stepRects = sequenceStepRects(rect, sequence.steps.length);
      return sequence.steps.map((step, i) => [
        `steps[${i}]`,
        step.description ? `${step.label}: ${step.description}` : step.label,
        BODY_FONT_SIZE_PT,
        stepRects[i],
      ]);
    }
    default:
      return [];
  }
}

export function walkPrimitives(items: PrimitiveSpecT[]): PrimitiveSpecT[] {
  const out: PrimitiveSpecT[] = [];
  for (const item of items) {
    out.push(item);
    if (item.primitive === "grid") out.push(...walkPrimitives(item.items));
  }
  return out;
}

function checkSlideOverflow(
  slideIndex: number,
  header: Header | null,
  body: PrimitiveSpecT[],
  template: Template,
  metrics: FontMetrics | null,
): Record<string, unknown>[] {
  if (!metrics) return [];
  const errors: Record<string, unknown>[] = [];
  const result = resolveSlide(template, header, body);

  // Iterate the resolver's own rects/items maps (the single source of
  // truth for the id scheme, including the "body[i]"/grid-nested ids it
  // auto-assigns) rather than re-deriving ids independently — the two
  // numbering schemes can silently diverge otherwise, and did (a real bug
  // caught by test/render.test.ts's overflow test: bullets with no
  // explicit `id` were never checked at all because the fallback id here
  // didn't match the resolver's "body[0]").
  for (const [id, rect] of result.rects) {
    const primitive = result.items.get(id);
    if (!primitive) continue;
    for (const [field, text, fontSizePt, subRect] of extractTextFields(primitive, rect, metrics)) {
      const checkRect = subRect ?? rect;
      const boxWidthPt = emuToIn(checkRect.w) * 72;
      const boxHeightPt = emuToIn(checkRect.h) * 72;
      const report = checkOverflow(text, metrics, fontSizePt, boxWidthPt, boxHeightPt);
      if (report.overflow) {
        errors.push(buildOverflowError(slideIndex, id, field, report, fontSizePt));
      }
    }
  }
  return errors;
}

export function validate(spec: unknown, templateOverride?: Template): ValidationReport {
  let deck: Deck;
  try {
    deck = parseDeck(spec);
  } catch (err) {
    if (err instanceof DeckValidationError) {
      return { valid: false, errors: err.errors, warnings: [] };
    }
    throw err;
  }

  const warnings: string[] = [];
  let template: Template;
  try {
    template = templateOverride ?? loadTemplateByName(deck.template);
  } catch (err) {
    return {
      valid: false,
      errors: [
        {
          slide: null,
          primitive: "template",
          field: "template",
          error: "unknown_template",
          detail: (err as Error).message,
          fix: "Use a template name that exists under templates/, or omit `template` for the default.",
        },
      ],
      warnings: [],
    };
  }

  const fontPath = resolveFontPath(template);
  let metrics: FontMetrics | null = null;
  if (fontPath) {
    metrics = loadFontMetrics(fontPath);
  } else {
    warnings.push("No font found for overflow validation — overflow checks were skipped, not faked.");
  }

  const errors: Record<string, unknown>[] = [];
  deck.slides.forEach((slide, i) => {
    try {
      resolveSlide(template, slide.header, slide.body);
    } catch (err) {
      errors.push({
        slide: i,
        primitive: "<slide>",
        field: null,
        error: "layout",
        detail: (err as Error).message,
        fix: "Reduce the number/size of body primitives, or split into two slides.",
      });
      return;
    }
    errors.push(...checkSlideOverflow(i, slide.header, slide.body, template, metrics));
  });

  return { valid: errors.length === 0, errors, warnings };
}

export async function renderDeck(spec: unknown, outputPath: string, templateOverride?: Template): Promise<RenderReport> {
  const deck = parseDeck(spec);
  const template = templateOverride ?? loadTemplateByName(deck.template);
  const report = validate(spec, template);
  if (!report.valid) {
    throw new DeckValidationError(report.errors);
  }

  const fontPath = resolveFontPath(template);
  const fontMetrics: FontMetrics | null = fontPath ? loadFontMetrics(fontPath) : null;

  const pres = new PptxGenJS();
  pres.defineLayout({ name: "COMPONO", width: emuToIn(template.pageWidth), height: emuToIn(template.pageHeight) });
  pres.layout = "COMPONO";

  const manifest: Record<string, unknown>[] = [];

  deck.slides.forEach((slideSpec, slideIndex) => {
    const pptxSlide = pres.addSlide();
    const layout = resolveSlide(template, slideSpec.header, slideSpec.body);

    if (slideSpec.header) {
      const headerId = slideSpec.header.id ?? "header";
      const rect = layout.rects.get(headerId);
      if (rect) renderHeader(pptxSlide, slideSpec.header, rect, template);
    }

    // Iterate the resolver's own rects/items maps (the single source of
    // truth for the id scheme, including synthesized ids like grid
    // children and diagram nodes) rather than walking the original spec
    // tree — a diagram's nodes only exist in `layout`, synthesized by
    // resolveSlide, so walking `slideSpec.body` would silently skip them.
    const headerId = slideSpec.header ? (slideSpec.header.id ?? "header") : null;
    for (const [itemId, rect] of layout.rects) {
      if (itemId === headerId) continue; // header already rendered above
      const primitive = layout.items.get(itemId);
      if (!primitive || primitive.primitive === "header") continue;
      if (primitive.primitive === "shape" && (primitive as Shape).kind === "connector") continue; // drawn below from layout.connectors
      renderPrimitive(pptxSlide, primitive as PrimitiveSpecT, rect, template, slideIndex, itemId, manifest, fontMetrics);
    }

    for (const points of layout.connectors.values()) {
      renderConnector(pptxSlide, points);
    }

    renderFooter(pptxSlide, template, slideIndex + 1, deck.slides.length);
  });

  await pres.writeFile({ fileName: outputPath });

  return { pptxPath: outputPath, manifest, warnings: report.warnings };
}

function renderPrimitive(
  slide: PptxSlideLike,
  primitive: PrimitiveSpecT,
  rect: Rect,
  template: Template,
  slideIndex: number,
  itemId: string,
  manifest: Record<string, unknown>[],
  fontMetrics: FontMetrics | null = null,
): void {
  switch (primitive.primitive) {
    case "text":
      renderText(slide, primitive, rect, template);
      break;
    case "shape":
      renderShape(slide, primitive, rect, template);
      break;
    case "image":
      renderImage(slide, primitive, rect, slideIndex, itemId, manifest);
      break;
    case "stat":
      renderStat(slide, primitive, rect, template);
      break;
    case "table":
      renderTable(slide, primitive, rect, template, fontMetrics);
      break;
    case "sequence":
      renderSequence(slide, primitive, rect, template);
      break;
    case "chart":
      renderChart(slide, primitive, rect, template);
      break;
    case "grid":
    case "diagram":
    case "gantt":
      // Grid/Diagram/Gantt have no visual of their own — only their
      // (already-flattened) children render (Diagram nodes are synthesized
      // as real Shape instances; Gantt fully collapses into a real Table).
      break;
  }
}

function rectIn(rect: Rect) {
  return { x: emuToIn(rect.x), y: emuToIn(rect.y), w: emuToIn(rect.w), h: emuToIn(rect.h) };
}

function renderHeader(slide: PptxSlideLike, header: Header, rect: Rect, template: Template): void {
  const box = rectIn(rect);
  const lines: string[] = [];
  if (header.eyebrow) lines.push(header.eyebrow);
  lines.push(header.title);
  if (header.subtitle) lines.push(header.subtitle);

  slide.addText(header.title, {
    ...box,
    fontFace: template.fontFamily,
    fontSize: HEADER_FONT_SIZE_PT,
    bold: true,
    align: header.align,
    valign: "top",
  });
  if (header.eyebrow) {
    slide.addText(header.eyebrow, {
      x: box.x,
      y: box.y,
      w: box.w,
      h: 0.3,
      fontFace: template.fontFamily,
      fontSize: 12,
      color: "666666",
      align: header.align,
    });
  }
  if (template.logoPath) {
    // Sized proportionally to header height, pinned to the top-right —
    // additive only: unset (the default for every stock template) means
    // byte-identical output to before this field existed.
    const logoH = box.h * 0.6;
    const logoY = box.y + (box.h - logoH) / 2;
    const dims = imageSize(readFileSync(template.logoPath));
    const aspect = (dims.width ?? 1) / (dims.height ?? 1);
    const logoW = logoH * aspect;
    const logoX = box.x + box.w - logoW;
    slide.addImage({ path: template.logoPath, x: logoX, y: logoY, w: logoW, h: logoH });
  }

  if (header.subtitle) {
    slide.addText(header.subtitle, {
      x: box.x,
      y: box.y + 0.5,
      w: box.w,
      h: 0.4,
      fontFace: template.fontFamily,
      fontSize: 16,
      color: "444444",
      align: header.align,
    });
  }
}

function renderText(slide: PptxSlideLike, text: Text, rect: Rect, template: Template): void {
  const box = rectIn(rect);
  if (text.mode === "bullets") {
    const items = Array.isArray(text.content) ? text.content : [text.content];
    slide.addText(
      items.map((t) => ({ text: t, options: { bullet: true, breakLine: true } })),
      { ...box, fontFace: template.fontFamily, fontSize: BODY_FONT_SIZE_PT, valign: "top" },
    );
  } else {
    const content = Array.isArray(text.content) ? text.content.join("\n") : text.content;
    slide.addText(content, {
      ...box,
      fontFace: template.fontFamily,
      fontSize: BODY_FONT_SIZE_PT,
      valign: "top",
    });
  }
}

const SHAPE_KIND_TO_PPTX: Record<string, string> = {
  rect: "rect",
  rounded_rect: "roundRect",
  oval: "ellipse",
};

function renderShape(slide: PptxSlideLike, shape: Shape, rect: Rect, template: Template): void {
  if (shape.kind === "connector") return; // handled in a second pass by renderConnector
  const box = rectIn(rect);

  if (shape.kind === "line" || shape.kind === "arrow") {
    slide.addShape("line", {
      ...box,
      line: {
        color: shape.border ?? shape.fill ?? "000000",
        width: 2,
        endArrowType: shape.kind === "arrow" ? "triangle" : "none",
      },
    });
    return;
  }

  const shapeName = SHAPE_KIND_TO_PPTX[shape.kind] ?? "rect";
  const fill = shape.fill ? { color: shape.fill.replace("#", "") } : { type: "none" };
  const line = shape.border ? { color: shape.border.replace("#", ""), width: 1 } : { type: "none" };

  if (shape.text) {
    // pptxgenjs's addText(text, {shape: ...}) draws the fill/line and the
    // text as one real shape (one <p:sp>) — addShape()+addText() as two
    // separate calls draws two stacked shapes at the identical rect
    // instead. That duplication is harmless to look at, but it's a real
    // shape-count bug: Inspire's row-grouping (inspire.ts) reads raw shape
    // geometry, and two overlapping shapes per grid cell throws off its
    // gap/width scoring (found via inspire.test.ts against a real
    // rendered grid deck, not a hypothetical).
    slide.addText(shape.text.content, {
      ...box,
      shape: shapeName,
      fill,
      line,
      fontFace: template.fontFamily,
      fontSize: BODY_FONT_SIZE_PT,
      align: shape.text.align,
      valign: shape.text.valign,
      color: shape.text.color ? shape.text.color.replace("#", "") : undefined,
    });
    return;
  }

  slide.addShape(shapeName, { ...box, fill, line });
}

function renderImage(
  slide: PptxSlideLike,
  image: { src: string | null; placeholder: boolean; caption: string | null; fit: "cover" | "contain" },
  rect: Rect,
  slideIndex: number,
  itemId: string,
  manifest: Record<string, unknown>[],
): void {
  const box = rectIn(rect);
  if (image.placeholder || !image.src) {
    slide.addShape("rect", {
      ...box,
      fill: { type: "none" },
      line: { color: "999999", width: 1, dashType: "dash" },
    });
    if (image.caption) {
      slide.addText(image.caption, {
        ...box,
        fontSize: CAPTION_FONT_SIZE_PT,
        align: "center",
        valign: "middle",
        italic: true,
        color: "666666",
      });
    }
    manifest.push({
      slide: slideIndex,
      primitive: itemId,
      rect: { x: rect.x, y: rect.y, w: rect.w, h: rect.h },
      caption: image.caption,
    });
    return;
  }

  slide.addImage({
    path: image.src,
    ...box,
    sizing: { type: image.fit === "cover" ? "cover" : "contain", w: box.w, h: box.h },
  });
}

function renderStat(slide: PptxSlideLike, stat: Stat, rect: Rect, template: Template): void {
  const box = rectIn(rect);
  const hasTrend = !!stat.trend;
  const valueH = box.h * (hasTrend ? 0.5 : 0.6);
  const labelH = box.h * (hasTrend ? 0.3 : 0.4);

  slide.addText(stat.value, {
    x: box.x,
    y: box.y,
    w: box.w,
    h: valueH,
    fontFace: template.fontFamily,
    fontSize: STAT_VALUE_FONT_SIZE_PT,
    bold: true,
    align: "center",
    valign: "bottom",
  });
  slide.addText(stat.label, {
    x: box.x,
    y: box.y + valueH,
    w: box.w,
    h: labelH,
    fontFace: template.fontFamily,
    fontSize: STAT_LABEL_FONT_SIZE_PT,
    align: "center",
    valign: "top",
  });
  if (stat.trend) {
    slide.addText(stat.trend, {
      x: box.x,
      y: box.y + valueH + labelH,
      w: box.w,
      h: box.h - valueH - labelH,
      fontFace: template.fontFamily,
      fontSize: STAT_LABEL_FONT_SIZE_PT - 2,
      color: "3A9A5C",
      align: "center",
      valign: "top",
    });
  }
}

const TABLE_HEADER_FILL = "4A7FC2";
const TABLE_ROW_FILL = "D9E2F3";
const TABLE_EMPHASIS_ROW_FILL = "EAF0FB";

interface MergeInfo {
  originSpans: Map<string, { rowspan: number; colspan: number }>;
  covered: Set<string>;
}

/** `merges`' rectangular ranges collapse to pptxgenjs's colspan/rowspan
 * model: the origin (top-left) cell gets `colspan`/`rowspan` options, and
 * every other cell in the range must be omitted from its row's array
 * entirely — unlike python-pptx's post-hoc `cell.merge()` call, pptxgenjs
 * has no merge API of its own; the row array's shape *is* the merge.
 */
function buildMergeInfo(merges: Table["merges"]): MergeInfo {
  const originSpans = new Map<string, { rowspan: number; colspan: number }>();
  const covered = new Set<string>();
  for (const m of merges ?? []) {
    originSpans.set(`${m.row1},${m.col1}`, {
      rowspan: m.row2 - m.row1 + 1,
      colspan: m.col2 - m.col1 + 1,
    });
    for (let r = m.row1; r <= m.row2; r++) {
      for (let c = m.col1; c <= m.col2; c++) {
        if (r === m.row1 && c === m.col1) continue;
        covered.add(`${r},${c}`);
      }
    }
  }
  return { originSpans, covered };
}

function renderTable(
  slide: PptxSlideLike,
  table: Table,
  rect: Rect,
  template: Template,
  fontMetrics: FontMetrics | null = null,
): void {
  const box = rectIn(rect);
  const headerRow = table.headers.map((h) => ({
    text: h,
    options: {
      bold: true,
      fill: { color: (template.primaryColor ?? TABLE_HEADER_FILL).replace("#", "") },
      color: "FFFFFF",
    },
  }));

  const cellFills = new Map((table.cell_fills ?? []).map((cf) => [`${cf.row},${cf.col}`, cf.fill]));
  const { originSpans, covered } = buildMergeInfo(table.merges);

  const bodyRows = table.rows.map((row, rowIndex) =>
    row
      .map((cell, colIndex) => {
        if (covered.has(`${rowIndex},${colIndex}`)) return null;
        const fillOverride = cellFills.get(`${rowIndex},${colIndex}`);
        const span = originSpans.get(`${rowIndex},${colIndex}`);
        return {
          text: cell,
          options: {
            bold: rowIndex === table.emphasis_row || colIndex === table.emphasis_col,
            fill: {
              color: fillOverride
                ? fillOverride.replace("#", "")
                : rowIndex === table.emphasis_row
                  ? TABLE_EMPHASIS_ROW_FILL
                  : TABLE_ROW_FILL,
            },
            ...(span && span.rowspan > 1 ? { rowspan: span.rowspan } : {}),
            ...(span && span.colspan > 1 ? { colspan: span.colspan } : {}),
          },
        };
      })
      .filter((cell): cell is NonNullable<typeof cell> => cell !== null),
  );
  const rows: unknown[] = [headerRow, ...bodyRows];

  const colWidthsEmu = tableColumnWidthsEmu(table.headers, table.rows, rect, fontMetrics);
  const colW = colWidthsEmu ? colWidthsEmu.map((w) => emuToIn(w)) : undefined;

  slide.addTable(rows, { ...box, fontFace: template.fontFamily, fontSize: TABLE_FONT_SIZE_PT, ...(colW ? { colW } : {}) });
}

function renderSequence(
  slide: PptxSlideLike,
  sequence: { steps: { label: string; description: string | null }[]; orientation: "horizontal" | "vertical" },
  rect: Rect,
  template: Template,
): void {
  const box = rectIn(rect);
  const n = sequence.steps.length;
  if (n === 0) return;
  const horizontal = sequence.orientation === "horizontal";
  const stepW = horizontal ? box.w / n : box.w;
  const stepH = horizontal ? box.h : box.h / n;

  sequence.steps.forEach((step, i) => {
    const x = horizontal ? box.x + i * stepW : box.x;
    const y = horizontal ? box.y : box.y + i * stepH;
    slide.addShape("roundRect", {
      x,
      y,
      w: stepW * 0.9,
      h: stepH * 0.6,
      fill: { color: (template.accentColor ?? "2A6FDB").replace("#", "") },
      line: { type: "none" },
    });
    slide.addText(step.label, {
      x,
      y,
      w: stepW * 0.9,
      h: stepH * 0.6,
      fontFace: template.fontFamily,
      fontSize: 14,
      color: "FFFFFF",
      align: "center",
      valign: "middle",
      bold: true,
    });
    if (step.description) {
      slide.addText(step.description, {
        x,
        y: y + stepH * 0.6,
        w: stepW * 0.9,
        h: stepH * 0.4,
        fontFace: template.fontFamily,
        fontSize: 11,
        align: "center",
        valign: "top",
      });
    }
  });
}

const CHART_TYPE_TO_PPTX: Record<string, string> = {
  bar: "bar",
  line: "line",
  pie: "pie",
};

function renderChart(slide: PptxSlideLike, chart: Chart, rect: Rect, template: Template): void {
  const box = rectIn(rect);
  const data = chart.series.map((series) => ({
    name: series.name,
    labels: chart.categories,
    values: series.values,
  }));
  // Typeface only (template.fontFamily) — no existing FONT_SIZE_PT constant
  // covers charts, so size stays at pptxgenjs's own defaults. Unlike
  // python-pptx, pptxgenjs's flat chart options don't throw for a chart
  // type that lacks a given element (e.g. a pie chart has no axes) — they
  // simply go unused, so no per-chart-type guard is needed here.
  slide.addChart(CHART_TYPE_TO_PPTX[chart.chart_type], data, {
    ...box,
    catAxisLabelFontFace: template.fontFamily,
    valAxisLabelFontFace: template.fontFamily,
    legendFontFace: template.fontFamily,
    dataLabelFontFace: template.fontFamily,
  });
}

function renderFooter(slide: PptxSlideLike, template: Template, slideNumber: number, totalSlides: number): void {
  const x = emuToIn(template.marginLeft);
  const y = emuToIn(template.pageHeight - template.marginBottom - template.footerHeight);
  const w = emuToIn(template.pageWidth - template.marginLeft - template.marginRight);
  const h = emuToIn(template.footerHeight);

  slide.addText(`${slideNumber} / ${totalSlides}`, {
    x,
    y,
    w,
    h,
    fontFace: template.fontFamily,
    fontSize: 10,
    color: "999999",
    align: "right",
    valign: "middle",
  });
}

function renderConnector(slide: PptxSlideLike, points: ConnectorPoints): void {
  const path = [points.start, ...points.waypoints, points.end];
  const lastIndex = path.length - 2;
  for (let i = 0; i < path.length - 1; i++) {
    const [x1, y1] = path[i];
    const [x2, y2] = path[i + 1];
    const x = Math.min(x1, x2);
    const y = Math.min(y1, y2);
    const w = Math.max(Math.abs(x2 - x1), 1);
    const h = Math.max(Math.abs(y2 - y1), 1);
    const flipV = (x2 >= x1) !== (y2 >= y1);
    slide.addShape("line", {
      x: emuToIn(x),
      y: emuToIn(y),
      w: emuToIn(w),
      h: emuToIn(h),
      flipV,
      line: {
        color: "555555",
        width: 1.5,
        endArrowType: i === lastIndex ? "triangle" : "none",
      },
    });
  }
}
