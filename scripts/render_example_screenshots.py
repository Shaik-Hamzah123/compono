"""One-off dev tool: render examples/*.json -> .pptx -> PNG screenshots.

Not part of CI or the installed package. Re-run manually whenever the
examples change meaningfully:

    uv run python scripts/render_example_screenshots.py

Pipeline per example: compono.render_deck -> .pptx (temp dir) ->
`soffice --headless --convert-to pdf` (LibreOffice) -> one PNG per page via
`pdftoppm` (poppler). Requires both tools on PATH or at the hardcoded
fallback paths below (adjust if yours differ).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
EXAMPLES_DIR = REPO_ROOT / "examples"
OUTPUT_DIR = REPO_ROOT / "assets" / "screenshots"

_SOFFICE_CANDIDATES = [
    "soffice",
    r"C:\Program Files\LibreOffice\program\soffice.exe",
]
_PDFTOPPM_CANDIDATES = [
    "pdftoppm",
    r"C:\Program Files\poppler-24.08.0\Library\bin\pdftoppm.exe",
]


def _resolve_tool(candidates: list[str]) -> str:
    for candidate in candidates:
        if shutil.which(candidate) or Path(candidate).exists():
            return candidate
    raise RuntimeError(f"None of {candidates} found on PATH or at the hardcoded fallback path.")


def render_example_to_pngs(spec_path: Path, output_dir: Path) -> list[Path]:
    from compono import render_deck

    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    name = spec_path.stem

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        pptx_path = tmp_path / f"{name}.pptx"
        render_deck(spec, pptx_path)

        soffice = _resolve_tool(_SOFFICE_CANDIDATES)
        subprocess.run(
            [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(tmp_path), str(pptx_path)],
            check=True,
            capture_output=True,
        )
        pdf_path = tmp_path / f"{name}.pdf"

        example_output_dir = output_dir / name
        example_output_dir.mkdir(parents=True, exist_ok=True)

        pdftoppm = _resolve_tool(_PDFTOPPM_CANDIDATES)
        subprocess.run(
            [pdftoppm, "-png", "-r", "150", str(pdf_path), str(example_output_dir / "slide")],
            check=True,
            capture_output=True,
        )

    return sorted(example_output_dir.glob("slide-*.png"))


def main() -> int:
    if not EXAMPLES_DIR.exists():
        print(f"No examples directory at {EXAMPLES_DIR}", file=sys.stderr)
        return 1

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for spec_path in sorted(EXAMPLES_DIR.glob("*.json")):
        print(f"Rendering {spec_path.name}...")
        pngs = render_example_to_pngs(spec_path, OUTPUT_DIR)
        for png in pngs:
            print(f"  -> {png.relative_to(REPO_ROOT)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
