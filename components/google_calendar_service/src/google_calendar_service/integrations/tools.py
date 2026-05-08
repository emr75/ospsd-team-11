"""Tool definitions and dispatch handlers for the AI agent."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Mapping
from datetime import datetime
from typing import TYPE_CHECKING

from calendar_client_api import EventCreate, EventUpdate
from calendar_client_api.event import UNSET

from google_calendar_service.integrations.issue_to_calendar import (
    create_event_from_issue_flow,
)

if TYPE_CHECKING:
    from api.client import Client as IssueClient  # type: ignore[import-untyped]
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
                    "event_reference": {
                        "type": "string",
                        "description": "Human-readable event reference, such as the meeting title.",
                    },
                    "start_time": {"type": "string", "description": "Optional ISO 8601 datetime."},
                    "end_time": {"type": "string", "description": "Optional ISO 8601 datetime."},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "location": {"type": ["string", "null"]},
                },
                "required": ["event_reference"],
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
    if name == "create_event":
        return _handle_create_event(calendar_client, arguments)

    if name == "list_events":
        return _handle_list_events(calendar_client, arguments)

    if name == "update_event":
        return _handle_update_event(calendar_client, arguments)

    if name == "create_event_from_issue":
        return _handle_create_event_from_issue(arguments, issue_client, calendar_client)

    message = f"Unknown tool: {name}"
    raise ValueError(message)


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


def _handle_create_event_from_issue(
    arguments: Mapping[str, object],
    issue_client: IssueClient,
    calendar_client: CalendarClient,
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


def _handle_update_event(
    calendar_client: CalendarClient,
    arguments: Mapping[str, object],
) -> object:
    """Resolve an event reference and update the matching event."""
    event_reference_obj = arguments.get("event_reference")

    if not isinstance(event_reference_obj, str):
        message = "Missing event_reference"
        raise TypeError(message)

    matched_event_id = _resolve_event_id(calendar_client, event_reference_obj)

    if matched_event_id is None:
        message = f"No event found for reference: {event_reference_obj}"
        raise ValueError(message)

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

    event = calendar_client.update_event_from_patch(matched_event_id, patch)
    return _event_to_dict(event)


def _resolve_event_id(
    calendar_client: CalendarClient,
    event_reference: str,
) -> str | None:
    """Resolve a human-readable event reference to a concrete event ID."""
    events = calendar_client.list_upcoming_events()
    normalized_reference = event_reference.strip().lower()

    for event in events:
        if event.title.strip().lower() == normalized_reference:
            return event.id

    return None
