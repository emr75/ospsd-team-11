# Contributing

## Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/)

## Setup

```bash
git clone <repo-url> && cd <repo-name>
uv sync --all-packages --extra dev
```

Copy `.env.example` to `.env` when you need to run the service or live integrations. Do not commit real OAuth, OpenAI, OTEL, Render, or issue-tracker credentials.

## Running Tests

```bash
# All tests
uv run pytest

# Component/unit tests
uv run pytest components -m "not local_credentials"

# Integration tests
uv run pytest tests/integration -m "not local_credentials"

# E2E tests that are safe for CI
uv run pytest tests/e2e -m "not local_credentials"

# Live Google Calendar E2E tests, only with local credentials
uv run pytest tests/e2e -m local_credentials

# With coverage
uv run pytest --cov=components
```

The project coverage threshold is configured in `pyproject.toml`.

## Linting and Type Checking

```bash
# Lint
uv run ruff check .

# Auto-fix lint errors
uv run ruff check . --fix

# Format
uv run ruff format .

# Type check
uv run mypy .

# Documentation
uv run mkdocs build
```

## Branch and PR Workflow

1. Create a feature branch from `main`.
2. Make your changes and ensure the relevant local checks pass.
3. Open a pull request. CircleCI installs the workspace with `uv`, then runs lint, type checking, component tests with coverage, integration tests, e2e tests, and a summary job.

## Documentation Updates

When changing public APIs, routes, environment variables, or component responsibilities, update the matching files:

- root `README.md`
- root `design.md`
- affected `components/*/README.md`
- affected pages under `docs/`
