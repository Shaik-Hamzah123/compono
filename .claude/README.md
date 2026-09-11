# .claude/ — Claude Code setup for compono contributors

This folder is committed to the repo so anyone developing `compono` with
Claude Code gets the same guardrails automatically, with no per-machine
setup.

- **`skills/compono-build/SKILL.md`** — the build-order workflow, hard
  invariants, and the pattern to follow when adding a new primitive. Claude
  loads this automatically when it's relevant; you can also invoke it
  directly.
- **`agents/compono-reviewer.md`** — a review subagent tuned to this
  project's specific invariants (real-shape-only rendering, pure
  resolver/validator, structured error shape, schema-as-documentation) rather
  than generic code review. Ask for it by name: "use the compono-reviewer
  agent to check this."
- **`settings.json` + `hooks/`** — two hooks, shared by the whole team:
  - `pre_commit_check.py` (PreToolUse on Bash): blocks any `git commit` if
    `ruff check .`, `mypy src`, or `pytest -q` fail. Fix the reported failure
    and retry — don't bypass it.
  - `format_on_edit.py` (PostToolUse on Edit/Write): auto-runs
    `ruff format` + `ruff check --fix` on any `.py` file just touched under
    `src/` or `tests/`, so style never drifts between commits.

Requires `uv` on `PATH` (both hooks shell out to `uv run ...`).
