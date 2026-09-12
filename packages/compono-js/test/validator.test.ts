import { existsSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { checkOverflow, loadFontMetrics, measureTextWidthPt, wrapLines } from "../src/validator.js";

const ARIAL = "C:/Windows/Fonts/arial.ttf";
const hasArial = existsSync(ARIAL);
const maybe = hasArial ? describe : describe.skip;

maybe("validator (real font metrics via fontkit)", () => {
  const metrics = loadFontMetrics(ARIAL);

  it("measures nonzero width for real text", () => {
    expect(measureTextWidthPt("Hello, world!", metrics, 18)).toBeGreaterThan(0);
  });

  it("wraps long text into multiple lines at a narrow width", () => {
    const lines = wrapLines(
      "one two three four five six seven eight nine ten",
      metrics,
      18,
      60,
    );
    expect(lines.length).toBeGreaterThan(1);
  });

  it("fits short text without overflow in a tall box", () => {
    const report = checkOverflow("Short", metrics, 18, 400, 400);
    expect(report.overflow).toBe(false);
  });

  it("flags overflow for long text in a short box", () => {
    const report = checkOverflow(
      "This is a very long sentence that should overflow a tiny box.",
      metrics,
      18,
      60,
      10,
    );
    expect(report.overflow).toBe(true);
  });
});
