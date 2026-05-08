# google_calendar_client_impl

## Role

Concrete implementation of the `calendar_client_api` interface backed by the Google Calendar API. Importing this package automatically registers it with the DI registry, so any call to `get_client()` will return a `GoogleCalendarClient` instance.

## Dependencies

| Package | Purpose |
|---------|---------|
| `calendar-client-api` | Abstract interface (workspace dependency) |
| `ospsd-calendar-api` | Shared cross-team calendar ABC that this implementation also satisfies |
| `google-api-python-client` | Google Calendar REST API client |
| `google-auth` | Google OAuth 2.0 credentials |
| `google-auth-oauthlib` | OAuth 2.0 interactive login flow |
| `python-dotenv` | Load environment variables from `.env` files |

## Public API

| Export | Type | Description |
|--------|------|-------------|
| `GoogleCalendarClient` | class | Implements `CalendarClient`. Authenticates via environment variables, token file, or interactive OAuth flow |
| `GoogleCalendarEvent` | class | Implements `Event`. Wraps Google Calendar API payloads |
| `CredentialsToken` | dataclass | Structured OAuth token input used by the FastAPI service to build a session-scoped client |
| `get_google_calendar_client()` | function | Factory function that creates a new `GoogleCalendarClient` instance |
| `get_calendar_client_with_credentials(creds_token)` | function | Factory used by the service when OAuth tokens are stored in the session |
| `register_google_calendar_client()` | function | Registers this implementation with `calendar_client_api` |

## Configuration

| Variable / File | Description |
|-----------------|-------------|
| `GOOGLE_CALENDAR_CLIENT_ID` | OAuth client ID used for refresh-token auth |
| `GOOGLE_CALENDAR_CLIENT_SECRET` | OAuth client secret used for refresh-token auth |
| `GOOGLE_CALENDAR_REFRESH_TOKEN` | Refresh token used by direct non-interactive auth |
| `GOOGLE_CALENDAR_TOKEN_URI` | Optional token endpoint override |
| `DEFAULT_CALENDAR_ID` | Calendar ID used when callers pass `calendar_id="primary"` |
| `credentials.json` | OAuth client credentials from Google Cloud |
| `token.json` | Stored user access/refresh tokens after authentication |

## DI Auto-Registration

On import, the package calls `register_client(get_google_calendar_client)`, so consumers only need:

```python
import google_calendar_client_impl
from calendar_client_api import get_client

client = get_client()  # returns a GoogleCalendarClient
```

## Notes

`GoogleCalendarClient` implements two interfaces:

- this repo's `calendar_client_api.CalendarClient`
- the shared `ospsd_calendar_api.CalendarClient`

The shared-interface methods are thin adapters around the local DTO-based methods.
