"""Tool definitions and dispatch handlers for the AI agent."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from api.issue import Status  # type: ignore[import-untyped] # The issue-tracker package does not ship a py.typed marker
from calendar_client_api import EventCreate, EventUpdate
from calendar_client_api.event import UNSET

from google_calendar_service.integrations.issue_to_calendar import (
    create_event_from_issue_flow,
)

if TYPE_CHECKING:
    from api.board import Board  # type: ignore[import-untyped]
    from api.client import Client as IssueClient  # type: ignore[import-untyped]
    from api.issue import Issue
    from calendar_client_api import CalendarClient, Event

logger = logging.getLogger(__name__)

ToolDefinition = dict[str, object]
ToolArguments = dict[str, object]
ToolHandler = Callable[[str, ToolArguments], str]

TOOLS: list[ToolDefinition] = [
    {
        "type": "function",
        "function": {
            "name": "create_event",
            "description": "Create a new calendar event.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "start": {"type": "string", "description": "ISO 8601 datetime."},
                    "end": {"type": "string", "description": "ISO 8601 datetime."},
                    "description": {"type": "string"},
                    "location": {"type": ["string", "null"]},
                },
                "required": ["title", "start", "end"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_events",
            "description": "List calendar events within a date range.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start": {"type": "string", "description": "Optional ISO 8601 datetime."},
                    "end": {"type": "string", "description": "Optional ISO 8601 datetime."},
                },
                "required": [],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_event",
            "description": "Update or reschedule an existing calendar event.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {
                        "type": "string",
                        "description": "The ID of the event to update (from list_events).",
                    },
                    "title": {"type": "string"},
                    "start_time": {"type": "string", "description": "Optional ISO 8601 datetime."},
                    "end_time": {"type": "string", "description": "Optional ISO 8601 datetime."},
                    "description": {"type": "string"},
                    "location": {"type": ["string", "null"]},
                },
                "required": ["event_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_event_from_issue",
            "description": (
                "Create a calendar event from an issue when the user asks to schedule a meeting related to an issue."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "issue_id": {"type": "string"},
                    "start": {"type": "string", "description": "ISO 8601 datetime."},
                    "end": {"type": "string", "description": "ISO 8601 datetime."},
                },
                "required": ["issue_id", "start", "end"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_issue_boards",
            "description": "List issue tracker boards/projects so the user can choose where issues live.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_issues",
            "description": (
                "List issues from a board, or from every board when no board_id is provided. Optionally filter by status."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "board_id": {"type": "string"},
                    "status": {
                        "type": "string",
                        "description": "Optional status: to_do, in_progress, completed, open, doing, done, or closed.",
                    },
                },
                "required": [],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_issue",
            "description": "Fetch one issue by ID, including title, description, assignees, due date, status, and board.",
            "parameters": {
                "type": "object",
                "properties": {
                    "issue_id": {"type": "string"},
                },
                "required": ["issue_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_issue",
            "description": "Create a new issue in the issue tracker.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "board_id": {"type": "string"},
                    "description": {"type": "string"},
                    "members": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "due_date": {"type": "string", "description": "Optional due date string accepted by the issue tracker."},
                    "status": {
                        "type": "string",
                        "description": "Optional status: to_do, in_progress, completed, open, doing, done, or closed.",
                    },
                },
                "required": ["title", "board_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_issue",
            "description": "Update issue tracker fields such as title, description, assignees, due date, status, or board.",
            "parameters": {
                "type": "object",
                "properties": {
                    "issue_id": {"type": "string"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "members": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "due_date": {"type": "string"},
                    "status": {
                        "type": "string",
                        "description": "Optional status: to_do, in_progress, completed, open, doing, done, or closed.",
                    },
                    "board_id": {"type": "string"},
                },
                "required": ["issue_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "schedule_issue_work_session",
            "description": (
                "Find the first available calendar slot in a window, create a work session for an issue, "
                "and optionally mark the issue in progress."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "issue_id": {"type": "string"},
                    "window_start": {"type": "string", "description": "ISO 8601 datetime for the search window start."},
                    "window_end": {"type": "string", "description": "ISO 8601 datetime for the search window end."},
                    "duration_minutes": {"type": "integer", "minimum": 1},
                    "event_title": {"type": "string"},
                    "location": {"type": ["string", "null"]},
                    "update_status": {
                        "type": "boolean",
                        "description": "When true, move the issue to in_progress after creating the event.",
                    },
                },
                "required": ["issue_id", "window_start", "window_end", "duration_minutes"],
                "additionalProperties": False,
            },
        },
    },
]


def make_tool_handler(
    calendar_client: CalendarClient,
    issue_client: IssueClient,
) -> ToolHandler:
    """Create a tool handler bound to service clients."""

    def handle_tool(name: str, arguments: ToolArguments) -> str:
        try:
            result = dispatch_tool(
                name=name,
                arguments=arguments,
                calendar_client=calendar_client,
                issue_client=issue_client,
            )
            return json.dumps(result, default=str)
        except (TypeError, ValueError) as exc:
            return json.dumps({"error": str(exc), "tool": name})
        except Exception as exc:
            logger.exception("Tool call failed: %s", name)
            return json.dumps({"error": str(exc), "tool": name})

    return handle_tool


def dispatch_tool(
    *,
    name: str,
    arguments: ToolArguments,
    calendar_client: CalendarClient,
    issue_client: IssueClient,
) -> object:
    """Dispatch an AI-requested tool call to the correct service action."""
    handlers: dict[str, Callable[[], object]] = {
        "create_event": lambda: _handle_create_event(calendar_client, arguments),
        "list_events": lambda: _handle_list_events(calendar_client, arguments),
        "update_event": lambda: _handle_update_event(calendar_client, arguments),
        "list_issue_boards": lambda: _handle_list_issue_boards(issue_client),
        "list_issues": lambda: _handle_list_issues(issue_client, arguments),
        "get_issue": lambda: _handle_get_issue(issue_client, arguments),
        "create_issue": lambda: _handle_create_issue(issue_client, arguments),
        "update_issue": lambda: _handle_update_issue(issue_client, arguments),
        "create_event_from_issue": lambda: _handle_create_event_from_issue(calendar_client, issue_client, arguments),
        "schedule_issue_work_session": lambda: _handle_schedule_issue_work_session(calendar_client, issue_client, arguments),
    }

    try:
        return handlers[name]()
    except KeyError as exc:
        message = f"Unknown tool: {name}"
        raise ValueError(message) from exc


def _event_to_dict(event: Event) -> dict[str, object]:
    """Convert an Event ABC instance to a JSON-serializable dict."""
    return {
        "id": event.id,
        "title": event.title,
        "start_time": event.start_time.isoformat(),
        "end_time": event.end_time.isoformat(),
        "description": event.description,
        "location": event.location,
    }


def _board_to_dict(board: Board) -> dict[str, object]:
    """Convert a Board ABC instance to a JSON-serializable dict."""
    return {
        "id": str(board.id),
        "name": board.board_name,
    }


def _issue_to_dict(issue: Issue) -> dict[str, object]:
    """Convert an Issue ABC instance to a JSON-serializable dict."""
    return {
        "id": str(issue.id),
        "title": issue.title,
        "description": issue.desc,
        "members": issue.members,
        "due_date": issue.due_date,
        "status": issue.status.value,
        "board_id": str(issue.board_id),
    }


def _handle_create_event(
    calendar_client: CalendarClient,
    arguments: Mapping[str, object],
) -> object:
    """Create a calendar event from tool arguments."""
    title = arguments.get("title")
    start = arguments.get("start")
    end = arguments.get("end")
    description = arguments.get("description")
    location = arguments.get("location")

    if not isinstance(title, str):
        msg = "Missing title"
        raise TypeError(msg)
    if not isinstance(start, str):
        msg = "Missing start"
        raise TypeError(msg)
    if not isinstance(end, str):
        msg = "Missing end"
        raise TypeError(msg)

    dto = EventCreate(
        title=title,
        start_time=datetime.fromisoformat(start),
        end_time=datetime.fromisoformat(end),
        attendees=[],
        attachments=[],
        description=description if isinstance(description, str) else None,
        location=location if isinstance(location, str) else None,
    )

    event = calendar_client.create_event_from_dto(dto)
    return _event_to_dict(event)


def _handle_list_events(
    calendar_client: CalendarClient,
    arguments: Mapping[str, object],
) -> object:
    """List calendar events, optionally filtering by date range."""
    start = arguments.get("start")
    end = arguments.get("end")

    if isinstance(start, str) and isinstance(end, str):
        events = calendar_client.list_events_between(
            datetime.fromisoformat(start),
            datetime.fromisoformat(end),
        )
    else:
        events = calendar_client.list_upcoming_events()

    return [_event_to_dict(e) for e in events]


def _handle_update_event(
    calendar_client: CalendarClient,
    arguments: Mapping[str, object],
) -> object:
    """Update a calendar event by its ID."""
    event_id = arguments.get("event_id")

    if not isinstance(event_id, str):
        message = "Missing event_id"
        raise TypeError(message)

    start_time_raw = arguments.get("start_time")
    end_time_raw = arguments.get("end_time")
    title_raw = arguments.get("title")
    description_raw = arguments.get("description")
    location_raw = arguments.get("location")

    patch = EventUpdate(
        title=title_raw if isinstance(title_raw, str) else UNSET,
        start_time=datetime.fromisoformat(start_time_raw) if isinstance(start_time_raw, str) else UNSET,
        end_time=datetime.fromisoformat(end_time_raw) if isinstance(end_time_raw, str) else UNSET,
        description=description_raw if isinstance(description_raw, str) else UNSET,
        location=location_raw if isinstance(location_raw, str) else UNSET,
    )

    event = calendar_client.update_event_from_patch(event_id, patch)
    return _event_to_dict(event)


def _handle_list_issue_boards(issue_client: IssueClient) -> object:
    """List issue tracker boards."""
    return [_board_to_dict(board) for board in issue_client.get_boards()]


def _handle_list_issues(
    issue_client: IssueClient,
    arguments: Mapping[str, object],
) -> object:
    """List issues from one board or every available board."""
    board_id = arguments.get("board_id")
    status = _parse_status(arguments.get("status"))
    issues: list[Issue] = []

    if isinstance(board_id, str) and board_id:
        issues.extend(issue_client.get_issues(board_id))
    else:
        for board in issue_client.get_boards():
            issues.extend(issue_client.get_issues(str(board.id)))

    if status is not None:
        issues = [issue for issue in issues if issue.status.value == status.value]

    return [_issue_to_dict(issue) for issue in issues]


def _handle_get_issue(
    issue_client: IssueClient,
    arguments: Mapping[str, object],
) -> object:
    """Fetch one issue."""
    issue_id = arguments.get("issue_id")

    if not isinstance(issue_id, str):
        message = "Missing issue_id"
        raise TypeError(message)

    return _issue_to_dict(issue_client.get_issue(issue_id))


def _handle_create_issue(
    issue_client: IssueClient,
    arguments: Mapping[str, object],
) -> object:
    """Create one issue."""
    title = arguments.get("title")
    board_id = arguments.get("board_id")
    description = arguments.get("description")
    due_date = arguments.get("due_date")

    if not isinstance(title, str):
        message = "Missing title"
        raise TypeError(message)

    if not isinstance(board_id, str):
        message = "Missing board_id"
        raise TypeError(message)

    issue = issue_client.create_issue(
        title=title,
        board_id=board_id,
        desc=description if isinstance(description, str) else None,
        members=_optional_string_list(arguments.get("members"), "members"),
        due_date=due_date if isinstance(due_date, str) else None,
        status=_parse_status(arguments.get("status")) or Status.TO_DO,
    )

    return _issue_to_dict(issue)


def _handle_update_issue(
    issue_client: IssueClient,
    arguments: Mapping[str, object],
) -> object:
    """Update one issue."""
    issue_id = arguments.get("issue_id")
    title = arguments.get("title")
    description = arguments.get("description")
    due_date = arguments.get("due_date")
    board_id = arguments.get("board_id")

    if not isinstance(issue_id, str):
        message = "Missing issue_id"
        raise TypeError(message)

    issue = issue_client.update_issue(
        issue_id=issue_id,
        title=title if isinstance(title, str) else None,
        desc=description if isinstance(description, str) else None,
        members=_optional_string_list(arguments.get("members"), "members"),
        due_date=due_date if isinstance(due_date, str) else None,
        status=_parse_status(arguments.get("status")),
        board_id=board_id if isinstance(board_id, str) else None,
    )

    return _issue_to_dict(issue)


def _handle_create_event_from_issue(
    calendar_client: CalendarClient,
    issue_client: IssueClient,
    arguments: Mapping[str, object],
) -> object:
    """Create a calendar event from an issue."""
    issue_id = arguments.get("issue_id")
    start = arguments.get("start")
    end = arguments.get("end")

    if not isinstance(issue_id, str):
        message = "Missing issue_id"
        raise TypeError(message)

    if not isinstance(start, str):
        message = "Missing start"
        raise TypeError(message)

    if not isinstance(end, str):
        message = "Missing end"
        raise TypeError(message)

    return create_event_from_issue_flow(
        issue_id=issue_id,
        start=start,
        end=end,
        issue_client=issue_client,
        calendar_client=calendar_client,
    )


def _handle_schedule_issue_work_session(
    calendar_client: CalendarClient,
    issue_client: IssueClient,
    arguments: Mapping[str, object],
) -> object:
    """Schedule issue work in the first available calendar slot."""
    issue_id = arguments.get("issue_id")
    window_start_raw = arguments.get("window_start")
    window_end_raw = arguments.get("window_end")
    duration_minutes = arguments.get("duration_minutes")
    event_title = arguments.get("event_title")
    location = arguments.get("location")
    update_status = arguments.get("update_status")

    if not isinstance(issue_id, str):
        message = "Missing issue_id"
        raise TypeError(message)
    if not isinstance(window_start_raw, str):
        message = "Missing window_start"
        raise TypeError(message)
    if not isinstance(window_end_raw, str):
        message = "Missing window_end"
        raise TypeError(message)
    if not isinstance(duration_minutes, int) or isinstance(duration_minutes, bool):
        message = "Missing duration_minutes"
        raise TypeError(message)

    issue = issue_client.get_issue(issue_id)
    window_start = datetime.fromisoformat(window_start_raw)
    window_end = datetime.fromisoformat(window_end_raw)
    duration = timedelta(minutes=duration_minutes)
    slot_start, slot_end = _find_first_free_slot(
        calendar_client=calendar_client,
        window_start=window_start,
        window_end=window_end,
        duration=duration,
    )

    dto = EventCreate(
        title=event_title if isinstance(event_title, str) and event_title else f"Issue Work: {issue.title}",
        start_time=slot_start,
        end_time=slot_end,
        attendees=[],
        attachments=[],
        description=_issue_event_description(issue),
        location=location if isinstance(location, str) else None,
    )
    event = calendar_client.create_event_from_dto(dto)

    updated_issue = issue_client.update_issue(issue_id, status=Status.IN_PROGRESS) if update_status is True else None

    return {
        "issue": _issue_to_dict(updated_issue or issue),
        "event": _event_to_dict(event),
        "status": "scheduled",
    }


def _find_first_free_slot(
    *,
    calendar_client: CalendarClient,
    window_start: datetime,
    window_end: datetime,
    duration: timedelta,
) -> tuple[datetime, datetime]:
    """Find the first free calendar slot inside a bounded window."""
    if window_end <= window_start:
        message = "window_end must be after window_start"
        raise ValueError(message)

    if duration <= timedelta(0):
        message = "duration_minutes must be greater than 0"
        raise ValueError(message)

    cursor = window_start
    events = sorted(
        calendar_client.list_events_between(window_start, window_end),
        key=lambda event: _align_datetime(event.start_time, window_start),
    )

    for event in events:
        event_start = _align_datetime(event.start_time, window_start)
        event_end = _align_datetime(event.end_time, window_start)

        if event_end <= cursor:
            continue

        if event_start > cursor and event_start - cursor >= duration:
            return cursor, cursor + duration

        cursor = max(cursor, event_end)

        if cursor + duration > window_end:
            break

    if window_end - cursor >= duration:
        return cursor, cursor + duration

    message = "No available calendar slot found in the requested window"
    raise ValueError(message)


def _align_datetime(value: datetime, reference: datetime) -> datetime:
    """Make event datetimes comparable with the requested window."""
    if value.tzinfo is None and reference.tzinfo is not None:
        return value.replace(tzinfo=reference.tzinfo)
    if value.tzinfo is not None and reference.tzinfo is None:
        return value.replace(tzinfo=None)
    return value


def _issue_event_description(issue: Issue) -> str:
    """Build a useful event description from issue fields."""
    parts = [f"Issue ID: {issue.id}"]
    if issue.desc:
        parts.append(issue.desc)
    status = issue.status.value if issue.status else None
    if status:
        parts.append(f"Status: {status}")
    if issue.due_date:
        parts.append(f"Due date: {issue.due_date}")
    return "\n".join(parts)


def _parse_status(value: object) -> Status | None:
    """Parse common user-facing status names to the shared status enum."""
    if value is None:
        return None
    if isinstance(value, Status):
        return value
    if not isinstance(value, str):
        message = "status must be a string"
        raise TypeError(message)

    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "todo": "to_do",
        "to_do": "to_do",
        "open": "to_do",
        "backlog": "to_do",
        "in_progress": "in_progress",
        "doing": "in_progress",
        "started": "in_progress",
        "completed": "completed",
        "done": "completed",
        "closed": "completed",
    }
    status_value = aliases.get(normalized, normalized)

    try:
        return Status(status_value)
    except ValueError as exc:
        message = f"Unsupported status: {value}"
        raise ValueError(message) from exc


def _optional_string_list(value: object, field_name: str) -> list[str] | None:
    """Validate optional list[str] tool arguments."""
    if value is None:
        return None
    if not isinstance(value, list):
        message = f"{field_name} must be a list of strings"
        raise TypeError(message)

    result: list[str] = []
    for item in value:
        if not isinstance(item, str):
            message = f"{field_name} must be a list of strings"
            raise TypeError(message)
        result.append(item)

    return result
