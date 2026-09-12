/**
 * The actual tool implementations, as plain directly-callable functions —
 * server.ts just registers these with the MCP SDK. Kept separate so tests
 * can call them directly (no live stdio transport needed), mirroring
 * packages/compono-mcp/tests/test_server.py's pattern of importing each
 * @mcp.tool()-decorated Python function directly.
 */

import {
  DeckValidationError,
  DocxValidationError,
  aggregate,
  renderDeck,
  renderDocx,
  review,
  validate,
  validateDocx,
  writeSkill,
} from "@skhamzah123/compono-js";

export function validateDeck(spec: Record<string, unknown>): Record<string, unknown> {
  const report = validate(spec);
  return { valid: report.valid, errors: report.errors, warnings: report.warnings };
}

export async function renderDeckTool(
  spec: Record<string, unknown>,
  outputPath: string,
): Promise<Record<string, unknown>> {
  try {
    const report = await renderDeck(spec, outputPath);
    return { pptxPath: report.pptxPath, manifest: report.manifest, warnings: report.warnings };
  } catch (err) {
    if (err instanceof DeckValidationError) return { valid: false, errors: err.errors };
    throw err;
  }
}

export function reviewDeck(spec: Record<string, unknown>): Record<string, unknown> {
  return review(spec) as unknown as Record<string, unknown>;
}

export async function inspireScan(
  pptxPaths: string[],
  outDir: string,
  name = "custom",
  minRepeatRatio = 0.5,
): Promise<Record<string, unknown>> {
  const profile = await aggregate(pptxPaths, minRepeatRatio);
  const files = writeSkill(profile, outDir, name);
  return {
    skill_md: files.skillMd,
    profile_json: files.profileJson,
    n_decks_scanned: profile.n_example_decks,
    warnings: profile.warnings,
  };
}

export function validateDocxTool(spec: Record<string, unknown>): Record<string, unknown> {
  const report = validateDocx(spec);
  return { valid: report.valid, errors: report.errors, warnings: report.warnings };
}

export async function renderDocxTool(
  spec: Record<string, unknown>,
  outputPath: string,
): Promise<Record<string, unknown>> {
  try {
    const report = await renderDocx(spec, outputPath);
    return { docxPath: report.docxPath, manifest: report.manifest, warnings: report.warnings };
  } catch (err) {
    if (err instanceof DocxValidationError) return { valid: false, errors: err.errors };
    throw err;
  }
}
