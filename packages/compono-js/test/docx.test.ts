import { mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import JSZip from "jszip";
import { describe, expect, it } from "vitest";
import { DocxValidationError, renderDocx, validateDocx } from "../src/docx.js";

const FULL_SPEC = {
  title: "Training Proposal",
  sections: [
    {
      header_text: "Confidential",
      footer_text: "Page footer",
      body: [
        { primitive: "heading", text: "Overview", level: 1 },
        {
          primitive: "paragraph",
          runs: [
            { text: "This is " },
            { text: "bold", bold: true },
            { text: " and this is a " },
            { text: "link", link: "https://example.com" },
            { text: "." },
          ],
        },
        { primitive: "bullet_list", items: [[{ text: "First point" }], [{ text: "Second point" }]] },
        { primitive: "numbered_list", items: [[{ text: "Step one" }], [{ text: "Step two" }]] },
        {
          primitive: "table",
          headers: ["Track", "Weeks"],
          rows: [
            ["AI Foundations", "1-2"],
            ["Advanced ML", "3-4"],
          ],
        },
        { primitive: "image", placeholder: true, caption: "Company logo" },
        {
          primitive: "chart",
          chart_type: "bar",
          categories: ["Q1", "Q2", "Q3"],
          series: [{ name: "Revenue", values: [10, 20, 15] }],
        },
        { primitive: "page_break" },
      ],
    },
  ],
};

function tmpPath(name: string): string {
  return join(mkdtempSync(join(tmpdir(), "compono-js-docx-")), name);
}

describe("validateDocx", () => {
  it("accepts a valid spec", () => {
    const report = validateDocx(FULL_SPEC);
    expect(report.valid).toBe(true);
  });

  it("returns structured errors for a malformed spec", () => {
    const report = validateDocx({ title: "Bad", sections: [{ body: [{ primitive: "heading" }] }] });
    expect(report.valid).toBe(false);
    expect(Object.keys(report.errors[0])).toEqual(
      expect.arrayContaining(["section", "primitive", "field", "error", "detail", "fix"]),
    );
  });
});

describe("renderDocx", () => {
  it("writes a real .docx file", async () => {
    const output = tmpPath("report.docx");
    const report = await renderDocx(FULL_SPEC, output);
    expect(report.docxPath).toBe(output);

    const buf = readFileSync(output);
    expect(buf[0]).toBe(0x50);
    expect(buf[1]).toBe(0x4b); // real zip (PK) — a genuine .docx
  });

  it("throws DocxValidationError and writes nothing on a malformed spec", async () => {
    const output = tmpPath("report.docx");
    await expect(
      renderDocx({ title: "Bad", sections: [{ body: [{ primitive: "heading" }] }] }, output),
    ).rejects.toBeInstanceOf(DocxValidationError);
    expect(() => readFileSync(output)).toThrow();
  });

  it("puts an image placeholder in the manifest, never as a real picture", async () => {
    const output = tmpPath("report.docx");
    const report = await renderDocx(FULL_SPEC, output);
    expect(report.manifest.some((e) => e.caption === "Company logo")).toBe(true);
  });

  it("renders every primitive except chart as a genuine Word XML object", async () => {
    const output = tmpPath("report.docx");
    await renderDocx(FULL_SPEC, output);

    const zip = await JSZip.loadAsync(readFileSync(output));
    const documentXml = await zip.files["word/document.xml"].async("string");

    expect(documentXml).toContain("Overview"); // real heading text
    expect(documentXml).toContain("<w:tbl>"); // real table
    expect(documentXml).toContain("<w:numPr>"); // real numbered-list paragraph properties
    expect(documentXml).toContain("<w:hyperlink"); // real hyperlink run
    expect(documentXml).toContain("<w:br"); // real page break

    // Exactly one real embedded picture: the chart (the image primitive
    // here is a placeholder, contributing text only).
    const mediaFiles = Object.keys(zip.files).filter(
      (name) => name.startsWith("word/media/") && !zip.files[name].dir,
    );
    expect(mediaFiles).toHaveLength(1);
  });

  it("gives the table real, full-page width (regression: defaulted to ~100 twips, an invisible sliver — verified visually via a LibreOffice render, not just this XML check)", async () => {
    const output = tmpPath("report.docx");
    await renderDocx(FULL_SPEC, output);

    const zip = await JSZip.loadAsync(readFileSync(output));
    const documentXml = await zip.files["word/document.xml"].async("string");
    expect(documentXml).toContain('<w:tblW w:type="pct" w:w="100%"/>');
    const cellWidths = [...documentXml.matchAll(/<w:tcW w:type="pct" w:w="(\d+)%"/g)].map((m) => Number(m[1]));
    expect(cellWidths.length).toBeGreaterThan(0);
    for (const w of cellWidths) expect(w).toBeGreaterThan(0);
  });

  it("styles hyperlink run text with an explicit color (regression: rendered invisible without one)", async () => {
    const output = tmpPath("report.docx");
    await renderDocx(FULL_SPEC, output);

    const zip = await JSZip.loadAsync(readFileSync(output));
    const documentXml = await zip.files["word/document.xml"].async("string");
    const hyperlinkSection = documentXml.slice(
      documentXml.indexOf("<w:hyperlink"),
      documentXml.indexOf("</w:hyperlink>") + "</w:hyperlink>".length,
    );
    expect(hyperlinkSection).toContain('<w:color w:val="0563C1"/>');
    expect(hyperlinkSection).toContain("<w:u ");
  });

  it("applies section header/footer text", async () => {
    const output = tmpPath("report.docx");
    await renderDocx(FULL_SPEC, output);

    const zip = await JSZip.loadAsync(readFileSync(output));
    const headerFiles = Object.keys(zip.files).filter((name) => /word\/header\d+\.xml$/.test(name));
    const footerFiles = Object.keys(zip.files).filter((name) => /word\/footer\d+\.xml$/.test(name));
    expect(headerFiles.length).toBeGreaterThan(0);
    expect(footerFiles.length).toBeGreaterThan(0);

    const headerXml = await zip.files[headerFiles[0]].async("string");
    const footerXml = await zip.files[footerFiles[0]].async("string");
    expect(headerXml).toContain("Confidential");
    expect(footerXml).toContain("Page footer");
  });
});
