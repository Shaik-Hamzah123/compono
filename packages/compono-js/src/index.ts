/**
 * Public exports ONLY — resolver/validator/template loader stay internal,
 * reached only through renderDeck/validate. Mirrors src/compono/__init__.py.
 */

export {
  Chart,
  ChartSeries,
  Deck,
  Grid,
  Header,
  Image,
  PrimitiveSpec,
  Sequence,
  SequenceStep,
  Shape,
  ShapeConnects,
  ShapeText,
  Slide,
  Stat,
  Table,
  Text,
} from "./schema.js";
export type { PrimitiveSpecT } from "./schema.js";

export { DeckValidationError, renderDeck, validate } from "./render.js";
export type { RenderReport, ValidationReport } from "./render.js";

export { review } from "./review.js";
export type { ReviewReport } from "./review.js";

export {
  BulletList,
  DocChart,
  DocChartSeries,
  DocImage,
  DocTable,
  DocxDoc,
  DocxPrimitiveSpec,
  Heading,
  NumberedList,
  PageBreak,
  Paragraph,
  Run,
  Section,
} from "./docx_schema.js";
export type { DocxPrimitiveSpecT } from "./docx_schema.js";

export { DocxValidationError, renderDocx, validateDocx } from "./docx.js";
export type { DocxRenderReport } from "./docx.js";

export { aggregate, scanDeck, writeSkill } from "./inspire.js";
export type { AggregatedProfile, DeckProfile, SkillFiles } from "./inspire.js";

export { loadTemplateByName, loadTemplateFromYaml } from "./resolver.js";
export type { Template } from "./resolver.js";
