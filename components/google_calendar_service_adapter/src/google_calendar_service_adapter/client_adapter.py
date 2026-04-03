"""Client adapter that implements CalendarClient over HTTP via the generated client."""

from collections.abc import Iterable
from datetime import datetime

from calendar_client_api.client import CalendarClient
from calendar_client_api.event import UNSET as API_UNSET
from calendar_client_api.event import EventCreate, EventUpdate
from google_calendar_service_client.api.default import (
    create_event_events_post,
    delete_event_events_event_id_delete,
    get_event_events_event_id_get,
    list_events_between_events_between_get,
    list_events_events_get,
    update_event_events_event_id_patch,
)
from google_calendar_service_client.client import Client
from google_calendar_service_client.models.attendee_request import AttendeeRequest
from google_calendar_service_client.models.event_create_request import EventCreateRequest
from google_calendar_service_client.models.event_envelope import EventEnvelope
from google_calendar_service_client.models.event_update_request import EventUpdateRequest
from google_calendar_service_client.models.events_envelope import EventsEnvelope
from google_calendar_service_client.types import UNSET as GEN_UNSET

from google_calendar_service_adapter.event_adapter import ServiceCalendarEvent


class ServiceCalendarClient(CalendarClient):
    """CalendarClient implementation that delegates to the FastAPI service over HTTP."""

    def __init__(self, base_url: str = "http://localhost:8000") -> None:
        """Initialize with the base URL of the running FastAPI service."""
        self._client = Client(base_url=base_url, raise_on_unexpected_status=True)

    def create_event(self, event_create: EventCreate) -> ServiceCalendarEvent:
        """Create a calendar event via the service."""
        attendees = [
            AttendeeRequest(email=a.email, name=a.name if a.name is not None else GEN_UNSET) for a in event_create.attendees
        ]
        body = EventCreateRequest(
            title=event_create.title,
            start_time=event_create.start_time,
            end_time=event_create.end_time,
            attendees=attendees,
            attachments=event_create.attachments,
            description=event_create.description if event_create.description is not None else GEN_UNSET,
            location=event_create.location if event_create.location is not None else GEN_UNSET,
        )
        response = create_event_events_post.sync(client=self._client, body=body)
        return self._unwrap_event_envelope(response)

    def get_event(self, event_id: str) -> ServiceCalendarEvent:
        """Get a single event by ID via the service."""
        response = get_event_events_event_id_get.sync(event_id, client=self._client)
        return self._unwrap_event_envelope(response)

    def list_events(self, max_results: int = 10) -> Iterable[ServiceCalendarEvent]:
        """List calendar events via the service."""
        response = list_events_events_get.sync(client=self._client, max_results=max_results)
        return self._unwrap_events_envelope(response)

    def list_events_between(self, start: datetime, end: datetime) -> Iterable[ServiceCalendarEvent]:
        """List calendar events between two datetimes via the service."""
        response = list_events_between_events_between_get.sync(client=self._client, start=start, end=end)
        return self._unwrap_events_envelope(response)

    def update_event(self, event_id: str, event_patch: EventUpdate) -> ServiceCalendarEvent:
        """Update a calendar event via the service."""
        body = EventUpdateRequest(
            title=event_patch.title if not isinstance(event_patch.title, type(API_UNSET)) else GEN_UNSET,
            start_time=event_patch.start_time if not isinstance(event_patch.start_time, type(API_UNSET)) else GEN_UNSET,
            end_time=event_patch.end_time if not isinstance(event_patch.end_time, type(API_UNSET)) else GEN_UNSET,
            description=event_patch.description if not isinstance(event_patch.description, type(API_UNSET)) else GEN_UNSET,
            location=event_patch.location if not isinstance(event_patch.location, type(API_UNSET)) else GEN_UNSET,
        )
        response = update_event_events_event_id_patch.sync(event_id, client=self._client, body=body)
        return self._unwrap_event_envelope(response)

    def delete_event(self, event_id: str) -> None:
        """Delete a calendar event via the service."""
        delete_event_events_event_id_delete.sync(event_id, client=self._client)

    @staticmethod
    def _unwrap_event_envelope(response: object) -> ServiceCalendarEvent:
        if not isinstance(response, EventEnvelope):
            msg = f"Unexpected response from service: {response}"
            raise TypeError(msg)
        return ServiceCalendarEvent(response.event)

    @staticmethod
    def _unwrap_events_envelope(response: object) -> list[ServiceCalendarEvent]:
        if not isinstance(response, EventsEnvelope):
            msg = f"Unexpected response from service: {response}"
            raise TypeError(msg)
        return [ServiceCalendarEvent(e) for e in response.events]
