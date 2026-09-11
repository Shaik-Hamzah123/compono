"""PostToolUse hook (Edit|Write): auto-format a just-touched Python file.

Wired via .claude/settings.json. No-ops for anything that isn't a .py file
under src/ or tests/. Runs `ruff format` then `ruff check --fix` on just
that file so style never drifts between commits — silent on success, and
deliberately non-blocking (formatting issues shouldn't interrupt the
assistant's flow the way a failing commit gate should).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    payload = json.load(sys.stdin)
    file_path = payload.get("tool_input", {}).get("file_path", "")
    if not file_path:
        return 0

    path = Path(file_path)
    if path.suffix != ".py":
        return 0
    if not ({"src", "tests"} & set(path.parts)):
        return 0
    if not path.exists():
        return 0

    subprocess.run(["uv", "run", "ruff", "format", str(path)], capture_output=True, check=False)
    subprocess.run(["uv", "run", "ruff", "check", "--fix", str(path)], capture_output=True, check=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
