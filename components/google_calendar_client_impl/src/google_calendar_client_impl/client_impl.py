"""Google Calendar implementation of the CalendarClient interface."""

import logging
import os
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar

import calendar_client_api
from calendar_client_api import Attendee, CalendarClient, Event, EventCreate, EventUpdate
from calendar_client_api.event import UNSET
from google.auth.exceptions import GoogleAuthError, RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore[import-untyped] # no py.typed
from googleapiclient.discovery import Resource, build
from ospsd_calendar_api import CalendarClient as SharedCalendarClient
from ospsd_calendar_api import Event as SharedEvent

from google_calendar_client_impl.event_impl import GoogleCalendarEvent


class GoogleCalendarClient(CalendarClient, SharedCalendarClient):
    """Concrete implementation of CalendarClient using Google Calendar."""

    TOKEN_PATH: ClassVar[str] = "token.json"  # noqa: S105
    CREDENTIALS_PATH: ClassVar[str] = "credentials.json"
    SCOPES: ClassVar[list[str]] = [
        "https://www.googleapis.com/auth/calendar",
    ]

    def __init__(
        self,
        service: Resource | None = None,
        *,
        creds: Credentials | None = None,
        interactive: bool = True,
    ) -> None:
        """Initialize the Google calendar client."""
        self._default_calendar_id: str = os.getenv("DEFAULT_CALENDAR_ID", "primary")
        self.logger = logging.getLogger(__name__)
        if service is not None:
            self.service = service
            return
        if creds is not None:
            self.service = build("calendar", "v3", credentials=creds)
            return
        creds = self._resolve_credentials(interactive=interactive)
        self.service = build("calendar", "v3", credentials=creds)

    def _resolve_credentials(self, *, interactive: bool) -> Credentials:
        creds_path = self.CREDENTIALS_PATH
        token_path = self.TOKEN_PATH

        creds: Credentials | None = self._auth_from_env()

        if not creds:
            creds = self._auth_from_file(token_path)

        if not creds and interactive:
            creds = self._auth_from_interactive(creds_path)

        creds = self._auth_refresh_token_if_invalid(creds)

        if not (creds and creds.valid):
            err_msg = "Failed to authenticate with Google Calendar API"
            raise RuntimeError(err_msg)

        # Save the credentials for the next run
        if creds and creds.valid and creds.refresh_token:
            with Path(token_path).open("w", encoding="utf-8") as file:
                file.write(creds.to_json())  # type: ignore[no-untyped-call] # google-auth Credentials.to_json() is untyped

        return creds

    def _auth_from_env(self) -> Credentials | None:
        client_id = os.environ.get("GOOGLE_CALENDAR_CLIENT_ID")
        client_secret = os.environ.get("GOOGLE_CALENDAR_CLIENT_SECRET")
        refresh_token = os.environ.get("GOOGLE_CALENDAR_REFRESH_TOKEN")
        token_uri = os.environ.get("GOOGLE_CALENDAR_TOKEN_URI", "https://oauth2.googleapis.com/token")

        if not (client_id and client_secret and refresh_token):
            return None

        try:
            creds = Credentials(  # type: ignore[no-untyped-call] # google-auth Credentials.__init__() is untyped
                None,
                refresh_token=refresh_token,
                token_uri=token_uri,
                client_id=client_id,
                client_secret=client_secret,
                scopes=self.SCOPES,
            )
            creds.refresh(Request())
        except (GoogleAuthError, RefreshError, OSError, ValueError):
            return None
        else:
            return creds

    def _auth_from_interactive(self, creds_path: str) -> Credentials:  # pragma: no cover — interactive browser flow
        if not Path(creds_path).exists():
            err_msg = f"'{creds_path}' not found. Cannot run interactive auth."
            raise FileNotFoundError(err_msg)
        flow = InstalledAppFlow.from_client_secrets_file(creds_path, self.SCOPES)
        return flow.run_local_server(port=0)  # type: ignore[no-any-return] # run_local_server returns Any due to untyped lib

    def _auth_from_file(self, token_path: str) -> Credentials | None:
        # get the token (access&refresh token) from token.json if the file exists
        if not Path(token_path).exists():
            return None
        try:
            return Credentials.from_authorized_user_file(token_path, self.SCOPES)  # type: ignore[no-untyped-call,no-any-return] # google-auth classmethod is untyped and returns Any
        except (OSError, ValueError):
            return None

    def _auth_refresh_token_if_invalid(self, creds: Credentials | None) -> Credentials | None:
        if creds and not creds.valid and creds.refresh_token:
            try:
                creds.refresh(Request())
            except (GoogleAuthError, RefreshError, OSError, ValueError):
                return None
        return creds

    def create_event_from_dto(self, event_create: EventCreate, calendar_id: str = "primary") -> Event:
        """Create a new calendar event and return its ID."""
        resolved_calendar_id = self._resolve_calendar_id(calendar_id)
        payload = _serialize_event_create(event_create)
        events_resource = self.service.events()  # type: ignore[attr-defined] # Resource is dynamically built; .events() not in stubs
        created_payload = events_resource.insert(
            calendarId=resolved_calendar_id,
            body=payload,
            supportsAttachments=bool(event_create.attachments),
        ).execute()
        return self._event_from_payload(created_payload, calendar_id=resolved_calendar_id)

    def get_event_by_id(self, event_id: str, calendar_id: str = "primary") -> Event:
        """Retrieve a calendar event by its ID."""
        resolved_calendar_id = self._resolve_calendar_id(calendar_id)
        events_resource = self.service.events()  # type: ignore[attr-defined] # Resource is dynamically built; .events() not in stubs
        event_payload = events_resource.get(calendarId=resolved_calendar_id, eventId=event_id).execute()
        return self._event_from_payload(event_payload, calendar_id=resolved_calendar_id)

    def list_upcoming_events(self, max_results: int = 10, calendar_id: str = "primary") -> Iterable[Event]:
        """Return an iterable of calendar events."""
        max_result_limit = 2500
        if max_results <= 0:
            err_msg = "'max_results' must be a positive integer."
            raise ValueError(err_msg)
        if max_results > max_result_limit:
            err_msg = "'max_results' cannot exceed 2500 due to Google Calendar API limits."
            raise ValueError(err_msg)

        resolved_calendar_id = self._resolve_calendar_id(calendar_id)
        events_resource = self.service.events()  # type: ignore[attr-defined] # Resource is dynamically built; .events() not in stubs
        events_payload = events_resource.list(
            calendarId=resolved_calendar_id,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        return self._events_from_list_payload(events_payload, calendar_id=resolved_calendar_id)

    def list_events_between(self, start: datetime, end: datetime, calendar_id: str = "primary") -> Iterable[Event]:
        """Return an iterable of calendar events between two dates."""
        if start >= end:
            err_msg = "'start' must be earlier than 'end'."
            raise ValueError(err_msg)

        resolved_calendar_id = self._resolve_calendar_id(calendar_id)
        events_resource = self.service.events()  # type: ignore[attr-defined] # Resource is dynamically built; .events() not in stubs
        events_payload = events_resource.list(
            calendarId=resolved_calendar_id,
            timeMin=_serialize_datetime(start),
            timeMax=_serialize_datetime(end),
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        return self._events_from_list_payload(events_payload, calendar_id=resolved_calendar_id)

    def update_event_from_patch(
        self,
        event_id: str,
        event_patch: EventUpdate,
        calendar_id: str = "primary",
    ) -> Event:
        """Update an existing calendar event."""
        payload = _serialize_event_update(event_patch)
        if not payload:
            err_msg = "No fields were provided in 'event_patch'."
            raise ValueError(err_msg)

        resolved_calendar_id = self._resolve_calendar_id(calendar_id)
        events_resource = self.service.events()  # type: ignore[attr-defined] # Resource is dynamically built; .events() not in stubs
        updated_payload = events_resource.patch(
            calendarId=resolved_calendar_id,
            eventId=event_id,
            body=payload,
            supportsAttachments=True,
        ).execute()
        return self._event_from_payload(updated_payload, calendar_id=resolved_calendar_id)

    def delete_event(self, event_id: str, calendar_id: str = "primary") -> None:
        """Delete a calendar event by its ID."""
        resolved_calendar_id = self._resolve_calendar_id(calendar_id)
        events_resource = self.service.events()  # type: ignore[attr-defined] # Resource is dynamically built; .events() not in stubs
        events_resource.delete(calendarId=resolved_calendar_id, eventId=event_id).execute()

    def _resolve_calendar_id(self, calendar_id: str) -> str:
        if calendar_id == "primary":
            return self._default_calendar_id
        return calendar_id

    def _event_from_payload(self, payload: object, *, calendar_id: str) -> GoogleCalendarEvent:
        if not isinstance(payload, Mapping):
            err_msg = "Google Calendar API returned a non-object event payload."
            raise TypeError(err_msg)
        return GoogleCalendarEvent(payload=payload, calendar_id=calendar_id)

    def _events_from_list_payload(self, payload: object, *, calendar_id: str) -> list[Event]:
        if not isinstance(payload, Mapping):
            err_msg = "Google Calendar API returned an invalid events list payload."
            raise TypeError(err_msg)

        items = payload.get("items")
        if items is None:
            return []

        if not isinstance(items, list):
            err_msg = "Google Calendar API list payload 'items' must be a list."
            raise TypeError(err_msg)

        parsed_events: list[Event] = []
        for item in items:
            try:
                parsed_events.append(self._event_from_payload(item, calendar_id=calendar_id))
            except (TypeError, ValueError):
                self.logger.warning("Skipping invalid event payload in list response.")
        return parsed_events

    # --- SharedCalendarClient implementation ---
    # These are thin adapters. They just call the methods above.
    # delete_event is exactly the same as the local interface

    def list_events(self, start: datetime, end: datetime) -> list[SharedEvent]:
        """List the events between two dates."""
        events = self.list_events_between(start=start, end=end)
        return [_event_to_shared_event(event) for event in events]

    def get_event(self, event_id: str) -> SharedEvent:
        """Get an event by its ID."""
        event = self.get_event_by_id(event_id)
        return _event_to_shared_event(event)

    def create_event(
        self, title: str, start_time: datetime, end_time: datetime, description: str = "", location: str | None = None
    ) -> SharedEvent:
        """Create a calendar event."""
        event = self.create_event_from_dto(
            EventCreate(
                title=title,
                start_time=start_time,
                end_time=end_time,
                description=description,
                location=location,
                attendees=[],
                attachments=[],
            )
        )
        return _event_to_shared_event(event)

    def update_event(  # noqa: PLR0913
        self,
        event_id: str,
        *,
        title: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        description: str | None = None,
        location: str | None = None,
    ) -> SharedEvent:
        """Update a calendar event."""
        patch = EventUpdate(
            title=UNSET if title is None else title,
            start_time=UNSET if start_time is None else start_time,
            end_time=UNSET if end_time is None else end_time,
            description=UNSET if description is None else description,
            location=UNSET if location is None else location,
        )
        event = self.update_event_from_patch(event_id, patch)
        return _event_to_shared_event(event)


def _event_to_shared_event(event: Event) -> SharedEvent:
    return SharedEvent(
        id=event.id,
        title=event.title,
        start_time=event.start_time,
        end_time=event.end_time,
        description=event.description,
        location=event.location,
    )


def _serialize_event_create(event_create: EventCreate) -> dict[str, object]:
    payload: dict[str, object] = {
        "summary": event_create.title,
        "start": {"dateTime": _serialize_datetime(event_create.start_time)},
        "end": {"dateTime": _serialize_datetime(event_create.end_time)},
    }
    if event_create.description is not None:
        payload["description"] = event_create.description
    if event_create.location is not None:
        payload["location"] = event_create.location

    attendees = _serialize_attendees(event_create.attendees)
    if attendees:
        payload["attendees"] = attendees

    attachments = _serialize_attachments(event_create.attachments)
    if attachments:
        payload["attachments"] = attachments

    return payload


def _serialize_event_update(event_patch: EventUpdate) -> dict[str, object]:
    payload: dict[str, object] = {}

    if event_patch.title is not UNSET:
        payload["summary"] = event_patch.title
    if isinstance(event_patch.start_time, datetime):
        payload["start"] = {"dateTime": _serialize_datetime(event_patch.start_time)}
    if isinstance(event_patch.end_time, datetime):
        payload["end"] = {"dateTime": _serialize_datetime(event_patch.end_time)}
    if event_patch.description is not UNSET:
        payload["description"] = event_patch.description
    if event_patch.location is not UNSET:
        payload["location"] = event_patch.location

    return payload


def _serialize_attendees(attendees: Iterable[Attendee]) -> list[dict[str, str]]:
    serialized_attendees: list[dict[str, str]] = []
    for attendee in attendees:
        attendee_payload: dict[str, str] = {"email": attendee.email}
        if attendee.name:
            attendee_payload["displayName"] = attendee.name
        serialized_attendees.append(attendee_payload)
    return serialized_attendees


def _serialize_attachments(attachments: Iterable[str]) -> list[dict[str, str]]:
    return [{"fileUrl": attachment} for attachment in attachments if attachment]


def _serialize_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.isoformat()


def load_env() -> None:
    """Load environment variables."""
    try:
        from dotenv import load_dotenv  # noqa: PLC0415

        load_dotenv()
    except ImportError:
        env_path = Path(".env")
        if env_path.exists():
            with env_path.open() as f:
                for raw_line in f:
                    line = raw_line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        os.environ[key.strip()] = value.strip()


def get_google_calendar_client() -> GoogleCalendarClient:
    """Get a Google Calendar client."""
    return GoogleCalendarClient()


@dataclass(frozen=True)
class CredentialsToken:
    """Structured representation of OAuth credentials for token-based auth."""

    client_id: str
    client_secret: str
    token_uri: str
    scopes: list[str]
    access_token: str
    refresh_token: str | None = None


def get_calendar_client_with_credentials(creds_token: CredentialsToken) -> GoogleCalendarClient:
    """Get a Google Calendar client using the provided credentials token."""
    creds = Credentials(  # type: ignore[no-untyped-call] # google-auth Credentials.__init__() is untyped
        token=creds_token.access_token,
        refresh_token=creds_token.refresh_token,
        token_uri=creds_token.token_uri,
        client_id=creds_token.client_id,
        client_secret=creds_token.client_secret,
        scopes=creds_token.scopes,
    )
    if creds_token.refresh_token is not None:
        creds.refresh(Request())
    return GoogleCalendarClient(creds=creds, interactive=False)


def register_google_calendar_client() -> None:
    """Register a Google Calendar client."""
    calendar_client_api.register_client(get_google_calendar_client)
