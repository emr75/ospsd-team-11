# Google Calendar Client Implementation

`google_calendar_client_impl` provides a concrete implementation, `GoogleCalendarClient`, that talks to the Google Calendar API and returns objects that satisfy the interfaces defined in `calendar_client_api`.

## What this component contains:

- **Concrete client implementation**: `GoogleCalendarClient`, which implements `calendar_client_api.client.CalendarClient`
- **Factory function**: `get_google_calendar_client()`, used by the DI system
- **Session-token factory**: `get_calendar_client_with_credentials()`, used by the FastAPI service after OAuth callback
- **DI registration hook**: `register_google_calendar_client()`, which registers the factory with `calendar_client_api.registry`
- **Shared API compatibility**: thin methods satisfying `ospsd-calendar-api`

## The Concrete Client

::: google_calendar_client_impl.client_impl.GoogleCalendarClient
    options:
      show_root_heading: true
      show_source: true

## Authentication / Configuration Notes

`GoogleCalendarClient` attempts to authenticate using (in order):

1. **Environment variables** (refresh-token flow)
2. **`token.json`** (authorized user credentials cache)
3. **Interactive OAuth** using **`credentials.json`** (when `interactive=True`)

If authentication fails, initialization raises `RuntimeError`.

### Environment Variables

These are used for the refresh-token flow:

- `GOOGLE_CALENDAR_CLIENT_ID`
- `GOOGLE_CALENDAR_CLIENT_SECRET`
- `GOOGLE_CALENDAR_REFRESH_TOKEN`
- `GOOGLE_CALENDAR_TOKEN_URI` (optional; defaults to Google's token endpoint)

Optional calendar selection:

- `DEFAULT_CALENDAR_ID` (used when the caller passes `calendar_id="primary"`)

## Factory Function

::: google_calendar_client_impl.client_impl.get_google_calendar_client
    options:
      show_root_heading: true
      show_source: true

::: google_calendar_client_impl.client_impl.get_calendar_client_with_credentials
    options:
      show_root_heading: true
      show_source: true

::: google_calendar_client_impl.client_impl.CredentialsToken
    options:
      show_root_heading: true
      show_source: true

## Dependency Injection Registration

`register_google_calendar_client()` registers this implementation with the `calendar_client_api` DI registry so that `calendar_client_api.get_client()` returns a `GoogleCalendarClient` instance.

::: google_calendar_client_impl.client_impl.register_google_calendar_client
    options:
      show_root_heading: true
      show_source: true
