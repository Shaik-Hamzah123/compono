import { describe, expect, it } from "vitest";
import {
  checkOverflow,
  loadFontMetrics,
  measureTextWidthPt,
  resolveSafeFont,
  wrapLines,
} from "../src/validator.js";

const STOCK_TEMPLATE_FONT_NAMES = ["Calibri", "Georgia", "Times New Roman", "Arial", "Open Sans"];

describe("resolveSafeFont", () => {
  it.each(STOCK_TEMPLATE_FONT_NAMES)(
    "resolves %s to a real, existing bundled file",
    (fontName) => {
      // Every stock template's fontFamily (templates/*.yaml) must resolve to
      // a real, bundled file — this is what backs overflow measurement for
      // that template. It is never the font actually written into a deck's
      // OOXML; only the template's own fontFamily string is.
      const path = resolveSafeFont(fontName);
      expect(path).not.toBeNull();
    },
  );

  it("returns null for a font not in the allowlist", () => {
    expect(resolveSafeFont("SomeRandomFont")).toBeNull();
  });
});

describe("validator (real font metrics via fontkit, bundled Open Sans)", () => {
  const path = resolveSafeFont("Open Sans");
  if (!path) throw new Error("bundled Open Sans font not found");
  const metrics = loadFontMetrics(path);

  it("measures nonzero width for real text", () => {
    expect(measureTextWidthPt("Hello, world!", metrics, 18)).toBeGreaterThan(0);
  });

  it("wraps long text into multiple lines at a narrow width", () => {
    const lines = wrapLines("one two three four five six seven eight nine ten", metrics, 18, 60);
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
