"""Tests for AI orchestration logic in agent.py."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

import pytest
from ai_client_api import AiClient
from calendar_client_api import Attendee, CalendarClient, Event, EventCreate, EventUpdate
from google_calendar_service.integrations import agent
from google_calendar_service.integrations.tools import dispatch_tool

if TYPE_CHECKING:
    from collections.abc import Iterable

    from api.issue import Issue  # type: ignore[import-untyped]


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
    """Fake calendar client for testing tool dispatch."""

    def __init__(self) -> None:
        """Initialize recorded calendar operations."""
        self.created_events: list[EventCreate] = []
        self.updated_events: list[tuple[str, EventUpdate]] = []

    def get_event_by_id(self, event_id: str) -> Event:
        """Return a fake event by ID."""
        return FakeEvent(_id=event_id)

    def delete_event(self, event_id: str) -> None:
        """No-op delete for testing."""

    def list_upcoming_events(self, max_results: int = 10) -> Iterable[Event]:
        """Return fake calendar events."""
        return [
            FakeEvent(
                _id="event-1",
                _title="Standup",
                _start_time=datetime.fromisoformat("2026-04-29T10:00:00"),
                _end_time=datetime.fromisoformat("2026-04-29T10:30:00"),
            ),
        ]

    def list_events_between(self, start: datetime, end: datetime) -> Iterable[Event]:
        """Return fake calendar events for a date range."""
        return list(self.list_upcoming_events())

    def create_event_from_dto(self, event_create: EventCreate) -> Event:
        """Record and return fake created event."""
        self.created_events.append(event_create)
        return FakeEvent(
            _id="created-1",
            _title=event_create.title,
            _start_time=event_create.start_time,
            _end_time=event_create.end_time,
            _description=event_create.description,
            _location=event_create.location,
        )

    def update_event_from_patch(self, event_id: str, event_patch: EventUpdate) -> Event:
        """Record and return fake updated event."""
        self.updated_events.append((event_id, event_patch))
        return FakeEvent(
            _id=event_id,
            _title=event_patch.title if isinstance(event_patch.title, str) else "Updated",
            _start_time=datetime.fromisoformat("2026-04-29T10:00:00"),
            _end_time=datetime.fromisoformat("2026-04-29T10:30:00"),
        )


class FakeAiClient(AiClient):
    """Fake AI client that captures inputs and returns a fixed response."""

    def __init__(self) -> None:
        """Initialize captured call storage."""
        self.called_with: dict[str, Any] | None = None

    def send_message(self, prompt: str, context: dict[str, Any] | None = None) -> str:
        """Return a fixed response for single-message calls."""
        return "Final AI response"

    def run_chat_with_tools(self, **kwargs: Any) -> str:
        """Capture tool-loop inputs and return a fixed response."""
        self.called_with = kwargs
        return "Final AI response"


class FakeIssueClient:
    """Fake issue client for testing tool dispatch."""

    def __init__(self) -> None:
        """Initialize recorded issue operations."""
        self.requested_issue_id: str | None = None

    def get_issue(self, issue_id: str) -> Issue:
        """Return a fake issue and record the requested ID."""
        self.requested_issue_id = issue_id
        return cast(
            "Issue",
            SimpleNamespace(
                id=issue_id,
                title="Bug: login broken",
                desc="Login page returns 500.",
                status="open",
            ),
        )


def test_run_ai_turn_calls_ai_client_with_expected_inputs() -> None:
    """Ensure run_ai_turn calls the AI client correctly."""
    ai = FakeAiClient()
    calendar = FakeCalendarClient()
    issue = FakeIssueClient()

    result = agent.run_ai_turn(
        prompt="Schedule a meeting",
        context={"timezone": "UTC"},
        ai_client=ai,
        calendar_client=calendar,
        issue_client=issue,
    )

    assert result == "Final AI response"
    assert ai.called_with is not None
    assert ai.called_with["system_prompt"] == agent.SYSTEM_PROMPT
    assert "Schedule a meeting" in ai.called_with["user_message"]
    assert "Context JSON" in ai.called_with["user_message"]
    assert isinstance(ai.called_with["tools"], list)


def test_dispatch_tool_create_event() -> None:
    """Ensure create_event tool is dispatched correctly."""
    calendar = FakeCalendarClient()
    issue = FakeIssueClient()

    result = dispatch_tool(
        name="create_event",
        arguments={
            "title": "Meeting",
            "start": "2026-04-21T15:00:00",
            "end": "2026-04-21T16:00:00",
        },
        calendar_client=calendar,
        issue_client=issue,
    )

    assert isinstance(result, dict)
    assert result["id"] == "created-1"
    assert len(calendar.created_events) == 1
    assert calendar.created_events[0].title == "Meeting"


def test_dispatch_tool_list_events() -> None:
    """Ensure list_events tool is dispatched correctly."""
    calendar = FakeCalendarClient()
    issue = FakeIssueClient()

    result = dispatch_tool(
        name="list_events",
        arguments={},
        calendar_client=calendar,
        issue_client=issue,
    )

    assert isinstance(result, list)
    assert result[0]["id"] == "event-1"


def test_dispatch_tool_update_event_missing_reference() -> None:
    """Ensure update_event raises TypeError when reference is missing."""
    calendar = FakeCalendarClient()
    issue = FakeIssueClient()

    with pytest.raises(TypeError, match="Missing event_reference"):
        dispatch_tool(
            name="update_event",
            arguments={},
            calendar_client=calendar,
            issue_client=issue,
        )


def test_dispatch_tool_unknown_tool() -> None:
    """Ensure unknown tool raises ValueError."""
    calendar = FakeCalendarClient()
    issue = FakeIssueClient()

    with pytest.raises(ValueError, match="Unknown tool"):
        dispatch_tool(
            name="unknown_tool",
            arguments={},
            calendar_client=calendar,
            issue_client=issue,
        )


def test_dispatch_tool_create_event_from_issue() -> None:
    """Ensure create_event_from_issue tool dispatches with injected clients."""
    calendar = FakeCalendarClient()
    issue = FakeIssueClient()

    result = cast(
        "dict[str, object]",
        dispatch_tool(
            name="create_event_from_issue",
            arguments={
                "issue_id": "42",
                "start": "2026-05-01T10:00:00",
                "end": "2026-05-01T11:00:00",
            },
            calendar_client=calendar,
            issue_client=issue,
        ),
    )

    assert result["status"] == "created"
    assert result["issue_id"] == "42"
    assert issue.requested_issue_id == "42"
    assert len(calendar.created_events) == 1
