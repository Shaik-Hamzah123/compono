---
name: compono-build
description: Conventions and build-order workflow for developing compono itself (not for generating decks with it). Use when implementing a step from COMPONO_PLAN.md, adding a primitive, touching the resolver/validator, or preparing a commit on this repo.
---

# Building compono

This skill orients any contributor (human or Claude) picking up work on the
`compono` library itself. The full spec is `COMPONO_PLAN.md` at the repo
root — read it first if you haven't. This skill is the condensed, actionable
version of its conventions.

## Where things stand

Check `CHANGELOG.md`'s `[Unreleased]` section and recent git log
(`git log --oneline -10`) to see which build-order step (COMPONO_PLAN.md
section 14) is done. Steps so far: repo scaffold, schema (header/text/grid/
shape), resolver, validator, render_deck/validate + CLI. Remaining: the rest
of the primitives (image/stat/table/sequence/chart), reference docs, golden
tests + CI, first release.

## Branching and commits

- Work happens on `dev` (or a short-lived branch cut from `dev`). `main` only
  ever receives a merge from `dev` when it's release-ready — never commit
  build-order work directly to `main`.
- One commit per build-order step, not per file. Commit message describes
  the capability added, not "wip".
- **Before every commit**: `uv run ruff check .`, `uv run mypy src`,
  `uv run pytest -q` must all pass. A pre-commit hook enforces this
  automatically (see `.claude/hooks/`) — if it blocks you, fix the reported
  failure rather than bypassing it.
- Don't bump the version in `pyproject.toml` per commit — only at a real
  release milestone, recorded in `CHANGELOG.md`.

## Hard invariants (never trade these away for convenience)

1. **Every primitive renders as a real, editable OOXML shape** — `p:sp`,
   `p:pic`, `p:graphicFrame` — never a flattened image or embedded video.
   This is the entire reason the project exists (COMPONO_PLAN.md section 3).
   Any new render code must produce inspectable native shapes; a golden test
   asserting this will exist per-primitive (see Step 7).
2. **The resolver and validator are pure functions.** No file I/O beyond
   `Template.from_yaml`/`load_font_metrics` themselves, no pptx writes, no
   network calls. This is what makes them independently unit-testable and
   millisecond-fast — don't let rendering concerns leak in.
3. **One shared "fit text into this rectangle" routine** for `text`,
   `stat`, and `shape.text` — don't duplicate shrink-to-fit logic per
   primitive (COMPONO_PLAN.md section 5, "Text-in-shape").
4. **Schema field `description`s are instructions to the calling agent**,
   not type labels — e.g. "Keep under ~60 characters — longer titles will be
   shrunk by the resolver," not "the title string." The schema is the
   in-context documentation (COMPONO_PLAN.md section 8, item 2).
5. **Errors are fixes, not diagnoses.** Every validation/render error is
   `{slide, primitive, field, error, detail, fix}` — see
   `validator.build_overflow_error` for the canonical shape. Never raise a
   bare exception or return a vague message from user-facing paths.
6. **Never silently guess in a way that hides a mistake.** Safe
   normalization (trimming whitespace, coercing types) is fine; anything
   that changes intent (auto-truncating text, dropping a field) must be a
   validation error instead.

## Adding a new primitive (pattern to follow)

Look at `header`/`text`/`grid`/`shape` in `schema.py` as the reference
pattern, then touch, in order:

1. **`schema.py`** — a new `PrimitiveBase` subclass, added to the
   `PrimitiveSpec` discriminated union, `Grid.model_rebuild()` re-run if the
   union changed shape.
2. **`resolver.py`** — teach `_place_item` (and `_layout_grid` if it needs
   2D placement) how to size/position it. Reuse `Rect`/`LayoutResult` as-is;
   don't invent a parallel positioning structure.
3. **`validator.py`** — if it carries text, feed it through the existing
   `check_overflow`/`measure_text_width_pt` functions, not a new bespoke
   check.
4. **`render.py`** — a `_render_<primitive>` function following the
   existing ones' shape: take `(pptx_slide, primitive, rect)`, produce a
   real OOXML shape via `python-pptx`.
5. **`__init__.py`** — export the new class if it's part of the public API
   surface.
6. Tests: extend `tests/test_schema.py`, `tests/test_resolver.py`, and
   `tests/test_render.py` in the same style as the existing primitives —
   don't create a separate test file per primitive.

## Where to look for canonical examples

- Pure-function style: `resolver.py`, `validator.py`.
- Discriminated union / recursive schema: `schema.py`'s `Grid`.
- Structured error shape: `validator.build_overflow_error`,
  `render._pydantic_error_to_dict`.
- End-to-end wiring: `render.py`'s `validate`/`render_deck`, exercised in
  `tests/test_render.py` against an inline minimal spec (kept in the test
  file, not `examples/`, since every example deck is now real reference
  material rather than a bare smoke-test fixture).
