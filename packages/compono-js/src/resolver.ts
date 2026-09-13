/**
 * The layout engine — TypeScript port of src/compono/resolver.py.
 *
 * Pure function — no file I/O beyond loadTemplate itself, no pptxgenjs
 * calls. Same directional box model as the Python resolver: header region
 * top, footer pinned bottom, body fills the remainder; body primitives
 * currently share height equally (a flex-equal fallback — real
 * content-based sizing is a known future improvement, matching the Python
 * side's "Known limitations"). `grid` is the one primitive doing true 2D
 * row/column math. Shape connectors resolve in a second pass, once every
 * other rect is final, by looking up the referenced `id`s. `diagram` nodes
 * are synthesized as real `Shape` primitives at layout time
 * (`layoutDiagram`) and its edges resolve in that same second pass
 * (`resolveDiagramConnectors`) via the connector router — this is why no
 * render.ts changes were needed to support it.
 */

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { parse as parseYaml } from "yaml";
import type { Diagram, DiagramEdge, Grid, Header, PrimitiveSpecT, Shape } from "./schema.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
export const DEFAULT_TEMPLATE_DIR = join(__dirname, "..", "templates");

export const EMU_PER_INCH = 914400;
export function inToEmu(value: number): number {
  return Math.round(value * EMU_PER_INCH);
}

export interface Template {
  pageWidth: number;
  pageHeight: number;
  marginTop: number;
  marginRight: number;
  marginBottom: number;
  marginLeft: number;
  headerHeight: number;
  footerHeight: number;
  gutter: number;
  fontFamily: string;
}

interface TemplateYaml {
  name?: string;
  page: { width_in: number; height_in: number };
  margin_in: { top: number; right: number; bottom: number; left: number };
  header: { height_in: number };
  footer: { height_in: number };
  gutter_in: number;
  font_family?: string;
}

export function loadTemplateFromYaml(path: string): Template {
  const data = parseYaml(readFileSync(path, "utf-8")) as TemplateYaml;
  return {
    pageWidth: inToEmu(data.page.width_in),
    pageHeight: inToEmu(data.page.height_in),
    marginTop: inToEmu(data.margin_in.top),
    marginRight: inToEmu(data.margin_in.right),
    marginBottom: inToEmu(data.margin_in.bottom),
    marginLeft: inToEmu(data.margin_in.left),
    headerHeight: inToEmu(data.header.height_in),
    footerHeight: inToEmu(data.footer.height_in),
    gutter: inToEmu(data.gutter_in),
    fontFamily: data.font_family ?? "Calibri",
  };
}

export function loadTemplateByName(name = "default", templateDir = DEFAULT_TEMPLATE_DIR): Template {
  const path = join(templateDir, `${name}.yaml`);
  try {
    return loadTemplateFromYaml(path);
  } catch {
    throw new Error(`Unknown template ${JSON.stringify(name)} (looked for ${path}).`);
  }
}

export interface Rect {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface ConnectorPoints {
  start: [number, number];
  end: [number, number];
  waypoints: [number, number][];
}

export interface LayoutResult {
  pageWidth: number;
  pageHeight: number;
  rects: Map<string, Rect>;
  connectors: Map<string, ConnectorPoints>;
  items: Map<string, PrimitiveSpecT | Header>;
  parents: Map<string, string>;
}

function newResult(template: Template): LayoutResult {
  return {
    pageWidth: template.pageWidth,
    pageHeight: template.pageHeight,
    rects: new Map(),
    connectors: new Map(),
    items: new Map(),
    parents: new Map(),
  };
}

function isConnectorShape(item: PrimitiveSpecT): boolean {
  return item.primitive === "shape" && (item as Shape).kind === "connector";
}

function isGrid(item: PrimitiveSpecT): item is Grid {
  return item.primitive === "grid";
}

function isDiagram(item: PrimitiveSpecT): item is Diagram {
  return item.primitive === "diagram";
}

export function resolveSlide(
  template: Template,
  header: Header | null = null,
  body: PrimitiveSpecT[] = [],
): LayoutResult {
  const result = newResult(template);
  const contentX = template.marginLeft;
  const contentW = template.pageWidth - template.marginLeft - template.marginRight;
  let cursorY = template.marginTop;
  const footerTop = template.pageHeight - template.marginBottom - template.footerHeight;

  if (header) {
    const headerId = header.id ?? "header";
    const headerHeight = body.length === 0 ? footerTop - cursorY : template.headerHeight;
    result.rects.set(headerId, { x: contentX, y: cursorY, w: contentW, h: headerHeight });
    result.items.set(headerId, header);
    cursorY += headerHeight;
  }

  const bodyHeight = footerTop - cursorY;
  if (bodyHeight < 0) {
    throw new Error("No room left for body content — header/footer leave a negative body height.");
  }

  layoutStack(body, { x: contentX, y: cursorY, w: contentW, h: bodyHeight }, template, result, "body");
  resolveConnectors(body, result, template);
  resolveDiagramConnectors(result, template);

  return result;
}

function layoutStack(
  items: PrimitiveSpecT[],
  rect: Rect,
  template: Template,
  result: LayoutResult,
  prefix: string,
): void {
  const realItems = items.filter((item) => !isConnectorShape(item));
  const n = realItems.length;
  if (n === 0) return;

  const slotH = n > 1 ? Math.trunc((rect.h - template.gutter * (n - 1)) / n) : rect.h;
  let y = rect.y;
  realItems.forEach((item, i) => {
    const itemId = item.id ?? `${prefix}[${i}]`;
    placeItem(item, { x: rect.x, y, w: rect.w, h: slotH }, template, result, itemId);
    y += slotH + template.gutter;
  });
}

function placeItem(
  item: PrimitiveSpecT,
  rect: Rect,
  template: Template,
  result: LayoutResult,
  itemId: string,
): void {
  result.rects.set(itemId, rect);
  result.items.set(itemId, item);
  if (isGrid(item)) {
    layoutGrid(item, rect, template, result, itemId);
  } else if (isDiagram(item)) {
    layoutDiagram(item, rect, template, result, itemId);
  }
}

function resolveGridColumns(grid: Grid, n: number): number {
  if (grid.columns !== "auto") return grid.columns;
  if (grid.direction === "column") return 1;
  return Math.max(1, n);
}

function layoutGrid(
  grid: Grid,
  rect: Rect,
  template: Template,
  result: LayoutResult,
  prefix: string,
): void {
  const realItems = grid.items.filter((item) => !isConnectorShape(item));
  const n = realItems.length;
  if (n === 0) return;

  const columns = Math.max(1, Math.min(resolveGridColumns(grid, n), n));
  const rows = Math.ceil(n / columns);
  const colW = Math.trunc((rect.w - template.gutter * (columns - 1)) / columns);
  const rowH = Math.trunc((rect.h - template.gutter * (rows - 1)) / rows);

  realItems.forEach((item, i) => {
    const r = Math.floor(i / columns);
    const c = i % columns;
    const x = rect.x + c * (colW + template.gutter);
    const y = rect.y + r * (rowH + template.gutter);
    const itemId = item.id ?? `${prefix}.items[${i}]`;
    result.parents.set(itemId, prefix);
    placeItem(item, { x, y, w: colW, h: rowH }, template, result, itemId);
  });
}

// --- Diagram layout (nodes synthesized as real Shape primitives) ---

function diagramNodeId(diagram: Diagram, prefix: string, index: number): string {
  return diagram.nodes[index].id ?? `${prefix}.nodes[${index}]`;
}

function resolveDiagramNodeRef(diagram: Diagram, prefix: string, ref: string): string {
  const explicitIndex = diagram.nodes.findIndex((node) => node.id === ref);
  if (explicitIndex !== -1) return diagramNodeId(diagram, prefix, explicitIndex);
  if (/^\d+$/.test(ref)) {
    const index = Number(ref);
    if (index < diagram.nodes.length) return diagramNodeId(diagram, prefix, index);
  }
  throw new Error(`Diagram edge references unknown node ${JSON.stringify(ref)}.`);
}

function layoutDiagram(
  diagram: Diagram,
  rect: Rect,
  template: Template,
  result: LayoutResult,
  prefix: string,
): void {
  const n = diagram.nodes.length;
  if (n === 0) return;

  const vertical = diagram.orientation === "vertical";
  const slotH = vertical ? (n > 1 ? Math.trunc((rect.h - template.gutter * (n - 1)) / n) : rect.h) : rect.h;
  const slotW = vertical ? rect.w : n > 1 ? Math.trunc((rect.w - template.gutter * (n - 1)) / n) : rect.w;

  diagram.nodes.forEach((node, i) => {
    const nodeId = diagramNodeId(diagram, prefix, i);
    const nodeRect: Rect = vertical
      ? { x: rect.x, y: rect.y + i * (slotH + template.gutter), w: rect.w, h: slotH }
      : { x: rect.x + i * (slotW + template.gutter), y: rect.y, w: slotW, h: rect.h };

    result.parents.set(nodeId, prefix);
    const nodeShape: Shape = {
      primitive: "shape",
      id: nodeId,
      notes: null,
      kind: node.kind ?? diagram.node_kind,
      fill: node.fill ?? diagram.node_fill,
      fill_style: "solid",
      border: null,
      connects: null,
      text: {
        content: node.label,
        align: "center",
        valign: "middle",
        autofit: true,
        color: null,
      },
    };
    placeItem(nodeShape, nodeRect, template, result, nodeId);
  });
}

function defaultDiagramEdges(diagram: Diagram): DiagramEdge[] {
  const edges: DiagramEdge[] = [];
  for (let i = 0; i < diagram.nodes.length - 1; i++) {
    edges.push({ from: String(i), to: String(i + 1) });
  }
  return edges;
}

function iterShapes(items: PrimitiveSpecT[]): Shape[] {
  const shapes: Shape[] = [];
  for (const item of items) {
    if (item.primitive === "shape") {
      shapes.push(item as Shape);
    } else if (isGrid(item)) {
      shapes.push(...iterShapes(item.items));
    }
  }
  return shapes;
}

// --- Connector routing (two-pass system) ---

const CONNECTOR_GAP_EMU = 50800; // 4pt visual standoff

function rectCenter(rect: Rect): [number, number] {
  return [rect.x + rect.w / 2, rect.y + rect.h / 2];
}

function rectBoundaryPoint(rect: Rect, toward: [number, number], gap = CONNECTOR_GAP_EMU): [number, number] {
  const [cx, cy] = rectCenter(rect);
  const dx = toward[0] - cx;
  const dy = toward[1] - cy;
  if (dx === 0 && dy === 0) {
    return [Math.round(cx), Math.round(cy)];
  }
  const halfW = rect.w / 2;
  const halfH = rect.h / 2;
  const scale = Math.min(dx !== 0 ? halfW / Math.abs(dx) : Infinity, dy !== 0 ? halfH / Math.abs(dy) : Infinity);
  const exitX = cx + dx * scale;
  const exitY = cy + dy * scale;
  const len = Math.hypot(dx, dy);
  const ux = dx / len;
  const uy = dy / len;
  return [Math.round(exitX + ux * gap), Math.round(exitY + uy * gap)];
}

function rectBounds(rect: Rect): [number, number, number, number] {
  return [rect.x, rect.y, rect.x + rect.w, rect.y + rect.h];
}

/** Liang-Barsky line clipping — true only for a genuine interior crossing. */
function segmentCrossesRect(p1: [number, number], p2: [number, number], rect: Rect): boolean {
  const [x0, y0, x1, y1] = rectBounds(rect);
  const dx = p2[0] - p1[0];
  const dy = p2[1] - p1[1];
  let u1 = 0;
  let u2 = 1;

  const clip = (p: number, q: number): boolean => {
    if (p === 0) {
      if (q < 0) return false;
      return true;
    }
    const r = q / p;
    if (p < 0) {
      if (r > u2) return false;
      if (r > u1) u1 = r;
    } else {
      if (r < u1) return false;
      if (r < u2) u2 = r;
    }
    return true;
  };

  if (!clip(-dx, p1[0] - x0)) return false;
  if (!clip(dx, x1 - p1[0])) return false;
  if (!clip(-dy, p1[1] - y0)) return false;
  if (!clip(dy, y1 - p1[1])) return false;

  return u1 < u2;
}

function pathCrossesAny(points: [number, number][], obstacles: Rect[]): boolean {
  for (let i = 0; i < points.length - 1; i++) {
    for (const obstacle of obstacles) {
      if (segmentCrossesRect(points[i], points[i + 1], obstacle)) return true;
    }
  }
  return false;
}

function routeConnector(
  fromRect: Rect,
  toRect: Rect,
  obstacles: Rect[],
  pageWidth: number,
  pageHeight: number,
  gutter: number,
): [number, number][] {
  const fromCenter = rectCenter(fromRect);
  const toCenter = rectCenter(toRect);

  const directStart = rectBoundaryPoint(fromRect, toCenter);
  const directEnd = rectBoundaryPoint(toRect, fromCenter);
  const direct: [number, number][] = [directStart, directEnd];
  if (!pathCrossesAny(direct, obstacles)) return direct;

  const margin = Math.max(1, Math.trunc(gutter / 2));
  const [, fromY0, , fromY1] = rectBounds(fromRect);
  const [, toY0, , toY1] = rectBounds(toRect);

  const verticalCandidates: number[] = [];
  if (fromY1 <= toY0) verticalCandidates.push(Math.trunc((fromY1 + toY0) / 2));
  else if (toY1 <= fromY0) verticalCandidates.push(Math.trunc((toY1 + fromY0) / 2));
  verticalCandidates.push(Math.min(fromY0, toY0) - margin, Math.max(fromY1, toY1) + margin);

  for (const gutterY of verticalCandidates) {
    const fromX = fromRect.x + fromRect.w / 2;
    const toX = toRect.x + toRect.w / 2;
    const fromEdgeY = gutterY < fromY0 ? fromY0 - CONNECTOR_GAP_EMU : fromY1 + CONNECTOR_GAP_EMU;
    const toEdgeY = gutterY < toY0 ? toY0 - CONNECTOR_GAP_EMU : toY1 + CONNECTOR_GAP_EMU;
    const path: [number, number][] = [
      [Math.round(fromX), Math.round(fromEdgeY)],
      [Math.round(fromX), Math.round(gutterY)],
      [Math.round(toX), Math.round(gutterY)],
      [Math.round(toX), Math.round(toEdgeY)],
    ];
    if (!pathCrossesAny(path, obstacles)) return path;
  }

  const [fromX0, , fromX1] = rectBounds(fromRect);
  const [toX0, , toX1] = rectBounds(toRect);
  const horizontalCandidates: number[] = [];
  if (fromX1 <= toX0) horizontalCandidates.push(Math.trunc((fromX1 + toX0) / 2));
  else if (toX1 <= fromX0) horizontalCandidates.push(Math.trunc((toX1 + fromX0) / 2));
  horizontalCandidates.push(Math.min(fromX0, toX0) - margin, Math.max(fromX1, toX1) + margin);

  for (const gutterX of horizontalCandidates) {
    const fromY = fromRect.y + fromRect.h / 2;
    const toY = toRect.y + toRect.h / 2;
    const fromEdgeX = gutterX < fromX0 ? fromX0 - CONNECTOR_GAP_EMU : fromX1 + CONNECTOR_GAP_EMU;
    const toEdgeX = gutterX < toX0 ? toX0 - CONNECTOR_GAP_EMU : toX1 + CONNECTOR_GAP_EMU;
    const path: [number, number][] = [
      [Math.round(fromEdgeX), Math.round(fromY)],
      [Math.round(gutterX), Math.round(fromY)],
      [Math.round(gutterX), Math.round(toY)],
      [Math.round(toEdgeX), Math.round(toY)],
    ];
    if (!pathCrossesAny(path, obstacles)) return path;
  }

  void pageWidth;
  void pageHeight;
  return direct;
}

function resolveConnectors(body: PrimitiveSpecT[], result: LayoutResult, template: Template): void {
  const obstaclesById = new Map<string, Rect>();
  for (const [id, rect] of result.rects) {
    const item = result.items.get(id);
    if (item && item.primitive !== "grid") obstaclesById.set(id, rect);
  }

  for (const shape of iterShapes(body)) {
    if (shape.kind !== "connector" || !shape.connects) continue;
    const { from_id: fromId, to_id: toId } = shape.connects;
    const fromRect = result.rects.get(fromId);
    const toRect = result.rects.get(toId);
    if (!fromRect) throw new Error(`Connector references unknown id ${JSON.stringify(fromId)}.`);
    if (!toRect) throw new Error(`Connector references unknown id ${JSON.stringify(toId)}.`);

    const obstacles = [...obstaclesById.entries()]
      .filter(([id]) => id !== fromId && id !== toId)
      .map(([, rect]) => rect);

    const path = routeConnector(
      fromRect,
      toRect,
      obstacles,
      result.pageWidth,
      result.pageHeight,
      template.gutter,
    );
    const connectorId = shape.id ?? `connector[${fromId}->${toId}]`;
    result.connectors.set(connectorId, {
      start: path[0],
      end: path[path.length - 1],
      waypoints: path.slice(1, -1),
    });
  }
}

/** Second pass, run after resolveConnectors: walks the resolver's own
 * `result.items` (populated post-layoutDiagram, so every node's resolved id
 * is already known) for `Diagram` instances, derives each edge (explicit or
 * the default linear chain), and routes it via the same obstacle-avoiding
 * `routeConnector` every `shape(kind="connector")` uses — so a diagram's
 * edges correctly avoid every other resolved rect on the slide, not just
 * what existed when the diagram itself was laid out.
 */
function resolveDiagramConnectors(result: LayoutResult, template: Template): void {
  const obstaclesById = new Map<string, Rect>();
  for (const [id, rect] of result.rects) {
    const item = result.items.get(id);
    if (item && item.primitive !== "grid") obstaclesById.set(id, rect);
  }

  for (const [prefix, item] of result.items) {
    if (!isDiagram(item)) continue;
    const edges = item.edges ?? defaultDiagramEdges(item);
    edges.forEach((edge, i) => {
      const fromId = resolveDiagramNodeRef(item, prefix, edge.from);
      const toId = resolveDiagramNodeRef(item, prefix, edge.to);
      const fromRect = result.rects.get(fromId);
      const toRect = result.rects.get(toId);
      if (!fromRect || !toRect) return;

      const obstacles = [...obstaclesById.entries()]
        .filter(([id]) => id !== fromId && id !== toId)
        .map(([, r]) => r);

      const path = routeConnector(fromRect, toRect, obstacles, result.pageWidth, result.pageHeight, template.gutter);
      const edgeId = `${prefix}.edges[${i}]`;
      result.connectors.set(edgeId, {
        start: path[0],
        end: path[path.length - 1],
        waypoints: path.slice(1, -1),
      });
    });
  }
}
