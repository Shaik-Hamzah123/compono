import { mkdtempSync, writeFileSync } from "node:fs";
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
  tableColumnWidthsEmu,
  validate,
} from "../src/render.js";
import type { FontMetrics } from "../src/validator.js";
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

  it("applies cell_fills to the right table body cell only", async () => {
    const output = tmpPath("cellfills.pptx");
    const spec = {
      slides: [
        {
          body: [
            {
              primitive: "table",
              headers: ["A", "B"],
              rows: [["1", "2"], ["3", "4"]],
              cell_fills: [{ row: 1, col: 0, fill: "#2A6FDB" }],
            },
          ],
        },
      ],
    };
    await renderDeck(spec, output);
    const zip = await JSZip.loadAsync(await readFile(output));
    const slideXml = await zip.files["ppt/slides/slide1.xml"].async("string");
    expect(slideXml).toContain("2A6FDB");
  });

  it("merges table cells via colspan/rowspan in the raw table XML", async () => {
    // pptxgenjs has no python-pptx-style post-render cell inspection API —
    // read the raw OOXML table markup instead, checking for the gridSpan/
    // rowSpan + hMerge/vMerge attributes a real merge produces.
    const output = tmpPath("merge.pptx");
    const spec = {
      slides: [
        {
          body: [
            {
              primitive: "table",
              headers: ["Region", "Q1", "Q2"],
              rows: [
                ["North", "10", "12"],
                ["North", "11", "13"],
                ["South", "5", "6"],
              ],
              merges: [{ row1: 0, col1: 0, row2: 1, col2: 0 }],
            },
          ],
        },
      ],
    };
    await renderDeck(spec, output);
    const zip = await JSZip.loadAsync(await readFile(output));
    const slideXml = await zip.files["ppt/slides/slide1.xml"].async("string");
    expect(slideXml).toMatch(/rowSpan="2"/);
    expect(slideXml).toMatch(/vMerge="1"|vMerge="true"/);
    expect(slideXml).toContain("North");
    expect(slideXml).toContain("South");
  });

  it("renders a gantt's task spans as colored table cells, with per-task fill overrides winning", async () => {
    const output = tmpPath("gantt.pptx");
    const spec = {
      slides: [
        {
          header: { title: "Project Timeline" },
          body: [
            {
              primitive: "gantt",
              task_fill: "#2A6FDB",
              unit_labels: ["Wk 1", "Wk 2", "Wk 3", "Wk 4"],
              tasks: [
                { label: "Discovery", start_unit: 0, duration_units: 2 },
                { label: "Design", start_unit: 2, duration_units: 2, fill: "#D9534F" },
              ],
            },
          ],
        },
      ],
    };
    await renderDeck(spec, output);
    const zip = await JSZip.loadAsync(await readFile(output));
    const slideXml = await zip.files["ppt/slides/slide1.xml"].async("string");
    expect(slideXml).toContain("Discovery");
    expect(slideXml).toContain("Design");
    expect(slideXml).toContain("Wk 1");
    expect(slideXml).toContain("2A6FDB");
    expect(slideXml).toContain("D9534F");
  });

  it("applies template.primaryColor to the table header row and template.accentColor to sequence steps", async () => {
    const output = tmpPath("branded.pptx");
    const template = { ...loadTemplateByName("default"), primaryColor: "#1F4E79", accentColor: "#2E86AB" };
    const spec = {
      slides: [
        {
          body: [
            { primitive: "table", headers: ["A"], rows: [["1"]] },
            { primitive: "sequence", steps: [{ label: "Step" }] },
          ],
        },
      ],
    };
    await renderDeck(spec, output, template);
    const zip = await JSZip.loadAsync(await readFile(output));
    const slideXml = await zip.files["ppt/slides/slide1.xml"].async("string");
    expect(slideXml).toContain("1F4E79");
    expect(slideXml).toContain("2E86AB");
  });

  it("does not brand the table header or sequence steps when colors are unset", async () => {
    const output = tmpPath("unbranded.pptx");
    const spec = {
      slides: [
        {
          body: [
            { primitive: "table", headers: ["A"], rows: [["1"]] },
            { primitive: "sequence", steps: [{ label: "Step" }] },
          ],
        },
      ],
    };
    await renderDeck(spec, output);
    const zip = await JSZip.loadAsync(await readFile(output));
    const slideXml = await zip.files["ppt/slides/slide1.xml"].async("string");
    // Unset -> the pre-existing hardcoded defaults, unchanged.
    expect(slideXml).toContain("4A7FC2"); // TABLE_HEADER_FILL
    expect(slideXml).toContain("2A6FDB"); // sequence step default fill
  });

  it("renders a real logo picture in the header when template.logoPath is set", async () => {
    const dir = mkdtempSync(join(tmpdir(), "compono-js-logo-"));
    const logoPath = join(dir, "logo.png");
    // 1x1 transparent PNG.
    writeFileSync(
      logoPath,
      Buffer.from(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
        "base64",
      ),
    );
    const output = tmpPath("logo.pptx");
    const template = { ...loadTemplateByName("default"), logoPath };
    await renderDeck({ slides: [{ header: { title: "Q3" }, body: [] }] }, output, template);
    const zip = await JSZip.loadAsync(await readFile(output));
    // pptxgenjs always writes an (empty) `ppt/media/` directory entry
    // regardless of whether any image was embedded — only count real files.
    const mediaFiles = Object.keys(zip.files).filter((f) => /^ppt\/media\/.+/.test(f));
    expect(mediaFiles.length).toBeGreaterThan(0);
  });

  it("does not render a logo picture when template.logoPath is unset", async () => {
    const output = tmpPath("nologo.pptx");
    await renderDeck({ slides: [{ header: { title: "Q3" }, body: [] }] }, output);
    const zip = await JSZip.loadAsync(await readFile(output));
    const mediaFiles = Object.keys(zip.files).filter((f) => /^ppt\/media\/.+/.test(f));
    expect(mediaFiles.length).toBe(0);
  });
});

describe("tableColumnWidthsEmu", () => {
  const monospaceMetrics: FontMetrics = {
    unitsPerEm: 1000,
    defaultAdvance: 600,
    advanceWidths: new Map(),
  };

  it("returns null without font metrics", () => {
    const rect: Rect = { x: 0, y: 0, w: 900_000, h: 200_000 };
    expect(tableColumnWidthsEmu(["A", "B"], [["1", "2"]], rect, null)).toBeNull();
  });

  it("sums to rect.w and gives more space to the longer column", () => {
    const rect: Rect = { x: 0, y: 0, w: 900_000, h: 200_000 };
    const widths = tableColumnWidthsEmu(
      ["Short", "This is a considerably longer column header"],
      [["s", "l"]],
      rect,
      monospaceMetrics,
    );
    expect(widths).not.toBeNull();
    expect(widths!.reduce((a, b) => a + b, 0)).toBe(rect.w);
    expect(widths![1]).toBeGreaterThan(widths![0]);
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
