import { execFileSync } from "node:child_process";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const CLI = join(import.meta.dirname, "..", "dist", "cli.js");

function tmpPath(name: string): string {
  return join(mkdtempSync(join(tmpdir(), "compono-js-cli-")), name);
}

const MINIMAL_SPEC = {
  slides: [{ header: { title: "Hi" }, body: [{ primitive: "text", content: "Hello" }] }],
};

describe("cli", () => {
  it("validate exits 0 and prints a valid report for a good spec", () => {
    const specPath = tmpPath("spec.json");
    writeFileSync(specPath, JSON.stringify(MINIMAL_SPEC));

    const out = execFileSync("node", [CLI, "validate", specPath], { encoding: "utf-8" });
    const report = JSON.parse(out);
    expect(report.valid).toBe(true);
  });

  it("render writes a real .pptx and prints its path", () => {
    const specPath = tmpPath("spec.json");
    writeFileSync(specPath, JSON.stringify(MINIMAL_SPEC));
    const outputPath = tmpPath("deck.pptx");

    const out = execFileSync("node", [CLI, "render", specPath, "-o", outputPath], {
      encoding: "utf-8",
    });
    const report = JSON.parse(out);
    expect(report.pptxPath).toBe(outputPath);
  });
});
