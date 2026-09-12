/**
 * Orchestrates validate -> write docx via the `docx` npm package.
 *
 * TypeScript port of src/compono/docx.py. No resolver step — Word flows
 * content top-to-bottom on its own. This is the only module allowed to
 * import `docx`/a chart-rasterization library, mirroring render.ts's
 * "only module allowed to import pptxgenjs" rule.
 */

import { readFileSync } from "node:fs";
import { ChartJSNodeCanvas } from "chartjs-node-canvas";
import {
  AlignmentType,
  Document,
  ExternalHyperlink,
  Footer,
  Header,
  HeadingLevel,
  ImageRun,
  LevelFormat,
  Packer,
  PageBreak as DocxPageBreak,
  Paragraph as DocxParagraph,
  Table as DocxTable,
  TableCell,
  TableRow,
  TextRun,
  WidthType,
} from "docx";
import { z } from "zod";
import {
  BulletList,
  DocChart,
  DocImage,
  DocTable,
  DocxDoc,
  Heading,
  NumberedList,
  PageBreak,
  Paragraph,
  Run,
  Section,
  type DocxPrimitiveSpecT,
} from "./docx_schema.js";
import type { ValidationReport } from "./render.js";

const PX_PER_INCH = 96;
const NUMBERING_REFERENCE = "compono-numbered-list";

export class DocxValidationError extends Error {
  errors: Record<string, unknown>[];
  constructor(errors: Record<string, unknown>[]) {
    super(`${errors.length} validation error(s)`);
    this.errors = errors;
  }
}

export interface DocxRenderReport {
  docxPath: string;
  manifest: Record<string, unknown>[];
  warnings: string[];
}

function zodErrorToDicts(error: z.ZodError): Record<string, unknown>[] {
  return error.issues.map((issue) => ({
    section: null,
    primitive: issue.path.join(".") || "<docx>",
    field: issue.path.length ? issue.path[issue.path.length - 1] : null,
    error: issue.code,
    detail: issue.message,
    fix: "Check the field against the schema description and correct the value/type.",
  }));
}

function parseDocxDoc(spec: unknown): DocxDoc {
  const result = DocxDoc.safeParse(spec);
  if (!result.success) {
    throw new DocxValidationError(zodErrorToDicts(result.error));
  }
  return result.data;
}

export function validateDocx(spec: unknown): ValidationReport {
  try {
    parseDocxDoc(spec);
  } catch (err) {
    if (err instanceof DocxValidationError) {
      return { valid: false, errors: err.errors, warnings: [] };
    }
    throw err;
  }
  return { valid: true, errors: [], warnings: [] };
}

function docxRunChild(runSpec: Run): TextRun | ExternalHyperlink {
  if (runSpec.link) {
    // A run inside ExternalHyperlink gets none of Word's "Hyperlink" character
    // style automatically from this library — without an explicit color/
    // underline it silently renders invisible in some viewers (LibreOffice
    // included) even though the text and the relationship are both present
    // in the XML. Style it explicitly, matching compono's pptx/docx-Python
    // renderers' own manual hyperlink styling.
    const textRun = new TextRun({
      text: runSpec.text,
      bold: runSpec.bold,
      italics: runSpec.italic,
      underline: {},
      color: "0563C1",
    });
    return new ExternalHyperlink({ children: [textRun], link: runSpec.link });
  }
  return new TextRun({
    text: runSpec.text,
    bold: runSpec.bold,
    italics: runSpec.italic,
    underline: runSpec.underline ? {} : undefined,
  });
}

function renderHeadingParagraph(primitive: Heading): DocxParagraph {
  const levelMap: Record<number, (typeof HeadingLevel)[keyof typeof HeadingLevel]> = {
    1: HeadingLevel.HEADING_1,
    2: HeadingLevel.HEADING_2,
    3: HeadingLevel.HEADING_3,
    4: HeadingLevel.HEADING_4,
  };
  return new DocxParagraph({ text: primitive.text, heading: levelMap[primitive.level] });
}

function renderParagraphParagraph(primitive: Paragraph): DocxParagraph {
  return new DocxParagraph({ children: primitive.runs.map(docxRunChild) });
}

function renderBulletParagraphs(primitive: BulletList): DocxParagraph[] {
  return primitive.items.map(
    (runs) => new DocxParagraph({ bullet: { level: 0 }, children: runs.map(docxRunChild) }),
  );
}

function renderNumberedParagraphs(primitive: NumberedList): DocxParagraph[] {
  return primitive.items.map(
    (runs) =>
      new DocxParagraph({
        numbering: { reference: NUMBERING_REFERENCE, level: 0 },
        children: runs.map(docxRunChild),
      }),
  );
}

// Without an explicit width, docx's Table/TableCell default to a handful
// of twips (~0.07in) — a real bug caught by rendering a real spec and
// looking at the output: the table was structurally present in the XML
// but visually a sliver, invisible on the page. Every table gets full
// page width, split evenly across columns — real column-width awareness
// (matching content) is a known future improvement, not attempted here.
const FULL_TABLE_WIDTH = { size: 100, type: WidthType.PERCENTAGE };

function renderTable(primitive: DocTable): DocxTable {
  const colWidth = { size: Math.floor(100 / primitive.headers.length), type: WidthType.PERCENTAGE };
  const headerRow = new TableRow({
    children: primitive.headers.map(
      (h) =>
        new TableCell({
          width: colWidth,
          children: [new DocxParagraph({ children: [new TextRun({ text: h, bold: true })] })],
        }),
    ),
  });
  const bodyRows = primitive.rows.map(
    (row) =>
      new TableRow({
        children: row.map((cell) => new TableCell({ width: colWidth, children: [new DocxParagraph(cell)] })),
      }),
  );
  return new DocxTable({ width: FULL_TABLE_WIDTH, rows: [headerRow, ...bodyRows] });
}

function renderImage(primitive: DocImage): { nodes: DocxParagraph[]; manifestEntry: Record<string, unknown> | null } {
  if (primitive.placeholder || !primitive.src) {
    const nodes: DocxParagraph[] = [
      new DocxParagraph({
        alignment: AlignmentType.CENTER,
        children: [new TextRun({ text: `[image placeholder: ${primitive.caption ?? "untitled"}]`, italics: true })],
      }),
    ];
    return {
      nodes,
      manifestEntry: { primitive: "image", caption: primitive.caption, width_in: primitive.width_in },
    };
  }

  const data = readFileSync(primitive.src);
  const widthPx = primitive.width_in * PX_PER_INCH;
  // Real image height isn't known without decoding — a fixed 3:4 fallback
  // aspect keeps this simple; callers who care about exact proportions
  // should size their source image to width_in's aspect themselves. (A
  // known limitation, called out in docs, not silently "fixed" by
  // guessing a decode.)
  const heightPx = widthPx * 0.75;
  const imageNode = new ImageRun({
    type: "png",
    data,
    transformation: { width: widthPx, height: heightPx },
  });
  const nodes = [new DocxParagraph({ alignment: AlignmentType.CENTER, children: [imageNode] })];
  if (primitive.caption) {
    nodes.push(
      new DocxParagraph({
        alignment: AlignmentType.CENTER,
        children: [new TextRun({ text: primitive.caption, italics: true })],
      }),
    );
  }
  return { nodes, manifestEntry: null };
}

async function renderChart(primitive: DocChart): Promise<DocxParagraph> {
  // No native Word chart API exists in any JS library either (see
  // DocChart's docstring in docx_schema.ts) — rasterize via chart.js
  // (headless, through chartjs-node-canvas) and embed as a picture. The
  // one documented exception to "always a real, editable object."
  const widthPx = Math.round(primitive.width_in * PX_PER_INCH);
  const heightPx = Math.round(widthPx * 0.6);
  const canvas = new ChartJSNodeCanvas({ width: widthPx, height: heightPx, backgroundColour: "white" });

  const chartJsType = primitive.chart_type === "bar" ? "bar" : primitive.chart_type === "line" ? "line" : "pie";
  const buffer = await canvas.renderToBuffer({
    type: chartJsType,
    data: {
      labels: primitive.categories,
      datasets: primitive.series.map((s) => ({ label: s.name, data: s.values })),
    },
    options: { plugins: { legend: { display: primitive.series.length > 1 } } },
  });

  return new DocxParagraph({
    alignment: AlignmentType.CENTER,
    children: [new ImageRun({ type: "png", data: buffer, transformation: { width: widthPx, height: heightPx } })],
  });
}

async function renderPrimitive(
  primitive: DocxPrimitiveSpecT,
): Promise<{ nodes: (DocxParagraph | DocxTable)[]; manifestEntry: Record<string, unknown> | null }> {
  switch (primitive.primitive) {
    case "heading":
      return { nodes: [renderHeadingParagraph(primitive)], manifestEntry: null };
    case "paragraph":
      return { nodes: [renderParagraphParagraph(primitive)], manifestEntry: null };
    case "bullet_list":
      return { nodes: renderBulletParagraphs(primitive), manifestEntry: null };
    case "numbered_list":
      return { nodes: renderNumberedParagraphs(primitive), manifestEntry: null };
    case "table":
      return { nodes: [renderTable(primitive)], manifestEntry: null };
    case "image": {
      const { nodes, manifestEntry } = renderImage(primitive);
      return { nodes, manifestEntry };
    }
    case "chart":
      return { nodes: [await renderChart(primitive)], manifestEntry: null };
    case "page_break":
      return { nodes: [new DocxParagraph({ children: [new DocxPageBreak()] })], manifestEntry: null };
  }
}

export async function renderDocx(spec: unknown, outputPath: string): Promise<DocxRenderReport> {
  const doc = parseDocxDoc(spec);
  const manifest: Record<string, unknown>[] = [];

  const sections = await Promise.all(
    doc.sections.map(async (section: Section) => {
      const children: (DocxParagraph | DocxTable)[] = [];
      for (const primitive of section.body) {
        const { nodes, manifestEntry } = await renderPrimitive(primitive);
        children.push(...nodes);
        if (manifestEntry) manifest.push(manifestEntry);
      }
      return {
        headers: section.header_text
          ? { default: new Header({ children: [new DocxParagraph({ text: section.header_text })] }) }
          : undefined,
        footers: section.footer_text
          ? { default: new Footer({ children: [new DocxParagraph({ text: section.footer_text })] }) }
          : undefined,
        children,
      };
    }),
  );

  const document = new Document({
    title: doc.title,
    numbering: {
      config: [
        {
          reference: NUMBERING_REFERENCE,
          levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.START }],
        },
      ],
    },
    sections,
  });

  const buffer = await Packer.toBuffer(document);
  const { writeFile } = await import("node:fs/promises");
  await writeFile(outputPath, buffer);

  return { docxPath: outputPath, manifest, warnings: [] };
}
