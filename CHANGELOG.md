# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-03-10

### Added
- Project scaffold: `pyproject.toml`, `uv`, src layout
- Pre-commit hooks: `ruff` (lint + format), `mypy`, `pre-commit-hooks`
- GitHub Actions CI (lint + test on push) and publish workflow (PyPI on tag)
- Directory structure: `src/trading_advisor/`, `tests/`, `scripts/`, `data/`, `logs/`
- Module stubs: `data/`, `indicators/`, `guards/`, `strategy/`, `portfolio/`, `notifications/`, `backtest/`
- Economic calendar seed data (FOMC/NFP/CPI 2020–2026)
- `Makefile` with `install`, `test`, `lint`, `fmt`, `check`, `clean` targets
- MIT License, README, CHANGELOG

[Unreleased]: https://github.com/mrdwan/wealthops/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/mrdwan/wealthops/releases/tag/v0.1.0
