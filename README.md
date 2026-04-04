# Calendar Client Platform — OSPSD Team 11

## Purpose

This project implements a Calendar Client. The interface defines a contract for calendar operations (creating, reading, updating, and deleting events), while the concrete implementation targets Google Calendar via its API, and an initial FastAPI service layer that exposes calendar functionality over HTTP.

You can use the same application-facing API in two ways:

1. **Direct implementation**: call Google Calendar directly (`google_calendar_client_impl`)
2. **Service adapter**: call a deployed FastAPI service (`google_calendar_service_adapter` + `google_calendar_service_api_client`)

This keeps business logic decoupled from transport and provider details.

---

## Architecture Overview

This project follows a **ports/adapters architecture**:

- **Port (core contract)**: `calendar_client_api`
- **Adapters**:
  - `google_calendar_client_impl` (direct Google API adapter)
  - `google_calendar_service_adapter` (HTTP adapter through deployed service)
- **FastAPI Service**: `google_calendar_service` (FastAPI app)
- **Generated API Client**: `google_calendar_service_api_client`

---

## Repository Layout

```text
.
├── components/
│   ├── calendar_client_api/                # Port: interfaces, DTOs, registry, domain exceptions
│   ├── google_calendar_client_impl/        # Direct Google adapter
│   ├── google_calendar_service/            # FastAPI deployment/service boundary
│   ├── google_calendar_service_api_client/ # Generated typed HTTP client
│   └── google_calendar_service_adapter/    # CalendarClient adapter over HTTP service
├── tests/                                  # Integration + e2e tests
├── docs/                                   # MkDocs source
├── Dockerfile                              # uv-based multi-stage image
├── pyproject.toml                          # uv workspace config
└── uv.lock                                 # locked dependency graph
```

---

## Setup

### Prerequisites

- Python **3.13+**
- [uv](https://docs.astral.sh/uv/)

### Install dependencies

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
# Clone the repository
git clone <repo-url> && cd <repo-name>
# Install dependencies
uv sync --all-packages --extra dev
```

---

## Toolchain Usage

| Tool | Purpose | Command |
|------|---------|---------|
| **uv** | Dependency & workspace management | `uv sync --all-packages --extra dev` |
| **ruff** | Linting & formatting | `ruff check .` / `ruff format .` |
| **mypy** | Static type checking (strict mode) | `mypy .` |
| **pytest** | Test runner with coverage (≥ 85 % threshold) | `pytest` |
| **MkDocs** | Documentation site | `mkdocs serve` / `mkdocs build` |
| **CircleCI** | Continuous integration | Triggered on push (see `.circleci/config.yml`) |

```bash
# Sync workspace
uv sync --all-packages --extra dev

# Run tests
uv run pytest --cov

# Run unit/integration/e2e subsets
uv run pytest -m unit
uv run pytest -m integration
uv run pytest -m e2e

# Lint and format
uv run ruff check .
uv run ruff format .

# Type check
uv run mypy .

# Build docs
uv run mkdocs serve
uv run mkdocs build
```


---

## Testing

Tests are organized into three tiers using pytest markers:

| Tier | Marker | What it covers |
|------|--------|----------------|
| **Unit** | `@pytest.mark.unit` | Isolated tests per component (ABC contracts, registry, CRUD, auth, event parsing) |
| **Integration** | `@pytest.mark.integration` | DI wiring: auto-registration, factory behavior, type hierarchies, error propagation |
| **E2E** | `@pytest.mark.e2e` | Full system tests against real Google Calendar API |

### Running tests locally

```bash
# Run all tests
uv run pytest

# Run only unit tests
uv run pytest -m unit

# Run only integration tests
uv run pytest -m integration

# Run with coverage report
uv run pytest --cov=components/calendar_client_api/src --cov=components/google_calendar_client_impl/src --cov=...

# Run a specific test file
uv run pytest tests/integration/test_client_integration.py -v
```

### Linting and formatting

```bash
# Check for lint errors
uv run ruff check . --fix

# Formatting
uv run ruff format
```

---

## Authentication Setup

You can authenticate in two modes depending on adapter choice.

### Direct implementation (`google_calendar_client_impl`)

Used when your app imports `google_calendar_client_impl` and calls `get_client()`.

Set the direct Google auth environment variables (or `.env`):
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`

The credential/token files (e.g., `credentials.json`, `token.json`) may also be used by the implementation.

### Service mode (`google_calendar_service`)

Used when you deploy FastAPI and consume via HTTP adapter.

Required service OAuth variables:
- `GOOGLE_CALENDAR_CLIENT_ID`
- `GOOGLE_CALENDAR_CLIENT_SECRET`
- `GOOGLE_CALENDAR_REDIRECT_URI` (default: `http://localhost:8000/auth/callback`)

Other optional OAuth/session settings:
- `GOOGLE_CALENDAR_SCOPES`
- `GOOGLE_CALENDAR_OAUTH_AUTH_URL`
- `GOOGLE_CALENDAR_OAUTH_TOKEN_URL`
- `GOOGLE_CALENDAR_OAUTH_ALLOWED_TOKEN_HOSTS`
- `GOOGLE_CALENDAR_OAUTH_PROMPT`
- `GOOGLE_CALENDAR_OAUTH_STATE_TTL_SECONDS`
- `GOOGLE_CALENDAR_OAUTH_TOKEN_TIMEOUT_SECONDS`
- `GOOGLE_CALENDAR_SESSION_COOKIE_NAME`
- `GOOGLE_CALENDAR_SESSION_IDENTIFIER`
- `GOOGLE_CALENDAR_SESSION_SECRET`
- `GOOGLE_CALENDAR_SESSION_COOKIE_SECURE`

---

## Running Locally

### Run the service

```bash
uv run uvicorn google_calendar_service.main:app --host 0.0.0.0 --port 8000
```

Service base URL (local): `http://127.0.0.1:8000`

### Service endpoints

- `GET /health`
- `GET /auth/login`
- `GET /auth/callback`
- `POST /auth/logout`
- `GET /events/`
- `GET /events/{event_id}`
- `POST /events/`
- `PATCH /events/{event_id}`
- `DELETE /events/{event_id}`

---

## Deployment (Platform, URL, Env Vars)

Deploy using the root `Dockerfile` on Render.

### 1) Build image

```bash
docker build -t google-calendar-service .
```

### 2) Run locally as container

```bash
docker run --rm -p 8000:8000 \
  -e GOOGLE_CALENDAR_CLIENT_ID=... \
  -e GOOGLE_CALENDAR_CLIENT_SECRET=... \
  -e GOOGLE_CALENDAR_REDIRECT_URI=https://<your-domain>/auth/callback \
  -e GOOGLE_CALENDAR_SESSION_SECRET=... \
  google-calendar-service
```

or, specify a `.env` file:

```bash
docker run --rm -p 8000:8000 \
  --env-file .env \
  google-calendar-service
```

### 3) Deploy to Render

This step is automatically triggered by CircleCI.

### 4) Set service URL

After deployment, the service base URL is: https://ospsd-team-11.onrender.com

Use this URL in clients or adapter registration:

```python
from google_calendar_service_adapter import register_service_calendar_client

register_service_calendar_client(base_url="https://ospsd-team-11.onrender.com")
```

---
