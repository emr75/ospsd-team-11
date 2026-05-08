"""Tests for AI orchestration logic in agent.py."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

import pytest
from ai_client_api import AiClient
from api.issue import Status  # type: ignore[import-untyped]
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
        self.events_between: list[Event] = []

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
        if self.events_between:
            return self.events_between
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
        self.boards: list[Any] = [
            SimpleNamespace(id="board-1", board_name="Engineering"),
        ]
        self.issues: dict[str, Any] = {
            "42": SimpleNamespace(
                id="42",
                title="Bug: login broken",
                desc="Login page returns 500.",
                members=["alice@example.com"],
                due_date="2026-05-08",
                status=Status.TO_DO,
                board_id="board-1",
            ),
            "43": SimpleNamespace(
                id="43",
                title="Add audit logs",
                desc="Track event mutations.",
                members=None,
                due_date=None,
                status=Status.COMPLETED,
                board_id="board-1",
            ),
        }
        self.created_issues: list[dict[str, Any]] = []
        self.updated_issues: list[dict[str, Any]] = []

    def get_issue(self, issue_id: str) -> Issue:
        """Return a fake issue and record the requested ID."""
        self.requested_issue_id = issue_id
        return cast("Issue", self.issues[issue_id])

    def get_boards(self) -> Iterable[Any]:
        """Return fake boards."""
        return self.boards

    def get_issues(self, board_id: str) -> Iterable[Issue]:
        """Return fake issues for a board."""
        return [cast("Issue", issue) for issue in self.issues.values() if issue.board_id == board_id]

    def create_issue(  # noqa: PLR0913
        self,
        title: str,
        board_id: str,
        desc: str | None = None,
        members: list[str] | None = None,
        due_date: str | None = None,
        status: Any = None,
    ) -> Issue:
        """Create and store a fake issue."""
        issue_id = "created-issue"
        resolved_status = status if isinstance(status, Status) else Status.TO_DO
        issue = SimpleNamespace(
            id=issue_id,
            title=title,
            desc=desc or "",
            members=members,
            due_date=due_date,
            status=resolved_status,
            board_id=board_id,
        )
        self.issues[issue_id] = issue
        self.created_issues.append(
            {
                "title": title,
                "board_id": board_id,
                "desc": desc,
                "members": members,
                "due_date": due_date,
                "status": resolved_status,
            }
        )
        return cast("Issue", issue)

    def update_issue(  # noqa: PLR0913
        self,
        issue_id: str,
        title: str | None = None,
        desc: str | None = None,
        members: list[str] | None = None,
        due_date: str | None = None,
        status: Any = None,
        board_id: str | None = None,
    ) -> Issue:
        """Update a fake issue."""
        issue = self.issues[issue_id]
        if title is not None:
            issue.title = title
        if desc is not None:
            issue.desc = desc
        if members is not None:
            issue.members = members
        if due_date is not None:
            issue.due_date = due_date
        if status is not None:
            issue.status = status
        if board_id is not None:
            issue.board_id = board_id
        self.updated_issues.append(
            {
                "issue_id": issue_id,
                "title": title,
                "desc": desc,
                "members": members,
                "due_date": due_date,
                "status": status,
                "board_id": board_id,
            }
        )
        return cast("Issue", issue)


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


def test_dispatch_tool_update_event_missing_id() -> None:
    """Ensure update_event raises TypeError when event_id is missing."""
    calendar = FakeCalendarClient()
    issue = FakeIssueClient()

    with pytest.raises(TypeError, match="Missing event_id"):
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


def test_dispatch_tool_lists_issue_boards() -> None:
    """Ensure issue boards are exposed to the AI tool layer."""
    calendar = FakeCalendarClient()
    issue = FakeIssueClient()

    result = dispatch_tool(
        name="list_issue_boards",
        arguments={},
        calendar_client=calendar,
        issue_client=issue,
    )

    assert isinstance(result, list)
    assert result == [{"id": "board-1", "name": "Engineering"}]


def test_dispatch_tool_lists_filtered_issues() -> None:
    """Ensure issues can be listed and filtered by shared status."""
    calendar = FakeCalendarClient()
    issue = FakeIssueClient()

    result = dispatch_tool(
        name="list_issues",
        arguments={"board_id": "board-1", "status": "done"},
        calendar_client=calendar,
        issue_client=issue,
    )

    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["id"] == "43"


def test_dispatch_tool_get_issue() -> None:
    """Ensure a single issue can be fetched."""
    calendar = FakeCalendarClient()
    issue = FakeIssueClient()

    result = cast(
        "dict[str, object]",
        dispatch_tool(
            name="get_issue",
            arguments={"issue_id": "42"},
            calendar_client=calendar,
            issue_client=issue,
        ),
    )

    assert result["title"] == "Bug: login broken"
    assert result["board_id"] == "board-1"


def test_dispatch_tool_create_issue() -> None:
    """Ensure the agent can create issue tracker issues."""
    calendar = FakeCalendarClient()
    issue = FakeIssueClient()

    result = cast(
        "dict[str, object]",
        dispatch_tool(
            name="create_issue",
            arguments={
                "title": "Fix calendar OAuth refresh",
                "board_id": "board-1",
                "description": "Refresh token handling fails.",
                "members": ["dev@example.com"],
                "status": "open",
            },
            calendar_client=calendar,
            issue_client=issue,
        ),
    )

    assert result["id"] == "created-issue"
    assert result["status"] == "to_do"
    assert issue.created_issues[0]["desc"] == "Refresh token handling fails."


def test_dispatch_tool_update_issue_status() -> None:
    """Ensure the agent can update issue status."""
    calendar = FakeCalendarClient()
    issue = FakeIssueClient()

    result = cast(
        "dict[str, object]",
        dispatch_tool(
            name="update_issue",
            arguments={"issue_id": "42", "status": "in progress"},
            calendar_client=calendar,
            issue_client=issue,
        ),
    )

    assert result["status"] == "in_progress"
    assert issue.updated_issues[0]["status"] == Status.IN_PROGRESS


def test_dispatch_tool_schedule_issue_work_session_uses_first_gap() -> None:
    """Ensure issue work scheduling creates an event in the first available slot."""
    calendar = FakeCalendarClient()
    calendar.events_between = [
        FakeEvent(
            _id="busy-1",
            _title="Blocked",
            _start_time=datetime.fromisoformat("2026-05-08T09:00:00"),
            _end_time=datetime.fromisoformat("2026-05-08T10:00:00"),
        ),
        FakeEvent(
            _id="busy-2",
            _title="Another meeting",
            _start_time=datetime.fromisoformat("2026-05-08T11:00:00"),
            _end_time=datetime.fromisoformat("2026-05-08T11:30:00"),
        ),
    ]
    issue = FakeIssueClient()

    result = cast(
        "dict[str, object]",
        dispatch_tool(
            name="schedule_issue_work_session",
            arguments={
                "issue_id": "42",
                "window_start": "2026-05-08T09:00:00",
                "window_end": "2026-05-08T12:00:00",
                "duration_minutes": 45,
                "update_status": True,
            },
            calendar_client=calendar,
            issue_client=issue,
        ),
    )

    event = cast("dict[str, object]", result["event"])
    scheduled_issue = cast("dict[str, object]", result["issue"])
    assert result["status"] == "scheduled"
    assert event["start_time"] == "2026-05-08T10:00:00"
    assert event["end_time"] == "2026-05-08T10:45:00"
    assert scheduled_issue["status"] == "in_progress"
    assert calendar.created_events[0].title == "Issue Work: Bug: login broken"
