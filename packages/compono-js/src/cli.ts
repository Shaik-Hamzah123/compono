#!/usr/bin/env node
/**
 * Console-script entry point mirroring src/compono/cli.py's two verbs.
 *
 * compono-js validate spec.json
 * compono-js render spec.json --template modern -o deck.pptx
 */

import { readFileSync } from "node:fs";
import { Command } from "commander";
import { DeckValidationError, renderDeck, validate } from "./render.js";
import { loadTemplateByName } from "./resolver.js";
import { review } from "./review.js";
import { DocxValidationError, renderDocx, validateDocx } from "./docx.js";

function loadSpec(path: string): unknown {
  return JSON.parse(readFileSync(path, "utf-8"));
}

const program = new Command();
program.name("compono-js");

program
  .command("validate")
  .argument("<spec>", "Path to a JSON deck spec.")
  .action((specPath: string) => {
    const spec = loadSpec(specPath);
    const report = validate(spec);
    console.log(JSON.stringify(report, null, 2));
    process.exitCode = report.valid ? 0 : 1;
  });

program
  .command("render")
  .argument("<spec>", "Path to a JSON deck spec.")
  .option("-o, --output <path>", "Output .pptx path.", "deck.pptx")
  .option("--template <name>", "Template name under templates/.")
  .action(async (specPath: string, opts: { output: string; template?: string }) => {
    const spec = loadSpec(specPath);
    try {
      const template = opts.template ? loadTemplateByName(opts.template) : undefined;
      const report = await renderDeck(spec, opts.output, template);
      console.log(JSON.stringify(report, null, 2));
    } catch (err) {
      if (err instanceof DeckValidationError) {
        console.error(JSON.stringify({ valid: false, errors: err.errors }, null, 2));
        process.exitCode = 1;
        return;
      }
      throw err;
    }
  });

program
  .command("review")
  .argument("<spec>", "Path to a JSON deck spec.")
  .action((specPath: string) => {
    const spec = loadSpec(specPath);
    const report = review(spec);
    console.log(JSON.stringify(report, null, 2));
  });

const docxProgram = program.command("docx").description("Validate/render a docx document spec.");

docxProgram
  .command("validate")
  .argument("<spec>", "Path to a JSON docx spec.")
  .action((specPath: string) => {
    const spec = loadSpec(specPath);
    const report = validateDocx(spec);
    console.log(JSON.stringify(report, null, 2));
    process.exitCode = report.valid ? 0 : 1;
  });

docxProgram
  .command("render")
  .argument("<spec>", "Path to a JSON docx spec.")
  .option("-o, --output <path>", "Output .docx path.", "document.docx")
  .action(async (specPath: string, opts: { output: string }) => {
    const spec = loadSpec(specPath);
    try {
      const report = await renderDocx(spec, opts.output);
      console.log(JSON.stringify(report, null, 2));
    } catch (err) {
      if (err instanceof DocxValidationError) {
        console.error(JSON.stringify({ valid: false, errors: err.errors }, null, 2));
        process.exitCode = 1;
        return;
      }
      throw err;
    }
  });

program.parseAsync(process.argv);
