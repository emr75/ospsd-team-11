"""Unit tests for ServiceCalendarEvent — generated EventResponse → domain Event mapping."""

from datetime import UTC, datetime

from calendar_client_api.event import Attendee, Event
from google_calendar_service_adapter.event_adapter import ServiceCalendarEvent
from google_calendar_service_client.models.attendee_response import AttendeeResponse
from google_calendar_service_client.models.event_response import EventResponse
from google_calendar_service_client.types import UNSET as GEN_UNSET
from google_calendar_service_client.types import Unset

_SAMPLE_START = datetime(2026, 6, 1, 10, 0, tzinfo=UTC)
_SAMPLE_END = datetime(2026, 6, 1, 11, 0, tzinfo=UTC)


def _make_response(  # noqa: PLR0913
    *,
    event_id: str = "evt_1",
    title: str = "Standup",
    description: str | None | Unset = GEN_UNSET,
    location: str | None | Unset = GEN_UNSET,
    attendees: list[AttendeeResponse] | None = None,
    attachments: list[str] | None = None,
) -> EventResponse:
    return EventResponse(
        id=event_id,
        title=title,
        start_time=_SAMPLE_START,
        end_time=_SAMPLE_END,
        attendees=attendees or [],
        attachments=attachments or [],
        description=description,
        location=location,
    )


class TestServiceCalendarEvent:
    """Tests for the EventResponse → Event adapter."""

    def test_implements_event_abc(self) -> None:
        """ServiceCalendarEvent should be a subclass of Event."""
        event = ServiceCalendarEvent(_make_response())

        assert isinstance(event, Event)

    def test_maps_required_fields(self) -> None:
        """Required fields should be mapped directly from the response."""
        event = ServiceCalendarEvent(
            _make_response(event_id="evt_99", title="Retro")
        )

        assert event.id == "evt_99"
        assert event.title == "Retro"
        assert event.start_time == datetime(2026, 6, 1, 10, 0, tzinfo=UTC)
        assert event.end_time == datetime(2026, 6, 1, 11, 0, tzinfo=UTC)

    def test_unset_description_returns_none(self) -> None:
        """An UNSET description in the response should return None."""
        event = ServiceCalendarEvent(_make_response(description=GEN_UNSET))

        assert event.description is None

    def test_explicit_description_returned(self) -> None:
        """An explicit description should be returned as-is."""
        event = ServiceCalendarEvent(_make_response(description="Team retro notes"))

        assert event.description == "Team retro notes"

    def test_none_description_returned_as_none(self) -> None:
        """An explicit None description should return None."""
        event = ServiceCalendarEvent(_make_response(description=None))

        assert event.description is None

    def test_unset_location_returns_none(self) -> None:
        """An UNSET location in the response should return None."""
        event = ServiceCalendarEvent(_make_response(location=GEN_UNSET))

        assert event.location is None

    def test_explicit_location_returned(self) -> None:
        """An explicit location should be returned as-is."""
        event = ServiceCalendarEvent(_make_response(location="Room 42"))

        assert event.location == "Room 42"

    def test_attendees_converted_to_domain_type(self) -> None:
        """Generated AttendeeResponse should be converted to domain Attendee."""
        response = _make_response(
            attendees=[
                AttendeeResponse(email="alice@example.com", name="Alice"),
                AttendeeResponse(email="bob@example.com", name=GEN_UNSET),
            ]
        )
        event = ServiceCalendarEvent(response)

        expected_count = 2
        assert len(event.attendees) == expected_count
        assert event.attendees[0] == Attendee(email="alice@example.com", name="Alice")
        assert event.attendees[1] == Attendee(email="bob@example.com", name=None)

    def test_empty_attendees(self) -> None:
        """No attendees in the response should yield an empty list."""
        event = ServiceCalendarEvent(_make_response(attendees=[]))

        assert event.attendees == []

    def test_attachments_passed_through(self) -> None:
        """Attachment URLs should be passed through as-is."""
        event = ServiceCalendarEvent(
            _make_response(attachments=["https://a.com/1", "https://b.com/2"])
        )

        assert event.attachments == ["https://a.com/1", "https://b.com/2"]

    def test_empty_attachments(self) -> None:
        """No attachments in the response should yield an empty list."""
        event = ServiceCalendarEvent(_make_response(attachments=[]))

        assert event.attachments == []
