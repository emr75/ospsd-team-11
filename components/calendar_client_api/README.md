# calendar_client_api

## Role

Defines the abstract interface, event DTOs, domain exceptions, and dependency injection registry for calendar operations. This package contains no concrete implementation and has zero external dependencies.

## Dependencies

None (Python stdlib only)

## Public API

| Export | Type | Description |
|--------|------|-------------|
| `CalendarClient` | ABC | Abstract base class with six methods for create, get, list upcoming, list between, patch update, and delete |
| `Event` | ABC | Abstract base class with properties: `id`, `title`, `start_time`, `end_time`, `description`, `location`, `attendees`, `attachments` |
| `EventCreate` | dataclass | DTO for creating events (title, start/end time, attendees, attachments, description, location) |
| `EventUpdate` | dataclass | DTO for partial updates using an `UNSET` sentinel to distinguish "not provided" from `None` |
| `Attendee` | dataclass | Value object representing an event attendee (email, optional name) |
| `CalendarClientError` | exception | Base exception for calendar client failures |
| `AuthorizationError` | exception | Raised for missing/invalid credentials or permissions |
| `EventNotFoundError` | exception | Raised when an event ID does not exist |
| `ValidationError` | exception | Raised when request payloads fail validation |
| `ServiceUnavailableError` | exception | Raised when a remote service is unavailable |
| `register_client(factory)` | function | Registers a factory function `() -> CalendarClient` with the DI registry |
| `get_client()` | function | Returns a new `CalendarClient` instance from the registered factory. Raises `RuntimeError` if no factory is registered |

## Client Contract

Current method names are intentionally explicit:

- `create_event_from_dto(event_create)`
- `get_event_by_id(event_id)`
- `list_upcoming_events(max_results=10)`
- `list_events_between(start, end)`
- `update_event_from_patch(event_id, event_patch)`
- `delete_event(event_id)`

The direct Google implementation also implements the shared `ospsd-calendar-api` interface for cross-team compatibility.
