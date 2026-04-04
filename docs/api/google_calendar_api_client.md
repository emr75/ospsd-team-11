# Google Calendar OpenAPI Client

`google_calendar_service_api_client` is the generated Python client for the FastAPI service in `google_calendar_service`.

It provides strongly typed request/response models and endpoint functions so application code (or adapters) can call the service without hand-writing HTTP requests.

---

## Role in the Architecture

This package is the **transport client layer** between:

- service consumers (for example, `google_calendar_service_adapter`)
- and the deployed FastAPI service (`google_calendar_service`)

It is generated from OpenAPI and should be treated as generated code.

---

## Dependencies

- `httpx`
- `attrs`
- `python-dateutil`

---

## Package Layout

- `google_calendar_service_client/client.py`  
  Core HTTP client classes (`Client`, `AuthenticatedClient`)
- `google_calendar_service_client/api/default/*`  
  Generated endpoint functions
- `google_calendar_service_client/models/*`  
  Typed request/response models
- `google_calendar_service_client/errors.py`  
  Error types such as `UnexpectedStatus`
- `google_calendar_service_client/types.py`  
  Shared generated helper types (`UNSET`, `Unset`, `Response`, etc.)

---

## Endpoint Function Modules

The generated default API modules include:

- `login_auth_login_get`
- `callback_auth_callback_get`
- `logout_auth_logout_post`
- `health_health_get`
- `list_events_events_get`
- `list_events_between_events_between_get`
- `get_event_events_event_id_get`
- `create_event_events_post`
- `update_event_events_event_id_patch`
- `delete_event_events_event_id_delete`

Each module generally exposes:

- `sync(...)`
- `sync_detailed(...)`
- `asyncio(...)`
- `asyncio_detailed(...)`

---

## Key Models

Commonly used generated models include:

- `EventCreateRequest`
- `EventUpdateRequest`
- `AttendeeRequest`
- `EventResponse`
- `EventsEnvelope`
- `EventEnvelope`
- `StatusResponse`
- validation models (`HttpValidationError`, `ValidationError`, etc.)

---

## Typical Usage

```python
from google_calendar_service_client import Client
from google_calendar_service_client.api.default import list_events_events_get

client = Client(base_url="http://localhost:8000")

events = list_events_events_get.sync(client=client, max_results=10)
```

For authenticated workflows requiring explicit token usage, use `AuthenticatedClient` instead.

---

## Notes

- This client is generated from OpenAPI; manual edits should be avoided because regeneration may overwrite them.
- Prefer updating service OpenAPI/schema and regenerating the client when API contracts change.
- The `google_calendar_service_adapter` package wraps this client to provide the domain-level `CalendarClient` interface.