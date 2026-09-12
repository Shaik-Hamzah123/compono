#!/usr/bin/env node
/**
 * MCP server exposing compono-js's renderDeck/validate/review/inspire/docx
 * as MCP tools — TypeScript port of packages/compono-mcp/src/compono_mcp/server.py.
 *
 * Every tool here is a thin proxy over tools.ts — no reimplemented logic.
 * `spec` params are typed as a generic JSON object, not the zod Deck/
 * DocxDoc type, so malformed input reaches compono-js's validate/
 * renderDeck itself and comes back as its own structured {slide,
 * primitive, field, error, detail, fix} shape, never MCP's generic
 * schema-rejection error.
 */

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import {
  inspireScan,
  renderDeckTool,
  renderDocxTool,
  reviewDeck,
  validateDeck,
  validateDocxTool,
} from "./tools.js";

const __dirname = dirname(fileURLToPath(import.meta.url));

export const server = new McpServer({ name: "compono-js", version: "0.1.0" });

function jsonResult(value: unknown): { content: { type: "text"; text: string }[] } {
  return { content: [{ type: "text", text: JSON.stringify(value, null, 2) }] };
}

const specSchema = {
  spec: z.record(z.string(), z.unknown()).describe("The deck/document spec as a plain JSON object."),
};

server.registerTool(
  "validate_deck",
  {
    description:
      "Validate a compono deck spec: schema + layout + text-overflow checks, no file write. " +
      "Cheap — prefer this before render_deck_tool when iterating. Never raises: malformed input " +
      "comes back as {valid: false, errors: [...]}, each error shaped " +
      "{slide, primitive, field, error, detail, fix}.",
    inputSchema: specSchema,
  },
  async ({ spec }) => jsonResult(validateDeck(spec)),
);

server.registerTool(
  "render_deck_tool",
  {
    description:
      "Render a compono deck spec to a real, editable .pptx file at output_path. On success: " +
      "{pptxPath, manifest, warnings}. On any validation/layout/overflow error: {valid: false, errors: [...]} " +
      "in the same shape as validate_deck — nothing is written to output_path in that case.",
    inputSchema: { ...specSchema, output_path: z.string().describe("Path to write the .pptx file to.") },
  },
  async ({ spec, output_path: outputPath }) => jsonResult(await renderDeckTool(spec, outputPath)),
);

server.registerTool(
  "review_deck",
  {
    description:
      "Design-quality suggestions for a compono deck spec: contrast, whitespace, image fit, " +
      "font-size proximity to overflow, style. Never blocking — {suggestions: [...], warnings: [...]}; " +
      "suggestions may be empty. Complements validate_deck, doesn't replace it — pair the two.",
    inputSchema: specSchema,
  },
  async ({ spec }) => jsonResult(reviewDeck(spec)),
);

server.registerTool(
  "inspire_scan",
  {
    description:
      "Scan a set of .pptx files someone already likes into a style profile, and write it as a " +
      "skills/inspire-<name>/ folder (SKILL.md + profile.json) at out_dir. Extracts only measurable " +
      "structure — palette, fonts, spacing, grid patterns with a confidence score — never literal " +
      "text or images from the scanned decks. Returns {skill_md, profile_json, n_decks_scanned, warnings}; " +
      "a .pptx that fails to open is skipped and named in the returned warnings, not raised.",
    inputSchema: {
      pptx_paths: z.array(z.string()).describe("Paths to .pptx files someone already likes."),
      out_dir: z.string().describe("Output folder for SKILL.md + profile.json."),
      name: z.string().default("custom").describe("Name used in SKILL.md's frontmatter."),
      min_repeat_ratio: z
        .number()
        .default(0.5)
        .describe("Fraction of decks a fact must appear in to count as recurring."),
    },
  },
  async ({ pptx_paths: pptxPaths, out_dir: outDir, name, min_repeat_ratio: minRepeatRatio }) =>
    jsonResult(await inspireScan(pptxPaths, outDir, name, minRepeatRatio)),
);

server.registerTool(
  "validate_docx_tool",
  {
    description:
      "Validate a compono docx spec: schema checks only, no file write. Never raises: malformed input " +
      "comes back as {valid: false, errors: [...]}, each error shaped " +
      "{section, primitive, field, error, detail, fix} (docx's analogue of validate_deck's per-slide shape).",
    inputSchema: specSchema,
  },
  async ({ spec }) => jsonResult(validateDocxTool(spec)),
);

server.registerTool(
  "render_docx_tool",
  {
    description:
      "Render a compono docx spec to a real, editable .docx file at output_path. On success: " +
      "{docxPath, manifest, warnings}. On any validation error: {valid: false, errors: [...]} in the same " +
      "shape as validate_docx_tool. chart primitives render as a rasterized image (chart.js) — every " +
      "other primitive is a real, editable object.",
    inputSchema: { ...specSchema, output_path: z.string().describe("Path to write the .docx file to.") },
  },
  async ({ spec, output_path: outputPath }) => jsonResult(await renderDocxTool(spec, outputPath)),
);

server.registerResource(
  "reference",
  "compono://reference",
  {
    title: "compono-js reference",
    description:
      "The full agent-facing compono-js reference: quickstart, primitive catalog, worked examples, and error shape.",
    mimeType: "text/markdown",
  },
  async (uri) => ({
    contents: [
      {
        uri: uri.href,
        mimeType: "text/markdown",
        text: readFileSync(join(__dirname, "..", "reference.md"), "utf-8"),
      },
    ],
  }),
);

export async function main(): Promise<void> {
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

const isMain = process.argv[1] === fileURLToPath(import.meta.url);
if (isMain) {
  main();
}
