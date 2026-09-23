import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { crc32 } from "node:zlib";
import { describe, expect, it } from "vitest";
import { review } from "../src/review.js";

function tmpPath(name: string): string {
  return join(mkdtempSync(join(tmpdir(), "compono-js-review-")), name);
}

/** A minimal, valid-enough PNG (signature + IHDR + empty IDAT + IEND) —
 * image-size only reads the IHDR chunk, so no real pixel data is needed. */
function writeMinimalPng(path: string, width: number, height: number): void {
  const chunk = (type: string, data: Buffer): Buffer => {
    const typeBuf = Buffer.from(type, "ascii");
    const len = Buffer.alloc(4);
    len.writeUInt32BE(data.length, 0);
    const crcInput = Buffer.concat([typeBuf, data]);
    const crcBuf = Buffer.alloc(4);
    crcBuf.writeUInt32BE(crc32(crcInput) >>> 0, 0);
    return Buffer.concat([len, typeBuf, data, crcBuf]);
  };

  const signature = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);
  const ihdrData = Buffer.alloc(13);
  ihdrData.writeUInt32BE(width, 0);
  ihdrData.writeUInt32BE(height, 4);
  ihdrData[8] = 8; // bit depth
  ihdrData[9] = 2; // color type: RGB
  ihdrData[10] = 0;
  ihdrData[11] = 0;
  ihdrData[12] = 0;

  const png = Buffer.concat([
    signature,
    chunk("IHDR", ihdrData),
    chunk("IDAT", Buffer.alloc(0)),
    chunk("IEND", Buffer.alloc(0)),
  ]);
  writeFileSync(path, png);
}

describe("review", () => {
  it("flags low-contrast shape text", () => {
    const spec = {
      slides: [
        {
          header: { title: "Contrast check" },
          body: [
            {
              primitive: "shape",
              kind: "rounded_rect",
              fill: "#111827",
              text: { content: "Hard to read", color: "#1F2937" },
            },
          ],
        },
      ],
    };
    const report = review(spec);
    const contrast = report.suggestions.filter((s) => s.category === "contrast");
    expect(contrast).toHaveLength(1);
    expect(contrast[0].field).toBe("text.color");
  });

  it("does not flag contrast without an explicit text color", () => {
    const spec = {
      slides: [
        {
          header: { title: "No explicit color" },
          body: [{ primitive: "shape", kind: "rounded_rect", fill: "#111827" }],
        },
      ],
    };
    const report = review(spec);
    expect(report.suggestions.filter((s) => s.category === "contrast")).toEqual([]);
  });

  it("does not flag good contrast", () => {
    const spec = {
      slides: [
        {
          header: { title: "Good contrast" },
          body: [
            {
              primitive: "shape",
              kind: "rounded_rect",
              fill: "#111827",
              text: { content: "Easy to read", color: "#FFFFFF" },
            },
          ],
        },
      ],
    };
    const report = review(spec);
    expect(report.suggestions.filter((s) => s.category === "contrast")).toEqual([]);
  });

  it("flags a lone stat alone in a tall body", () => {
    const spec = {
      slides: [
        {
          header: { title: "Sparse" },
          body: [{ primitive: "stat", value: "42%", label: "growth" }],
        },
      ],
    };
    const report = review(spec);
    expect(report.suggestions.some((s) => s.category === "whitespace")).toBe(true);
  });

  it("never flags whitespace on a header-only slide", () => {
    const spec = { slides: [{ header: { title: "Title slide" } }] };
    const report = review(spec);
    expect(report.suggestions.filter((s) => s.category === "whitespace")).toEqual([]);
  });

  it("does not flag whitespace for a multi-item body", () => {
    const spec = {
      slides: [
        {
          header: { title: "Not sparse" },
          body: [
            { primitive: "stat", value: "1", label: "one" },
            { primitive: "stat", value: "2", label: "two" },
          ],
        },
      ],
    };
    const report = review(spec);
    expect(report.suggestions.filter((s) => s.category === "whitespace")).toEqual([]);
  });

  it("does not flag whitespace for a lone but dense grid (regression)", () => {
    const spec = {
      slides: [
        {
          header: { title: "Program at a Glance" },
          body: [
            {
              primitive: "grid",
              columns: 4,
              items: [
                { primitive: "stat", value: "8", label: "sessions" },
                { primitive: "stat", value: "4", label: "labs" },
                { primitive: "stat", value: "1", label: "channel" },
                { primitive: "stat", value: "100+", label: "templates" },
              ],
            },
          ],
        },
      ],
    };
    const report = review(spec);
    expect(report.suggestions.filter((s) => s.category === "whitespace")).toEqual([]);
  });

  it("flags text close to overflowing without crashing", () => {
    const spec = {
      slides: [
        {
          header: { title: "Tight" },
          body: [
            {
              primitive: "text",
              mode: "bullets",
              content: [
                "One bullet",
                "Two bullet",
                "Three bullet",
                "Four bullet",
                "Five bullet",
                "Six bullet",
                "Seven bullet",
              ],
            },
            { primitive: "stat", value: "1", label: "filler" },
            { primitive: "stat", value: "2", label: "filler" },
          ],
        },
      ],
    };
    const report = review(spec);
    for (const s of report.suggestions.filter((x) => x.category === "font_size")) {
      expect(s).toHaveProperty("fix");
      expect(s).toHaveProperty("detail");
    }
  });

  it("flags a badly cropped cover image", () => {
    const imgPath = tmpPath("wide.png");
    writeMinimalPng(imgPath, 2000, 200); // very wide, box is ~square-ish

    const spec = {
      slides: [
        {
          header: { title: "Cropped image" },
          body: [{ primitive: "image", src: imgPath, fit: "cover" }],
        },
      ],
    };
    const report = review(spec);
    const imageFit = report.suggestions.filter((s) => s.category === "image_fit");
    expect(imageFit).toHaveLength(1);
    expect(imageFit[0].field).toBe("fit");
  });

  it("never flags image_fit for a placeholder", () => {
    const spec = {
      slides: [
        {
          header: { title: "Placeholder" },
          body: [{ primitive: "image", placeholder: true, caption: "Photo goes here" }],
        },
      ],
    };
    const report = review(spec);
    expect(report.suggestions.filter((s) => s.category === "image_fit")).toEqual([]);
  });

  it("flags an em dash in text", () => {
    const spec = {
      slides: [
        {
          header: { title: "Style check" },
          body: [{ primitive: "text", content: "Fast — reliable — simple" }],
        },
      ],
    };
    const report = review(spec);
    expect(report.suggestions.some((s) => s.category === "style")).toBe(true);
  });

  it("never raises on a well-formed deck", () => {
    const spec = {
      slides: [
        {
          header: { title: "Fine" },
          body: [{ primitive: "stat", value: "1", label: "x" }],
        },
      ],
    };
    expect(() => review(spec)).not.toThrow();
  });

  it("flags table_density when rows leave a cramped row height", () => {
    const spec = {
      slides: [
        {
          header: { title: "Cramped table" },
          body: [
            {
              primitive: "table",
              headers: ["A", "B"],
              rows: Array.from({ length: 29 }, () => ["x", "y"]),
            },
          ],
        },
      ],
    };
    const report = review(spec);
    const density = report.suggestions.filter((s) => s.category === "table_density");
    expect(density).toHaveLength(1);
    expect(density[0].detail as string).toContain("row height");
  });

  it("does not flag table_density for a small table", () => {
    const spec = {
      slides: [
        {
          header: { title: "Fine table" },
          body: [{ primitive: "table", headers: ["Metric", "Value"], rows: [["Revenue", "$1.2M"]] }],
        },
      ],
    };
    const report = review(spec);
    expect(report.suggestions.filter((s) => s.category === "table_density")).toEqual([]);
  });
});
