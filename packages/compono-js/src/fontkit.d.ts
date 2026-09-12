/**
 * Minimal ambient typing for `fontkit` — it ships no .d.ts and there's no
 * @types/fontkit package. Only the surface validator.ts actually uses.
 */
declare module "fontkit" {
  export interface Glyph {
    advanceWidth: number;
  }

  export interface Font {
    unitsPerEm: number;
    glyphForCodePoint(codePoint: number): Glyph;
  }

  export function openSync(path: string): Font;
}
