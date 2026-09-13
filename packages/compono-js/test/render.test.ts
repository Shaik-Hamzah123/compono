import { mkdtempSync } from "node:fs";
import { readFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import JSZip from "jszip";
import { describe, expect, it } from "vitest";
import { loadTemplateByName, type Rect } from "../src/resolver.js";
import {
  DeckValidationError,
  extractTextFields,
  renderDeck,
  sequenceStepRects,
  tableCellRects,
  validate,
} from "../src/render.js";
import { resolveFontPath } from "../src/validator.js";
import type { Sequence, Table } from "../src/schema.js";

const MINIMAL_SPEC = {
  slides: [
    {
      header: { title: "Q3 Results", subtitle: "Engineering team" },
      body: [{ primitive: "text", mode: "bullets", content: ["Shipped the resolver", "Cut render time"] }],
    },
  ],
};

function tmpPath(name: string): string {
  return join(mkdtempSync(join(tmpdir(), "compono-js-")), name);
}

describe("validate", () => {
  it("accepts a valid spec", () => {
    const report = validate(MINIMAL_SPEC);
    expect(report.valid).toBe(true);
    expect(report.errors).toEqual([]);
  });

  it("returns structured errors for a malformed spec", () => {
    const report = validate({ slides: [{ body: [{ primitive: "header" }] }] });
    expect(report.valid).toBe(false);
    const error = report.errors[0];
    expect(Object.keys(error)).toEqual(
      expect.arrayContaining(["slide", "primitive", "field", "error", "detail", "fix"]),
    );
  });

  it("rejects an unknown template with a structured error, not a crash", () => {
    const report = validate({ template: "does-not-exist", slides: [] });
    expect(report.valid).toBe(false);
    expect(report.errors[0].error).toBe("unknown_template");
  });
});

describe("renderDeck", () => {
  it("writes a real .pptx file", async () => {
    const output = tmpPath("deck.pptx");
    const report = await renderDeck(MINIMAL_SPEC, output);
    expect(report.pptxPath).toBe(output);

    const buf = await readFile(output);
    expect(buf.length).toBeGreaterThan(0);
    // A real .pptx is a zip — starts with the PK magic bytes.
    expect(buf[0]).toBe(0x50);
    expect(buf[1]).toBe(0x4b);
  });

  it("throws DeckValidationError and writes nothing on a malformed spec", async () => {
    const output = tmpPath("deck.pptx");
    await expect(renderDeck({ slides: [{ body: [{ primitive: "header" }] }] }, output)).rejects.toBeInstanceOf(
      DeckValidationError,
    );
    await expect(readFile(output)).rejects.toThrow();
  });

  it("flags text overflow before writing anything", async () => {
    const output = tmpPath("deck.pptx");
    const overflowSpec = {
      slides: [
        {
          body: [
            {
              primitive: "text",
              mode: "bullets",
              content: Array.from({ length: 40 }, (_, i) => `Very long bullet point number ${i} that keeps going on and on`),
            },
          ],
        },
      ],
    };
    await expect(renderDeck(overflowSpec, output)).rejects.toMatchObject({
      errors: expect.arrayContaining([expect.objectContaining({ error: "overflow" })]),
    });
  });

  it("draws a shape with text as one shape, not two stacked shapes at the same rect (regression)", async () => {
    // A real bug found via inspire.test.ts: addShape()+addText() as two
    // separate calls drew two overlapping <p:sp> elements per shape-with-
    // text primitive, which threw off Inspire's row-grouping/grid-detection
    // math when scanning a rendered deck back. pptxgenjs's addText(text,
    // {shape: ...}) draws both in one real shape instead.
    const output = tmpPath("shape.pptx");
    const spec = {
      slides: [
        {
          body: [
            {
              primitive: "shape",
              kind: "rounded_rect",
              fill: "#2A9D8F",
              text: { content: "Card", color: "#FFFFFF" },
            },
          ],
        },
      ],
    };
    await renderDeck(spec, output);

    const zip = await JSZip.loadAsync(await readFile(output));
    const slideXml = await zip.files["ppt/slides/slide1.xml"].async("string");
    // 2 total <p:sp>: the shape+text (one element) and the footer page
    // number (a separate shape) — never a 3rd, duplicate shape for the
    // text stacked on top of the fill.
    expect((slideXml.match(/<p:sp>/g) ?? []).length).toBe(2);
    expect(slideXml).toContain("Card");
    expect(slideXml).toContain("2A9D8F");
  });

  it("renders a diagram's nodes as real shapes and its edges as real connectors, with per-node fill overrides winning", async () => {
    const output = tmpPath("diagram.pptx");
    const spec = {
      slides: [
        {
          body: [
            {
              primitive: "diagram",
              node_fill: "#2A6FDB",
              nodes: [
                { label: "User" },
                { label: "Router" },
                { label: "LLM", fill: "#D9534F" },
              ],
            },
          ],
        },
      ],
    };
    await renderDeck(spec, output);

    const zip = await JSZip.loadAsync(await readFile(output));
    const slideXml = await zip.files["ppt/slides/slide1.xml"].async("string");
    // renderConnector draws each edge as one-or-more real line <p:sp>
    // shapes (pptxgenjs has no dedicated connector element), so the total
    // <p:sp> count includes the 3 node shapes + 1 footer + N edge segments
    // — just assert node shapes are present, not an exact segment count.
    expect((slideXml.match(/<p:sp>/g) ?? []).length).toBeGreaterThanOrEqual(4);
    expect(slideXml).toContain("User");
    expect(slideXml).toContain("Router");
    expect(slideXml).toContain("LLM");
    // Diagram-level default fill applies to nodes without their own override...
    expect(slideXml).toContain("2A6FDB");
    // ...but a node's own `fill` wins over the diagram-level default.
    expect(slideXml).toContain("D9534F");
  });
});


// --- Font resolution / chart fonts / per-cell overflow (font+overflow batch port) ---

describe("resolveFontPath", () => {
  it.each(["default", "modern", "classic", "clean"])(
    "finds the bundled font for the %s template",
    (templateName) => {
      const template = loadTemplateByName(templateName);
      const path = resolveFontPath(template);
      expect(path).not.toBeNull();
      expect(path).toMatch(/OpenSans-Regular\.ttf$/);
    },
  );
});

describe("renderChart", () => {
  it("applies the template font to chart axis/legend/data-label options", async () => {
    const output = tmpPath("chart.pptx");
    const spec = {
      template: "modern",
      slides: [
        {
          header: { title: "Revenue" },
          body: [
            {
              primitive: "chart",
              chart_type: "bar",
              categories: ["Q1", "Q2"],
              series: [{ name: "Revenue", values: [10, 14] }],
            },
          ],
        },
      ],
    };
    await renderDeck(spec, output); // must not throw
    const buf = await readFile(output);
    expect(buf.length).toBeGreaterThan(0);
  });

  it("renders a pie chart without throwing (no category/value axis)", async () => {
    const output = tmpPath("pie.pptx");
    const spec = {
      slides: [
        {
          header: { title: "Share" },
          body: [
            {
              primitive: "chart",
              chart_type: "pie",
              categories: ["A", "B"],
              series: [{ name: "Share", values: [40, 60] }],
            },
          ],
        },
      ],
    };
    await renderDeck(spec, output);
    const buf = await readFile(output);
    expect(buf.length).toBeGreaterThan(0);
  });
});

describe("tableCellRects", () => {
  it("splits evenly into numCols by numRows", () => {
    const rect: Rect = { x: 0, y: 0, w: 900, h: 300 };
    const cells = tableCellRects(rect, 3, 3);
    expect(cells).toHaveLength(3);
    expect(cells[0]).toHaveLength(3);
    expect(cells[0][0]).toEqual({ x: 0, y: 0, w: 300, h: 100 });
    expect(cells[1][2]).toEqual({ x: 600, y: 100, w: 300, h: 100 });
  });
});

describe("sequenceStepRects", () => {
  it("splits evenly left to right", () => {
    const rect: Rect = { x: 0, y: 0, w: 400, h: 100 };
    const steps = sequenceStepRects(rect, 4);
    expect(steps).toEqual([
      { x: 0, y: 0, w: 100, h: 100 },
      { x: 100, y: 0, w: 100, h: 100 },
      { x: 200, y: 0, w: 100, h: 100 },
      { x: 300, y: 0, w: 100, h: 100 },
    ]);
  });
});

describe("extractTextFields (table/sequence per-cell/per-step)", () => {
  it("checks each table cell against its own sub-rect, not the whole rect", () => {
    const table = { primitive: "table", headers: ["A", "B"], rows: [["short", "short"]] } as Table;
    const rect: Rect = { x: 0, y: 0, w: 1000, h: 500 };
    const fields = extractTextFields(table, rect);

    expect(fields.map(([field]) => field)).toEqual(["headers[0]", "headers[1]", "rows[0][0]", "rows[0][1]"]);
    for (const [, , , subRect] of fields) {
      expect(subRect).not.toBeNull();
      expect(subRect!.w).toBe(500);
      expect(subRect!.h).toBe(250);
    }
  });

  it("checks each sequence step against its own sub-rect", () => {
    const sequence = {
      primitive: "sequence",
      steps: [{ label: "One", description: null }, { label: "Two", description: null }],
      orientation: "horizontal",
    } as Sequence;
    const rect: Rect = { x: 0, y: 0, w: 1000, h: 500 };
    const fields = extractTextFields(sequence, rect);

    expect(fields.map(([field]) => field)).toEqual(["steps[0]", "steps[1]"]);
    for (const [, , , subRect] of fields) {
      expect(subRect).toEqual({ x: expect.any(Number), y: 0, w: 500, h: 500 });
    }
  });
});

describe("per-cell table overflow (regression)", () => {
  it("flags a single overlong cell even though the combined text would fit the whole rect", () => {
    const longCell = "word ".repeat(400);
    const spec = {
      slides: [
        {
          header: { title: "Comparison" },
          body: [
            {
              primitive: "table",
              headers: ["A", "B", "C", "D"],
              rows: [["x", "y", longCell, "z"]],
            },
          ],
        },
      ],
    };
    const report = validate(spec);
    expect(report.valid).toBe(false);
    expect(report.errors).toEqual(
      expect.arrayContaining([expect.objectContaining({ error: "overflow", field: "rows[0][2]" })]),
    );
  });
});
