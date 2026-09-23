# `text`

Prose or a bullet list.

## Fields

| Field | Type | Notes |
|---|---|---|
| `mode` | `"paragraph" \| "bullets"` | Default `"paragraph"`. |
| `content` | `str \| list[str]` | A single string for paragraph mode, or a list of strings for bullets mode. Keep bullet items under ~100 characters so they fit without shrinking. |
| `columns` | `int` | Default `1`. Number of layout columns to split content across. |
| `emphasis_indices` | `list[int] \| null` | 0-based indices of bullet items/sentences to visually emphasize (bold). |

## Examples

Paragraph:

```json
{ "primitive": "text", "mode": "paragraph", "content": "A single flowing block of prose." }
```

Bullets, with the third item emphasized:

```json
{
  "primitive": "text",
  "mode": "bullets",
  "content": [
    "The agent never writes raw x/y/w/h coordinates",
    "A constraint-based resolver computes real EMU positions",
    "Every primitive renders as a genuine, editable OOXML shape"
  ],
  "emphasis_indices": [2]
}
```

Overflow (text too big for its resolved box) is checked via real glyph
advance widths from the active template's font — never faked, never
silently shrunk below a readable size. See
[templates-and-fonts.md](../templates-and-fonts.md).
