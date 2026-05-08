# Component Definition

Every workspace component lives under `components/<component_name>/`. Each component is one of:

- a contract (implementation-independent interface)
- a concrete implementation of a contract
- a service boundary
- a generated transport client
- a transport adapter

Components are designed to be wired together via dependency injection (DI) so the rest of the codebase depends only on contracts.

## Current Components

| Component | Kind | Role |
|-----------|------|------|
| `calendar_client_api` | Contract | Calendar ABC, event DTOs, exceptions, and DI registry |
| `ai_client_api` | Contract | AI ABC and DI registry |
| `google_calendar_client_impl` | Provider adapter | Direct Google Calendar implementation; also satisfies the shared `ospsd-calendar-api` interface |
| `google_calendar_service` | Service | FastAPI health/auth/event/AI routes, OAuth sessions, issue-tracker integration, telemetry |
| `google_calendar_service_api_client` | Generated client | OpenAPI-generated Python client for health/auth/event routes |
| `google_calendar_service_adapter` | Transport adapter | `CalendarClient` implementation over the generated service client |
| `openai_ai_client_impl` | Provider adapter | OpenAI Chat Completions implementation of `AiClient` |


## Directory Layout

Each component follows this structure:

```text
components/<component_name>/
├── pyproject.toml
├── README.md
├── src/<component_name>/
│   ├── __init__.py
│   ├── client.py     # contracts / public types live here (if applicable)
│   ├── event.py      # shared event contract/types (if applicable)
│   ├── registry.py   # DI registry (if applicable)
│   ├── client_impl.py# concrete implementations live here (for impl components only)
│   └── event_impl.py # concrete implementations live here (for impl components only)
└── tests/            # optional component-scoped tests
```

## pyproject.toml Checklist
- `[project]`: align `name` with the folder, set `version`, `description`, `readme = "README.md"`, `requires-python = ">=3.13"`, and list direct dependencies.
- `[build-system]`: keep hatchling as the backend.
- `[tool.uv.sources]`: declare workspace dependencies when another component is required.

## README Expectations
Document, at minimum: component’s role, scope, factory functions (if any), and component dependencies. Keep examples using absolute imports.

## Implementation Notes (_impl.py)

Place concrete classes here so `__init__.py` can focus on exports and dependency injection wiring.

## Package Initialisation (`__init__.py`)
- Contract packages: export the ABC and registry helpers.
- Implementation and adapter packages: import the contract, handle provider-specific configuration, and register themselves with the relevant DI registry on import when appropriate.
- Generated packages: expose generated client/model modules and should not contain hand-written business logic.

## Testing

Component-level tests belong in tests/. Target the public interface, use mocks to isolate external services, and keep fixtures local to the component.
