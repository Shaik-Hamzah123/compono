import { describe, expect, it } from "vitest";
import { Chart, Deck, Diagram, Gantt, Grid, Image, Sequence, Table } from "../src/schema.js";

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

  it("accepts valid table cell_fills", () => {
    const t = Table.parse({
      headers: ["Name", "Score"],
      rows: [["Alice", "90"], ["Bob", "85"]],
      cell_fills: [{ row: 0, col: 1, fill: "#2A6FDB" }],
    });
    expect(t.cell_fills?.[0]).toMatchObject({ row: 0, col: 1, fill: "#2A6FDB" });
  });

  it("rejects table cell_fills outside bounds", () => {
    expect(() =>
      Table.parse({
        headers: ["Name", "Score"],
        rows: [["Alice", "90"]],
        cell_fills: [{ row: 5, col: 0, fill: "#2A6FDB" }],
      }),
    ).toThrow();
  });

  it("accepts valid table merges", () => {
    const t = Table.parse({
      headers: ["Region", "Q1", "Q2"],
      rows: [["North", "10", "12"], ["North", "11", "13"]],
      merges: [{ row1: 0, col1: 0, row2: 1, col2: 0 }],
    });
    expect(t.merges?.[0].row2).toBe(1);
  });

  it("rejects table merges outside bounds", () => {
    expect(() =>
      Table.parse({
        headers: ["A", "B"],
        rows: [["1", "2"]],
        merges: [{ row1: 0, col1: 0, row2: 5, col2: 0 }],
      }),
    ).toThrow();
  });

  it("rejects an inverted table merge range", () => {
    expect(() =>
      Table.parse({
        headers: ["A", "B"],
        rows: [["1", "2"], ["3", "4"]],
        merges: [{ row1: 1, col1: 0, row2: 0, col2: 0 }],
      }),
    ).toThrow();
  });

  it("rejects overlapping table merges", () => {
    expect(() =>
      Table.parse({
        headers: ["A", "B"],
        rows: [["1", "2"], ["3", "4"], ["5", "6"]],
        merges: [
          { row1: 0, col1: 0, row2: 1, col2: 0 },
          { row1: 1, col1: 0, row2: 2, col2: 0 },
        ],
      }),
    ).toThrow();
  });

  it("accepts a minimal gantt", () => {
    const g = Gantt.parse({
      unit_labels: ["Wk 1", "Wk 2", "Wk 3"],
      tasks: [{ label: "Discovery", start_unit: 0, duration_units: 2 }],
    });
    expect(g.primitive).toBe("gantt");
    expect(g.task_fill).toBe("#2A6FDB");
    expect(g.tasks[0].fill).toBeNull();
  });

  it("accepts a per-task gantt fill override", () => {
    const g = Gantt.parse({
      unit_labels: ["Wk 1", "Wk 2"],
      tasks: [{ label: "A", start_unit: 0, duration_units: 1, fill: "#D9534F" }],
    });
    expect(g.tasks[0].fill).toBe("#D9534F");
  });

  it("rejects a gantt task extending past unit_labels", () => {
    expect(() =>
      Gantt.parse({
        unit_labels: ["Wk 1", "Wk 2"],
        tasks: [{ label: "Too long", start_unit: 1, duration_units: 2 }],
      }),
    ).toThrow();
  });

  it("rejects an empty gantt tasks list", () => {
    expect(() => Gantt.parse({ unit_labels: ["Wk 1"], tasks: [] })).toThrow();
  });

  it("rejects an empty gantt unit_labels list", () => {
    expect(() =>
      Gantt.parse({ unit_labels: [], tasks: [{ label: "A", start_unit: 0, duration_units: 1 }] }),
    ).toThrow();
  });
});
