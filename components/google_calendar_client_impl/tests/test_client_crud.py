"""Unit tests for GoogleCalendarClient CRUD operations."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from calendar_client_api import Attendee, EventCreate, EventUpdate
from google_calendar_client_impl.client_impl import GoogleCalendarClient


def _event_payload(
    *,
    event_id: str = "evt_123",
    title: str = "Team Sync",
    start: str = "2026-03-01T09:00:00+00:00",
    end: str = "2026-03-01T10:00:00+00:00",
) -> dict[str, object]:
    return {
        "id": event_id,
        "summary": title,
        "start": {"dateTime": start},
        "end": {"dateTime": end},
    }


def _build_client(
    monkeypatch: pytest.MonkeyPatch, default_calendar_id: str = "primary"
) -> tuple[GoogleCalendarClient, MagicMock]:
    monkeypatch.setenv("DEFAULT_CALENDAR_ID", default_calendar_id)
    service = MagicMock()
    client = GoogleCalendarClient(service=service)
    return client, service


class TestGoogleCalendarClientCreate:
    """Tests for create_event."""

    def test_create_event_serializes_payload_and_returns_event(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Create event sends normalized body and returns parsed event."""
        client, service = _build_client(monkeypatch)
        payload = _event_payload(title="Design Review")
        service.events.return_value.insert.return_value.execute.return_value = payload

        created = EventCreate(
            title="Design Review",
            start_time=datetime(2026, 3, 1, 9, 0, tzinfo=UTC),
            end_time=datetime(2026, 3, 1, 10, 0, tzinfo=UTC),
            description="Review V2",
            location="Room 9",
            attendees=[Attendee(email="alice@example.com", name="Alice")],
            attachments=["https://example.com/spec"],
        )

        event = client.create_event_from_dto(created)

        service.events.return_value.insert.assert_called_once_with(
            calendarId="primary",
            body={
                "summary": "Design Review",
                "start": {"dateTime": "2026-03-01T09:00:00+00:00"},
                "end": {"dateTime": "2026-03-01T10:00:00+00:00"},
                "description": "Review V2",
                "location": "Room 9",
                "attendees": [{"email": "alice@example.com", "displayName": "Alice"}],
                "attachments": [{"fileUrl": "https://example.com/spec"}],
            },
            supportsAttachments=True,
        )
        assert event.id == "evt_123"
        assert event.title == "Design Review"

    def test_create_event_uses_default_calendar_id_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Default calendar id should resolve from DEFAULT_CALENDAR_ID."""
        client, service = _build_client(monkeypatch, default_calendar_id="team-calendar")
        service.events.return_value.insert.return_value.execute.return_value = _event_payload()

        created = EventCreate(
            title="Sync",
            start_time=datetime(2026, 3, 1, 9, 0, tzinfo=UTC),
            end_time=datetime(2026, 3, 1, 10, 0, tzinfo=UTC),
            attendees=[],
            attachments=[],
        )

        client.create_event_from_dto(created)

        service.events.return_value.insert.assert_called_once()
        _, kwargs = service.events.return_value.insert.call_args
        assert kwargs["calendarId"] == "team-calendar"
        assert kwargs["supportsAttachments"] is False


class TestGoogleCalendarClientRead:
    """Tests for get_event and list operations."""

    def test_get_event_fetches_by_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """get_event should call Google API with calendar and event identifiers."""
        client, service = _build_client(monkeypatch)
        service.events.return_value.get.return_value.execute.return_value = _event_payload(event_id="evt_456")

        event = client.get_event_by_id("evt_456", calendar_id="work")

        service.events.return_value.get.assert_called_once_with(
            calendarId="work",
            eventId="evt_456",
        )
        assert event.id == "evt_456"

    def test_list_events_returns_mapped_events(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """list_events should map API list items into Event objects."""
        client, service = _build_client(monkeypatch)
        service.events.return_value.list.return_value.execute.return_value = {
            "items": [
                _event_payload(event_id="evt_1", title="A"),
                _event_payload(event_id="evt_2", title="B"),
            ]
        }

        events = list(client.list_upcoming_events(max_results=2, calendar_id="work"))

        service.events.return_value.list.assert_called_once_with(
            calendarId="work",
            maxResults=2,
            singleEvents=True,
            orderBy="startTime",
        )
        assert [event.id for event in events] == ["evt_1", "evt_2"]

    def test_list_events_validates_max_results(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """list_events should reject non-positive max_results values."""
        client, service = _build_client(monkeypatch)

        with pytest.raises(ValueError, match="max_results"):
            client.list_upcoming_events(max_results=0)

        service.events.return_value.list.assert_not_called()

    def test_list_events_between_passes_time_range(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """list_events_between should pass timeMin/timeMax as RFC3339 strings."""
        client, service = _build_client(monkeypatch)
        service.events.return_value.list.return_value.execute.return_value = {"items": [_event_payload(event_id="evt_777")]}

        start = datetime(2026, 3, 1, 9, 0, tzinfo=UTC)
        end = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
        events = list(client.list_events_between(start, end))

        service.events.return_value.list.assert_called_once_with(
            calendarId="primary",
            timeMin="2026-03-01T09:00:00+00:00",
            timeMax="2026-03-01T12:00:00+00:00",
            singleEvents=True,
            orderBy="startTime",
        )
        assert len(events) == 1
        assert events[0].id == "evt_777"

    def test_list_events_between_validates_start_end(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """list_events_between should reject an inverted date range."""
        client, service = _build_client(monkeypatch)
        start = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
        end = datetime(2026, 3, 1, 9, 0, tzinfo=UTC)

        with pytest.raises(ValueError, match="earlier"):
            client.list_events_between(start, end)

        service.events.return_value.list.assert_not_called()


class TestGoogleCalendarClientUpdateDelete:
    """Tests for update_event and delete_event."""

    def test_update_event_sends_patch_payload(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """update_event should serialize only explicit patch fields."""
        client, service = _build_client(monkeypatch)
        service.events.return_value.patch.return_value.execute.return_value = _event_payload(
            event_id="evt_999",
            title="Updated",
        )

        event_patch = EventUpdate(
            title="Updated",
            start_time=datetime(2026, 3, 1, 11, 0, tzinfo=UTC),
            end_time=datetime(2026, 3, 1, 12, 0, tzinfo=UTC),
            description=None,
            location="Zoom",
        )
        event = client.update_event_from_patch("evt_999", event_patch, calendar_id="work")

        service.events.return_value.patch.assert_called_once_with(
            calendarId="work",
            eventId="evt_999",
            body={
                "summary": "Updated",
                "start": {"dateTime": "2026-03-01T11:00:00+00:00"},
                "end": {"dateTime": "2026-03-01T12:00:00+00:00"},
                "description": None,
                "location": "Zoom",
            },
            supportsAttachments=True,
        )
        assert event.id == "evt_999"
        assert event.title == "Updated"

    def test_update_event_rejects_empty_patch(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """update_event should raise when no patch fields are provided."""
        client, service = _build_client(monkeypatch)

        with pytest.raises(ValueError, match="No fields"):
            client.update_event_from_patch("evt_1", EventUpdate())

        service.events.return_value.patch.assert_not_called()

    def test_delete_event_calls_google_api(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """delete_event should call delete().execute() with identifiers."""
        client, service = _build_client(monkeypatch)

        client.delete_event("evt_del", calendar_id="work")

        service.events.return_value.delete.assert_called_once_with(
            calendarId="work",
            eventId="evt_del",
        )
        service.events.return_value.delete.return_value.execute.assert_called_once_with()
