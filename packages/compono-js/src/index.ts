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

export { loadTemplateByName, loadTemplateFromYaml } from "./resolver.js";
export type { Template } from "./resolver.js";
