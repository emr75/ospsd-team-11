# google_calendar_client_impl

## Role

Concrete implementation of the `calendar_client_api` interface backed by the Google Calendar API. Importing this package automatically registers it with the DI registry, so any call to `get_client()` will return a `GoogleCalendarClient` instance.

## Dependencies

| Package | Purpose |
|---------|---------|
| `calendar-client-api` | Abstract interface (workspace dependency) |
| `google-api-python-client` | Google Calendar REST API client |
| `google-auth` | Google OAuth 2.0 credentials |
| `google-auth-oauthlib` | OAuth 2.0 interactive login flow |
| `python-dotenv` | Load environment variables from `.env` files |

## Public API

| Export | Type | Description |
|--------|------|-------------|
| `GoogleCalendarClient` | class | Implements `CalendarClient`. Authenticates via environment variables, token file, or interactive OAuth flow |
| `GoogleCalendarEvent` | class | Implements `Event`. Wraps Google Calendar API payloads |
| `get_google_calendar_client()` | function | Factory function that creates a new `GoogleCalendarClient` instance |

## Configuration

| Variable / File | Description |
|-----------------|-------------|
| `credentials.json` | OAuth client credentials from Google Cloud |
| `token.json` | Stored user access/refresh tokens after authentication |
| Environment Variables | Optional configuration loaded via `.env` (if used) |

## DI Auto-Registration

On import, the package calls `register_client(get_google_calendar_client)`, so consumers only need:

```python
import google_calendar_client_impl

client = get_client()  # returns a GoogleCalendarClient
```
