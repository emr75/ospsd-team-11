"""Tests for issue-to-calendar integration flow."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

from calendar_client_api import Attendee, CalendarClient, Event, EventCreate, EventUpdate
from google_calendar_service.integrations import issue_to_calendar

if TYPE_CHECKING:
    from api.issue import Issue  # type: ignore[import-untyped] # The issue-tracker package does not ship a py.typed marker

ISSUE_ID = "123"


@dataclass
class FakeEvent(Event):
    """Concrete Event implementation for tests."""

    _id: str = "fake-event"
    _title: str = "Fake Event"
    _start_time: datetime = field(default_factory=lambda: datetime(2026, 1, 1, tzinfo=UTC))
    _end_time: datetime = field(default_factory=lambda: datetime(2026, 1, 1, 1, tzinfo=UTC))
    _description: str | None = None
    _location: str | None = None
    _attendees: list[Attendee] = field(default_factory=list)
    _attachments: list[str] = field(default_factory=list)

    @property
    def id(self) -> str:
        """Return event ID."""
        return self._id

    @property
    def title(self) -> str:
        """Return event title."""
        return self._title

    @property
    def start_time(self) -> datetime:
        """Return event start time."""
        return self._start_time

    @property
    def end_time(self) -> datetime:
        """Return event end time."""
        return self._end_time

    @property
    def description(self) -> str | None:
        """Return event description."""
        return self._description

    @property
    def location(self) -> str | None:
        """Return event location."""
        return self._location

    @property
    def attendees(self) -> list[Attendee]:
        """Return event attendees."""
        return self._attendees

    @property
    def attachments(self) -> list[str]:
        """Return event attachments."""
        return self._attachments


class FakeCalendarClient(CalendarClient):
    """Fake calendar client that records create_event_from_dto calls."""

    def __init__(self) -> None:
        """Initialize recorded calendar create calls."""
        self.created_events: list[EventCreate] = []

    def create_event_from_dto(self, event_create: EventCreate) -> Event:
        """Record event creation and return a mock event."""
        self.created_events.append(event_create)
        return FakeEvent(
            _id="evt-999",
            _title=event_create.title,
            _start_time=event_create.start_time,
            _end_time=event_create.end_time,
            _description=event_create.description,
        )

    def get_event_by_id(self, event_id: str) -> Event:
        """Return a fake event by ID."""
        return FakeEvent(_id=event_id)

    def list_upcoming_events(self, max_results: int = 10) -> list[Event]:
        """Return empty list."""
        return []

    def list_events_between(self, start: datetime, end: datetime) -> list[Event]:
        """Return empty list."""
        return []

    def update_event_from_patch(self, event_id: str, event_patch: EventUpdate) -> Event:
        """Return a fake updated event."""
        return FakeEvent(_id=event_id)

    def delete_event(self, event_id: str) -> None:
        """No-op delete for testing."""


class FakeIssueClient:
    """Fake issue client that records calls and returns a mock issue."""

    def __init__(self) -> None:
        """Initialize fake issue client state."""
        self.requested_issue_id: str | None = None

    def get_issue(self, issue_id: str) -> Issue:
        """Return a mock issue and record the requested ID."""
        self.requested_issue_id = issue_id
        return cast(
            "Issue",
            SimpleNamespace(
                id=123,
                title="Broken auth redirect",
                desc="Investigate redirect_uri mismatch in OAuth callback flow.",
                status="open",
            ),
        )


def test_build_event_payload_from_issue_includes_issue_fields() -> None:
    """Verify payload includes title, time, and issue-derived description fields."""
    issue = cast(
        "Issue",
        SimpleNamespace(
            id=123,
            title="Broken auth redirect",
            desc="Investigate redirect_uri mismatch in OAuth callback flow.",
            status="open",
        ),
    )

    payload = issue_to_calendar.build_event_payload_from_issue(
        issue=issue,
        start="2026-04-23T15:00:00-04:00",
        end="2026-04-23T16:00:00-04:00",
    )

    assert payload["title"] == "Issue Review: Broken auth redirect"
    assert payload["start"] == "2026-04-23T15:00:00-04:00"
    assert payload["end"] == "2026-04-23T16:00:00-04:00"

    description = payload["description"]
    assert isinstance(description, str)
    assert "Issue ID: 123" in description
    assert "Investigate redirect_uri mismatch in OAuth callback flow." in description
    assert "Status: open" in description


def test_create_event_from_issue_flow_fetches_issue_and_creates_calendar_event() -> None:
    """Verify full flow: issue is fetched and event is created with correct payload."""
    fake_issue_client = FakeIssueClient()
    fake_calendar_client = FakeCalendarClient()

    result = issue_to_calendar.create_event_from_issue_flow(
        issue_id=ISSUE_ID,
        start="2026-04-23T15:00:00-04:00",
        end="2026-04-23T16:00:00-04:00",
        issue_client=fake_issue_client,
        calendar_client=fake_calendar_client,
    )

    assert fake_issue_client.requested_issue_id == ISSUE_ID

    assert len(fake_calendar_client.created_events) == 1
    create_call = fake_calendar_client.created_events[0]

    assert create_call.title == "Issue Review: Broken auth redirect"
    assert create_call.start_time == datetime.fromisoformat("2026-04-23T15:00:00-04:00")
    assert create_call.end_time == datetime.fromisoformat("2026-04-23T16:00:00-04:00")
    assert isinstance(create_call.description, str)
    assert "Issue ID: 123" in create_call.description
    assert "Status: open" in create_call.description

    assert result == {
        "issue_id": "123",
        "event_id": "evt-999",
        "event_title": "Issue Review: Broken auth redirect",
        "status": "created",
    }
