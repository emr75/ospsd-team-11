# ruff: noqa: D103, PLR0913
"""Focused unit tests for AI tool dispatch argument handling."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import Mock

import pytest
from api.issue import Status  # type: ignore[import-untyped] # The issue-tracker package does not ship a py.typed marker
from calendar_client_api import EventCreate, EventUpdate
from google_calendar_service.integrations import tools
from google_calendar_service.integrations.tools import dispatch_tool, make_tool_handler

if TYPE_CHECKING:
    from calendar_client_api import CalendarClient

ISSUE_COUNT = 2


def _event(
    *,
    event_id: str = "event-1",
    title: str = "Standup",
    start: datetime | None = None,
    end: datetime | None = None,
    description: str | None = None,
    location: str | None = None,
) -> Any:
    return SimpleNamespace(
        id=event_id,
        title=title,
        start_time=start or datetime(2026, 5, 8, 9, 0, tzinfo=UTC),
        end_time=end or datetime(2026, 5, 8, 9, 30, tzinfo=UTC),
        description=description,
        location=location,
    )


def _issue(
    *,
    issue_id: str = "42",
    title: str = "Bug: login broken",
    status: Status = Status.TO_DO,
    due_date: str | None = "2026-05-08",
) -> Any:
    return SimpleNamespace(
        id=issue_id,
        title=title,
        desc="Login page returns 500.",
        members=["alice@example.com"],
        due_date=due_date,
        status=status,
        board_id="board-1",
    )


def _calendar_client() -> Mock:
    client = Mock()
    client.create_event_from_dto.side_effect = lambda dto: _event(
        event_id="created-1",
        title=dto.title,
        start=dto.start_time,
        end=dto.end_time,
        description=dto.description,
        location=dto.location,
    )
    client.list_upcoming_events.return_value = [_event()]
    client.list_events_between.return_value = []
    client.update_event_from_patch.side_effect = lambda event_id, patch: _event(
        event_id=event_id,
        title=patch.title if isinstance(patch.title, str) else "Updated",
        start=patch.start_time if isinstance(patch.start_time, datetime) else datetime(2026, 5, 1, 9, 0, tzinfo=UTC),
        end=patch.end_time if isinstance(patch.end_time, datetime) else datetime(2026, 5, 1, 10, 0, tzinfo=UTC),
        description=patch.description if isinstance(patch.description, str) else None,
        location=patch.location if isinstance(patch.location, str) else None,
    )
    return client


def _issue_client() -> Mock:
    issues = {
        "42": _issue(),
        "43": _issue(issue_id="43", title="Add audit logs", status=Status.COMPLETED, due_date=None),
    }
    client = Mock()
    client.get_boards.return_value = [SimpleNamespace(id="board-1", board_name="Engineering")]
    client.get_issues.side_effect = lambda board_id: [issue for issue in issues.values() if issue.board_id == board_id]
    client.get_issue.side_effect = lambda issue_id: issues[issue_id]

    def create_issue(**kwargs: Any) -> Any:
        issue = _issue(
            issue_id="created-issue",
            title=kwargs["title"],
            status=kwargs.get("status", Status.TO_DO),
            due_date=kwargs.get("due_date"),
        )
        issue.desc = kwargs.get("desc")
        issue.members = kwargs.get("members")
        issue.board_id = kwargs["board_id"]
        return issue

    def update_issue(issue_id: str, **kwargs: Any) -> Any:
        issue = issues[issue_id]
        for source, target in {
            "title": "title",
            "desc": "desc",
            "members": "members",
            "due_date": "due_date",
            "status": "status",
            "board_id": "board_id",
        }.items():
            if kwargs.get(source) is not None:
                setattr(issue, target, kwargs[source])
        return issue

    client.create_issue.side_effect = create_issue
    client.update_issue.side_effect = update_issue
    return client


def test_calendar_tools_map_arguments_to_client_calls() -> None:
    calendar = _calendar_client()
    issue = _issue_client()

    created = cast(
        "dict[str, object]",
        dispatch_tool(
            name="create_event",
            arguments={
                "title": "Planning",
                "start": "2026-04-21T15:00:00",
                "end": "2026-04-21T16:00:00",
                "description": "Sprint work",
                "location": "Room A",
            },
            calendar_client=calendar,
            issue_client=issue,
        ),
    )
    upcoming = dispatch_tool(name="list_events", arguments={}, calendar_client=calendar, issue_client=issue)
    ranged = dispatch_tool(
        name="list_events",
        arguments={"start": "2026-04-29T00:00:00", "end": "2026-04-30T00:00:00"},
        calendar_client=calendar,
        issue_client=issue,
    )
    updated = cast(
        "dict[str, object]",
        dispatch_tool(
            name="update_event",
            arguments={
                "event_id": "event-1",
                "title": "Renamed",
                "start_time": "2026-05-01T09:00:00",
                "end_time": "2026-05-01T10:00:00",
                "description": "New desc",
                "location": "Room B",
            },
            calendar_client=calendar,
            issue_client=issue,
        ),
    )

    create_dto = calendar.create_event_from_dto.call_args.args[0]
    update_patch = calendar.update_event_from_patch.call_args.args[1]
    assert isinstance(create_dto, EventCreate)
    assert create_dto.title == "Planning"
    assert created["id"] == "created-1"
    assert isinstance(upcoming, list)
    assert isinstance(ranged, list)
    assert isinstance(update_patch, EventUpdate)
    assert update_patch.location == "Room B"
    assert updated["id"] == "event-1"
    calendar.list_events_between.assert_called_once()


def test_issue_tools_map_arguments_to_client_calls() -> None:
    calendar = _calendar_client()
    issue = _issue_client()

    boards = dispatch_tool(name="list_issue_boards", arguments={}, calendar_client=calendar, issue_client=issue)
    filtered = dispatch_tool(
        name="list_issues",
        arguments={"board_id": "board-1", "status": "done"},
        calendar_client=calendar,
        issue_client=issue,
    )
    all_issues = dispatch_tool(name="list_issues", arguments={}, calendar_client=calendar, issue_client=issue)
    created = cast(
        "dict[str, object]",
        dispatch_tool(
            name="create_issue",
            arguments={
                "title": "Fix calendar OAuth refresh",
                "board_id": "board-1",
                "description": "Refresh token handling fails.",
                "members": ["dev@example.com"],
                "due_date": "2026-05-12",
                "status": "open",
            },
            calendar_client=calendar,
            issue_client=issue,
        ),
    )
    updated = cast(
        "dict[str, object]",
        dispatch_tool(
            name="update_issue",
            arguments={
                "issue_id": "42",
                "title": "Fix login",
                "description": "OAuth redirect fails.",
                "members": ["owner@example.com"],
                "due_date": "2026-05-13",
                "status": "in progress",
                "board_id": "board-1",
            },
            calendar_client=calendar,
            issue_client=issue,
        ),
    )
    fetched = cast(
        "dict[str, object]",
        dispatch_tool(name="get_issue", arguments={"issue_id": "42"}, calendar_client=calendar, issue_client=issue),
    )

    assert boards == [{"id": "board-1", "name": "Engineering"}]
    assert isinstance(filtered, list)
    assert filtered[0]["id"] == "43"
    assert isinstance(all_issues, list)
    assert len(all_issues) == ISSUE_COUNT
    assert created["status"] == "to_do"
    assert updated["status"] == "in_progress"
    assert fetched["title"] == "Fix login"
    issue.create_issue.assert_called_once()
    issue.update_issue.assert_called_once()


def test_issue_calendar_tools_delegate_and_schedule_first_free_slot(monkeypatch: pytest.MonkeyPatch) -> None:
    calendar = _calendar_client()
    issue = _issue_client()
    busy = _event(
        event_id="busy-1",
        start=datetime.fromisoformat("2026-05-08T09:00:00"),
        end=datetime.fromisoformat("2026-05-08T10:00:00"),
    )
    calendar.list_events_between.return_value = [busy]

    delegated_result = {"issue_id": "42", "event_id": "created-1", "event_title": "Issue Review", "status": "created"}
    delegated = Mock(return_value=delegated_result)
    monkeypatch.setattr(tools, "create_event_from_issue_flow", delegated)

    from_issue = dispatch_tool(
        name="create_event_from_issue",
        arguments={"issue_id": "42", "start": "2026-05-01T10:00:00", "end": "2026-05-01T11:00:00"},
        calendar_client=calendar,
        issue_client=issue,
    )
    scheduled = cast(
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

    scheduled_event = cast("dict[str, object]", scheduled["event"])
    scheduled_issue = cast("dict[str, object]", scheduled["issue"])
    schedule_dto = calendar.create_event_from_dto.call_args.args[0]
    assert from_issue == delegated_result
    delegated.assert_called_once()
    assert schedule_dto.title == "Issue Work: Bug: login broken"
    assert scheduled_event["start_time"] == "2026-05-08T10:00:00"
    assert scheduled_event["end_time"] == "2026-05-08T10:45:00"
    assert scheduled_issue["status"] == "in_progress"


@pytest.mark.parametrize(
    ("name", "arguments", "message"),
    [
        ("unknown_tool", {}, "Unknown tool"),
        ("create_event", {"title": "Meeting", "end": "2026-05-01T16:00:00"}, "Missing start"),
        ("create_event", {"title": "Meeting", "start": "2026-05-01T15:00:00"}, "Missing end"),
        ("update_event", {}, "Missing event_id"),
        ("get_issue", {}, "Missing issue_id"),
        ("create_issue", {"board_id": "board-1"}, "Missing title"),
        ("create_issue", {"title": "New issue"}, "Missing board_id"),
        ("update_issue", {}, "Missing issue_id"),
        ("create_event_from_issue", {"start": "2026-05-01T10:00:00", "end": "2026-05-01T11:00:00"}, "Missing issue_id"),
        ("create_event_from_issue", {"issue_id": "42", "end": "2026-05-01T11:00:00"}, "Missing start"),
        ("create_event_from_issue", {"issue_id": "42", "start": "2026-05-01T10:00:00"}, "Missing end"),
        (
            "schedule_issue_work_session",
            {"window_start": "2026-05-08T09:00:00", "window_end": "2026-05-08T12:00:00", "duration_minutes": 30},
            "Missing issue_id",
        ),
        (
            "schedule_issue_work_session",
            {"issue_id": "42", "window_end": "2026-05-08T12:00:00", "duration_minutes": 30},
            "Missing window_start",
        ),
        (
            "schedule_issue_work_session",
            {"issue_id": "42", "window_start": "2026-05-08T09:00:00", "duration_minutes": 30},
            "Missing window_end",
        ),
        (
            "schedule_issue_work_session",
            {"issue_id": "42", "window_start": "2026-05-08T09:00:00", "window_end": "2026-05-08T12:00:00"},
            "Missing duration_minutes",
        ),
    ],
)
def test_dispatch_validates_required_arguments(name: str, arguments: dict[str, object], message: str) -> None:
    with pytest.raises((TypeError, ValueError), match=message):
        dispatch_tool(name=name, arguments=arguments, calendar_client=_calendar_client(), issue_client=_issue_client())


def test_scheduler_and_validator_edge_cases() -> None:
    calendar = _calendar_client()
    issue = _issue_client()
    calendar.list_events_between.return_value = [
        _event(
            event_id="busy-1",
            start=datetime.fromisoformat("2026-05-08T09:00:00"),
            end=datetime.fromisoformat("2026-05-08T12:00:00"),
        )
    ]

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
    with pytest.raises(ValueError, match="duration_minutes must be greater than 0"):
        tools._find_first_free_slot(
            calendar_client=cast("CalendarClient", calendar),
            window_start=datetime(2026, 5, 8, 9, 0, tzinfo=UTC),
            window_end=datetime(2026, 5, 8, 12, 0, tzinfo=UTC),
            duration=timedelta(0),
        )
    naive = datetime.fromisoformat("2026-05-08T09:00:00")
    aware = datetime(2026, 5, 8, 9, 0, tzinfo=UTC)
    assert tools._align_datetime(naive, aware).tzinfo is UTC
    assert tools._align_datetime(aware, naive).tzinfo is None


def test_tool_handler_and_small_validators() -> None:
    handler = make_tool_handler(cast("CalendarClient", _calendar_client()), _issue_client())

    success = json.loads(handler("list_events", {}))
    validation_error = json.loads(handler("create_event", {}))
    unexpected_error = json.loads(handler("get_issue", {"issue_id": "missing"}))

    assert success[0]["id"] == "event-1"
    assert validation_error["tool"] == "create_event"
    assert unexpected_error["tool"] == "get_issue"
    assert tools._parse_status(Status.IN_PROGRESS) is Status.IN_PROGRESS
    assert tools._parse_status("started") is Status.IN_PROGRESS
    assert tools._optional_string_list(None, "members") is None
    assert tools._optional_string_list(["dev@example.com"], "members") == ["dev@example.com"]
    with pytest.raises(ValueError, match="Unsupported status"):
        tools._parse_status("not-a-status")
    with pytest.raises(TypeError, match="status must be a string"):
        tools._parse_status(42)
    with pytest.raises(TypeError, match="members must be a list"):
        tools._optional_string_list("dev@example.com", "members")
    with pytest.raises(TypeError, match="members must be a list"):
        tools._optional_string_list([1], "members")
