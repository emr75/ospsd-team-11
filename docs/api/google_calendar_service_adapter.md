# Google Calendar Service Adapter

`google_calendar_service_adapter` provides an adapter implementation of the `calendar_client_api` port by calling the deployed FastAPI service over HTTP through the generated OpenAPI client.

## Role

This component is the **service-backed adapter** in the ports/adapters architecture:

- **Port**: `calendar_client_api.CalendarClient`
- **Adapter**: `google_calendar_service_adapter.ServiceCalendarClient`
- **Transport client**: `google_calendar_service_client` (generated from OpenAPI)

It allows application code to keep using `get_client()` and domain models while delegating execution to a remote service.

## Dependencies

- `calendar-client-api` — domain interfaces, DTOs, and exception types
- `google-calendar-service-client` — generated HTTP client for service endpoints

## Public API

### `ServiceCalendarClient`

Concrete implementation of `calendar_client_api.client.CalendarClient` over HTTP.

::: google_calendar_service_adapter.client_adapter.ServiceCalendarClient
    options:
      show_root_heading: true
      show_source: true

### `ServiceCalendarEvent`

Concrete implementation of `calendar_client_api.event.Event` by wrapping generated service response models.

::: google_calendar_service_adapter.event_adapter.ServiceCalendarEvent
    options:
      show_root_heading: true
      show_source: true

### `register_service_calendar_client(base_url=...)`

Registers `ServiceCalendarClient` in the global `calendar_client_api` registry.

::: google_calendar_service_adapter.register_service_calendar_client
    options:
      show_root_heading: true
      show_source: true

## Error Mapping Behavior

`ServiceCalendarClient` translates transport/service errors into domain exceptions defined in `calendar_client_api.exceptions`, including:

- `AuthorizationError`
- `EventNotFoundError`
- `ValidationError`
- `ServiceUnavailableError`
- `CalendarClientError`

This keeps calling code independent of HTTP-layer exception details.

## Auto-Registration

Importing `google_calendar_service_adapter` auto-registers the adapter with default base URL:

- `http://localhost:8000`

So consumers can do:

```python
import google_calendar_service_adapter
from calendar_client_api import get_client

client = get_client()
```

## Custom Service URL

To target a non-default deployment URL, explicitly re-register:

```python
from google_calendar_service_adapter import register_service_calendar_client

register_service_calendar_client(base_url="https://your-service.example.com")
```
