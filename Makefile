.PHONY: install test lint fmt check clean build

## install: set up virtual environment and pre-commit hooks
install:
	uv sync --all-extras
	uv run pre-commit install
	@echo "✅ Environment ready. Run 'make test' to verify."

## test: run pytest with coverage
test:
	uv run pytest

## lint: run ruff linter + mypy type checker
lint:
	uv run ruff check src/ tests/
	uv run mypy src/

## fmt: auto-format and auto-fix code
fmt:
	uv run ruff format src/ tests/
	uv run ruff check --fix src/ tests/

## check: lint + test (run before pushing)
check: lint test

## build: build distribution package (for PyPI)
build:
	uv run python -m build

## clean: remove generated artifacts
clean:
	rm -rf .pytest_cache htmlcov .coverage dist build .mypy_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} +

## help: show this help
help:
	@grep -E '^## ' Makefile | sed 's/## //'
