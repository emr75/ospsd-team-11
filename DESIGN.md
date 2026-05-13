# Design Document

## Overview

This project implements a calendar client platform with a stable local interface, a Google Calendar implementation, an HTTP service layer, a generated service client, a service-backed implementation, and an AI workflow layer.

The original calendar interface and Google implementation still work locally:

- **`calendar_client_api`** - abstract interface, event DTOs, domain exceptions, and dependency injection registry
- **`google_calendar_client_impl`** - concrete implementation backed by the Google Calendar API

The service layer makes the same calendar behavior available over HTTP:

- **`google_calendar_service`** - FastAPI service for OAuth, sessions, calendar event endpoints, AI workflow endpoints, and telemetry
- **`google_calendar_service_api_client`** - type-safe Python client generated from the service's OpenAPI spec
- **`google_calendar_service_adapter`** - service-backed implementation of the original `CalendarClient` interface using the generated client

The AI layer adds natural-language workflows on top of the calendar and issue-tracker integrations:

- **`ai_client_api`** - abstract interface for simple AI prompts and tool-calling workflows
- **`openai_ai_client_impl`** - OpenAI Chat Completions implementation of the AI interface

The central design goal is **implementation transparency**: consumer code can use the same `CalendarClient` interface whether calendar operations run in-process against Google Calendar or remotely through the FastAPI service.

---

## Architecture

```text
Local calendar path:
Consumer -> calendar_client_api.get_client()
         -> GoogleCalendarClient
         -> Google Calendar API

Remote calendar path:
Consumer -> calendar_client_api.get_client()
         -> ServiceCalendarClient
         -> google_calendar_service_client (generated, httpx)
         -> google_calendar_service (FastAPI)
         -> GoogleCalendarClient
         -> Google Calendar API

AI workflow path:
Consumer -> POST /ai/
         -> google_calendar_service
         -> OpenAiClient
         -> service tool handlers
         -> CalendarClient + Team 3 issue tracker client
```

In both calendar paths, the consumer-facing code is the same:

```python
# Local Google implementation
import google_calendar_client_impl
from calendar_client_api import EventCreate, get_client

client = get_client()  # returns GoogleCalendarClient
event = client.create_event_from_dto(EventCreate(title="Meeting", ...))
```

```python
# Remote service-backed implementation
import google_calendar_service_adapter
from calendar_client_api import EventCreate, get_client

client = get_client()  # returns ServiceCalendarClient
event = client.create_event_from_dto(EventCreate(title="Meeting", ...))
```

Only the imported implementation package changes. The registered DI factory switches transparently.

---

## Repository and Tooling Alignment

### Repository Process

The repository keeps the inherited project structure:

- implementation packages live under `components/`
- component-local unit tests live under each component's `tests/`
- integration and e2e tests live under root `tests/`
- documentation lives under `docs/` plus root `README.md` and `DESIGN.md`
- deployment configuration lives under `infra/`
- PR and issue templates live under `.github/`

The PR template explicitly asks reviewers to confirm the `hw-3` target branch, commit hygiene, repository layout, workspace membership, root-only lint/type configuration, and shared-interface impact.

### Tooling Configuration

The root `pyproject.toml` owns workspace membership, ruff configuration, mypy configuration, pytest markers, and coverage thresholds.

Current workspace members:

- `components/ai_client_api`
- `components/calendar_client_api`
- `components/google_calendar_client_impl`
- `components/google_calendar_service`
- `components/google_calendar_service_api_client`
- `components/google_calendar_service_adapter`
- `components/openai_ai_client_impl`

Generated code under `components/google_calendar_service_api_client` is excluded from ruff and mypy at the root because it is OpenAPI-generated. Team 3 packages do not ship `py.typed`, so import sites use narrowly scoped `# type: ignore[import-untyped]` comments instead of disabling strict type checking globally.

---

## Component A: `calendar_client_api`

### Responsibility

Define the stable calendar interface used by application code and implementations. This package has no Google, FastAPI, OpenAI, or generated-client dependencies.

### Public Surface

| Type / Function | Role |
|-----------------|------|
| `CalendarClient` | Abstract interface for calendar operations |
| `Event` | Abstract event representation |
| `Attendee` | Event attendee value object |
| `EventCreate` | DTO for creating events |
| `EventUpdate` | DTO for partial updates |
| `UNSET` | Sentinel used to distinguish omitted update fields from explicit `None` |
| `register_client(factory)` | Registers a `Callable[[], CalendarClient]` |
| `get_client()` | Returns a new client from the registered factory |
| domain exceptions | `CalendarClientError`, `AuthorizationError`, `EventNotFoundError`, `ValidationError`, `ServiceUnavailableError` |

### Calendar Interface

The current `CalendarClient` methods are:

| Method | Purpose |
|--------|---------|
| `create_event_from_dto(event_create)` | Create an event from an `EventCreate` DTO |
| `get_event_by_id(event_id)` | Fetch one event |
| `list_upcoming_events(max_results=10)` | List upcoming events |
| `list_events_between(start, end)` | List events in a datetime range |
| `update_event_from_patch(event_id, event_patch)` | Patch an event with `EventUpdate` |
| `delete_event(event_id)` | Delete an event |

---

## Component B: `google_calendar_client_impl`

### Responsibility

Provide the direct Google Calendar implementation of the `CalendarClient` interface. This package handles Google authentication, Google Calendar API payload construction, provider response parsing, and compatibility with the shared `ospsd-calendar-api` interface.

### Authentication Flow

`GoogleCalendarClient` authenticates through a three-step chain, stopping at the first success:

1. **Environment variables** - `GOOGLE_CALENDAR_CLIENT_ID`, `GOOGLE_CALENDAR_CLIENT_SECRET`, `GOOGLE_CALENDAR_REFRESH_TOKEN`, and optional `GOOGLE_CALENDAR_TOKEN_URI`.
2. **Token file** - a previously saved `token.json` with OAuth credentials.
3. **Interactive OAuth** - browser-based login using `credentials.json` when `interactive=True`.

No credentials are hardcoded. Secrets come from environment variables or ignored local credential files.

### Event Translation

Google Calendar payloads are converted into `GoogleCalendarEvent`, which implements the shared `Event` interface.

Important translation behavior:

- Google `summary` becomes `Event.title`.
- Google `start.dateTime` / `end.dateTime` become timezone-aware datetimes.
- All-day `date` values are normalized to midnight UTC.
- Google attendees are converted into `Attendee(email, name)`.
- Google attachments are exposed as attachment URL strings.

### Shared Interface Compatibility

`GoogleCalendarClient` also implements the shared `ospsd-calendar-api` calendar interface. Those methods are thin wrappers over this project's DTO-based methods, allowing cross-team code to use the same implementation.

---

## Component C: `google_calendar_service`

### Responsibility

Deploy the calendar implementation as a standalone FastAPI service. The service handles browser OAuth, session management, event CRUD endpoints, AI workflow endpoints, and OpenTelemetry setup.

### Module Breakdown

| Module | Role |
|--------|------|
| `main.py` | Creates the FastAPI app, configures OpenTelemetry, redirects `/` to `/docs`, and includes routers |
| `routes/auth_routes.py` | `/auth/login`, `/auth/callback`, `/auth/logout` |
| `routes/event_routes.py` | Calendar event endpoints |
| `routes/ai_routes.py` | Natural-language AI workflow endpoint |
| `routes/health_routes.py` | Health check endpoint |
| `models.py` | Pydantic request/response models and conversion helpers |
| `deps.py` | Dependency providers for calendar, AI, and issue-tracker clients |
| `settings.py` | Environment-backed OAuth and session settings |
| `oauth_utils.py` | PKCE/state helpers and OAuth token exchange |
| `session_store.py` | Session data model, cookie frontend, backend, verifier |
| `otel.py` | OpenTelemetry traces, metrics, and logs setup |
| `integrations/agent.py` | AI system prompt and turn orchestration |
| `integrations/tools.py` | AI tool definitions and dispatch handlers |
| `integrations/issue_to_calendar.py` | Shared issue-to-calendar event construction flow |

### Authorization Flow

The service uses Google OAuth through a browser flow:

1. `GET /auth/login` creates a session, stores an OAuth state value and PKCE verifier, and redirects the browser to Google's OAuth consent page.
2. The user grants access on Google.
3. Google redirects to `GET /auth/callback?code=...&state=...`.
4. The callback endpoint validates and consumes the stored state, exchanges the authorization code for tokens, and stores the token data in the session.
5. The session cookie is sent with later event requests.
6. `get_calendar_client` reads the session token data, builds a `CredentialsToken`, and returns a session-scoped `GoogleCalendarClient`.

Event routes require a valid session with non-expired OAuth tokens. Missing or invalid sessions return HTTP auth errors before calendar logic runs.

### REST Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Redirects to FastAPI docs |
| `GET` | `/health` | Returns service status |
| `GET` | `/auth/login` | Starts Google OAuth login |
| `GET` | `/auth/callback` | Handles OAuth callback and stores tokens |
| `POST` | `/auth/logout` | Clears token state and deletes session cookie |
| `GET` | `/events/` | Lists upcoming events |
| `GET` | `/events/between` | Lists events in a datetime range |
| `GET` | `/events/{event_id}` | Gets one event |
| `POST` | `/events/` | Creates an event |
| `PATCH` | `/events/{event_id}` | Partially updates an event |
| `DELETE` | `/events/{event_id}` | Deletes an event |
| `POST` | `/ai/` | Runs an AI-assisted calendar/issue workflow |

### AI Workflow

The `/ai/` endpoint accepts:

```json
{
  "prompt": "Schedule work time for issue 42 tomorrow afternoon",
  "context": {
    "timezone": "America/New_York"
  }
}
```

The service injects three clients:

- `AiClient` from `openai_ai_client_impl`
- session-scoped `CalendarClient`
- Team 3 issue-tracker client from `issue_tracker_client_adapter`

Available AI tools:

| Category | Tools |
|----------|-------|
| Calendar | `create_event`, `list_events`, `update_event` |
| Issue tracker | `list_issue_boards`, `list_issues`, `get_issue`, `create_issue`, `update_issue` |
| Cross-service | `create_event_from_issue`, `schedule_issue_work_session` |

`schedule_issue_work_session` fetches an issue, checks calendar availability in the requested window, creates an event in the first available slot, and can optionally move the issue to `in_progress`.

Issue deletion is intentionally not exposed to the model.

### Telemetry

The service emits OpenTelemetry signals over OTLP/HTTP when `OTEL_EXPORTER_OTLP_ENDPOINT` is set:

- traces from FastAPI request instrumentation
- metrics from `http.server.request.duration`
- logs bridged from Python logging

If `OTEL_EXPORTER_OTLP_ENDPOINT` is unset, telemetry is disabled and the service still starts normally.

### Deployment

The service runs from the root `Dockerfile` with Uvicorn on port 8000. The Dockerfile uses a multi-stage build with `uv` to install the `google-calendar-service` package and runtime dependencies.

Terraform in `infra/` manages the Render web service, health check path, and non-secret environment variables. Secret env vars (API keys, OAuth secrets, tokens) are set manually in the Render dashboard to keep them out of the Terraform state file. CircleCI runs linting, type checking, tests, and can trigger Render deployment through `RENDER_DEPLOY_HOOK`.

Important runtime environment variables:

| Variable | Purpose |
|----------|---------|
| `GOOGLE_CALENDAR_CLIENT_ID` | Google OAuth client ID |
| `GOOGLE_CALENDAR_CLIENT_SECRET` | Google OAuth client secret |
| `GOOGLE_CALENDAR_REDIRECT_URI` | OAuth callback URL |
| `GOOGLE_CALENDAR_SCOPES` | Requested Google Calendar scopes |
| `GOOGLE_CALENDAR_SESSION_SECRET` | Session signing secret |
| `GOOGLE_CALENDAR_SESSION_COOKIE_SECURE` | Whether session cookie requires HTTPS |
| `OPENAI_API_KEY` | OpenAI API key |
| `OPENAI_MODEL` | Optional OpenAI model override |
| `ISSUE_TRACKER_SERVICE_URL` | Team 3 issue-tracker service base URL |
| `ISSUE_TRACKER_SESSION_ID` | Optional issue-tracker session cookie |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Enables OpenTelemetry export when set |
| `OTEL_EXPORTER_OTLP_HEADERS` | OTLP auth headers, for example Grafana Cloud auth |

---

## Component D: `google_calendar_service_api_client`

### Responsibility

Provide a type-safe Python library for calling the FastAPI service over HTTP. The client is auto-generated from the service's OpenAPI schema and should not contain hand-written business logic.

### Generation

FastAPI generates an OpenAPI spec from route definitions and Pydantic models. The generated client turns each endpoint into typed Python functions and attrs-based models.

The checked-in generated client currently covers:

- health endpoint
- auth endpoints
- calendar event endpoints

The service's newer `/ai/` endpoint is not represented in the generated client yet.

### Structure

| Path | Contents |
|------|----------|
| `google_calendar_service_client/api/default/` | One module per generated endpoint |
| `google_calendar_service_client/models/` | attrs-based request/response models |
| `google_calendar_service_client/client.py` | Generated `Client` and `AuthenticatedClient` helpers around `httpx` |
| `google_calendar_service_client/types.py` | Shared generated helpers such as `UNSET`, `Unset`, and `Response` |
| `google_calendar_service_client/errors.py` | Generated error types such as `UnexpectedStatus` |

Each generated endpoint module generally exposes:

- `sync(...)`
- `sync_detailed(...)`
- `asyncio(...)`
- `asyncio_detailed(...)`

### Why Excluded from Ruff and Mypy

Generated code often does not follow the same style as hand-written project code and can produce false-positive lint or type-checking issues. The root `pyproject.toml` excludes `components/google_calendar_service_api_client` from ruff and mypy. The service-backed implementation hides generated code from normal consumers.

### Testing

This package is tested indirectly. Service-backed implementation tests patch generated endpoint modules to verify delegation, response unwrapping, and error translation without making real HTTP calls.

---

## Component E: `google_calendar_service_adapter`

### Responsibility

Make the remote service look like the local calendar implementation from the consumer's perspective. `ServiceCalendarClient` implements the original `CalendarClient` interface and delegates to the generated service client.

### Service-Backed Implementation

`ServiceCalendarClient` creates a generated `Client` with:

- `base_url` for the running service
- optional session cookie for authenticated requests
- `follow_redirects=True` so FastAPI slash redirects are transparent
- `raise_on_unexpected_status=True` so HTTP failures can be translated into domain exceptions

Each interface method performs three steps:

1. Convert interface DTOs into generated request models.
2. Call the matching generated endpoint function.
3. Convert generated response models back into interface objects.

Example:

```python
def create_event_from_dto(self, event_create: EventCreate) -> ServiceCalendarEvent:
    body = EventCreateRequest(
        title=event_create.title,
        start_time=event_create.start_time,
        end_time=event_create.end_time,
        attendees=[
            AttendeeRequest(email=a.email, name=a.name if a.name is not None else GEN_UNSET)
            for a in event_create.attendees
        ],
        attachments=event_create.attachments,
        description=event_create.description if event_create.description is not None else GEN_UNSET,
        location=event_create.location if event_create.location is not None else GEN_UNSET,
    )
    response = create_event_events_post.sync(client=self._client, body=body)
    return self._unwrap_event_envelope(response)
```

`ServiceCalendarEvent` wraps generated `EventResponse` objects and implements the original `Event` interface. It also converts generated `Unset` values back to `None` for optional fields.

### Error Translation

Generated-client and transport errors are translated into calendar domain exceptions:

| HTTP / Transport Failure | Domain Exception |
|--------------------------|------------------|
| `401` / `403` | `AuthorizationError` |
| `404` with event ID | `EventNotFoundError` |
| `422` | `ValidationError` |
| `5xx` | `ServiceUnavailableError` |
| `httpx` connection/timeout errors | `ServiceUnavailableError` |
| Other unexpected statuses | `CalendarClientError` |

### DI Auto-Registration

`google_calendar_service_adapter.__init__` registers the service-backed factory at import time:

```python
calendar_client_api.register_client(
    lambda: ServiceCalendarClient(base_url=base_url, cookie=cookie)
)
```

Configuration can be supplied explicitly or through environment variables:

| Variable | Purpose |
|----------|---------|
| `CALENDAR_SERVICE_BASE_URL` | Service base URL; defaults to `http://localhost:8000` |
| `CALENDAR_COOKIE_ID` | Session cookie name |
| `CALENDAR_COOKIE_VALUE` | Session cookie value |

---

## Component F: `ai_client_api`

### Responsibility

Define the stable AI interface needed by service workflows. This package has no OpenAI dependency.

### Interface

| Method | Purpose |
|--------|---------|
| `send_message(prompt, context=None)` | Send a simple prompt and return a text response |
| `run_chat_with_tools(system_prompt, user_message, tools, handle_tool, max_tool_rounds=8)` | Run a tool-calling loop and return the final assistant message |

The service owns tool definitions and dispatch. The AI implementation only needs to call the model and pass model-requested tool calls to `handle_tool`.

---

## Component G: `openai_ai_client_impl`

### Responsibility

Implement `AiClient` using the OpenAI Chat Completions API.

### Behavior

- `send_message(...)` sends a system prompt plus one user message and returns plain text.
- `run_chat_with_tools(...)` sends service-defined tool schemas to the model, executes requested tool calls through a callback, appends tool results, and repeats until the model returns final text.
- The loop stops after `max_tool_rounds` and returns a limit message if the model does not finish.

### Configuration

| Variable | Purpose |
|----------|---------|
| `OPENAI_API_KEY` | Required API key |
| `OPENAI_MODEL` | Optional model override; defaults to `gpt-4o-mini` |

---

## Component Dependency Graph

| Component | Depends On |
|-----------|------------|
| `calendar_client_api` | Python stdlib |
| `ai_client_api` | Python stdlib |
| `google_calendar_client_impl` | `calendar_client_api`, `ospsd-calendar-api`, Google auth/API packages, `python-dotenv` |
| `google_calendar_service` | `calendar_client_api`, `google_calendar_client_impl`, `ai_client_api`, `openai_ai_client_impl`, Team 3 issue-tracker packages, FastAPI, `httpx`, OpenTelemetry |
| `google_calendar_service_api_client` | `httpx`, `attrs`, `python-dateutil` |
| `google_calendar_service_adapter` | `calendar_client_api`, `google_calendar_service_client` |
| `openai_ai_client_impl` | `ai_client_api`, `openai` |

Note: `google_calendar_service_adapter` does not import the FastAPI service implementation. It only speaks HTTP to a service URL through the generated client.

---

## Design Decisions

### Interface Package Has No Provider Dependencies

`calendar_client_api` remains independent of Google Calendar, FastAPI, and the generated service client. This keeps consumer code stable and allows multiple implementations to satisfy the same interface.

### Service Session Storage

The service uses `fastapi-sessions` with an in-memory backend. This is simple and works for local development and small deployments. The trade-off is that sessions are lost on service restart. A production version should use Redis or another shared session store.

### OAuth State and PKCE

The service stores OAuth state and PKCE verifier data in the session before redirecting to Google. The callback validates and consumes the stored handshake before token exchange, reducing CSRF and replay risk.

### Generated Client vs. Hand-Written HTTP Client

Auto-generation keeps Python models and endpoint functions aligned with the FastAPI OpenAPI schema. The trade-off is verbose generated code that is excluded from ruff and mypy. The service-backed implementation hides that generated code from consumers.

### Separate HTTP Models and Interface DTOs

The service uses Pydantic request/response models for the HTTP wire format and converts them to interface DTOs before calling `CalendarClient`. This separation prevents HTTP concerns from leaking into the calendar interface.

### AI Tool Dispatch Lives in the Service

OpenAI-specific code does not create calendar events or issue-tracker records directly. The service defines tool schemas and dispatch handlers, so model behavior can be tested with fake calendar and issue clients.

### No Destructive Issue Tools

Issue deletion is intentionally unavailable to the AI tool loop. The service exposes read, create, update, and scheduling workflows, but avoids destructive issue operations.

### Direct OTLP Export

The service exports traces, metrics, and logs directly to Grafana Cloud through OTLP/HTTP when configured. No collector sidecar is required for the current deployment.

---

## Testing Strategy

Testing is split by component and by runtime scope.

### Component Tests

| Component | Tests |
|-----------|-------|
| `calendar_client_api` | ABC contract, registry behavior, DTOs, exceptions |
| `ai_client_api` | Registry behavior and interface selection |
| `google_calendar_client_impl` | Authentication chain, CRUD serialization, event parsing, shared interface compatibility |
| `google_calendar_service` | FastAPI routes, OAuth flow, session store, settings, AI route, tool dispatch, issue-to-calendar flow |
| `google_calendar_service_adapter` | DTO conversion, generated-client delegation, envelope unwrapping, error translation |
| `openai_ai_client_impl` | Simple prompt behavior and tool-loop behavior with mocked OpenAI SDK responses |

### Integration Tests

Integration tests in `tests/integration/` verify cross-component behavior:

- implementation packages register themselves with the DI registry
- `get_client()` returns an object satisfying the expected interface
- direct implementation and service-backed implementation keep compatible behavior
- error propagation remains consistent across boundaries

### End-to-End Tests

E2E tests live in `tests/e2e/`:

- `test_application_ci.py` runs the full CRUD lifecycle against a mocked Google service resource and is safe for CI.
- `test_application.py` runs against the real Google Calendar API using local credentials and is marked `local_credentials`, so it is skipped in CI.

### CI

CircleCI installs the workspace with `uv`, then runs:

- `ruff check .`
- `mypy .`
- component tests with coverage
- integration tests
- e2e tests that do not require local credentials
- a summary/report job
- optional Render deployment through `RENDER_DEPLOY_HOOK`

Coverage has a project threshold of 85%.

---

## Cross-Vertical Integration

### Choice of Vertical

We integrate with the **issue-tracker vertical** (Team 3's Trello-backed service). Calendar and issue tracking are natural complements: users schedule meetings about issues, block focus time for ticket work, and track issue status alongside their calendar.

### Dependency Wiring

Team 3 publishes two packages:

| Package | Purpose |
|---------|---------|
| `ospd-issue-tracker-api` | Shared ABC (`Client`) with domain types (`Issue`, `Board`, `Status`) |
| `issue-tracker-client-adapter` | `ServiceClientAdapter` that calls Team 3's deployed HTTP service |

Both are declared as Git sources in root `pyproject.toml`:

```toml
ospd-issue-tracker-api = { git = "...", branch = "main" }
issue-tracker-client-adapter = { git = "...", branch = "hw-3", subdirectory = "components/issue_tracker_client_adapter" }
```

The adapter is injected via FastAPI's `Depends()` in `deps.py`. The issue-tracker client is constructed from `ISSUE_TRACKER_SERVICE_URL` and an optional `ISSUE_TRACKER_SESSION_ID` environment variable.

### Type Checking

Team 3's packages do not ship a `py.typed` marker, so mypy treats them as untyped. Each import site uses a narrowly scoped `# type: ignore[import-untyped]` with an inline comment explaining the reason, rather than a blanket module-level exclusion.

---

## Observability Strategy

### Instrumentation

The FastAPI service is instrumented with the [OpenTelemetry](https://opentelemetry.io/) SDK. The `otel.py` module configures three signal pipelines — traces, metrics, and logs — each exported via OTLP/HTTP to Grafana Cloud.

| Signal | Source | Backend |
|--------|--------|---------|
| Traces | `FastAPIInstrumentor` auto-instrumentation | Grafana Tempo |
| Metrics | `http.server.request.duration` histogram (HTTP Semantic Conventions) | Grafana Prometheus |
| Logs | Python `logging` bridged into OTLP, correlated with active trace | Grafana Loki |

### Key Metrics

- **Request latency**: derived from the `http.server.request.duration` histogram, broken down by route, method, and status code.
- **Success rate**: ratio of 2xx responses to total requests.
- **Failure rate**: ratio of 4xx/5xx responses to total requests, distinguishing client errors (domain validation) from server errors (infrastructure failures).

### Deployment

Telemetry is configured entirely through standard OTEL environment variables (`OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_EXPORTER_OTLP_HEADERS`, etc.). The app exports directly to Grafana Cloud — no collector sidecar is needed. If `OTEL_EXPORTER_OTLP_ENDPOINT` is unset, telemetry is silently disabled and the service starts normally.

### Dashboard

The Grafana Cloud dashboard visualizes latency percentiles, success/failure rates, and per-route breakdowns. See `docs/telemetry.md` for PromQL queries.

---

## Adaptation Plan: Standardized `ospsd-calendar-api` Interface

### Context

The shared `ospsd-calendar-api` package defines a cross-team standardized calendar interface. Our codebase already has its own local interface (`calendar_client_api`) from the first calendar implementation. This section describes how we adapted our implementation to satisfy the standardized contract while preserving backward compatibility with our existing call sites.

The shared interface lives in its own package. It uses Python ABCs and provider-agnostic domain types. Our implementation consumes that package as a Git dependency and makes `GoogleCalendarClient` satisfy the shared contract.

### Interface Comparison

| Aspect | Local `calendar_client_api` | Shared `ospsd-calendar-api` |
|--------|---------------------------|----------------------------|
| Event model | Abstract `Event` ABC with `@property` methods | Concrete `Event` dataclass |
| Extra fields | `attendees`, `attachments` | Not present |
| Create API | `create_event_from_dto(EventCreate)` | `create_event(title, start_time, end_time, ...)` |
| Read (single) | `get_event_by_id(event_id)` | `get_event(event_id)` |
| Read (range) | `list_events_between(start, end)` | `list_events(start, end)` |
| Read (upcoming) | `list_upcoming_events(max_results)` | Not present |
| Update API | `update_event_from_patch(event_id, EventUpdate)` with `UNSET` sentinel | `update_event(event_id, *, title=None, ...)` with `None` = unchanged |
| Delete API | `delete_event(event_id)` | `delete_event(event_id)` (identical) |
| Exception hierarchy | `CalendarClientError` → `EventNotFoundError`, `AuthorizationError`, `ValidationError`, `ServiceUnavailableError` | `CalendarError` → `EventNotFoundError`, `CalendarOperationError` |

### Approach: Dual-Interface Implementation

Since our local interface is essentially a richer superset of the shared interface, we have `GoogleCalendarClient` extend both ABCs:

```python
from calendar_client_api import CalendarClient
from ospsd_calendar_api import CalendarClient as SharedCalendarClient

class GoogleCalendarClient(CalendarClient, SharedCalendarClient):
    ...
```

The five shared-interface methods are implemented as thin adapters that delegate to the existing local-interface methods:

| Shared method | Delegates to |
|---------------|-------------|
| `list_events(start, end)` | `list_events_between(start, end)` + event conversion |
| `get_event(event_id)` | `get_event_by_id(event_id)` + event conversion |
| `create_event(title, start_time, ...)` | `create_event_from_dto(EventCreate(...))` + event conversion |
| `update_event(event_id, *, title, ...)` | `update_event_from_patch(event_id, EventUpdate(...))` + event conversion |
| `delete_event(event_id)` | Identical signature, shared directly through MRO |

### Event Model Conversion

The local `Event` is an abstract ABC with property methods, while the shared `Event` is a concrete frozen dataclass. A private `_event_to_shared_event` function bridges the two:

```python
def _event_to_shared_event(event: Event) -> SharedEvent:
    return SharedEvent(
        id=event.id,
        title=event.title,
        start_time=event.start_time,
        end_time=event.end_time,
        description=event.description,
        location=event.location,
    )
```

The `attendees` and `attachments` fields from the local model are dropped during conversion because the shared contract does not include them.

### Update Semantics Translation

The shared interface uses `None` to mean "don't change this field," while the local interface uses an `UNSET` sentinel for the same purpose (allowing `None` to explicitly clear a field). The adapter translates between the two conventions:

```python
def update_event(self, event_id, *, title=None, ...):
    patch = EventUpdate(
        title=UNSET if title is None else title,
        ...
    )
    event = self.update_event_from_patch(event_id, patch)
    return _event_to_shared_event(event)
```

This means the shared interface cannot express "set description to null" — only "don't change it." This is an acceptable limitation because the shared contract does not distinguish the two cases.

### Breaking Changes to Call Sites

No existing call sites break. All changes are additive:

1. **`GoogleCalendarClient` class declaration** — added `SharedCalendarClient` as a second base class. Existing code that uses `CalendarClient` (the local ABC) is unaffected because the new base class adds methods rather than removing them.

2. **New methods on the implementation** — `list_events`, `get_event`, `create_event`, and `update_event` are new methods that did not exist before. They do not shadow any local-interface method because we deliberately named the local methods differently (`list_events_between`, `get_event_by_id`, `create_event_from_dto`, `update_event_from_patch`).

3. **`delete_event` signature** — both interfaces define `delete_event(event_id: str) -> None` with compatible signatures. Python MRO resolves this without conflict.

4. **New dependency** — `ospsd-calendar-api` is added to `google_calendar_client_impl`'s dependencies in `pyproject.toml`. This is a build-time addition, not a runtime behavior change.

5. **Exception mapping** — callers using the shared interface receive `CalendarOperationError` or `EventNotFoundError` from `ospsd_calendar_api.exceptions`. Internal call sites using the local interface still receive exceptions from `calendar_client_api.exceptions`. Both hierarchies coexist.

### What Is Not Covered by the Shared Interface

| Local-only capability | Why it is retained |
|-----------------------|-------------------|
| `list_upcoming_events(max_results)` | Used by the AI agent tools for quick "what's next" queries without specifying a date range |
| `Attendee` / `attendees` field | Used by `EventCreate` for meeting invitations; the shared contract omits attendees |
| `attachments` field | Used by `EventCreate` for Google Calendar file attachments |
| `UNSET` sentinel on `EventUpdate` | Allows "set to None" vs "don't change" distinction for partial updates |
| `ServiceCalendarClient` (adapter) | Service-backed implementation that talks to the FastAPI service over HTTP; uses the local interface only |

These capabilities remain available through the local `CalendarClient` interface. Cross-team code that only needs the standardized operations uses `SharedCalendarClient`.
