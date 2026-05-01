"""AI agent orchestration for calendar and issue workflows."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Protocol

from google_calendar_service.integrations.issue_to_calendar import (
    create_event_from_issue_flow,
)

logger = logging.getLogger(__name__)

ToolDefinition = dict[str, object]
ToolArguments = dict[str, object]
ToolHandler = Callable[[str, ToolArguments], str]


class AiClientProtocol(Protocol):
    """Protocol for AI clients used by orchestration."""

    def run_chat_with_tools(
        self,
        *,
        system_prompt: str,
        user_message: str,
        tools: list[ToolDefinition],
        handle_tool: ToolHandler,
        max_tool_rounds: int = 8,
    ) -> str:
        """Run a chat completion loop with tool support."""


class CalendarClientProtocol(Protocol):
    """Protocol for calendar client methods used by AI orchestration."""

    def list_events(self, **kwargs: object) -> list[object]:
        """Return calendar events."""

    def create_event(self, **kwargs: object) -> object:
        """Create calendar event."""

    def update_event(self, **kwargs: object) -> object:
        """Update calendar event."""


SYSTEM_PROMPT = (
    "You are an assistant for calendar and cross-service workflows. "
    "Use tools when the user asks to list, create, update, or schedule calendar events. "
    "Use the issue-related tool when the user asks to schedule something based on an issue. "
    "Do not invent tool results. After tools are executed, summarize the result clearly."
)


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


def run_ai_turn(
    *,
    prompt: str,
    context: dict[str, object] | None,
    ai_client: AiClientProtocol,
    calendar_client: CalendarClientProtocol,
) -> str:
    """Run one AI conversation turn with calendar and issue tools."""
    user_message = _build_user_message(prompt=prompt, context=context)

    return ai_client.run_chat_with_tools(
        system_prompt=SYSTEM_PROMPT,
        user_message=user_message,
        tools=TOOLS,
        handle_tool=_make_tool_handler(calendar_client),
    )


def _build_user_message(
    *,
    prompt: str,
    context: dict[str, object] | None,
) -> str:
    """Build the user message with optional structured context."""
    if not context:
        return prompt

    return f"{prompt}\n\nContext JSON:\n{json.dumps(context, default=str)}"


def _make_tool_handler(calendar_client: CalendarClientProtocol) -> ToolHandler:
    """Create a tool handler bound to service clients."""

    def handle_tool(name: str, arguments: ToolArguments) -> str:
        try:
            result = _dispatch_tool(
                name=name,
                arguments=arguments,
                calendar_client=calendar_client,
            )
            return json.dumps(result, default=str)
        except (TypeError, ValueError) as exc:
            return json.dumps({"error": str(exc), "tool": name})
        except Exception as exc:
            logger.exception("Tool call failed: %s", name)
            return json.dumps({"error": str(exc), "tool": name})

    return handle_tool


def _dispatch_tool(
    *,
    name: str,
    arguments: ToolArguments,
    calendar_client: CalendarClientProtocol,
) -> object:
    """Dispatch an AI-requested tool call to the correct service action."""
    if name == "create_event":
        return _handle_create_event(calendar_client, arguments)

    if name == "list_events":
        return calendar_client.list_events(**arguments)

    if name == "update_event":
        return _handle_update_event(calendar_client, arguments)

    if name == "create_event_from_issue":
        return _handle_create_event_from_issue(arguments)

    message = f"Unknown tool: {name}"
    raise ValueError(message)


def _handle_create_event(
    calendar_client: CalendarClientProtocol,
    arguments: Mapping[str, object],
) -> object:
    """Create a calendar event from tool arguments."""
    create_args = dict(arguments)

    start = create_args.get("start")
    end = create_args.get("end")

    if isinstance(start, str):
        create_args["start"] = datetime.fromisoformat(start)

    if isinstance(end, str):
        create_args["end"] = datetime.fromisoformat(end)

    return calendar_client.create_event(**create_args)


def _handle_create_event_from_issue(arguments: Mapping[str, object]) -> object:
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
    )


def _handle_update_event(
    calendar_client: CalendarClientProtocol,
    arguments: Mapping[str, object],
) -> object:
    """Resolve an event reference and update the matching event."""
    update_arguments = dict(arguments)
    event_reference_obj = update_arguments.pop("event_reference", None)

    start_time = update_arguments.get("start_time")
    end_time = update_arguments.get("end_time")

    if isinstance(start_time, str):
        update_arguments["start_time"] = datetime.fromisoformat(start_time)

    if isinstance(end_time, str):
        update_arguments["end_time"] = datetime.fromisoformat(end_time)

    if not isinstance(event_reference_obj, str):
        message = "Missing event_reference"
        raise TypeError(message)

    matched_event_id = _resolve_event_id(calendar_client, event_reference_obj)

    if matched_event_id is None:
        message = f"No event found for reference: {event_reference_obj}"
        raise ValueError(message)

    update_arguments["event_id"] = matched_event_id
    return calendar_client.update_event(**update_arguments)


def _resolve_event_id(
    calendar_client: CalendarClientProtocol,
    event_reference: str,
) -> str | None:
    """Resolve a human-readable event reference to a concrete event ID."""
    events = calendar_client.list_events()
    normalized_reference = event_reference.strip().lower()

    for event in events:
        title: object | None
        event_id: object | None

        if isinstance(event, Mapping):
            title = event.get("title")
            event_id = event.get("id")
        else:
            title = getattr(event, "title", None)
            event_id = getattr(event, "id", None)

        if isinstance(title, str) and isinstance(event_id, str) and title.strip().lower() == normalized_reference:
            return event_id

    return None
