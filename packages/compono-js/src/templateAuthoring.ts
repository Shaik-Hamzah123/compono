/**
 * Host/developer-side tool: draft a new `templates/<name>.yaml` from an
 * existing corporate .pptx (`compono-js template extract`, cli.ts) —
 * TypeScript port of src/compono/template_authoring.py.
 *
 * Deliberately not part of the core schema/resolver/render pipeline — this
 * module owns the one "read an existing .pptx for its theme/page-size/logo,
 * then write a template yaml (+ optional logo asset) to disk" concern.
 * Reuses inspire.ts's exact zip+XML pattern (`JSZip.loadAsync` +
 * `fast-xml-parser`) rather than introducing a new one.
 *
 * Extraction is always best-effort: a missing/malformed theme part, or no
 * logo picture on the master, degrades to `undefined` fields rather than
 * throwing — a developer running the CLI command should get a usable draft
 * yaml to review/edit, never a crash on an unusual source deck.
 *
 * Explicitly not attempted (see NEXT-STEPS.md): placeholder/slide-layout
 * geometry inheritance (compono's resolver computes its own EMU box model
 * and never uses PowerPoint placeholder inheritance), full theme extraction
 * beyond two accent colors and one body typeface, and chart color theming.
 *
 * Logo extraction has no python-pptx-style object model to lean on in JS,
 * so it takes one more manual step than the Python side: parse the slide
 * master's XML for a `<p:pic>` element's `r:embed` relationship id, resolve
 * it via the master's `.rels` part, then read the target media file's bytes
 * from the zip directly.
 */

import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { readFile } from "node:fs/promises";
import { dirname, join, posix } from "node:path";
import { fileURLToPath } from "node:url";
import { XMLParser } from "fast-xml-parser";
import JSZip from "jszip";
import { parse as parseYaml, stringify as stringifyYaml } from "yaml";

const __dirname = dirname(fileURLToPath(import.meta.url));
const DEFAULT_TEMPLATE_PATH = join(__dirname, "..", "templates", "default.yaml");

const parser = new XMLParser({ ignoreAttributes: false, attributeNamePrefix: "@_" });

const EMU_PER_IN = 914400;

function asArray<T>(value: T | T[] | undefined): T[] {
  if (value === undefined) return [];
  return Array.isArray(value) ? value : [value];
}

export interface ExtractedTemplateData {
  pageWidthIn: number;
  pageHeightIn: number;
  fontFamily?: string;
  primaryColor?: string;
  accentColor?: string;
  logoBytes?: Buffer;
  logoExt?: string;
}

/** Deep search for the first `<p:pic>` element anywhere under `node` — a
 * corporate logo is typically placed directly on the slide master's shape
 * tree, but this doesn't assume a fixed nesting depth (e.g. inside a group).
 */
function findFirstPic(node: unknown): Record<string, unknown> | null {
  if (node === null || typeof node !== "object") return null;
  const obj = node as Record<string, unknown>;
  if ("p:pic" in obj) {
    const pic = obj["p:pic"];
    const first = Array.isArray(pic) ? pic[0] : pic;
    return (first as Record<string, unknown>) ?? null;
  }
  for (const value of Object.values(obj)) {
    for (const item of Array.isArray(value) ? value : [value]) {
      if (item !== null && typeof item === "object") {
        const found = findFirstPic(item);
        if (found) return found;
      }
    }
  }
  return null;
}

function themeColor(clrScheme: Record<string, unknown> | undefined, schemeName: string): string | undefined {
  const node = clrScheme?.[schemeName] as Record<string, unknown> | undefined;
  if (!node) return undefined;
  const srgb = node["a:srgbClr"] as Record<string, unknown> | undefined;
  if (srgb?.["@_val"]) return `#${String(srgb["@_val"]).toUpperCase()}`;
  const sysClr = node["a:sysClr"] as Record<string, unknown> | undefined;
  if (sysClr?.["@_lastClr"]) return `#${String(sysClr["@_lastClr"]).toUpperCase()}`;
  return undefined;
}

function themeFont(fontScheme: Record<string, unknown> | undefined): string | undefined {
  for (const group of ["a:minorFont", "a:majorFont"]) {
    const node = fontScheme?.[group] as Record<string, unknown> | undefined;
    const latin = node?.["a:latin"] as Record<string, unknown> | undefined;
    const typeface = latin?.["@_typeface"] as string | undefined;
    if (typeface && !typeface.startsWith("+")) return typeface;
  }
  return undefined;
}

/** Best-effort extraction of a template's page size, theme accent colors,
 * theme body font, and master logo from an existing .pptx. Margins/header/
 * footer height/gutter are never derived here — see `writeExtractedTemplate`,
 * which fills those in from compono-js's own bundled `default.yaml` instead,
 * since arbitrary master placeholder geometry has no meaningful mapping
 * onto compono's resolver box model.
 */
export async function extractTemplateData(pptxPath: string): Promise<ExtractedTemplateData> {
  const zip = await JSZip.loadAsync(await readFile(pptxPath));

  const presentationXml = await zip.files["ppt/presentation.xml"]?.async("string");
  const presentation = presentationXml ? parser.parse(presentationXml)["p:presentation"] : undefined;
  const sldSz = presentation?.["p:sldSz"];
  const pageWidthIn = sldSz?.["@_cx"] ? Number(sldSz["@_cx"]) / EMU_PER_IN : 13.333;
  const pageHeightIn = sldSz?.["@_cy"] ? Number(sldSz["@_cy"]) / EMU_PER_IN : 7.5;

  let fontFamily: string | undefined;
  let primaryColor: string | undefined;
  let accentColor: string | undefined;
  try {
    const themeXml = await zip.files["ppt/theme/theme1.xml"]?.async("string");
    if (themeXml) {
      const theme = parser.parse(themeXml)["a:theme"]?.["a:themeElements"];
      fontFamily = themeFont(theme?.["a:fontScheme"]);
      primaryColor = themeColor(theme?.["a:clrScheme"], "a:accent1");
      accentColor = themeColor(theme?.["a:clrScheme"], "a:accent2");
    }
  } catch {
    // Missing/malformed theme part — degrade to undefined, never throw.
  }

  let logoBytes: Buffer | undefined;
  let logoExt: string | undefined;
  try {
    const masterXml = await zip.files["ppt/slideMasters/slideMaster1.xml"]?.async("string");
    if (masterXml) {
      const master = parser.parse(masterXml)["p:sldMaster"];
      const spTree = master?.["p:cSld"]?.["p:spTree"];
      const pic = findFirstPic(spTree);
      const rId = (pic?.["p:blipFill"] as Record<string, unknown> | undefined)?.["a:blip"] as
        | Record<string, unknown>
        | undefined;
      const embedId = rId?.["@_r:embed"] as string | undefined;
      if (embedId) {
        const relsXml = await zip.files["ppt/slideMasters/_rels/slideMaster1.xml.rels"]?.async("string");
        if (relsXml) {
          const rels = asArray<Record<string, unknown>>(
            parser.parse(relsXml)["Relationships"]?.["Relationship"],
          );
          const rel = rels.find((r) => r["@_Id"] === embedId);
          const target = rel?.["@_Target"] as string | undefined;
          if (target) {
            const mediaPath = posix.normalize(posix.join("ppt/slideMasters", target));
            const file = zip.files[mediaPath];
            if (file) {
              logoBytes = await file.async("nodebuffer");
              logoExt = mediaPath.split(".").pop();
            }
          }
        }
      }
    }
  } catch {
    // No master, no picture, or a malformed relationship — never throw.
  }

  return { pageWidthIn, pageHeightIn, fontFamily, primaryColor, accentColor, logoBytes, logoExt };
}

/** Write `<outputDir>/<name>.yaml` (and, if a logo was found,
 * `<outputDir>/assets/<name>-logo.<ext>`), merging the extracted page
 * size/font/colors onto compono-js's own default margin/header/footer/
 * gutter values. Returns the written yaml's path.
 */
export function writeExtractedTemplate(data: ExtractedTemplateData, name: string, outputDir: string): string {
  const defaults = parseYaml(readFileSync(DEFAULT_TEMPLATE_PATH, "utf-8"));

  const doc: Record<string, unknown> = {
    name,
    page: { width_in: Math.round(data.pageWidthIn * 1000) / 1000, height_in: Math.round(data.pageHeightIn * 1000) / 1000 },
    margin_in: defaults.margin_in,
    header: defaults.header,
    footer: defaults.footer,
    gutter_in: defaults.gutter_in,
    font_family: data.fontFamily ?? defaults.font_family,
  };

  const colors: Record<string, string> = {};
  if (data.primaryColor) colors.primary = data.primaryColor;
  if (data.accentColor) colors.accent = data.accentColor;
  if (Object.keys(colors).length > 0) doc.colors = colors;

  mkdirSync(outputDir, { recursive: true });
  if (data.logoBytes) {
    const assetsDir = join(outputDir, "assets");
    mkdirSync(assetsDir, { recursive: true });
    const logoFilename = `${name}-logo.${data.logoExt ?? "png"}`;
    writeFileSync(join(assetsDir, logoFilename), data.logoBytes);
    doc.logo = `assets/${logoFilename}`;
  }

  const yamlPath = join(outputDir, `${name}.yaml`);
  const headerComment =
    "# Extracted via `compono-js template extract` from an existing .pptx.\n" +
    "# Page size, font, and accent colors were parsed from its theme; margins/\n" +
    "# header/footer/gutter are copied from compono-js's own default.yaml, since\n" +
    "# arbitrary master placeholder geometry has no equivalent in compono's\n" +
    "# resolver box model. Review before committing, same as any hand-authored\n" +
    "# templates/*.yaml.\n\n";
  writeFileSync(yamlPath, headerComment + stringifyYaml(doc));
  return yamlPath;
}
