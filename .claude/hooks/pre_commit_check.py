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
import tempfile
from pathlib import Path


def main() -> int:
    payload = json.load(sys.stdin)
    command = payload.get("tool_input", {}).get("command", "")

    if "git commit" not in command:
        return 0

    # mypy's cache uses sqlite, which can raise "database is locked" when
    # the repo is checked out over a UNC/network path (e.g. editing a WSL
    # checkout from Windows) -- point it at the system temp dir instead of
    # the repo's own (possibly UNC) .mypy_cache, which sidesteps this on
    # every platform without hardcoding a machine-specific path.
    mypy_cache_dir = str(Path(tempfile.gettempdir()) / "compono-mypy-cache")

    checks: list[tuple[str, list[str]]] = [
        ("ruff", ["uv", "run", "ruff", "check", "."]),
        ("mypy", ["uv", "run", "mypy", "--cache-dir", mypy_cache_dir, "src"]),
        # `python -m pytest`, not the `pytest` console-script shim: the
        # shim's DLL search behavior breaks numpy/matplotlib imports when
        # the repo is checked out over a UNC/network path, even though
        # plain `python -m pytest` from the same venv works fine.
        ("pytest", ["uv", "run", "python", "-m", "pytest", "-q"]),
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
