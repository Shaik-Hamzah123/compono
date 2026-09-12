/**
 * Zod models for compono's docx primitive catalog — TypeScript port of
 * src/compono/docx_schema.py. Same catalog: heading, paragraph,
 * bullet_list, numbered_list, table, image, chart, page_break.
 *
 * A Word document flows top-to-bottom on its own — no resolver/EMU layout
 * math needed here, unlike the pptx primitive set in schema.ts.
 */

import { z } from "zod";

const docxPrimitiveBase = {
  id: z
    .string()
    .nullable()
    .default(null)
    .describe(
      "Stable identifier for this primitive. Optional — nothing in the docx " +
        "renderer currently needs to reference it back, but kept for symmetry " +
        "with the pptx primitive catalog and future use.",
    ),
  notes: z
    .string()
    .nullable()
    .default(null)
    .describe("Internal note about this primitive. Not rendered into the document."),
};

export const Run = z
  .object({
    text: z.string().describe("The run's literal text."),
    bold: z.boolean().default(false).describe("Render this run in bold."),
    italic: z.boolean().default(false).describe("Render this run in italics."),
    underline: z.boolean().default(false).describe("Render this run underlined."),
    link: z
      .string()
      .nullable()
      .default(null)
      .describe("If set, this run becomes a clickable hyperlink to this URL."),
  })
  .strict();
export type Run = z.infer<typeof Run>;

export const Heading = z
  .object({
    primitive: z.literal("heading").default("heading"),
    ...docxPrimitiveBase,
    text: z.string().describe("Heading text. Keep short — one line."),
    level: z
      .number()
      .int()
      .min(1)
      .max(4)
      .default(1)
      .describe(
        "Heading level 1-4, mapped to Word's built-in Heading 1-4 styles. Use " +
          "level 1 sparingly (usually once per document, as the title of a major " +
          "section) and go deeper for subsections.",
      ),
  })
  .strict();
export type Heading = z.infer<typeof Heading>;

export const Paragraph = z
  .object({
    primitive: z.literal("paragraph").default("paragraph"),
    ...docxPrimitiveBase,
    runs: z
      .array(Run)
      .describe(
        "One or more styled spans of text, concatenated in order to form the " +
          "paragraph. Use multiple runs only where inline styling (bold/italic/" +
          "underline/link) actually changes mid-sentence — a plain paragraph is " +
          "a single run with no styling flags set.",
      ),
  })
  .strict();
export type Paragraph = z.infer<typeof Paragraph>;

export const BulletList = z
  .object({
    primitive: z.literal("bullet_list").default("bullet_list"),
    ...docxPrimitiveBase,
    items: z
      .array(z.array(Run))
      .describe(
        "One list of runs per bullet item, same run-styling rules as Paragraph. " +
          "Keep each item under ~100 characters so it reads as a bullet, not a paragraph.",
      ),
  })
  .strict();
export type BulletList = z.infer<typeof BulletList>;

export const NumberedList = z
  .object({
    primitive: z.literal("numbered_list").default("numbered_list"),
    ...docxPrimitiveBase,
    items: z
      .array(z.array(Run))
      .describe(
        "One list of runs per numbered item, same run-styling rules as Paragraph. " +
          "Word numbers items automatically in document order.",
      ),
  })
  .strict();
export type NumberedList = z.infer<typeof NumberedList>;

export const DocTable = z
  .object({
    primitive: z.literal("table").default("table"),
    ...docxPrimitiveBase,
    headers: z.array(z.string()).describe("Column headers, in order."),
    rows: z
      .array(z.array(z.string()))
      .describe("Row values. Each row must have the same length as headers."),
  })
  .strict()
  .refine((v) => v.rows.every((row) => row.length === v.headers.length), {
    message: "rows do not have the same length as headers.",
  });
export type DocTable = z.infer<typeof DocTable>;

export const DocImage = z
  .object({
    primitive: z.literal("image").default("image"),
    ...docxPrimitiveBase,
    src: z
      .string()
      .nullable()
      .default(null)
      .describe("Path to the image file. Omit when placeholder=True."),
    placeholder: z
      .boolean()
      .default(false)
      .describe(
        "If true, renders a bordered placeholder paragraph with the caption text " +
          "instead of a real image, for a later fill pass (e.g. a company logo the " +
          "agent doesn't have yet).",
      ),
    caption: z
      .string()
      .nullable()
      .default(null)
      .describe("Caption shown under the image (or inside a placeholder)."),
    width_in: z
      .number()
      .gt(0)
      .default(4.0)
      .describe(
        "Image width in inches. Height scales automatically to preserve the " +
          "source image's aspect ratio.",
      ),
  })
  .strict()
  .refine((v) => v.placeholder || !!v.src, {
    message: "image requires either 'src' or 'placeholder=True'.",
  });
export type DocImage = z.infer<typeof DocImage>;

export const DocChartSeries = z
  .object({
    name: z.string().describe("Series name, shown in the chart legend."),
    values: z
      .array(z.number())
      .describe("One value per category, same length and order as categories."),
  })
  .strict();
export type DocChartSeries = z.infer<typeof DocChartSeries>;

/**
 * Renders as a static image, not a native Word chart object. No JS/npm
 * library builds native Word charts either (same gap as python-docx) — a
 * native Word chart is a whole embedded-package format (chart XML + an
 * embedded worksheet). This primitive is rasterized via chart.js
 * (headless, through chartjs-node-canvas) and embedded as a picture: real,
 * but not editable in Word the way a pptx chart is. Documented explicitly.
 */
export const DocChart = z
  .object({
    primitive: z.literal("chart").default("chart"),
    ...docxPrimitiveBase,
    chart_type: z
      .enum(["bar", "line", "pie"])
      .describe("Chart type to render. Same scoped catalog as compono's pptx chart."),
    categories: z.array(z.string()).describe("Category labels along the axis (or pie slice labels)."),
    series: z
      .array(DocChartSeries)
      .describe("One or more data series. A pie chart should have exactly one series."),
    width_in: z.number().gt(0).default(5.5).describe("Rendered chart image width in inches."),
  })
  .strict()
  .refine((v) => v.series.every((s) => s.values.length === v.categories.length), {
    message: "series do not have one value per category.",
  })
  .refine((v) => !(v.chart_type === "pie" && v.series.length !== 1), {
    message: "a pie chart must have exactly one series.",
  });
export type DocChart = z.infer<typeof DocChart>;

export const PageBreak = z
  .object({
    primitive: z.literal("page_break").default("page_break"),
    ...docxPrimitiveBase,
  })
  .strict();
export type PageBreak = z.infer<typeof PageBreak>;

export const DocxPrimitiveSpec = z.union([
  Heading,
  Paragraph,
  BulletList,
  NumberedList,
  DocTable,
  DocImage,
  DocChart,
  PageBreak,
]);
export type DocxPrimitiveSpecT =
  | Heading
  | Paragraph
  | BulletList
  | NumberedList
  | DocTable
  | DocImage
  | DocChart
  | PageBreak;

export const Section = z
  .object({
    header_text: z
      .string()
      .nullable()
      .default(null)
      .describe("Optional running header text repeated on every page of this section."),
    footer_text: z
      .string()
      .nullable()
      .default(null)
      .describe("Optional running footer text repeated on every page of this section."),
    body: z.array(DocxPrimitiveSpec).default([]).describe("Body primitives, in document order."),
  })
  .strict();
export type Section = z.infer<typeof Section>;

export const DocxDoc = z
  .object({
    title: z.string().describe("Document title. Used as the .docx core-properties title."),
    sections: z.array(Section).describe("Sections, in document order."),
  })
  .strict();
export type DocxDoc = z.infer<typeof DocxDoc>;
