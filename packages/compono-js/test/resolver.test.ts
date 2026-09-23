import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { loadTemplateByName, loadTemplateFromYaml, resolveSlide } from "../src/resolver.js";
import type { PrimitiveSpecT, Table } from "../src/schema.js";

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

  it("splits diagram node rects evenly along vertical orientation", () => {
    const body: PrimitiveSpecT[] = [
      {
        primitive: "diagram",
        id: "d",
        notes: null,
        nodes: [{ id: null, label: "A", kind: null, fill: null }, { id: null, label: "B", kind: null, fill: null }],
        edges: null,
        orientation: "vertical",
        node_kind: "rounded_rect",
        node_fill: null,
      },
    ];
    const result = resolveSlide(template, null, body);
    const a = result.rects.get("d.nodes[0]")!;
    const b = result.rects.get("d.nodes[1]")!;
    expect(a.w).toBe(b.w);
    expect(a.h).toBe(b.h);
    expect(b.y).toBeGreaterThan(a.y);
    expect(result.parents.get("d.nodes[0]")).toBe("d");
    // Nodes render as real Shape instances by construction.
    expect(result.items.get("d.nodes[0]")).toMatchObject({ primitive: "shape", text: { content: "A" } });
  });

  it("splits diagram node rects evenly along horizontal orientation", () => {
    const body: PrimitiveSpecT[] = [
      {
        primitive: "diagram",
        id: "d",
        notes: null,
        nodes: [{ id: null, label: "A", kind: null, fill: null }, { id: null, label: "B", kind: null, fill: null }],
        edges: null,
        orientation: "horizontal",
        node_kind: "rounded_rect",
        node_fill: null,
      },
    ];
    const result = resolveSlide(template, null, body);
    const a = result.rects.get("d.nodes[0]")!;
    const b = result.rects.get("d.nodes[1]")!;
    expect(a.h).toBe(b.h);
    expect(b.x).toBeGreaterThan(a.x);
  });

  it("defaults to a linear-chain edge when edges is omitted", () => {
    const body: PrimitiveSpecT[] = [
      {
        primitive: "diagram",
        id: "d",
        notes: null,
        nodes: [
          { id: null, label: "A", kind: null, fill: null },
          { id: null, label: "B", kind: null, fill: null },
          { id: null, label: "C", kind: null, fill: null },
        ],
        edges: null,
        orientation: "vertical",
        node_kind: "rounded_rect",
        node_fill: null,
      },
    ];
    const result = resolveSlide(template, null, body);
    expect(result.connectors.has("d.edges[0]")).toBe(true);
    expect(result.connectors.has("d.edges[1]")).toBe(true);
  });

  it("resolves explicit edges by node id, including a skip-ahead edge that must route around a node between them", () => {
    const body: PrimitiveSpecT[] = [
      {
        primitive: "diagram",
        id: "d",
        notes: null,
        nodes: [
          { id: "start", label: "Start", kind: null, fill: null },
          { id: "middle", label: "Middle", kind: null, fill: null },
          { id: "end", label: "End", kind: null, fill: null },
        ],
        edges: [{ from: "start", to: "end" }],
        orientation: "vertical",
        node_kind: "rounded_rect",
        node_fill: null,
      },
    ];
    const result = resolveSlide(template, null, body);
    expect(result.connectors.has("d.edges[0]")).toBe(true);
    const points = result.connectors.get("d.edges[0]")!;
    // A direct path from Start to End would cross Middle; the router must
    // detour, meaning at least one waypoint is emitted.
    expect(points.waypoints.length).toBeGreaterThan(0);
  });

  it("throws when a diagram edge references an unknown node", () => {
    const diagram = {
      primitive: "diagram" as const,
      id: "d",
      notes: null,
      nodes: [{ id: null, label: "A", kind: null, fill: null }],
      edges: [{ from: "0", to: "does-not-exist" }],
      orientation: "vertical" as const,
      node_kind: "rounded_rect" as const,
      node_fill: null,
    };
    expect(() => resolveSlide(template, null, [diagram])).toThrow(/unknown node/);
  });

  it("loads colors/logo from a template yaml when present", () => {
    const dir = mkdtempSync(join(tmpdir(), "compono-js-tpl-"));
    const yamlPath = join(dir, "branded.yaml");
    writeFileSync(
      yamlPath,
      `
name: branded
page: {width_in: 13.333, height_in: 7.5}
margin_in: {top: 0.5, right: 0.6, bottom: 0.5, left: 0.6}
header: {height_in: 1.2}
footer: {height_in: 0.4}
gutter_in: 0.2
font_family: Calibri
colors:
  primary: "#1F4E79"
  accent: "#2E86AB"
logo: assets/acme-logo.png
`,
    );
    const branded = loadTemplateFromYaml(yamlPath);
    expect(branded.primaryColor).toBe("#1F4E79");
    expect(branded.accentColor).toBe("#2E86AB");
    expect(branded.logoPath).toBe(join(dir, "assets", "acme-logo.png"));
  });

  it("leaves colors/logo undefined when a template yaml omits them", () => {
    expect(template.primaryColor).toBeUndefined();
    expect(template.accentColor).toBeUndefined();
    expect(template.logoPath).toBeUndefined();
  });

  it("resolves a gantt to a real Table at its own id", () => {
    const gantt = {
      primitive: "gantt" as const,
      id: null,
      notes: null,
      unit_labels: ["Wk 1", "Wk 2", "Wk 3"],
      task_fill: "#2A6FDB",
      tasks: [{ label: "Discovery", start_unit: 0, duration_units: 2, fill: null }],
    };
    const result = resolveSlide(template, null, [gantt]);
    const synthesized = result.items.get("body[0]") as Table;
    expect(synthesized.primitive).toBe("table");
    expect(synthesized.headers).toEqual(["Task", "Wk 1", "Wk 2", "Wk 3"]);
    expect(synthesized.rows).toEqual([["Discovery", "", "", ""]]);
    expect(result.items.has("body[0].tasks[0]")).toBe(false);
  });

  it("gantt cell_fills cover exactly each task's span, with per-task overrides winning", () => {
    const gantt = {
      primitive: "gantt" as const,
      id: null,
      notes: null,
      unit_labels: ["Wk 1", "Wk 2", "Wk 3", "Wk 4"],
      task_fill: "#2A6FDB",
      tasks: [
        { label: "Discovery", start_unit: 0, duration_units: 2, fill: null },
        { label: "Design", start_unit: 2, duration_units: 1, fill: "#D9534F" },
      ],
    };
    const result = resolveSlide(template, null, [gantt]);
    const synthesized = result.items.get("body[0]") as Table;
    const fills = new Map((synthesized.cell_fills ?? []).map((cf) => [`${cf.row},${cf.col}`, cf.fill]));
    expect(fills.get("0,1")).toBe("#2A6FDB");
    expect(fills.get("0,2")).toBe("#2A6FDB");
    expect(fills.has("0,3")).toBe(false);
    expect(fills.get("1,3")).toBe("#D9534F");
    expect(fills.has("1,1")).toBe(false);
  });
});
