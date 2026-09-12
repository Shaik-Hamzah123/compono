/**
 * Design-quality suggestions — TypeScript port of src/compono/review.py.
 *
 * validate() answers "will this render without breaking". review() answers
 * "does this look good" — never blocking, only suggestions (possibly
 * zero). Pure function — reuses resolveSlide's real rects and
 * validator.ts's checkOverflow rather than bespoke routines.
 *
 * Five categories, same thresholds as the Python side:
 *   - contrast: shape.text.color vs shape.fill, WCAG-style ratio.
 *   - whitespace: a lone top-level body primitive in a tall box. A
 *     header-only slide, or a lone-but-dense grid, is never flagged.
 *   - image_fit: a real image whose aspect ratio diverges a lot from its
 *     box, under fit="cover" (crops) or fit="contain" (letterboxes).
 *   - font_size: text using most of its box's height without (yet)
 *     overflowing.
 *   - style: an em dash (—) in any text-bearing field.
 */

import { readFileSync } from "node:fs";
import { imageSize } from "image-size";
import {
  loadTemplateByName,
  resolveSlide,
  EMU_PER_INCH,
  type Rect,
  type Template,
} from "./resolver.js";
import { Grid, type Deck, type Header, type Image, type PrimitiveSpecT, type Shape } from "./schema.js";
import { loadFontMetrics, checkOverflow, resolveFontPath, type FontMetrics } from "./validator.js";
import { extractTextFields, parseDeck, walkPrimitives } from "./render.js";

const MIN_CONTRAST_RATIO = 4.5;
const WHITESPACE_MIN_HEIGHT_PT = 300.0;
const IMAGE_ASPECT_TOLERANCE = 0.35;
const TIGHT_FIT_FRACTION = 0.85;
const EM_DASH = "—";

export interface ReviewReport {
  suggestions: Record<string, unknown>[];
  warnings: string[];
}

function suggestion(
  slide: number,
  primitive: string,
  fieldName: string | null,
  category: string,
  detail: string,
  fix: string,
): Record<string, unknown> {
  return { slide, primitive, field: fieldName, category, detail, fix };
}

function rectWidthPt(rect: Rect): number {
  return (rect.w / EMU_PER_INCH) * 72;
}

function rectHeightPt(rect: Rect): number {
  return (rect.h / EMU_PER_INCH) * 72;
}

function relativeLuminance(hex: string): number {
  const clean = hex.replace("#", "");
  const channel = (c: number) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
  const r = channel(parseInt(clean.slice(0, 2), 16) / 255);
  const g = channel(parseInt(clean.slice(2, 4), 16) / 255);
  const b = channel(parseInt(clean.slice(4, 6), 16) / 255);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrastRatio(hexA: string, hexB: string): number {
  const [l1, l2] = [relativeLuminance(hexA), relativeLuminance(hexB)].sort((a, b) => b - a);
  return (l1 + 0.05) / (l2 + 0.05);
}

function checkContrast(slideIndex: number, itemId: string, primitive: Shape): Record<string, unknown> | null {
  if (!primitive.text || !primitive.text.color || !primitive.fill) return null;
  const ratio = contrastRatio(primitive.text.color, primitive.fill);
  if (ratio >= MIN_CONTRAST_RATIO) return null;
  return suggestion(
    slideIndex,
    itemId,
    "text.color",
    "contrast",
    `text.color '${primitive.text.color}' against fill '${primitive.fill}' has a ` +
      `contrast ratio of ~${ratio.toFixed(1)}:1 (WCAG AA wants ${MIN_CONTRAST_RATIO}:1).`,
    "Pick a lighter/darker text.color for more contrast against fill, or use a lighter/darker fill.",
  );
}

function emDashFix(text: string): string {
  return text.replace(new RegExp(`\\s*${EM_DASH}\\s*`, "g"), " - ").trim();
}

function checkStyle(
  slideIndex: number,
  itemId: string,
  fieldName: string,
  text: string,
): Record<string, unknown> | null {
  if (!text.includes(EM_DASH)) return null;
  return suggestion(
    slideIndex,
    itemId,
    fieldName,
    "style",
    `'${fieldName}' contains an em dash ('${EM_DASH}'); many readers flag em dashes as a sign of AI-generated text.`,
    `Replace with a plain hyphen: '${text}' -> '${emDashFix(text)}'`,
  );
}

function checkWhitespace(
  slideIndex: number,
  itemId: string,
  rect: Rect,
  isLoneTopLevelItem: boolean,
): Record<string, unknown> | null {
  if (!isLoneTopLevelItem) return null;
  const boxHeightPt = rectHeightPt(rect);
  if (boxHeightPt < WHITESPACE_MIN_HEIGHT_PT) return null;
  return suggestion(
    slideIndex,
    itemId,
    null,
    "whitespace",
    `This is the only item in the body and its box is ~${boxHeightPt.toFixed(0)}pt tall — ` +
      "likely more empty space than the content needs.",
    "Add a supporting stat/bullet/image alongside it in a `grid`, or reduce the slide to a " +
      "header-only title/section slide if that's the intent.",
  );
}

function checkImageFit(slideIndex: number, itemId: string, primitive: Image, rect: Rect): Record<string, unknown> | null {
  if (primitive.placeholder || !primitive.src) return null;
  let dims: { width?: number; height?: number };
  try {
    dims = imageSize(readFileSync(primitive.src));
  } catch {
    return null; // unreadable file is validate()'s concern, not review()'s
  }
  if (!dims.width || !dims.height) return null;

  const imgRatio = dims.width / dims.height;
  const boxRatio = rect.w / rect.h;
  const diff = Math.abs(imgRatio - boxRatio) / boxRatio;
  if (diff <= IMAGE_ASPECT_TOLERANCE) return null;

  const detail =
    primitive.fit === "cover"
      ? `Image aspect ratio (${imgRatio.toFixed(2)}) differs from its box (${boxRatio.toFixed(2)}) by ` +
        `${(diff * 100).toFixed(0)}% under fit='cover' — likely crops a meaningful part of the image.`
      : `Image aspect ratio (${imgRatio.toFixed(2)}) differs from its box (${boxRatio.toFixed(2)}) by ` +
        `${(diff * 100).toFixed(0)}% under fit='contain' — likely leaves large empty bars.`;
  const fix =
    primitive.fit === "cover"
      ? "Use fit='contain' to avoid cropping, or choose an image closer to the box's aspect ratio."
      : "Use fit='cover' if cropping is acceptable, or choose an image closer to the box's aspect ratio.";
  return suggestion(slideIndex, itemId, "fit", "image_fit", detail, fix);
}

export function review(spec: unknown, templateOverride?: Template): ReviewReport {
  const deck: Deck = parseDeck(spec);
  const template = templateOverride ?? loadTemplateByName(deck.template);

  const fontPath = resolveFontPath();
  const metrics: FontMetrics | null = fontPath ? loadFontMetrics(fontPath) : null;

  const suggestions: Record<string, unknown>[] = [];
  const warnings: string[] = [];
  let skippedFontCheck = false;

  deck.slides.forEach((slide, slideIndex) => {
    const layout = resolveSlide(template, slide.header, slide.body);

    const topLevelBodyIds = [...layout.items.entries()]
      .filter(([id, primitive]) => primitive !== slide.header && !layout.parents.has(id))
      .map(([id]) => id);

    const soleBodyItem: PrimitiveSpecT | null = slide.body.length === 1 ? slide.body[0] : null;
    const isDenseGrid = !!soleBodyItem && soleBodyItem.primitive === "grid" && (soleBodyItem as Grid).items.length > 1;
    const loneTopLevelId =
      slide.body.length === 1 && topLevelBodyIds.length === 1 && !isDenseGrid ? topLevelBodyIds[0] : null;

    for (const [itemId, rect] of layout.rects) {
      const primitive = layout.items.get(itemId);
      if (!primitive) continue;

      if (primitive.primitive === "shape") {
        const s = checkContrast(slideIndex, itemId, primitive as Shape);
        if (s) suggestions.push(s);
      }

      if (primitive.primitive === "image") {
        const s = checkImageFit(slideIndex, itemId, primitive as Image, rect);
        if (s) suggestions.push(s);
      }

      const isLoneTopLevel = itemId === loneTopLevelId && !layout.parents.has(itemId);
      const w = checkWhitespace(slideIndex, itemId, rect, isLoneTopLevel);
      if (w) suggestions.push(w);

      const textFields = extractTextFields(primitive as PrimitiveSpecT | Header);

      for (const [fieldName, text] of textFields) {
        const s = checkStyle(slideIndex, itemId, fieldName, text);
        if (s) suggestions.push(s);
      }

      if (!metrics) {
        skippedFontCheck = true;
        continue;
      }

      for (const [fieldName, text, fontSizePt] of textFields) {
        const boxHeightPt = rectHeightPt(rect);
        const report = checkOverflow(text, metrics, fontSizePt, rectWidthPt(rect), boxHeightPt);
        if (!report.overflow && report.totalHeightPt > TIGHT_FIT_FRACTION * boxHeightPt) {
          suggestions.push(
            suggestion(
              slideIndex,
              itemId,
              fieldName,
              "font_size",
              `Text fills ~${((report.totalHeightPt / boxHeightPt) * 100).toFixed(0)}% of its ` +
                "box's height — close to overflowing.",
              "Shorten the text or reduce the font size for margin before it overflows on a slightly longer edit.",
            ),
          );
        }
      }
    }
  });

  if (skippedFontCheck) {
    warnings.push("no font available — font_size proximity checks skipped.");
  }

  return { suggestions, warnings };
}
