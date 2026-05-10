# Calendar Client Platform - OSPSD Team 11

## Purpose

This project implements a calendar client platform. The calendar interface defines a contract for creating, reading, updating, listing, and deleting events; the direct implementation targets Google Calendar; and the FastAPI service exposes calendar and AI-assisted workflows over HTTP. The AI layer supports tool/function calling for calendar actions, issue-tracker actions, and cross-service scheduling.

You can use the same application-facing API in three ways:

1. **Direct implementation**: call Google Calendar directly (`google_calendar_client_impl`)
2. **Service adapter**: call a deployed FastAPI service (`google_calendar_service_adapter` + `google_calendar_service_api_client`)
3. **AI workflow**: call `POST /ai/` on the service to let the OpenAI-backed agent use calendar and issue-tracker tools

This keeps business logic decoupled from transport and provider details.

---

## Architecture Overview

This project follows an interface/implementation architecture:

- **Core interfaces**: `calendar_client_api`, `ai_client_api`
- **Implementations**:
  - `google_calendar_client_impl` (direct Google Calendar implementation)
  - `google_calendar_service_adapter` (HTTP-backed calendar implementation through the deployed service)
  - `openai_ai_client_impl` (OpenAI-backed AI implementation)
- **FastAPI Service**: `google_calendar_service` (FastAPI app)
- **Generated API Client**: `google_calendar_service_api_client`
- **Cross-vertical integration**: Team 3 issue-tracker service adapter used by the AI workflow
- **Telemetry**: OpenTelemetry traces, metrics, and logs exported to Grafana Cloud via OTLP

---

## Repository Layout

```text
.
├── components/
│   ├── ai_client_api/                      # AI client interface
│   ├── calendar_client_api/                # Calendar interface, DTOs, registry, domain exceptions
│   ├── google_calendar_client_impl/        # Direct Google implementation
│   ├── google_calendar_service/            # FastAPI deployment/service boundary
│   ├── google_calendar_service_api_client/ # Generated typed HTTP client
│   ├── google_calendar_service_adapter/    # CalendarClient adapter over HTTP service
│   └── openai_ai_client_impl/              # OpenAI AI implementation
├── tests/                                  # Integration + e2e tests
├── docs/                                   # MkDocs source
├── infra/                                  # Terraform-managed Render deployment
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
| **pytest** | Test runner with coverage (>= 85% threshold) | `pytest` |
| **MkDocs** | Documentation site | `mkdocs serve` / `mkdocs build` |
| **CircleCI** | Continuous integration | Triggered on push (see `.circleci/config.yml`) |

```bash
# Sync workspace
uv sync --all-packages --extra dev

# Run tests; coverage settings are in pyproject.toml
uv run pytest --cov

# Run unit/integration/e2e subsets
uv run pytest components -m "not local_credentials"
uv run pytest tests/integration -m "not local_credentials"
uv run pytest tests/e2e -m "not local_credentials"

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

Tests are organized into three tiers using pytest markers and paths:

| Tier | Marker | What it covers |
|------|--------|----------------|
| **Unit** | `@pytest.mark.unit` | Component-level behavior, route logic, OAuth/session helpers, implementations, AI route/tool orchestration |
| **Integration** | `@pytest.mark.integration` | DI wiring, auto-registration, factory behavior, type hierarchies, error propagation |
| **E2E** | `@pytest.mark.e2e` | Full application workflows; live Google tests are marked `local_credentials` and skipped in CI |

### Running tests locally

```bash
# Run all tests
uv run pytest

# Run component/unit tests
uv run pytest components -m "not local_credentials"

# Run integration tests
uv run pytest tests/integration -m "not local_credentials"

# Run e2e tests safe for CI
uv run pytest tests/e2e -m "not local_credentials"

# Run with coverage report
uv run pytest --cov=components

# Run a specific test file
uv run pytest tests/integration/test_client_integration.py -v
```

## Telemetry

The FastAPI service is instrumented with the [OpenTelemetry](https://opentelemetry.io/) SDK and exports **traces, metrics, and logs** directly to [Grafana Cloud](https://grafana.com/products/cloud/) via OTLP. Metric names follow the [HTTP Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/http/http-metrics/).

- Request latency and total counts from the `http.server.request.duration` histogram.
- Success rate from requests with `http.response.status_code` in 2xx.
- Failure rate from requests with `http.response.status_code` in 4xx/5xx.

Telemetry is disabled if `OTEL_EXPORTER_OTLP_ENDPOINT` is not set. See `docs/telemetry.md` for setup instructions and PromQL queries.

**Grafana URL**: [https://grafanafreebee942.grafana.net](https://grafanafreebee942.grafana.net)

Dashboard panels and PromQL queries are documented in `docs/telemetry.md`. The dashboard should show request latency, success rate, and failure rate from the deployed service during the demo.

---

## AI Integration Overview

The service includes an AI orchestration layer powered by a provider-neutral `ai_client_api` interface with a concrete `openai_ai_client_impl` backed by OpenAI Chat Completions.

The `POST /ai/` endpoint accepts natural-language prompts and delegates to an AI agent (`agent.py`) that can call ten tools spanning calendar CRUD, issue-tracker operations, and cross-service scheduling workflows.

### Cross-Vertical Integration

The AI workflow integrates with **Team 3's issue-tracker service** (Trello-backed) through their shared `ospd-issue-tracker-api` interface. The dependency is declared in `pyproject.toml` as a Git source, and the issue-tracker client is injected via FastAPI's dependency system.

Available cross-service tools:

- `create_event_from_issue` — create a calendar event from an issue's metadata
- `schedule_issue_work_session` — find available calendar time and schedule a work block for an issue

---

## Infrastructure as Code (IaC)

Terraform configuration lives in `infra/` and provisions the Render web service, health check, and environment variables.

### Bootstrap

```bash
cd infra
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with real values (API keys, OAuth secrets, etc.)
terraform init
terraform plan -var-file=terraform.tfvars
terraform apply -var-file=terraform.tfvars
```

See `infra/terraform.tfvars.example` for the full list of required variables. Never commit `terraform.tfvars` — it is gitignored.

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
- `GOOGLE_CALENDAR_CLIENT_ID`
- `GOOGLE_CALENDAR_CLIENT_SECRET`
- `GOOGLE_CALENDAR_REFRESH_TOKEN`
- `GOOGLE_CALENDAR_TOKEN_URI` (optional; defaults to Google's token endpoint)

The direct implementation can also use `token.json`, or run interactive OAuth from `credentials.json` when `interactive=True`.

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

### AI Client (`openai_ai_client_impl`)

Used when your application imports `openai_ai_client_impl` and calls `get_client()`.

Required environment variables:
- `OPENAI_API_KEY`

Optional:
- `OPENAI_MODEL` (overrides the default model)

No OAuth flow is required. Authentication is handled via API key.

### Issue Tracker Integration

The AI workflow depends on Team 3's issue-tracker adapter through the shared issue-tracker API. Set:

- `ISSUE_TRACKER_SERVICE_URL`
- `ISSUE_TRACKER_SESSION_ID` (optional, when the issue tracker requires a session cookie)

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
- `GET /events/between`
- `GET /events/{event_id}`
- `POST /events/`
- `PATCH /events/{event_id}`
- `DELETE /events/{event_id}`
- `POST /ai/`

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

Render deployment is triggered by CircleCI's `deploy` job when the workflow runs on the configured branch and `RENDER_DEPLOY_HOOK` is available.

### 4) Set service URL

After deployment, the service base URL is: https://ospsd-team-11.onrender.com

Use this URL in clients or adapter registration:

```python
from google_calendar_service_adapter import register_service_calendar_client

register_service_calendar_client(base_url="https://ospsd-team-11.onrender.com")
```

The adapter can also read `CALENDAR_SERVICE_BASE_URL`, `CALENDAR_COOKIE_ID`, and `CALENDAR_COOKIE_VALUE` from the environment.

---
