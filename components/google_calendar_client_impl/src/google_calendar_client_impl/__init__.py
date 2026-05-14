"""Public exports and dependency injections for the Google Calendar implementation package."""

from google_calendar_client_impl.client_impl import CredentialsToken as CredentialsToken
from google_calendar_client_impl.client_impl import GoogleCalendarClient as GoogleCalendarClient
from google_calendar_client_impl.client_impl import (
    get_calendar_client_with_credentials as get_calendar_client_with_credentials,
)
from google_calendar_client_impl.client_impl import (
    get_google_calendar_client as get_google_calendar_client,
)
from google_calendar_client_impl.client_impl import (
    load_env as load_env,
)
from google_calendar_client_impl.client_impl import (
    register_google_calendar_client as _register_client,
)
from google_calendar_client_impl.event_impl import GoogleCalendarEvent as GoogleCalendarEvent

_register_client()
