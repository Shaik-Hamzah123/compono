import { mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import JSZip from "jszip";
import { describe, expect, it } from "vitest";
import { renderDeck } from "../src/render.js";
import { loadTemplateFromYaml } from "../src/resolver.js";
import { extractTemplateData, writeExtractedTemplate } from "../src/templateAuthoring.js";

function tmpPath(name: string): string {
  return join(mkdtempSync(join(tmpdir(), "compono-js-tplauth-")), name);
}

const LOGO_PNG_BASE64 =
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=";

/** Builds a real .pptx via renderDeck (a real theme part comes bundled by
 * pptxgenjs, same as any real deck), then injects a `<p:pic>` onto the
 * slide master plus its relationship + media entry — mirroring the low-
 * level fixture technique the Python test suite uses for the same
 * python-pptx-can't-add-a-master-picture limitation.
 */
async function buildFixturePptx(path: string, withLogo: boolean): Promise<void> {
  await renderDeck({ slides: [{ header: { title: "Q3" }, body: [] }] }, path);
  if (!withLogo) return;

  const zip = await JSZip.loadAsync(readFileSync(path));
  zip.file("ppt/media/image1.png", Buffer.from(LOGO_PNG_BASE64, "base64"));

  const relsPath = "ppt/slideMasters/_rels/slideMaster1.xml.rels";
  let relsXml = await zip.files[relsPath].async("string");
  relsXml = relsXml.replace(
    "</Relationships>",
    '<Relationship Id="rIdLogo" ' +
      'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" ' +
      'Target="../media/image1.png"/></Relationships>',
  );
  zip.file(relsPath, relsXml);

  const masterPath = "ppt/slideMasters/slideMaster1.xml";
  let masterXml = await zip.files[masterPath].async("string");
  const picXml =
    "<p:pic><p:nvPicPr><p:cNvPr id=\"99\" name=\"Logo\"/><p:cNvPicPr/><p:nvPr/></p:nvPicPr>" +
    '<p:blipFill><a:blip r:embed="rIdLogo"/><a:stretch><a:fillRect/></a:stretch></p:blipFill>' +
    '<p:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="500000" cy="300000"/></a:xfrm>' +
    '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic>';
  masterXml = masterXml.replace("</p:spTree>", picXml + "</p:spTree>");
  zip.file(masterPath, masterXml);

  const out = await zip.generateAsync({ type: "nodebuffer" });
  const fs = await import("node:fs");
  fs.writeFileSync(path, out);
}

describe("extractTemplateData", () => {
  it("reads the real page size", async () => {
    const path = tmpPath("source.pptx");
    await buildFixturePptx(path, false);
    const data = await extractTemplateData(path);
    expect(data.pageWidthIn).toBeCloseTo(13.333, 2);
    expect(data.pageHeightIn).toBeCloseTo(7.5, 2);
  });

  it("finds a real font and colors from the bundled default theme", async () => {
    // A real pptxgenjs-produced deck always ships a real theme part —
    // assert non-empty/well-formed, not a specific value (the bundled
    // default theme is an implementation detail, not something this repo
    // documents or should pin against).
    const path = tmpPath("source.pptx");
    await buildFixturePptx(path, false);
    const data = await extractTemplateData(path);
    expect(data.fontFamily).toBeTruthy();
    for (const color of [data.primaryColor, data.accentColor]) {
      expect(color).toMatch(/^#[0-9A-F]{6}$/);
    }
  });

  it("finds the master logo when present", async () => {
    const path = tmpPath("source.pptx");
    await buildFixturePptx(path, true);
    const data = await extractTemplateData(path);
    expect(data.logoBytes).toBeInstanceOf(Buffer);
    expect(data.logoExt).toBe("png");
  });

  it("logo is undefined without one", async () => {
    const path = tmpPath("source.pptx");
    await buildFixturePptx(path, false);
    const data = await extractTemplateData(path);
    expect(data.logoBytes).toBeUndefined();
  });

  it("never throws on a missing theme part", async () => {
    const path = tmpPath("source.pptx");
    await buildFixturePptx(path, false);
    const zip = await JSZip.loadAsync(readFileSync(path));
    zip.remove("ppt/theme/theme1.xml");
    const stripped = tmpPath("stripped.pptx");
    const fs = await import("node:fs");
    fs.writeFileSync(stripped, await zip.generateAsync({ type: "nodebuffer" }));

    const data = await extractTemplateData(stripped);
    expect(data.fontFamily).toBeUndefined();
    expect(data.primaryColor).toBeUndefined();
    expect(data.accentColor).toBeUndefined();
  });
});

describe("writeExtractedTemplate", () => {
  it("round-trips through loadTemplateFromYaml", async () => {
    const path = tmpPath("source.pptx");
    await buildFixturePptx(path, true);
    const data = await extractTemplateData(path);

    const outputDir = tmpPath("out");
    const yamlPath = writeExtractedTemplate(data, "acme", outputDir);
    expect(yamlPath).toBe(join(outputDir, "acme.yaml"));

    const template = loadTemplateFromYaml(yamlPath);
    expect(template.fontFamily).toBe(data.fontFamily);
    expect(template.primaryColor).toBe(data.primaryColor);
    expect(template.accentColor).toBe(data.accentColor);
    expect(template.logoPath).toBeTruthy();
    expect(readFileSync(template.logoPath!)).toEqual(data.logoBytes);

    // Margins/header/footer/gutter are copied from compono-js's own
    // default — never derived from the source deck.
    const defaultTemplate = loadTemplateFromYaml(join(import.meta.dirname, "..", "templates", "default.yaml"));
    expect(template.marginTop).toBe(defaultTemplate.marginTop);
    expect(template.headerHeight).toBe(defaultTemplate.headerHeight);
    expect(template.footerHeight).toBe(defaultTemplate.footerHeight);
    expect(template.gutter).toBe(defaultTemplate.gutter);
  });

  it("omits colors/logo keys when absent", async () => {
    const path = tmpPath("source.pptx");
    await buildFixturePptx(path, false);
    const data = await extractTemplateData(path);
    const bare = { ...data, primaryColor: undefined, accentColor: undefined };

    const outputDir = tmpPath("out");
    const yamlPath = writeExtractedTemplate(bare, "bare", outputDir);
    const template = loadTemplateFromYaml(yamlPath);
    expect(template.primaryColor).toBeUndefined();
    expect(template.accentColor).toBeUndefined();
    expect(template.logoPath).toBeUndefined();
  });
});
