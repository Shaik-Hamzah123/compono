.PHONY: install lint typecheck test check format build clean

install:
	uv sync --all-packages

lint:
	uv run ruff check .

format:
	uv run ruff format .
	uv run ruff check --fix .

typecheck:
	uv run mypy src packages/compono-mcp/src

test:
	# `python -m pytest`, not the `pytest` console-script shim: the shim's
	# DLL search behavior breaks numpy/matplotlib imports when the repo is
	# checked out over a UNC/network path (e.g. Windows -> WSL), even
	# though plain `python -m pytest` from the same venv works fine.
	uv run python -m pytest -q

check: lint typecheck test

build:
	uv build

clean:
	rm -rf dist build *.egg-info .pytest_cache .ruff_cache .mypy_cache
	find . -name "__pycache__" -type d -prune -exec rm -rf {} +
