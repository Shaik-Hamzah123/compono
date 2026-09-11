# Contributing to compono

## Dev setup

```
git clone <repo>
cd compono
uv sync --all-extras
```

## Running tests

```
uv run pytest
```

## Branching

- `main` — production branch, only receives merges from `dev` when release-ready. Tagging a version on `main` publishes to PyPI.
- `dev` — integration branch. Cut feature branches from `dev`, merge back into `dev` via PR.

## Code style

- Format/lint with `ruff`.
- Type-check with `mypy` (or the project's configured type checker).
- Keep functions small and pure where possible, especially in `resolver.py` and `validator.py` — they're unit-tested independently of rendering.

## Commit messages

Describe the capability added or the bug fixed, not just "wip" or "fix".

## Using Claude Code on this repo

If you're developing with Claude Code, `.claude/` is committed and wires up
automatically — see `.claude/README.md`. It includes a build-workflow skill,
a project-specific review subagent, and commit-blocking lint/type/test hooks
so every contributor gets the same guardrails without extra setup.
