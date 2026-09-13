import { describe, expect, it } from "vitest";
import { Chart, Deck, Diagram, Grid, Image, Sequence, Table } from "../src/schema.js";

describe("schema", () => {
  it("accepts a minimal valid deck", () => {
    const deck = Deck.parse({
      slides: [{ header: { title: "Hi" }, body: [{ primitive: "text", content: "Hello" }] }],
    });
    expect(deck.template).toBe("default");
    expect(deck.slides[0].body[0]).toMatchObject({ primitive: "text", content: "Hello" });
  });

  it("rejects a table whose rows don't match the header length", () => {
    expect(() => Table.parse({ headers: ["A", "B"], rows: [["1", "2"], ["only-one"]] })).toThrow();
  });

  it("accepts a table with matching rows", () => {
    const table = Table.parse({ headers: ["A", "B"], rows: [["1", "2"]] });
    expect(table.rows).toEqual([["1", "2"]]);
  });

  it("rejects an empty headers list", () => {
    // Would divide by zero in render.ts's tableCellRects otherwise.
    expect(() => Table.parse({ headers: [], rows: [] })).toThrow();
  });

  it("rejects an empty rows list", () => {
    expect(() => Table.parse({ headers: ["A", "B"], rows: [] })).toThrow();
  });

  it("rejects an empty sequence steps list", () => {
    // Would divide by zero in render.ts's sequenceStepRects otherwise.
    expect(() => Sequence.parse({ steps: [] })).toThrow();
  });

  it("requires src or placeholder on image", () => {
    expect(() => Image.parse({})).toThrow();
    expect(Image.parse({ placeholder: true }).placeholder).toBe(true);
    expect(Image.parse({ src: "logo.png" }).src).toBe("logo.png");
  });

  it("rejects a chart series/category length mismatch", () => {
    expect(() =>
      Chart.parse({
        chart_type: "bar",
        categories: ["Q1", "Q2"],
        series: [{ name: "Revenue", values: [1] }],
      }),
    ).toThrow();
  });

  it("rejects a pie chart with more than one series", () => {
    expect(() =>
      Chart.parse({
        chart_type: "pie",
        categories: ["A", "B"],
        series: [
          { name: "s1", values: [1, 2] },
          { name: "s2", values: [3, 4] },
        ],
      }),
    ).toThrow();
  });

  it("recursively validates a grid containing nested primitives, including another grid", () => {
    const grid = Grid.parse({
      items: [
        { primitive: "stat", value: "1", label: "one" },
        { primitive: "grid", items: [{ primitive: "stat", value: "2", label: "two" }] },
      ],
    });
    expect(grid.items).toHaveLength(2);
    expect(grid.items[1]).toMatchObject({ primitive: "grid" });
  });

  it("rejects unknown extra fields (strict)", () => {
    expect(() => Deck.parse({ slides: [], unexpected: true })).toThrow();
  });

  it("accepts a diagram with nodes-only (default linear chain)", () => {
    const diagram = Diagram.parse({
      nodes: [{ label: "User" }, { label: "Router" }, { label: "LLM" }],
    });
    expect(diagram.edges).toBeNull();
    expect(diagram.nodes).toHaveLength(3);
  });

  it("accepts a diagram with explicit edges by id and positional index", () => {
    const diagram = Diagram.parse({
      nodes: [{ id: "a", label: "A" }, { label: "B" }, { id: "c", label: "C" }],
      edges: [
        { from: "a", to: "1" },
        { from: "1", to: "c" },
      ],
    });
    expect(diagram.edges).toHaveLength(2);
  });

  it("accepts per-node kind/fill overrides", () => {
    const diagram = Diagram.parse({
      nodes: [{ label: "A", kind: "oval", fill: "#FF0000" }, { label: "B" }],
      node_kind: "rect",
    });
    expect(diagram.nodes[0].kind).toBe("oval");
    expect(diagram.nodes[0].fill).toBe("#FF0000");
    expect(diagram.nodes[1].kind).toBeNull();
    expect(diagram.node_kind).toBe("rect");
  });

  it("rejects an edge referencing an unknown node", () => {
    expect(() =>
      Diagram.parse({
        nodes: [{ label: "A" }],
        edges: [{ from: "0", to: "does-not-exist" }],
      }),
    ).toThrow();
  });

  it("rejects an empty nodes list", () => {
    expect(() => Diagram.parse({ nodes: [] })).toThrow();
  });
});
