/**
 * Inspire: scan liked decks into a structural/style profile — TypeScript
 * port of src/compono/inspire.py.
 *
 * There is no npm equivalent to python-pptx's read-side object model, so
 * this reads the OOXML directly: a .pptx is a zip (via `jszip`) of XML
 * parts (parsed via `fast-xml-parser`). `ppt/presentation.xml` gives slide
 * dimensions; each `ppt/slides/slideN.xml` gives shape position/size
 * (`a:off`/`a:ext`), fill color (`a:solidFill>a:srgbClr`), and run font
 * family/size (`a:rPr`/`a:latin`) — the XML-level equivalents of the
 * python-pptx attributes scan_deck reads.
 *
 * Hard invariant, unchanged from Python: never read or return literal run
 * text (`a:t`), table cell text, or image bytes — only measurable
 * structure. This is what makes scanning someone's own old decks safe by
 * default.
 */

import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { XMLParser } from "fast-xml-parser";
import JSZip from "jszip";

const EMU_PER_IN = 914400;
const MIN_GRID_CONFIDENCE = 0.6;
const MIN_GRID_MEMBERS = 3;

const parser = new XMLParser({ ignoreAttributes: false, attributeNamePrefix: "@_" });

function toIn(emu: number | undefined | null): number {
  return Math.round(((emu ?? 0) / EMU_PER_IN) * 1000) / 1000;
}

/** fast-xml-parser collapses a single child into an object, not a
 * one-element array — normalize every access through this helper so the
 * extraction code never has to special-case "was there only one". */
function asArray<T>(value: T | T[] | undefined): T[] {
  if (value === undefined) return [];
  return Array.isArray(value) ? value : [value];
}

type Rect = [left: number, top: number, width: number, height: number];

interface GridDetected {
  slide: number;
  columns: number;
  avg_gap_in: number;
  confidence: number;
}

export interface DeckProfile {
  slide_size_in: [number, number];
  n_slides: number;
  palette_top: { hex: string; count: number }[];
  fonts_top: { family: string; size_pt: number | "?"; count: number }[];
  shape_mix: Record<string, number>;
  avg_margin_in: number | null;
  avg_gap_in: number | null;
  grids_detected: GridDetected[];
}

export interface AggregatedProfile {
  n_example_decks: number;
  recurring_palette: string[];
  one_off_palette: string[];
  recurring_fonts: { family: string; size_pt: number | "?" }[];
  avg_margin_in: number | null;
  avg_gap_in: number | null;
  grid_column_counts_seen: Record<number, number>;
  avg_grids_per_deck: number;
  style_note: string;
  warnings: string[];
}

function gridConfidence(members: Rect[]): number {
  const widths = members.map((m) => m[2]);
  const maxW = Math.max(...widths);
  if (maxW <= 0) return 0.0;
  const widthSpread = (Math.max(...widths) - Math.min(...widths)) / maxW;
  const widthScore = Math.max(0.0, 1.0 - widthSpread / 0.3);

  const sorted = [...members].sort((a, b) => a[0] - b[0]);
  const gaps: number[] = [];
  for (let i = 0; i < sorted.length - 1; i++) {
    gaps.push(sorted[i + 1][0] - (sorted[i][0] + sorted[i][2]));
  }

  let gapScore: number;
  if (gaps.length === 0) {
    gapScore = 1.0;
  } else {
    const avgGap = gaps.reduce((a, b) => a + b, 0) / gaps.length;
    if (avgGap <= 0) {
      gapScore = 0.5;
    } else {
      const gapSpread = (Math.max(...gaps) - Math.min(...gaps)) / Math.max(Math.abs(avgGap), 1e-6);
      gapScore = Math.max(0.0, 1.0 - gapSpread / 0.5);
    }
  }

  return Math.round(Math.min(widthScore, gapScore) * 100) / 100;
}

interface ShapeFacts {
  shapeType: string;
  rect: Rect | null;
  fillHex: string | null;
  runs: { family: string; sizePt: number | "?" }[];
}

function extractXfrm(spPr: unknown): Rect | null {
  const xfrm = (spPr as Record<string, unknown> | undefined)?.["a:xfrm"] as Record<string, unknown> | undefined;
  if (!xfrm) return null;
  const off = xfrm["a:off"] as Record<string, unknown> | undefined;
  const ext = xfrm["a:ext"] as Record<string, unknown> | undefined;
  if (!off || !ext) return null;
  const left = toIn(Number(off["@_x"]));
  const top = toIn(Number(off["@_y"]));
  const w = toIn(Number(ext["@_cx"]));
  const h = toIn(Number(ext["@_cy"]));
  return [left, top, w, h];
}

function extractFill(spPr: unknown): string | null {
  const solidFill = (spPr as Record<string, unknown> | undefined)?.["a:solidFill"] as
    | Record<string, unknown>
    | undefined;
  if (!solidFill) return null;
  const srgbClr = solidFill["a:srgbClr"] as Record<string, unknown> | undefined;
  const val = srgbClr?.["@_val"];
  return typeof val === "string" ? val.toUpperCase() : null;
}

function extractRuns(txBody: unknown): { family: string; sizePt: number | "?" }[] {
  const body = txBody as Record<string, unknown> | undefined;
  if (!body) return [];
  const runs: { family: string; sizePt: number | "?" }[] = [];
  for (const p of asArray(body["a:p"] as unknown)) {
    for (const r of asArray((p as Record<string, unknown>)["a:r"] as unknown)) {
      const rPr = (r as Record<string, unknown>)["a:rPr"] as Record<string, unknown> | undefined;
      const sz = rPr?.["@_sz"];
      const sizePt: number | "?" = sz !== undefined ? Number(sz) / 100 : "?";
      const latin = rPr?.["a:latin"] as Record<string, unknown> | undefined;
      const family = typeof latin?.["@_typeface"] === "string" ? (latin["@_typeface"] as string) : "?";
      runs.push({ family, sizePt });
    }
  }
  return runs;
}

function walkShapes(spTree: Record<string, unknown>): ShapeFacts[] {
  const shapes: ShapeFacts[] = [];

  for (const sp of asArray(spTree["p:sp"] as unknown)) {
    const spPr = (sp as Record<string, unknown>)["p:spPr"];
    shapes.push({
      shapeType: "AUTO_SHAPE",
      rect: extractXfrm(spPr),
      fillHex: extractFill(spPr),
      runs: extractRuns((sp as Record<string, unknown>)["p:txBody"]),
    });
  }
  for (const pic of asArray(spTree["p:pic"] as unknown)) {
    const spPr = (pic as Record<string, unknown>)["p:spPr"];
    shapes.push({ shapeType: "PICTURE", rect: extractXfrm(spPr), fillHex: null, runs: [] });
  }
  for (const gf of asArray(spTree["p:graphicFrame"] as unknown)) {
    const xfrm = (gf as Record<string, unknown>)["p:xfrm"] as Record<string, unknown> | undefined;
    let rect: Rect | null = null;
    if (xfrm) {
      const off = xfrm["a:off"] as Record<string, unknown> | undefined;
      const ext = xfrm["a:ext"] as Record<string, unknown> | undefined;
      if (off && ext) {
        rect = [toIn(Number(off["@_x"])), toIn(Number(off["@_y"])), toIn(Number(ext["@_cx"])), toIn(Number(ext["@_cy"]))];
      }
    }
    shapes.push({ shapeType: "GRAPHIC_FRAME", rect, fillHex: null, runs: [] });
  }

  return shapes;
}

export async function scanDeck(path: string): Promise<DeckProfile> {
  const zip = await JSZip.loadAsync(readFileSync(path));

  const presentationXml = await zip.files["ppt/presentation.xml"].async("string");
  const presentation = parser.parse(presentationXml)["p:presentation"];
  const sldSz = presentation["p:sldSz"];
  const slideWIn = toIn(Number(sldSz["@_cx"]));
  const slideHIn = toIn(Number(sldSz["@_cy"]));

  const slideFiles = Object.keys(zip.files)
    .filter((name) => /^ppt\/slides\/slide\d+\.xml$/.test(name))
    .sort((a, b) => {
      const na = Number(a.match(/slide(\d+)\.xml$/)![1]);
      const nb = Number(b.match(/slide(\d+)\.xml$/)![1]);
      return na - nb;
    });

  const palette = new Map<string, number>();
  const fonts = new Map<string, { family: string; sizePt: number | "?"; count: number }>();
  const shapeMix = new Map<string, number>();
  const allGaps: number[] = [];
  const allMargins: number[] = [];
  const gridsDetected: GridDetected[] = [];

  for (let slideI = 0; slideI < slideFiles.length; slideI++) {
    const xml = await zip.files[slideFiles[slideI]].async("string");
    const parsed = parser.parse(xml)["p:sld"];
    const spTree = parsed["p:cSld"]["p:spTree"];
    const shapes = walkShapes(spTree);

    const rects: Rect[] = [];
    for (const shape of shapes) {
      shapeMix.set(shape.shapeType, (shapeMix.get(shape.shapeType) ?? 0) + 1);
      if (shape.fillHex) palette.set(shape.fillHex, (palette.get(shape.fillHex) ?? 0) + 1);
      for (const run of shape.runs) {
        const key = `${run.family} ${run.sizePt}`;
        const existing = fonts.get(key);
        fonts.set(key, { family: run.family, sizePt: run.sizePt, count: (existing?.count ?? 0) + 1 });
      }
      if (shape.rect) {
        rects.push(shape.rect);
        const [left, top, w, h] = shape.rect;
        allMargins.push(Math.min(left, top, slideWIn - (left + w), slideHIn - (top + h)));
      }
    }

    const byRow = new Map<number, Rect[]>();
    for (const rect of rects) {
      const key = Math.round(rect[1] * 10) / 10;
      const list = byRow.get(key) ?? [];
      list.push(rect);
      byRow.set(key, list);
    }
    for (const members of byRow.values()) {
      if (members.length < MIN_GRID_MEMBERS) continue;
      const confidence = gridConfidence(members);
      if (confidence < MIN_GRID_CONFIDENCE) continue;
      const sorted = [...members].sort((a, b) => a[0] - b[0]);
      const gaps: number[] = [];
      for (let i = 0; i < sorted.length - 1; i++) {
        gaps.push(Math.round((sorted[i + 1][0] - (sorted[i][0] + sorted[i][2])) * 100) / 100);
      }
      gridsDetected.push({
        slide: slideI,
        columns: members.length,
        avg_gap_in: gaps.length ? Math.round((gaps.reduce((a, b) => a + b, 0) / gaps.length) * 100) / 100 : 0.0,
        confidence,
      });
      allGaps.push(...gaps);
    }
  }

  const paletteTop = [...palette.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6)
    .map(([hex, count]) => ({ hex, count }));
  const fontsTop = [...fonts.values()]
    .sort((a, b) => b.count - a.count)
    .slice(0, 6)
    .map(({ family, sizePt, count }) => ({ family, size_pt: sizePt, count }));

  return {
    slide_size_in: [slideWIn, slideHIn],
    n_slides: slideFiles.length,
    palette_top: paletteTop,
    fonts_top: fontsTop,
    shape_mix: Object.fromEntries(shapeMix),
    avg_margin_in: allMargins.length
      ? Math.round((allMargins.reduce((a, b) => a + b, 0) / allMargins.length) * 100) / 100
      : null,
    avg_gap_in: allGaps.length ? Math.round((allGaps.reduce((a, b) => a + b, 0) / allGaps.length) * 100) / 100 : null,
    grids_detected: gridsDetected,
  };
}

export async function aggregate(paths: string[], minRepeatRatio = 0.5): Promise<AggregatedProfile> {
  const profiles: DeckProfile[] = [];
  const skipped: string[] = [];
  for (const p of paths) {
    try {
      profiles.push(await scanDeck(p));
    } catch (err) {
      skipped.push(`Skipped ${p}: ${(err as Error).message}`);
    }
  }
  const n = profiles.length;
  if (n === 0) {
    throw new Error(
      "aggregate() found no scannable deck among the given paths." +
        (skipped.length ? ` (${skipped.join("; ")})` : ""),
    );
  }

  const paletteCounter = new Map<string, number>();
  const fontCounter = new Map<string, { family: string; sizePt: number | "?"; count: number }>();
  const gridColumnCounts = new Map<number, number>();
  const margins: number[] = [];
  const gaps: number[] = [];
  let totalGrids = 0;

  for (const profile of profiles) {
    for (const entry of profile.palette_top) {
      paletteCounter.set(entry.hex, (paletteCounter.get(entry.hex) ?? 0) + 1);
    }
    for (const entry of profile.fonts_top) {
      // "?" means no run set an explicit font override — common across
      // almost every deck regardless of what font it actually renders in,
      // so counting it would let "no override" crowd out a real, recurring
      // font choice in the vote below (a real bug in the original design,
      // already fixed in Python's aggregate() — ported fixed, not buggy).
      if (entry.family === "?") continue;
      const key = `${entry.family} ${entry.size_pt}`;
      const existing = fontCounter.get(key);
      fontCounter.set(key, { family: entry.family, sizePt: entry.size_pt, count: (existing?.count ?? 0) + 1 });
    }
    for (const g of profile.grids_detected) {
      gridColumnCounts.set(g.columns, (gridColumnCounts.get(g.columns) ?? 0) + 1);
    }
    totalGrids += profile.grids_detected.length;
    if (profile.avg_margin_in !== null) margins.push(profile.avg_margin_in);
    if (profile.avg_gap_in !== null) gaps.push(profile.avg_gap_in);
  }

  const isRecurring = (count: number) => count / n >= minRepeatRatio;

  const recurringColors = [...paletteCounter.entries()].filter(([, c]) => isRecurring(c)).map(([hex]) => hex);
  const oneOffColors = [...paletteCounter.entries()].filter(([, c]) => !isRecurring(c)).map(([hex]) => hex);
  const recurringFonts = [...fontCounter.values()]
    .filter((f) => isRecurring(f.count))
    .map((f) => ({ family: f.family, size_pt: f.sizePt }));

  const avgGridsPerDeck = Math.round((totalGrids / n) * 100) / 100;
  const avgMargin = margins.length ? Math.round((margins.reduce((a, b) => a + b, 0) / margins.length) * 100) / 100 : null;
  const avgGap = gaps.length ? Math.round((gaps.reduce((a, b) => a + b, 0) / gaps.length) * 100) / 100 : null;

  const gridColumnCountsObj = Object.fromEntries(gridColumnCounts);
  const styleNote =
    `Across ${n} example deck${n !== 1 ? "s" : ""}: ` +
    (recurringColors.length
      ? `recurring palette colors are [${recurringColors.map((c) => `'${c}'`).join(", ")}]; `
      : "no single color recurred across decks; ") +
    (totalGrids
      ? `grids appear on average ${avgGridsPerDeck.toFixed(1)} time(s) per deck ` +
        `(column counts seen: ${JSON.stringify(gridColumnCountsObj)}); `
      : "grids were rarely or never used; ") +
    (avgMargin !== null && avgGap !== null
      ? `typical margin ~${avgMargin}in, gap ~${avgGap}in.`
      : "not enough spacing data to draw a margin/gap conclusion.");

  return {
    n_example_decks: n,
    recurring_palette: recurringColors,
    one_off_palette: oneOffColors,
    recurring_fonts: recurringFonts,
    avg_margin_in: avgMargin,
    avg_gap_in: avgGap,
    grid_column_counts_seen: gridColumnCountsObj,
    avg_grids_per_deck: avgGridsPerDeck,
    style_note: styleNote,
    warnings: skipped,
  };
}

export interface SkillFiles {
  skillMd: string;
  profileJson: string;
}

function skillMdBody(profile: AggregatedProfile, name: string): string {
  const palette = profile.recurring_palette ?? [];
  const fonts = profile.recurring_fonts ?? [];
  const note = profile.style_note ?? "";

  const lines = [
    "---",
    `name: inspire-${name}`,
    `description: Style practices learned from ${profile.n_example_decks ?? "?"} example decks, for compono ` +
      "to adopt loosely (not literally) on new decks.",
    "---",
    "",
    `# inspire-${name}`,
    "",
    "Practices extracted from a set of example decks the user already likes. This is " +
      "guidance for `compono` deck generation, not a template to copy literally — apply " +
      "what fits the new deck's own content, ignore what doesn't. None of the original " +
      "decks' text or images are represented here; only measurable structure/style facts.",
    "",
    note,
    "",
  ];

  if (palette.length) {
    lines.push(
      "## Recurring palette",
      "",
      "Reuse these colors by default for `shape.fill`/`ShapeText.color` unless the requested deck specifies otherwise:",
      "",
      ...palette.map((c) => `- \`${c}\``),
      "",
    );
  }
  if (fonts.length) {
    lines.push(
      "## Recurring fonts",
      "",
      "Prefer a `Template`/`font_family` matching one of these when the deck has no other font requirement:",
      "",
      ...fonts.map((f) => `- ${f.family} (${f.size_pt}pt)`),
      "",
    );
  }
  if (Object.keys(profile.grid_column_counts_seen ?? {}).length) {
    lines.push(
      "## Layout habits",
      "",
      `Grid column counts seen across the example decks: ${JSON.stringify(profile.grid_column_counts_seen)}. ` +
        "Prefer `grid` over a long `text` bullet wall where the content naturally splits into cards.",
      "",
    );
  }
  lines.push(
    "## Full structural profile",
    "",
    "See `profile.json` in this folder for the complete structural facts (palette/font " +
      "frequency, spacing, per-slide grid detections with confidence scores) this summary was generated from.",
    "",
  );
  return lines.join("\n");
}

export function writeSkill(profile: AggregatedProfile, outDir: string, name: string): SkillFiles {
  mkdirSync(outDir, { recursive: true });
  const skillMd = join(outDir, "SKILL.md");
  const profileJson = join(outDir, "profile.json");
  writeFileSync(skillMd, skillMdBody(profile, name), "utf-8");
  writeFileSync(profileJson, JSON.stringify(profile, null, 2), "utf-8");
  return { skillMd, profileJson };
}
