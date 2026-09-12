/**
 * Tests for tools.ts — call the underlying tool functions directly (no
 * live stdio transport needed), mirroring
 * packages/compono-mcp/tests/test_server.py's pattern.
 */

import { mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { renderDeck } from "@skhamzah123/compono-js";
import { describe, expect, it } from "vitest";
import {
  inspireScan,
  renderDeckTool,
  renderDocxTool,
  reviewDeck,
  validateDeck,
  validateDocxTool,
} from "../src/tools.js";

const MINIMAL_SPEC = {
  slides: [
    {
      header: { title: "Q3 Results", subtitle: "Engineering team" },
      body: [{ primitive: "text", mode: "bullets", content: ["Shipped the resolver", "Cut render time by 40%"] }],
    },
  ],
};

function tmpPath(name: string): string {
  return join(mkdtempSync(join(tmpdir(), "compono-js-mcp-")), name);
}

describe("validateDeck", () => {
  it("accepts a valid spec", () => {
    const result = validateDeck(MINIMAL_SPEC);
    expect(result.valid).toBe(true);
    expect(result.errors).toEqual([]);
  });

  it("returns structured errors for a malformed spec", () => {
    const result = validateDeck({ slides: [{ body: [{ primitive: "header" }] }] });
    expect(result.valid).toBe(false);
    const error = (result.errors as Record<string, unknown>[])[0];
    expect(Object.keys(error)).toEqual(
      expect.arrayContaining(["slide", "primitive", "field", "error", "detail", "fix"]),
    );
  });
});

describe("renderDeckTool", () => {
  it("writes a real .pptx", async () => {
    const output = tmpPath("deck.pptx");
    const result = await renderDeckTool(MINIMAL_SPEC, output);
    expect(result.pptxPath).toBe(output);
    expect(readFileSync(output).length).toBeGreaterThan(0);
  });

  it("returns structured errors instead of throwing", async () => {
    const output = tmpPath("deck.pptx");
    const result = await renderDeckTool({ slides: [{ body: [{ primitive: "header" }] }] }, output);
    expect(result.valid).toBe(false);
    expect(() => readFileSync(output)).toThrow();
  });
});

describe("reviewDeck", () => {
  it("returns suggestions, never blocking", () => {
    const result = reviewDeck(MINIMAL_SPEC);
    expect(Array.isArray(result.suggestions)).toBe(true);
    expect(Array.isArray(result.warnings)).toBe(true);
  });

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
    const result = reviewDeck(spec);
    expect((result.suggestions as Record<string, unknown>[]).some((s) => s.category === "contrast")).toBe(true);
  });
});

describe("inspireScan", () => {
  it("writes a skill folder from real .pptx files", async () => {
    const deckPath = tmpPath("liked.pptx");
    await renderDeck(MINIMAL_SPEC, deckPath);

    const outDir = tmpPath("skills-inspire-team");
    const result = await inspireScan([deckPath], outDir, "team");

    expect(result.n_decks_scanned).toBe(1);
    expect(result.warnings).toEqual([]);
    expect(readFileSync(result.skill_md as string, "utf-8")).toContain("name: inspire-team");
    expect(() => readFileSync(result.profile_json as string)).not.toThrow();
  });

  it("never leaks literal source text", async () => {
    const deckPath = tmpPath("liked2.pptx");
    await renderDeck(MINIMAL_SPEC, deckPath);

    const outDir = tmpPath("skills-inspire-team2");
    const result = await inspireScan([deckPath], outDir, "team");

    const profileText = readFileSync(result.profile_json as string, "utf-8");
    expect(profileText).not.toContain("Shipped the resolver");
    expect(profileText).not.toContain("Q3 Results");
  });
});

describe("validateDocxTool / renderDocxTool", () => {
  const docxSpec = {
    title: "Q3 Report",
    sections: [
      {
        body: [
          { primitive: "heading", text: "Overview", level: 1 },
          { primitive: "paragraph", runs: [{ text: "Shipped the resolver." }] },
        ],
      },
    ],
  };

  it("validateDocxTool accepts a valid spec", () => {
    const result = validateDocxTool(docxSpec);
    expect(result.valid).toBe(true);
  });

  it("validateDocxTool returns structured errors for a malformed spec", () => {
    const result = validateDocxTool({ title: "Bad", sections: [{ body: [{ primitive: "heading" }] }] });
    expect(result.valid).toBe(false);
    const error = (result.errors as Record<string, unknown>[])[0];
    expect(Object.keys(error)).toEqual(
      expect.arrayContaining(["section", "primitive", "field", "error", "detail", "fix"]),
    );
  });

  it("renderDocxTool writes a real .docx", async () => {
    const output = tmpPath("report.docx");
    const result = await renderDocxTool(docxSpec, output);
    expect(result.docxPath).toBe(output);
    expect(readFileSync(output).length).toBeGreaterThan(0);
  });

  it("renderDocxTool returns structured errors instead of throwing", async () => {
    const output = tmpPath("report.docx");
    const result = await renderDocxTool({ title: "Bad", sections: [{ body: [{ primitive: "heading" }] }] }, output);
    expect(result.valid).toBe(false);
    expect(() => readFileSync(output)).toThrow();
  });
});
