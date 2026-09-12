import { describe, expect, it } from "vitest";
import { DocChart, DocImage, DocTable, DocxDoc } from "../src/docx_schema.js";

describe("docx_schema", () => {
  it("rejects a table with rows not matching header length", () => {
    expect(() => DocTable.parse({ headers: ["A", "B"], rows: [["1", "2"], ["only-one"]] })).toThrow();
  });

  it("requires src or placeholder on image", () => {
    expect(() => DocImage.parse({})).toThrow();
    expect(DocImage.parse({ placeholder: true }).placeholder).toBe(true);
  });

  it("rejects a chart series/category length mismatch", () => {
    expect(() =>
      DocChart.parse({ chart_type: "bar", categories: ["A"], series: [{ name: "s", values: [1, 2] }] }),
    ).toThrow();
  });

  it("rejects a pie chart with more than one series", () => {
    expect(() =>
      DocChart.parse({
        chart_type: "pie",
        categories: ["A", "B"],
        series: [
          { name: "s1", values: [1, 2] },
          { name: "s2", values: [3, 4] },
        ],
      }),
    ).toThrow();
  });

  it("accepts a full docx doc with every primitive type", () => {
    const doc = DocxDoc.parse({
      title: "Report",
      sections: [
        {
          body: [
            { primitive: "heading", text: "Title", level: 1 },
            { primitive: "paragraph", runs: [{ text: "Hello" }] },
            { primitive: "bullet_list", items: [[{ text: "One" }]] },
            { primitive: "numbered_list", items: [[{ text: "Step 1" }]] },
            { primitive: "table", headers: ["A"], rows: [["1"]] },
            { primitive: "image", placeholder: true, caption: "Logo" },
            {
              primitive: "chart",
              chart_type: "bar",
              categories: ["A"],
              series: [{ name: "s", values: [1] }],
            },
            { primitive: "page_break" },
          ],
        },
      ],
    });
    expect(doc.sections[0].body).toHaveLength(8);
  });
});
