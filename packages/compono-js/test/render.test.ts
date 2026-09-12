import { mkdtempSync } from "node:fs";
import { readFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import JSZip from "jszip";
import { describe, expect, it } from "vitest";
import { DeckValidationError, renderDeck, validate } from "../src/render.js";

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
});
