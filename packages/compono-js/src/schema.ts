/**
 * Zod models for each primitive -> JSON Schema — the TypeScript port of
 * src/compono/schema.py (see COMPONO_PLAN.md / .claude/CLAUDE.md).
 *
 * Malformed input is rejected structurally here, not caught visually later.
 * Field `.describe(...)` strings are written as instructions to the calling
 * agent, not type labels, carried over verbatim from schema.py — the schema
 * doubles as in-context documentation, same convention as the Python side.
 *
 * Full v1 catalog: header, text, image, stat, grid, table, sequence, chart,
 * shape.
 */

import { z } from "zod";

export const Align = z.enum(["start", "center", "end", "stretch"]);
export const Justify = z.enum(["start", "center", "end", "space-between"]);

const primitiveBase = {
  id: z
    .string()
    .nullable()
    .default(null)
    .describe(
      "Stable identifier for this primitive. Required if another primitive " +
        "needs to reference its resolved position (e.g. a shape connector).",
    ),
  notes: z
    .string()
    .nullable()
    .default(null)
    .describe("Speaker notes for this primitive/slide. Not rendered on the slide itself."),
};

export const Header = z
  .object({
    primitive: z.literal("header").default("header"),
    ...primitiveBase,
    title: z
      .string()
      .describe("Keep under ~60 characters — longer titles will be shrunk by the resolver."),
    subtitle: z
      .string()
      .nullable()
      .default(null)
      .describe("Optional supporting line under the title. Keep under ~80 characters."),
    eyebrow: z
      .string()
      .nullable()
      .default(null)
      .describe("Optional small label above the title (e.g. a section tag or date)."),
    align: z
      .enum(["left", "center", "right"])
      .default("left")
      .describe("Horizontal alignment of the header block within its region."),
  })
  .strict();
export type Header = z.infer<typeof Header>;

export const Text = z
  .object({
    primitive: z.literal("text").default("text"),
    ...primitiveBase,
    mode: z
      .enum(["paragraph", "bullets"])
      .default("paragraph")
      .describe(
        "'paragraph' renders content as flowing prose; 'bullets' renders each " +
          "list item as a bullet.",
      ),
    content: z
      .union([z.string(), z.array(z.string())])
      .describe(
        "A single string for paragraph mode, or a list of strings for bullets mode. " +
          "Keep bullet items short (under ~100 characters) so they fit without shrinking.",
      ),
    columns: z
      .number()
      .int()
      .min(1)
      .default(1)
      .describe("Number of layout columns to split content across. Defaults to 1 (single column)."),
    emphasis_indices: z
      .array(z.number().int())
      .nullable()
      .default(null)
      .describe("Indices (0-based) of bullet items or sentences to visually emphasize."),
  })
  .strict();
export type Text = z.infer<typeof Text>;

export const ShapeText = z
  .object({
    content: z.string().describe("Text to render inside the shape."),
    align: z
      .enum(["left", "center", "right"])
      .default("left")
      .describe("Horizontal alignment of the text within the shape."),
    valign: z
      .enum(["top", "middle", "bottom"])
      .default("middle")
      .describe("Vertical alignment of the text within the shape."),
    autofit: z
      .boolean()
      .default(true)
      .describe("If true, the shared shrink-to-fit routine reduces font size to avoid overflow."),
    color: z
      .string()
      .nullable()
      .default(null)
      .describe(
        "Text color, e.g. a hex string. Omit for the theme default. Set this " +
          "explicitly on a shape with a dark `fill` — review()'s contrast check " +
          "can only evaluate legibility against `fill` when this is set.",
      ),
  })
  .strict();
export type ShapeText = z.infer<typeof ShapeText>;

export const ShapeConnects = z
  .object({
    from_id: z.string().describe("id of the primitive this connector originates from."),
    to_id: z.string().describe("id of the primitive this connector points to."),
  })
  .strict();
export type ShapeConnects = z.infer<typeof ShapeConnects>;

export const Shape = z
  .object({
    primitive: z.literal("shape").default("shape"),
    ...primitiveBase,
    kind: z
      .enum(["rect", "rounded_rect", "oval", "line", "arrow", "connector"])
      .describe("Shape geometry to render."),
    fill: z
      .string()
      .nullable()
      .default(null)
      .describe("Fill color, e.g. a hex string. Omit for no fill / template default."),
    fill_style: z
      .enum(["solid", "gradient"])
      .default("solid")
      .describe(
        "'solid' (default) is a flat fill. 'gradient' blends a lighter tint of " +
          "`fill` into the color itself, top to bottom — an explicit choice, not " +
          "applied automatically, so use it only where it fits the deck's look.",
      ),
    border: z
      .string()
      .nullable()
      .default(null)
      .describe("Border color, e.g. a hex string. Omit for no border."),
    connects: ShapeConnects.nullable()
      .default(null)
      .describe(
        "Only valid when kind='connector'. References two other primitives by id; " +
          "the resolver draws the connector between their resolved rects.",
      ),
    text: ShapeText.nullable()
      .default(null)
      .describe("Optional text rendered inside the shape."),
  })
  .strict();
export type Shape = z.infer<typeof Shape>;

export const Image = z
  .object({
    primitive: z.literal("image").default("image"),
    ...primitiveBase,
    src: z
      .string()
      .nullable()
      .default(null)
      .describe("Path or URL to the image. Omit when placeholder=True."),
    placeholder: z
      .boolean()
      .default(false)
      .describe(
        "If true, renders an intentional placeholder (dashed border + caption) instead of " +
          "a real image, and records the exact rect in the render manifest for a later fill pass.",
      ),
    caption: z
      .string()
      .nullable()
      .default(null)
      .describe("Caption describing the image (shown on placeholders; also usable as alt text)."),
    fit: z
      .enum(["cover", "contain"])
      .default("contain")
      .describe("'contain' preserves aspect ratio within the box; 'cover' fills the box exactly."),
  })
  .strict()
  .refine((v) => v.placeholder || !!v.src, {
    message: "image requires either 'src' or 'placeholder=True'.",
  });
export type Image = z.infer<typeof Image>;

export const Stat = z
  .object({
    primitive: z.literal("stat").default("stat"),
    ...primitiveBase,
    value: z.string().describe("The headline number/value, e.g. '42%'. Keep short — it renders large."),
    label: z.string().describe("Short label under the value, e.g. 'YoY growth'."),
    trend: z
      .string()
      .nullable()
      .default(null)
      .describe("Optional trend indicator, e.g. '+12% vs last quarter'."),
  })
  .strict();
export type Stat = z.infer<typeof Stat>;

export const Table = z
  .object({
    primitive: z.literal("table").default("table"),
    ...primitiveBase,
    headers: z.array(z.string()).min(1).describe("Column headers, in order."),
    rows: z
      .array(z.array(z.string()))
      .min(1)
      .describe("Row values. Each row must have the same length as headers."),
    emphasis_row: z
      .number()
      .int()
      .nullable()
      .default(null)
      .describe("0-based index (into rows) of a row to visually emphasize."),
    emphasis_col: z
      .number()
      .int()
      .nullable()
      .default(null)
      .describe("0-based index (into headers) of a column to visually emphasize."),
  })
  .strict()
  .refine((v) => v.rows.every((row) => row.length === v.headers.length), {
    message: "rows do not have the same length as headers.",
  });
export type Table = z.infer<typeof Table>;

export const SequenceStep = z
  .object({
    label: z.string().describe("Short step label, e.g. 'Discovery'."),
    description: z
      .string()
      .nullable()
      .default(null)
      .describe("Optional one-line elaboration of the step."),
  })
  .strict();
export type SequenceStep = z.infer<typeof SequenceStep>;

export const Sequence = z
  .object({
    primitive: z.literal("sequence").default("sequence"),
    ...primitiveBase,
    steps: z
      .array(SequenceStep)
      .min(1)
      .describe("Ordered steps, rendered left-to-right or top-to-bottom."),
    orientation: z
      .enum(["horizontal", "vertical"])
      .default("horizontal")
      .describe("Layout direction of the step sequence."),
  })
  .strict();
export type Sequence = z.infer<typeof Sequence>;

export const ChartSeries = z
  .object({
    name: z.string().describe("Series name, shown in the chart legend."),
    values: z
      .array(z.number())
      .describe("One value per category, same length and order as categories."),
  })
  .strict();
export type ChartSeries = z.infer<typeof ChartSeries>;

export const Chart = z
  .object({
    primitive: z.literal("chart").default("chart"),
    ...primitiveBase,
    chart_type: z.enum(["bar", "line", "pie"]).describe("Chart type to render."),
    categories: z.array(z.string()).describe("Category labels along the axis (or pie slice labels)."),
    series: z
      .array(ChartSeries)
      .describe("One or more data series. A pie chart should have exactly one series."),
  })
  .strict()
  .refine((v) => v.series.every((s) => s.values.length === v.categories.length), {
    message: "series do not have one value per category.",
  })
  .refine((v) => !(v.chart_type === "pie" && v.series.length !== 1), {
    message: "a pie chart must have exactly one series.",
  });
export type Chart = z.infer<typeof Chart>;

// Grid is self-referential (items: PrimitiveSpec[], which includes Grid
// itself) — z.lazy() plays the role schema.py's forward-ref string +
// Grid.model_rebuild() plays in pydantic.
export interface Grid {
  primitive: "grid";
  id: string | null;
  notes: string | null;
  items: PrimitiveSpecT[];
  columns: number | "auto";
  direction: "row" | "column";
  align: z.infer<typeof Align>;
  justify: z.infer<typeof Justify>;
}

// z.lazy()'s inferred type can't be constrained to an exact recursive
// interface without `any` creeping into `_input`/`_output` (a known zod
// limitation for self-referential schemas) — cast broadly here, once, at
// the two lazy definitions, rather than let `any` leak into every call
// site that uses Grid/PrimitiveSpec.
export const Grid = z.lazy(() =>
  z
    .object({
      primitive: z.literal("grid").default("grid"),
      ...primitiveBase,
      items: z
        .array(PrimitiveSpec)
        .describe(
          "Nested primitive specs, in the same shape as a slide's top-level primitives — " +
            "grids can contain any primitive, including other grids.",
        ),
      columns: z
        .union([z.number().int(), z.literal("auto")])
        .default("auto")
        .describe("Number of columns, or 'auto' to let the resolver infer from item count."),
      direction: z
        .enum(["row", "column"])
        .default("row")
        .describe("Main-axis direction items are laid out along."),
      align: Align.default("stretch").describe("Cross-axis alignment of items within the grid."),
      justify: Justify.default("start").describe(
        "Main-axis alignment/distribution of items within the grid.",
      ),
    })
    .strict(),
) as unknown as z.ZodType<Grid, z.ZodTypeDef, unknown>;

// Grid is self-referential via z.lazy(), which zod's discriminatedUnion
// cannot accept as a member (it needs to introspect `.shape` at schema-
// build time, which a lazy/effects-wrapped schema doesn't expose) — a
// plain union still validates correctly (each member's own `primitive`
// literal still discriminates at runtime), just with less specialized
// error messages than discriminatedUnion would give.
export const PrimitiveSpec = z.lazy(() =>
  z.union([Header, Text, Image, Stat, Grid, Table, Sequence, Chart, Shape]),
) as unknown as z.ZodType<PrimitiveSpecT, z.ZodTypeDef, unknown>;
export type PrimitiveSpecT = Header | Text | Image | Stat | Grid | Table | Sequence | Chart | Shape;

export const Slide = z
  .object({
    header: Header.nullable().default(null).describe("Optional header region for this slide."),
    body: z
      .array(PrimitiveSpec)
      .default([])
      .describe("Body primitives, laid out top-to-bottom by default."),
    notes: z.string().nullable().default(null).describe("Speaker notes for the whole slide."),
  })
  .strict();
export type Slide = z.infer<typeof Slide>;

export const Deck = z
  .object({
    template: z
      .string()
      .default("default")
      .describe("Template name — a config file under templates/, or 'default'."),
    slides: z.array(Slide).describe("Slides, in presentation order."),
  })
  .strict();
export type Deck = z.infer<typeof Deck>;
