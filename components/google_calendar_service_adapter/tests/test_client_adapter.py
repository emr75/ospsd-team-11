"""Unit tests for ServiceCalendarClient adapter — type mapping and error propagation."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import httpx
import pytest
from calendar_client_api.event import Attendee, EventCreate, EventUpdate
from calendar_client_api.exceptions import (
    AuthorizationError,
    EventNotFoundError,
    ServiceUnavailableError,
)
from google_calendar_service_adapter.client_adapter import ServiceCalendarClient
from google_calendar_service_adapter.event_adapter import ServiceCalendarEvent
from google_calendar_service_client.errors import UnexpectedStatus
from google_calendar_service_client.models.attendee_response import AttendeeResponse
from google_calendar_service_client.models.event_envelope import EventEnvelope
from google_calendar_service_client.models.event_response import EventResponse
from google_calendar_service_client.models.events_envelope import EventsEnvelope
from google_calendar_service_client.types import UNSET as GEN_UNSET
from google_calendar_service_client.types import Unset

_BASE = "google_calendar_service_adapter.client_adapter"

_SAMPLE_START = datetime(2026, 6, 1, 10, 0, tzinfo=UTC)
_SAMPLE_END = datetime(2026, 6, 1, 11, 0, tzinfo=UTC)


def _event_response(
    *,
    event_id: str = "evt_1",
    title: str = "Standup",
    description: str | None | Unset = GEN_UNSET,
    location: str | None | Unset = GEN_UNSET,
) -> EventResponse:
    return EventResponse(
        id=event_id,
        title=title,
        start_time=_SAMPLE_START,
        end_time=_SAMPLE_END,
        attendees=[AttendeeResponse(email="alice@example.com", name="Alice")],
        attachments=["https://example.com/doc"],
        description=description,
        location=location,
    )


def _event_envelope(
    *,
    event_id: str = "evt_1",
    title: str = "Standup",
) -> EventEnvelope:
    return EventEnvelope(event=_event_response(event_id=event_id, title=title))


def _events_envelope(count: int = 2) -> EventsEnvelope:
    return EventsEnvelope(
        events=[_event_response(event_id=f"evt_{i}") for i in range(count)]
    )


class TestCreateEvent:
    """Tests for ServiceCalendarClient.create_event type mapping."""

    @patch(f"{_BASE}.create_event_events_post")
    def test_maps_domain_types_to_generated_request(self, mock_post: MagicMock) -> None:
        """create_event should convert EventCreate into the generated request model."""
        mock_post.sync.return_value = _event_envelope(title="Design Review")

        client = ServiceCalendarClient(base_url="http://test:8000")
        event_create = EventCreate(
            title="Design Review",
            start_time=_SAMPLE_START,
            end_time=_SAMPLE_END,
            attendees=[Attendee(email="bob@example.com", name="Bob")],
            attachments=["https://example.com/spec"],
            description="Review the design",
            location="Room 5",
        )
        result = client.create_event(event_create)

        assert isinstance(result, ServiceCalendarEvent)
        assert result.title == "Design Review"
        # Verify the generated request was built with correct values
        call_kwargs = mock_post.sync.call_args
        body = call_kwargs.kwargs["body"]
        assert body.title == "Design Review"
        assert body.description == "Review the design"
        assert body.location == "Room 5"
        assert len(body.attendees) == 1
        assert body.attendees[0].email == "bob@example.com"

    @patch(f"{_BASE}.create_event_events_post")
    def test_maps_none_optional_fields_to_gen_unset(self, mock_post: MagicMock) -> None:
        """None values for optional fields should become GEN_UNSET in the request."""
        mock_post.sync.return_value = _event_envelope()

        client = ServiceCalendarClient()
        event_create = EventCreate(
            title="Quick Sync",
            start_time=_SAMPLE_START,
            end_time=_SAMPLE_END,
            attendees=[],
            attachments=[],
        )
        client.create_event(event_create)

        body = mock_post.sync.call_args.kwargs["body"]
        assert body.description is GEN_UNSET
        assert body.location is GEN_UNSET

    @patch(f"{_BASE}.create_event_events_post")
    def test_raises_authorization_error_on_401(self, mock_post: MagicMock) -> None:
        """create_event should translate 401 into AuthorizationError."""
        mock_post.sync.side_effect = UnexpectedStatus(status_code=401, content=b"Unauthorized")

        client = ServiceCalendarClient()
        with pytest.raises(AuthorizationError):
            client.create_event(
                EventCreate(title="X", start_time=_SAMPLE_START, end_time=_SAMPLE_END, attendees=[], attachments=[])
            )


class TestGetEvent:
    """Tests for ServiceCalendarClient.get_event."""

    @patch(f"{_BASE}.get_event_events_event_id_get")
    def test_returns_wrapped_event(self, mock_get: MagicMock) -> None:
        """get_event should return a ServiceCalendarEvent wrapping the response."""
        mock_get.sync.return_value = _event_envelope(event_id="evt_42", title="1:1")

        client = ServiceCalendarClient()
        result = client.get_event("evt_42")

        assert isinstance(result, ServiceCalendarEvent)
        assert result.id == "evt_42"
        assert result.title == "1:1"

    @patch(f"{_BASE}.get_event_events_event_id_get")
    def test_raises_event_not_found_on_404(self, mock_get: MagicMock) -> None:
        """get_event should translate 404 into EventNotFoundError with the event_id."""
        mock_get.sync.side_effect = UnexpectedStatus(status_code=404, content=b"Not Found")

        client = ServiceCalendarClient()
        with pytest.raises(EventNotFoundError, match="evt_missing") as exc_info:
            client.get_event("evt_missing")

        assert exc_info.value.event_id == "evt_missing"

    @patch(f"{_BASE}.get_event_events_event_id_get")
    def test_raises_service_unavailable_on_connection_error(self, mock_get: MagicMock) -> None:
        """get_event should translate httpx connection errors into ServiceUnavailableError."""
        mock_get.sync.side_effect = httpx.ConnectError(
            "Connection refused", request=httpx.Request("GET", "http://test/events/1")
        )

        client = ServiceCalendarClient()
        with pytest.raises(ServiceUnavailableError):
            client.get_event("evt_1")


class TestListEvents:
    """Tests for ServiceCalendarClient.list_events."""

    @patch(f"{_BASE}.list_events_events_get")
    def test_returns_list_of_wrapped_events(self, mock_list: MagicMock) -> None:
        """list_events should return a list of ServiceCalendarEvent."""
        mock_list.sync.return_value = _events_envelope(count=3)

        client = ServiceCalendarClient()
        result = list(client.list_events(max_results=3))

        expected_count = 3
        assert len(result) == expected_count
        assert all(isinstance(e, ServiceCalendarEvent) for e in result)
        assert [e.id for e in result] == ["evt_0", "evt_1", "evt_2"]


class TestListEventsBetween:
    """Tests for ServiceCalendarClient.list_events_between."""

    @patch(f"{_BASE}.list_events_between_events_between_get")
    def test_returns_events_in_range(self, mock_list: MagicMock) -> None:
        """list_events_between should delegate and return wrapped events."""
        mock_list.sync.return_value = _events_envelope(count=1)

        client = ServiceCalendarClient()
        start = datetime(2026, 6, 1, tzinfo=UTC)
        end = datetime(2026, 6, 2, tzinfo=UTC)
        result = list(client.list_events_between(start, end))

        assert len(result) == 1
        mock_list.sync.assert_called_once()


class TestUpdateEvent:
    """Tests for ServiceCalendarClient.update_event type mapping."""

    @patch(f"{_BASE}.update_event_events_event_id_patch")
    def test_maps_unset_fields_to_gen_unset(self, mock_patch: MagicMock) -> None:
        """UNSET fields in EventUpdate should become GEN_UNSET in the request."""
        mock_patch.sync.return_value = _event_envelope(event_id="evt_1")

        client = ServiceCalendarClient()
        patch_data = EventUpdate(title="New Title")
        client.update_event("evt_1", patch_data)

        body = mock_patch.sync.call_args.kwargs["body"]
        assert body.title == "New Title"
        assert body.start_time is GEN_UNSET
        assert body.end_time is GEN_UNSET
        assert body.description is GEN_UNSET
        assert body.location is GEN_UNSET

    @patch(f"{_BASE}.update_event_events_event_id_patch")
    def test_maps_explicit_none_description(self, mock_patch: MagicMock) -> None:
        """An explicit None for description should pass through as None, not UNSET."""
        mock_patch.sync.return_value = _event_envelope()

        client = ServiceCalendarClient()
        patch_data = EventUpdate(description=None)
        client.update_event("evt_1", patch_data)

        body = mock_patch.sync.call_args.kwargs["body"]
        assert body.description is None

    @patch(f"{_BASE}.update_event_events_event_id_patch")
    def test_raises_event_not_found_on_404(self, mock_patch: MagicMock) -> None:
        """update_event should translate 404 into EventNotFoundError."""
        mock_patch.sync.side_effect = UnexpectedStatus(status_code=404, content=b"Not Found")

        client = ServiceCalendarClient()
        with pytest.raises(EventNotFoundError, match="evt_gone"):
            client.update_event("evt_gone", EventUpdate(title="X"))


class TestDeleteEvent:
    """Tests for ServiceCalendarClient.delete_event."""

    @patch(f"{_BASE}.delete_event_events_event_id_delete")
    def test_delete_succeeds_silently(self, mock_delete: MagicMock) -> None:
        """delete_event should complete without error on success."""
        mock_delete.sync.return_value = None

        client = ServiceCalendarClient()
        client.delete_event("evt_1")

        mock_delete.sync.assert_called_once()

    @patch(f"{_BASE}.delete_event_events_event_id_delete")
    def test_raises_event_not_found_on_404(self, mock_delete: MagicMock) -> None:
        """delete_event should translate 404 into EventNotFoundError."""
        mock_delete.sync.side_effect = UnexpectedStatus(status_code=404, content=b"Not Found")

        client = ServiceCalendarClient()
        with pytest.raises(EventNotFoundError, match="evt_gone"):
            client.delete_event("evt_gone")
