# google_calendar_service_adapter

## Role

Implements the `calendar_client_api` interface over HTTP by adapting calls to the generated `google_calendar_service_client`.  
This component lets consumers use `get_client()` and the same domain contract (`Event`, `EventCreate`, `EventUpdate`) while delegating all operations to the deployed FastAPI service.

## Dependencies

| Package | Purpose |
|---------|---------|
| `calendar-client-api` | Abstract interface and DI registry |
| `google-calendar-service-client` | Auto-generated HTTP client for service endpoints |

## Public API

| Export | Type | Description |
|--------|------|-------------|
| `ServiceCalendarClient` | class | Implements `CalendarClient` by calling the service over HTTP |
| `ServiceCalendarEvent` | class | Implements `Event` by wrapping generated `EventResponse` models |
| `register_service_calendar_client(base_url=...)` | function | Registers a factory in `calendar_client_api` that returns `ServiceCalendarClient` |

## Behavior

- Converts domain DTOs (`EventCreate`, `EventUpdate`) to generated request models.
- Converts generated response models back to domain event objects.
- Translates transport/service errors into domain exceptions (`AuthorizationError`, `EventNotFoundError`, `ValidationError`, `ServiceUnavailableError`, `CalendarClientError`).
- Automatically registers itself on import using default base URL `http://localhost:8000`.

## DI Auto-Registration

On import, this package registers:

- `calendar_client_api.register_client(lambda: ServiceCalendarClient(base_url=...))`

That means consumers can do:

```python
import google_calendar_service_adapter
from calendar_client_api import get_client

client = get_client()  # returns ServiceCalendarClient
```

## Configuration

If your service runs at a different URL, register explicitly:

```python
import google_calendar_service_adapter
from google_calendar_service_adapter import register_service_calendar_client

register_service_calendar_client(base_url="http://google-calendar-service:8000")
```
