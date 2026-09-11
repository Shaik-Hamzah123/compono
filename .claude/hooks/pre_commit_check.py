"""PreToolUse hook (Bash): block `git commit` unless ruff, mypy, and pytest
all pass.

Wired via .claude/settings.json. Any Bash command that isn't a git commit
passes straight through untouched. On a commit attempt, runs the full check
suite; if anything fails, exits 2 so Claude Code blocks the tool call and
feeds the failure output back to the assistant to fix before retrying.
"""

from __future__ import annotations

import json
import subprocess
import sys


def main() -> int:
    payload = json.load(sys.stdin)
    command = payload.get("tool_input", {}).get("command", "")

    if "git commit" not in command:
        return 0

    checks: list[tuple[str, list[str]]] = [
        ("ruff", ["uv", "run", "ruff", "check", "."]),
        ("mypy", ["uv", "run", "mypy", "src"]),
        ("pytest", ["uv", "run", "pytest", "-q"]),
    ]

    failures = []
    for name, cmd in checks:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            failures.append(f"--- {name} failed ---\n{result.stdout}{result.stderr}")

    if failures:
        print(
            "Commit blocked: fix the following before committing.\n\n" + "\n\n".join(failures),
            file=sys.stderr,
        )
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
