import { describe, expect, it } from "vitest";
import { loadTemplateByName, resolveSlide } from "../src/resolver.js";
import type { PrimitiveSpecT } from "../src/schema.js";

const template = loadTemplateByName("default");

describe("resolveSlide", () => {
  it("gives a header-only slide the full remaining content area", () => {
    const result = resolveSlide(template, { primitive: "header", id: null, notes: null, title: "Hi", subtitle: null, eyebrow: null, align: "left" }, []);
    const headerRect = result.rects.get("header")!;
    const footerTop = template.pageHeight - template.marginBottom - template.footerHeight;
    expect(headerRect.h).toBe(footerTop - template.marginTop);
  });

  it("splits body primitives into equal-height slots (flex-equal fallback)", () => {
    const body: PrimitiveSpecT[] = [
      { primitive: "text", id: "a", notes: null, mode: "paragraph", content: "A", columns: 1, emphasis_indices: null },
      { primitive: "text", id: "b", notes: null, mode: "paragraph", content: "B", columns: 1, emphasis_indices: null },
    ];
    const result = resolveSlide(template, null, body);
    const a = result.rects.get("a")!;
    const b = result.rects.get("b")!;
    expect(a.h).toBe(b.h);
    expect(b.y).toBeGreaterThan(a.y);
  });

  it("lays out a grid in row-major order with equal column/row sizing", () => {
    const body: PrimitiveSpecT[] = [
      {
        primitive: "grid",
        id: "g",
        notes: null,
        columns: 2,
        direction: "row",
        align: "stretch",
        justify: "start",
        items: [
          { primitive: "stat", id: "s1", notes: null, value: "1", label: "one", trend: null },
          { primitive: "stat", id: "s2", notes: null, value: "2", label: "two", trend: null },
          { primitive: "stat", id: "s3", notes: null, value: "3", label: "three", trend: null },
        ],
      },
    ];
    const result = resolveSlide(template, null, body);
    const s1 = result.rects.get("s1")!;
    const s2 = result.rects.get("s2")!;
    const s3 = result.rects.get("s3")!;
    expect(s1.y).toBe(s2.y); // same row
    expect(s2.x).toBeGreaterThan(s1.x);
    expect(s3.y).toBeGreaterThan(s1.y); // second row
    expect(result.parents.get("s1")).toBe("g");
  });

  it("routes a connector directly when nothing obstructs the path", () => {
    const body: PrimitiveSpecT[] = [
      { primitive: "stat", id: "left", notes: null, value: "1", label: "one", trend: null },
      { primitive: "stat", id: "right", notes: null, value: "2", label: "two", trend: null },
      {
        primitive: "shape",
        id: "conn",
        notes: null,
        kind: "connector",
        fill: null,
        fill_style: "solid",
        border: null,
        text: null,
        connects: { from_id: "left", to_id: "right" },
      },
    ];
    const result = resolveSlide(template, null, body);
    expect(result.connectors.has("conn")).toBe(true);
    const points = result.connectors.get("conn")!;
    expect(points.start).not.toEqual(points.end);
  });

  it("throws when a connector references an unknown id", () => {
    const body: PrimitiveSpecT[] = [
      {
        primitive: "shape",
        id: "conn",
        notes: null,
        kind: "connector",
        fill: null,
        fill_style: "solid",
        border: null,
        text: null,
        connects: { from_id: "missing", to_id: "also-missing" },
      },
    ];
    expect(() => resolveSlide(template, null, body)).toThrow(/unknown id/);
  });
});
