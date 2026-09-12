/**
 * Overflow detection via real font metrics — TypeScript port of
 * src/compono/validator.py, backed by `fontkit` in place of `fontTools`.
 *
 * fontkit reads glyph advance widths directly from a font file (no
 * rendering), the same approach as the Python side's hmtx/cmap access.
 * SAFE_FONTS starts empty here too — no font ships with this package yet,
 * so overflow validation is skipped (never faked) with a warning if no
 * system font is found.
 */

import { existsSync } from "node:fs";
import { openSync as openFontSync } from "fontkit";

export interface FontMetrics {
  advanceWidths: Map<string, number>;
  unitsPerEm: number;
  defaultAdvance: number;
}

export const SAFE_FONTS: string[] = [];

export function resolveSafeFont(_name: string): string | null {
  return null;
}

export function loadFontMetrics(fontPath: string): FontMetrics {
  const font = openFontSync(fontPath);
  const unitsPerEm = font.unitsPerEm;
  const advanceWidths = new Map<string, number>();

  // Sample the printable ASCII range plus space — mirrors the Python
  // side's cmap-driven per-character advance width table.
  for (let code = 0x20; code <= 0x7e; code++) {
    const char = String.fromCharCode(code);
    const glyph = font.glyphForCodePoint(code);
    if (glyph && glyph.advanceWidth > 0) {
      advanceWidths.set(char, glyph.advanceWidth);
    }
  }

  const spaceAdvance = advanceWidths.get(" ");
  const defaultAdvance = spaceAdvance ?? Math.round(unitsPerEm * 0.5);

  return { advanceWidths, unitsPerEm, defaultAdvance };
}

function charWidthPt(char: string, metrics: FontMetrics, fontSizePt: number): number {
  const raw = metrics.advanceWidths.get(char) ?? metrics.defaultAdvance;
  return (raw / metrics.unitsPerEm) * fontSizePt;
}

export function measureTextWidthPt(text: string, metrics: FontMetrics, fontSizePt: number): number {
  let total = 0;
  for (const char of text) total += charWidthPt(char, metrics, fontSizePt);
  return total;
}

export function wrapLines(
  text: string,
  metrics: FontMetrics,
  fontSizePt: number,
  maxWidthPt: number,
): string[] {
  const words = text.split(/\s+/).filter((w) => w.length > 0);
  const lines: string[] = [];
  let currentWords: string[] = [];
  let currentWidth = 0;
  const spaceW = charWidthPt(" ", metrics, fontSizePt);

  for (const word of words) {
    const wordW = measureTextWidthPt(word, metrics, fontSizePt);
    const candidateWidth = currentWords.length === 0 ? wordW : currentWidth + spaceW + wordW;
    if (currentWords.length > 0 && candidateWidth > maxWidthPt) {
      lines.push(currentWords.join(" "));
      currentWords = [word];
      currentWidth = wordW;
    } else {
      currentWords.push(word);
      currentWidth = candidateWidth;
    }
  }
  if (currentWords.length > 0) lines.push(currentWords.join(" "));
  return lines.length > 0 ? lines : [""];
}

export interface OverflowReport {
  lines: string[];
  lineCount: number;
  totalHeightPt: number;
  boxHeightPt: number;
  overflow: boolean;
}

export function checkOverflow(
  text: string,
  metrics: FontMetrics,
  fontSizePt: number,
  boxWidthPt: number,
  boxHeightPt: number,
  lineHeightFactor = 1.2,
): OverflowReport {
  const lines = wrapLines(text, metrics, fontSizePt, boxWidthPt);
  const totalHeightPt = lines.length * fontSizePt * lineHeightFactor;
  return {
    lines,
    lineCount: lines.length,
    totalHeightPt,
    boxHeightPt,
    overflow: totalHeightPt > boxHeightPt,
  };
}

export function buildOverflowError(
  slide: number,
  primitivePath: string,
  field: string,
  report: OverflowReport,
  fontSizePt: number,
): Record<string, unknown> {
  const overBy = Math.max(0, report.totalHeightPt - report.boxHeightPt);
  return {
    slide,
    primitive: primitivePath,
    field,
    error: "overflow",
    detail: `Text is ~${overBy.toFixed(0)}pt too tall for the box at font size ${fontSizePt}pt (${report.lineCount} lines).`,
    fix: "Shorten the text, reduce bullet/line count, or split into two slides.",
  };
}

const FALLBACK_SYSTEM_FONTS = [
  "C:/Windows/Fonts/arial.ttf",
  "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
];

export function resolveFontPath(): string | null {
  for (const name of SAFE_FONTS) {
    const path = resolveSafeFont(name);
    if (path && existsSync(path)) return path;
  }
  return FALLBACK_SYSTEM_FONTS.find((p) => existsSync(p)) ?? null;
}
