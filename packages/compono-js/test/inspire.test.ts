/**
 * Tests for inspire.ts — mirrors tests/test_inspire.py's structure.
 * Fixtures render tiny specs through compono-js's own renderDeck() into
 * real .pptx files, then scan those.
 */

import { mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { beforeAll, describe, expect, it } from "vitest";
import { aggregate, scanDeck, writeSkill } from "../src/inspire.js";
import { renderDeck } from "../src/render.js";

function gridSpec(columns: number, fill: string) {
  return {
    slides: [
      {
        header: { title: "Grid deck" },
        body: [
          {
            primitive: "grid",
            columns,
            items: Array.from({ length: columns }, (_, i) => ({
              primitive: "shape",
              kind: "rect",
              fill,
              text: { content: `Card ${i}`, color: "#FFFFFF" },
            })),
          },
        ],
      },
    ],
  };
}

let tmpDir: string;
beforeAll(() => {
  tmpDir = mkdtempSync(join(tmpdir(), "compono-js-inspire-"));
});

async function renderFixture(name: string, spec: unknown): Promise<string> {
  const out = join(tmpDir, name);
  await renderDeck(spec, out);
  return out;
}

describe("scanDeck", () => {
  it("never returns literal source text", async () => {
    const deckPath = await renderFixture("three_col.pptx", gridSpec(3, "#2A9D8F"));
    const profile = await scanDeck(deckPath);
    const dumped = JSON.stringify(profile);
    expect(dumped).not.toContain("Card 0");
    expect(dumped).not.toContain("Grid deck");
  });

  it("recovers a known grid column count", async () => {
    const deckPath = await renderFixture("three_col2.pptx", gridSpec(3, "#2A9D8F"));
    const profile = await scanDeck(deckPath);
    const columnsSeen = new Set(profile.grids_detected.map((g) => g.columns));
    expect(columnsSeen.has(3)).toBe(true);
  });

  it("detected grids carry a confidence score in [0,1]", async () => {
    const deckPath = await renderFixture("three_col3.pptx", gridSpec(3, "#2A9D8F"));
    const profile = await scanDeck(deckPath);
    expect(profile.grids_detected.length).toBeGreaterThan(0);
    for (const g of profile.grids_detected) {
      expect(g.confidence).toBeGreaterThanOrEqual(0);
      expect(g.confidence).toBeLessThanOrEqual(1);
    }
  });

  it("omits low-confidence rows rather than guessing (a lone header-only slide)", async () => {
    const deckPath = await renderFixture("lone.pptx", { slides: [{ header: { title: "Just a title" } }] });
    const profile = await scanDeck(deckPath);
    expect(profile.grids_detected).toEqual([]);
  });
});

describe("aggregate", () => {
  it("promotes a color seen in a majority of decks, demotes a one-off", async () => {
    const threeCol = await renderFixture("agg_three.pptx", gridSpec(3, "#2A9D8F"));
    const fiveCol = await renderFixture("agg_five.pptx", gridSpec(5, "#2A9D8F"));
    const oneOff = await renderFixture("agg_oneoff.pptx", gridSpec(3, "#F4A261"));

    const profile = await aggregate([threeCol, fiveCol, oneOff], 0.5);
    expect(profile.recurring_palette).toContain("2A9D8F");
    expect(profile.one_off_palette).toContain("F4A261");
    expect(profile.recurring_palette).not.toContain("F4A261");
  });

  it("does not let a many-slide deck dominate a few-slide aggregate", async () => {
    const manySlides = {
      slides: Array.from({ length: 10 }, (_, i) => ({
        header: { title: `Slide ${i}` },
        body: [{ primitive: "shape", kind: "rect", fill: "#111111" }],
      })),
    };
    const manyPath = await renderFixture("many.pptx", manySlides);

    const otherPaths: string[] = [];
    for (const [i, color] of ["#222222", "#333333", "#444444"].entries()) {
      const spec = {
        slides: [{ header: { title: "One slide" }, body: [{ primitive: "shape", kind: "rect", fill: color }] }],
      };
      otherPaths.push(await renderFixture(`other_${i}.pptx`, spec));
    }

    const profile = await aggregate([manyPath, ...otherPaths], 0.5);
    // #111111 appears in exactly 1 of 4 decks, same as each of the others —
    // none should be "recurring" at a 50% threshold.
    expect(profile.recurring_palette).toEqual([]);
  });

  it("excludes unset ('?') font family from recurring fonts", async () => {
    // A shape without an explicit font override (theme-inherited) — its
    // runs carry no a:latin typeface, so scanDeck reports "?" for family.
    const spec = {
      slides: [
        {
          header: { title: "No font override" },
          body: [{ primitive: "text", content: "Body text with no explicit font" }],
        },
      ],
    };
    const deckPath = await renderFixture("no_font.pptx", spec);
    // This deck alone would trivially have all "?" fonts recur (100% of 1
    // deck) unless the "?" exclusion is real — assert none show up.
    const profile = await aggregate([deckPath], 0.5);
    expect(profile.recurring_fonts.some((f) => f.family === "?")).toBe(false);
  });

  it("raises on an empty path list", async () => {
    await expect(aggregate([], 0.5)).rejects.toThrow();
  });
});

describe("writeSkill", () => {
  it("produces both files with valid frontmatter, and profile.json round-trips", async () => {
    const deckPath = await renderFixture("skill_src.pptx", gridSpec(3, "#2A9D8F"));
    const profile = await aggregate([deckPath], 0.5);

    const outDir = join(tmpDir, "skills", "inspire-mystyle");
    const files = writeSkill(profile, outDir, "mystyle");

    const skillText = readFileSync(files.skillMd, "utf-8");
    expect(skillText.startsWith("---\n")).toBe(true);
    expect(skillText).toContain("name: inspire-mystyle");

    const roundTripped = JSON.parse(readFileSync(files.profileJson, "utf-8"));
    expect(roundTripped.n_example_decks).toBe(1);
  });
});
