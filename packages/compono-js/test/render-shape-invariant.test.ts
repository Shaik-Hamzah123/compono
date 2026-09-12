/**
 * Golden/invariant test: render examples/full_catalog.json, reopen the
 * .pptx with JSZip, and assert real structural properties — never
 * pixel-diffing. Mirrors tests/test_render_shape_invariant.py's intent:
 * every primitive renders as a genuine OOXML shape (real <p:sp>/<p:pic>/
 * <p:graphicFrame>), never a flattened image.
 */

import { mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import JSZip from "jszip";
import { describe, expect, it } from "vitest";
import { renderDeck } from "../src/render.js";

const EXAMPLES_DIR = join(import.meta.dirname, "..", "..", "..", "examples");

function tmpPath(name: string): string {
  return join(mkdtempSync(join(tmpdir(), "compono-js-")), name);
}

describe("render shape invariant", () => {
  it("renders every primitive in full_catalog.json as a real OOXML shape", async () => {
    const spec = JSON.parse(readFileSync(join(EXAMPLES_DIR, "full_catalog.json"), "utf-8"));
    const output = tmpPath("full_catalog.pptx");
    await renderDeck(spec, output);

    const zip = await JSZip.loadAsync(readFileSync(output));
    const slideFiles = Object.keys(zip.files).filter((name) => /^ppt\/slides\/slide\d+\.xml$/.test(name));
    expect(slideFiles.length).toBe(spec.slides.length);

    for (const name of slideFiles) {
      const xml = await zip.files[name].async("string");
      // Real shapes/tables/charts, never a flattened <p:pic> standing in
      // for text/table/chart content that should be a real object.
      expect(xml).toMatch(/<p:sp>|<p:graphicFrame>/);
    }

    // The one real image in this deck is a placeholder (dashed box + a
    // caption text run) — never a rasterized <p:pic>, since compono never
    // renders a placeholder as a real embedded image.
    const teamSlide = await zip.files[slideFiles[2]].async("string");
    expect(teamSlide).not.toMatch(/<p:pic>/);
    expect(teamSlide).toMatch(/Team photo goes here/);
  });

  it("round-trips real table and chart data into the file, not a picture", async () => {
    const spec = JSON.parse(readFileSync(join(EXAMPLES_DIR, "full_catalog.json"), "utf-8"));
    const output = tmpPath("full_catalog.pptx");
    await renderDeck(spec, output);

    const zip = await JSZip.loadAsync(readFileSync(output));
    const slide1 = await zip.files["ppt/slides/slide1.xml"].async("string");
    expect(slide1).toContain("Q1");
    expect(slide1).toContain("38%");

    const chartFiles = Object.keys(zip.files).filter((name) => /^ppt\/charts\/chart\d+\.xml$/.test(name));
    expect(chartFiles.length).toBeGreaterThan(0);
    const chartXml = await zip.files[chartFiles[0]].async("string");
    expect(chartXml).toContain("Revenue");
  });

  it("renders stat.trend and a footer page number (fields the schema declares that must not be silently dropped)", async () => {
    const spec = JSON.parse(readFileSync(join(EXAMPLES_DIR, "full_catalog.json"), "utf-8"));
    const output = tmpPath("full_catalog.pptx");
    await renderDeck(spec, output);

    const zip = await JSZip.loadAsync(readFileSync(output));
    const slide1 = await zip.files["ppt/slides/slide1.xml"].async("string");
    expect(slide1).toContain("+12% vs last quarter"); // stat.trend
    expect(slide1).toContain("1 / 3"); // footer page number
  });
});
