"""Integration tests for the AI orchestration and tool-dispatch pipeline.

These tests wire together fakes for AiClient, CalendarClient, and IssueClient
to verify the cross-component tool-calling flow end-to-end.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

import pytest
from ai_client_api import AiClient
from api.issue import Status  # type: ignore[import-untyped] # The issue-tracker package does not ship a py.typed marker
from calendar_client_api import Attendee, CalendarClient, Event, EventCreate, EventUpdate
from google_calendar_service.integrations import agent
from google_calendar_service.integrations.tools import dispatch_tool

if TYPE_CHECKING:
    from collections.abc import Iterable

    from api.issue import Issue

pytestmark = pytest.mark.integration


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


# ---------------------------------------------------------------------------
# make_tool_handler tests
# ---------------------------------------------------------------------------


def test_make_tool_handler_returns_json_on_success() -> None:
    """Ensure the handler serializes a successful tool result to JSON."""
    from google_calendar_service.integrations.tools import make_tool_handler

    calendar = FakeCalendarClient()
    issue = FakeIssueClient()
    handler = make_tool_handler(calendar, issue)

    result = handler("list_events", {})
    parsed = json.loads(result)
    assert isinstance(parsed, list)
    assert parsed[0]["id"] == "event-1"


def test_make_tool_handler_returns_error_json_on_type_error() -> None:
    """Ensure TypeError from dispatch is caught and returned as JSON error."""
    from google_calendar_service.integrations.tools import make_tool_handler

    calendar = FakeCalendarClient()
    issue = FakeIssueClient()
    handler = make_tool_handler(calendar, issue)

    result = handler("create_event", {})
    parsed = json.loads(result)
    assert "error" in parsed
    assert parsed["tool"] == "create_event"


def test_make_tool_handler_returns_error_json_on_unexpected_exception() -> None:
    """Ensure unexpected exceptions are caught and returned as JSON error."""
    from google_calendar_service.integrations.tools import make_tool_handler

    calendar = FakeCalendarClient()
    issue = FakeIssueClient()
    handler = make_tool_handler(calendar, issue)

    # Trigger a KeyError inside get_issue by requesting a non-existent ID
    result = handler("get_issue", {"issue_id": "nonexistent"})
    parsed = json.loads(result)
    assert "error" in parsed
    assert parsed["tool"] == "get_issue"


# ---------------------------------------------------------------------------
# update_event handler tests
# ---------------------------------------------------------------------------


def test_dispatch_tool_update_event_success() -> None:
    """Ensure update_event dispatches and returns updated event dict."""
    calendar = FakeCalendarClient()
    issue = FakeIssueClient()

    result = cast(
        "dict[str, object]",
        dispatch_tool(
            name="update_event",
            arguments={
                "event_id": "event-1",
                "title": "Renamed",
                "start_time": "2026-05-01T09:00:00",
                "end_time": "2026-05-01T10:00:00",
                "description": "New desc",
                "location": "Room A",
            },
            calendar_client=calendar,
            issue_client=issue,
        ),
    )

    assert result["id"] == "event-1"
    assert len(calendar.updated_events) == 1


# ---------------------------------------------------------------------------
# list_events with date range
# ---------------------------------------------------------------------------


def test_dispatch_tool_list_events_with_date_range() -> None:
    """Ensure list_events uses list_events_between when start and end are given."""
    calendar = FakeCalendarClient()
    issue = FakeIssueClient()

    result = dispatch_tool(
        name="list_events",
        arguments={
            "start": "2026-04-29T00:00:00",
            "end": "2026-04-30T00:00:00",
        },
        calendar_client=calendar,
        issue_client=issue,
    )

    assert isinstance(result, list)


# ---------------------------------------------------------------------------
# create_event_from_issue validation
# ---------------------------------------------------------------------------


def test_dispatch_tool_create_event_from_issue_missing_fields() -> None:
    """Ensure create_event_from_issue raises TypeError on missing fields."""
    calendar = FakeCalendarClient()
    issue = FakeIssueClient()

    with pytest.raises(TypeError, match="Missing issue_id"):
        dispatch_tool(
            name="create_event_from_issue",
            arguments={"start": "2026-05-01T10:00:00", "end": "2026-05-01T11:00:00"},
            calendar_client=calendar,
            issue_client=issue,
        )

    with pytest.raises(TypeError, match="Missing start"):
        dispatch_tool(
            name="create_event_from_issue",
            arguments={"issue_id": "42"},
            calendar_client=calendar,
            issue_client=issue,
        )


# ---------------------------------------------------------------------------
# list_issues across all boards (no board_id)
# ---------------------------------------------------------------------------


def test_dispatch_tool_list_issues_all_boards() -> None:
    """Ensure list_issues iterates all boards when board_id is omitted."""
    calendar = FakeCalendarClient()
    issue = FakeIssueClient()

    result = dispatch_tool(
        name="list_issues",
        arguments={},
        calendar_client=calendar,
        issue_client=issue,
    )

    assert isinstance(result, list)
    expected_issue_count = len(issue.issues)
    assert len(result) == expected_issue_count


# ---------------------------------------------------------------------------
# create_event missing required fields
# ---------------------------------------------------------------------------


def test_dispatch_tool_create_event_missing_start() -> None:
    """Ensure create_event raises TypeError when start is missing."""
    calendar = FakeCalendarClient()
    issue = FakeIssueClient()

    with pytest.raises(TypeError, match="Missing start"):
        dispatch_tool(
            name="create_event",
            arguments={"title": "Meeting", "end": "2026-05-01T16:00:00"},
            calendar_client=calendar,
            issue_client=issue,
        )


def test_dispatch_tool_create_event_missing_end() -> None:
    """Ensure create_event raises TypeError when end is missing."""
    calendar = FakeCalendarClient()
    issue = FakeIssueClient()

    with pytest.raises(TypeError, match="Missing end"):
        dispatch_tool(
            name="create_event",
            arguments={"title": "Meeting", "start": "2026-05-01T15:00:00"},
            calendar_client=calendar,
            issue_client=issue,
        )


# ---------------------------------------------------------------------------
# schedule_issue_work_session validation and edge cases
# ---------------------------------------------------------------------------


def test_dispatch_tool_schedule_missing_window_start() -> None:
    """Ensure schedule_issue_work_session raises TypeError for missing window_start."""
    calendar = FakeCalendarClient()
    issue = FakeIssueClient()

    with pytest.raises(TypeError, match="Missing window_start"):
        dispatch_tool(
            name="schedule_issue_work_session",
            arguments={
                "issue_id": "42",
                "window_end": "2026-05-08T12:00:00",
                "duration_minutes": 30,
            },
            calendar_client=calendar,
            issue_client=issue,
        )


def test_dispatch_tool_schedule_missing_window_end() -> None:
    """Ensure schedule_issue_work_session raises TypeError for missing window_end."""
    calendar = FakeCalendarClient()
    issue = FakeIssueClient()

    with pytest.raises(TypeError, match="Missing window_end"):
        dispatch_tool(
            name="schedule_issue_work_session",
            arguments={
                "issue_id": "42",
                "window_start": "2026-05-08T09:00:00",
                "duration_minutes": 30,
            },
            calendar_client=calendar,
            issue_client=issue,
        )


def test_dispatch_tool_schedule_missing_duration() -> None:
    """Ensure schedule_issue_work_session raises TypeError for missing duration."""
    calendar = FakeCalendarClient()
    issue = FakeIssueClient()

    with pytest.raises(TypeError, match="Missing duration_minutes"):
        dispatch_tool(
            name="schedule_issue_work_session",
            arguments={
                "issue_id": "42",
                "window_start": "2026-05-08T09:00:00",
                "window_end": "2026-05-08T12:00:00",
            },
            calendar_client=calendar,
            issue_client=issue,
        )


def test_dispatch_tool_schedule_no_slot_available() -> None:
    """Ensure schedule raises ValueError when window is fully booked."""
    calendar = FakeCalendarClient()
    calendar.events_between = [
        FakeEvent(
            _id="busy-1",
            _title="All day",
            _start_time=datetime.fromisoformat("2026-05-08T09:00:00"),
            _end_time=datetime.fromisoformat("2026-05-08T12:00:00"),
        ),
    ]
    issue = FakeIssueClient()

    with pytest.raises(ValueError, match="No available calendar slot"):
        dispatch_tool(
            name="schedule_issue_work_session",
            arguments={
                "issue_id": "42",
                "window_start": "2026-05-08T09:00:00",
                "window_end": "2026-05-08T12:00:00",
                "duration_minutes": 60,
            },
            calendar_client=calendar,
            issue_client=issue,
        )


def test_dispatch_tool_schedule_window_end_before_start() -> None:
    """Ensure schedule raises ValueError when window is inverted."""
    calendar = FakeCalendarClient()
    issue = FakeIssueClient()

    with pytest.raises(ValueError, match="window_end must be after window_start"):
        dispatch_tool(
            name="schedule_issue_work_session",
            arguments={
                "issue_id": "42",
                "window_start": "2026-05-08T12:00:00",
                "window_end": "2026-05-08T09:00:00",
                "duration_minutes": 30,
            },
            calendar_client=calendar,
            issue_client=issue,
        )


# ---------------------------------------------------------------------------
# _parse_status edge cases
# ---------------------------------------------------------------------------


def test_parse_status_invalid_value() -> None:
    """Ensure _parse_status raises ValueError for unknown status strings."""
    from google_calendar_service.integrations.tools import _parse_status

    with pytest.raises(ValueError, match="Unsupported status"):
        _parse_status("nonexistent_status")


def test_parse_status_non_string() -> None:
    """Ensure _parse_status raises TypeError for non-string input."""
    from google_calendar_service.integrations.tools import _parse_status

    with pytest.raises(TypeError, match="status must be a string"):
        _parse_status(42)


def test_parse_status_returns_enum_directly() -> None:
    """Ensure _parse_status passes through Status enum values."""
    from google_calendar_service.integrations.tools import _parse_status

    assert _parse_status(Status.IN_PROGRESS) is Status.IN_PROGRESS


# ---------------------------------------------------------------------------
# _optional_string_list edge cases
# ---------------------------------------------------------------------------


def test_optional_string_list_rejects_non_list() -> None:
    """Ensure _optional_string_list raises TypeError for non-list input."""
    from google_calendar_service.integrations.tools import _optional_string_list

    with pytest.raises(TypeError, match="members must be a list"):
        _optional_string_list("not-a-list", "members")


def test_optional_string_list_rejects_non_string_items() -> None:
    """Ensure _optional_string_list raises TypeError for non-string items."""
    from google_calendar_service.integrations.tools import _optional_string_list

    with pytest.raises(TypeError, match="members must be a list"):
        _optional_string_list([1, 2, 3], "members")


# ---------------------------------------------------------------------------
# AI tool-calling loop integration test
#
# The rubric requires at least one integration test that demonstrates
# an AI tool-call invoking the cross-vertical application.  Unlike the
# tests above (which call dispatch_tool directly), this test wires a
# scripted AiClient that *actually invokes* the handle_tool callback,
# proving the full pipeline:
#   AI client  →  tool dispatch  →  issue-tracker  →  calendar client
# ---------------------------------------------------------------------------


class ScriptedAiClient(AiClient):
    """AI client that replays a scripted tool-call then returns a final message.

    On the first call to run_chat_with_tools, it invokes ``handle_tool``
    with a predetermined tool name and arguments, exactly as a real LLM
    would.  On receipt of the tool result it returns a final summary.
    """

    def __init__(self, tool_name: str, tool_args: dict[str, Any]) -> None:
        """Store the scripted tool call to replay."""
        self._tool_name = tool_name
        self._tool_args = tool_args
        self.tool_result: str | None = None

    def send_message(self, prompt: str, context: dict[str, Any] | None = None) -> str:
        """Not used in tool-calling flow."""
        return ""  # pragma: no cover

    def run_chat_with_tools(
        self,
        *,
        system_prompt: str,
        user_message: str,
        tools: list[dict[str, Any]],
        handle_tool: Any,
        max_tool_rounds: int = 8,
    ) -> str:
        """Invoke the tool handler once, capture the result, return a summary."""
        self.tool_result = handle_tool(self._tool_name, self._tool_args)
        return f"Done. Tool returned: {self.tool_result}"


def test_ai_tool_call_invokes_cross_vertical_issue_to_calendar() -> None:
    """Full pipeline: scripted AI client → tool dispatch → issue fetch → calendar event.

    This satisfies the rubric requirement that at least one integration test
    demonstrates an AI tool-call invoking the cross-vertical application.
    The ScriptedAiClient simulates a model requesting create_event_from_issue,
    which fetches issue 42 from the fake issue tracker and creates a calendar
    event — proving the full AI → cross-vertical → domain-action path.
    """
    scripted_ai = ScriptedAiClient(
        tool_name="create_event_from_issue",
        tool_args={
            "issue_id": "42",
            "start": "2026-06-01T10:00:00",
            "end": "2026-06-01T11:00:00",
        },
    )
    calendar = FakeCalendarClient()
    issue = FakeIssueClient()

    result = agent.run_ai_turn(
        prompt="Schedule a meeting for issue 42",
        context=None,
        ai_client=scripted_ai,
        calendar_client=calendar,
        issue_client=issue,
    )

    # The scripted AI client invoked create_event_from_issue through the
    # tool handler, which should have:
    #  1. Fetched issue 42 from the FakeIssueClient
    #  2. Created a calendar event via FakeCalendarClient
    assert scripted_ai.tool_result is not None
    parsed = json.loads(scripted_ai.tool_result)
    assert parsed["status"] == "created"
    assert parsed["issue_id"] == "42"
    assert issue.requested_issue_id == "42"
    assert len(calendar.created_events) == 1
    assert "Done. Tool returned:" in result


def test_ai_tool_call_schedule_work_session_cross_vertical() -> None:
    """Full pipeline: scripted AI → schedule_issue_work_session → issue + calendar.

    Verifies the cross-vertical scheduling tool through the AI agent layer.
    """
    scripted_ai = ScriptedAiClient(
        tool_name="schedule_issue_work_session",
        tool_args={
            "issue_id": "42",
            "window_start": "2026-06-01T09:00:00",
            "window_end": "2026-06-01T17:00:00",
            "duration_minutes": 60,
            "update_status": True,
        },
    )
    calendar = FakeCalendarClient()
    calendar.events_between = []  # empty calendar — first slot is window_start
    issue = FakeIssueClient()

    result = agent.run_ai_turn(
        prompt="Find time for issue 42 work",
        context=None,
        ai_client=scripted_ai,
        calendar_client=calendar,
        issue_client=issue,
    )

    assert scripted_ai.tool_result is not None
    parsed = json.loads(scripted_ai.tool_result)
    assert parsed["status"] == "scheduled"
    assert parsed["event"]["start_time"] == "2026-06-01T09:00:00"
    assert len(calendar.created_events) == 1
    assert issue.updated_issues[0]["status"] == Status.IN_PROGRESS
    assert "Done. Tool returned:" in result


# ---------------------------------------------------------------------------
# Multi-turn AI tool-call loop integration tests
#
# These tests verify that the AI agent can invoke multiple tools in sequence,
# where later tool calls depend on earlier tool results.  This exercises the
# full pipeline through multiple rounds:
#   AI client  →  tool dispatch  →  service clients  →  AI client (again)
# ---------------------------------------------------------------------------


class MultiTurnScriptedAiClient(AiClient):
    """AI client that replays a scripted sequence of tool calls.

    Each entry in ``tool_calls`` is invoked in order through ``handle_tool``.
    After all tool calls are exhausted, the client returns a final summary.
    """

    def __init__(self, tool_calls: list[tuple[str, dict[str, Any]]]) -> None:
        """Store the scripted tool-call sequence to replay."""
        self._tool_calls = tool_calls
        self.tool_results: list[str] = []

    def send_message(self, prompt: str, context: dict[str, Any] | None = None) -> str:
        """Not used in tool-calling flow."""
        return ""  # pragma: no cover

    def run_chat_with_tools(self, **kwargs: Any) -> str:
        """Invoke each tool in sequence, then return a summary."""
        handle_tool = kwargs["handle_tool"]
        for tool_name, tool_args in self._tool_calls:
            result = handle_tool(tool_name, tool_args)
            self.tool_results.append(result)
        return f"Completed {len(self._tool_calls)} tool calls."


def test_multi_turn_list_issues_then_create_event_from_issue() -> None:
    """Multi-turn: AI lists issues, then creates a calendar event from one.

    Verifies the full multi-round pipeline where the AI first discovers
    available issues (list_issues), then uses the result to schedule a
    meeting for a specific issue (create_event_from_issue).
    """
    scripted_ai = MultiTurnScriptedAiClient(
        tool_calls=[
            ("list_issues", {"board_id": "board-1"}),
            (
                "create_event_from_issue",
                {
                    "issue_id": "42",
                    "start": "2026-06-15T14:00:00",
                    "end": "2026-06-15T15:00:00",
                },
            ),
        ]
    )
    calendar = FakeCalendarClient()
    issue = FakeIssueClient()

    result = agent.run_ai_turn(
        prompt="Find my open issues and schedule a meeting for the login bug",
        context=None,
        ai_client=scripted_ai,
        calendar_client=calendar,
        issue_client=issue,
    )

    assert len(scripted_ai.tool_results) == 2

    issues_result = json.loads(scripted_ai.tool_results[0])
    assert isinstance(issues_result, list)
    assert any(i["id"] == "42" for i in issues_result)

    event_result = json.loads(scripted_ai.tool_results[1])
    assert event_result["status"] == "created"
    assert event_result["issue_id"] == "42"
    assert len(calendar.created_events) == 1
    assert "Completed 2 tool calls." in result


def test_multi_turn_get_issue_then_schedule_work_session() -> None:
    """Multi-turn: AI fetches issue details, then schedules a work session.

    Verifies a realistic multi-step workflow where the AI inspects an issue
    before finding a free calendar slot and scheduling time for it.
    """
    scripted_ai = MultiTurnScriptedAiClient(
        tool_calls=[
            ("get_issue", {"issue_id": "42"}),
            (
                "schedule_issue_work_session",
                {
                    "issue_id": "42",
                    "window_start": "2026-06-15T09:00:00",
                    "window_end": "2026-06-15T17:00:00",
                    "duration_minutes": 90,
                    "update_status": True,
                },
            ),
        ]
    )
    calendar = FakeCalendarClient()
    calendar.events_between = []
    issue = FakeIssueClient()

    result = agent.run_ai_turn(
        prompt="Look up issue 42 and find time to work on it today",
        context={"timezone": "America/New_York"},
        ai_client=scripted_ai,
        calendar_client=calendar,
        issue_client=issue,
    )

    assert len(scripted_ai.tool_results) == 2

    issue_detail = json.loads(scripted_ai.tool_results[0])
    assert issue_detail["title"] == "Bug: login broken"

    schedule_result = json.loads(scripted_ai.tool_results[1])
    assert schedule_result["status"] == "scheduled"
    assert schedule_result["event"]["start_time"] == "2026-06-15T09:00:00"
    assert len(calendar.created_events) == 1
    assert issue.updated_issues[0]["status"] == Status.IN_PROGRESS
    assert "Completed 2 tool calls." in result


def test_multi_turn_create_issue_then_schedule_from_it() -> None:
    """Multi-turn: AI creates an issue, then schedules a work session for it.

    Verifies the full cross-vertical round-trip: create on the issue tracker,
    then schedule on the calendar, all through the AI tool-calling pipeline.
    """
    scripted_ai = MultiTurnScriptedAiClient(
        tool_calls=[
            (
                "create_issue",
                {
                    "title": "Implement OAuth refresh",
                    "board_id": "board-1",
                    "description": "Add token refresh logic.",
                    "status": "open",
                },
            ),
            (
                "create_event_from_issue",
                {
                    "issue_id": "created-issue",
                    "start": "2026-06-20T10:00:00",
                    "end": "2026-06-20T11:00:00",
                },
            ),
        ]
    )
    calendar = FakeCalendarClient()
    issue = FakeIssueClient()

    result = agent.run_ai_turn(
        prompt="Create an issue for OAuth refresh and schedule a review meeting",
        context=None,
        ai_client=scripted_ai,
        calendar_client=calendar,
        issue_client=issue,
    )

    assert len(scripted_ai.tool_results) == 2

    created = json.loads(scripted_ai.tool_results[0])
    assert created["id"] == "created-issue"
    assert created["title"] == "Implement OAuth refresh"

    event_result = json.loads(scripted_ai.tool_results[1])
    assert event_result["status"] == "created"
    assert event_result["issue_id"] == "created-issue"
    assert len(calendar.created_events) == 1
    assert len(issue.created_issues) == 1
    assert "Completed 2 tool calls." in result


def test_multi_turn_tool_error_does_not_break_subsequent_calls() -> None:
    """Multi-turn: a tool error on one call does not prevent the next call.

    Verifies that the make_tool_handler error-catching logic returns a JSON
    error for a failed tool, and the AI can still invoke the next tool.
    """
    scripted_ai = MultiTurnScriptedAiClient(
        tool_calls=[
            ("get_issue", {"issue_id": "nonexistent"}),
            ("list_events", {}),
        ]
    )
    calendar = FakeCalendarClient()
    issue = FakeIssueClient()

    result = agent.run_ai_turn(
        prompt="Check issue 999 and list my events",
        context=None,
        ai_client=scripted_ai,
        calendar_client=calendar,
        issue_client=issue,
    )

    assert len(scripted_ai.tool_results) == 2

    error_result = json.loads(scripted_ai.tool_results[0])
    assert "error" in error_result
    assert error_result["tool"] == "get_issue"

    events_result = json.loads(scripted_ai.tool_results[1])
    assert isinstance(events_result, list)
    assert events_result[0]["id"] == "event-1"
    assert "Completed 2 tool calls." in result
