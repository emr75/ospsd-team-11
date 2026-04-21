"""AI routes for handling assistant interactions."""

from collections.abc import Mapping
from typing import Protocol, cast

from ai_client_api import get_client as get_ai_client
from calendar_client_api import get_client as get_calendar_client
from fastapi import APIRouter
from pydantic import BaseModel


class CalendarClientProtocol(Protocol):
    """Protocol for calendar client methods used by AI routes."""

    def list_events(self, **kwargs: object) -> list[object]:
        """Return calendar events."""
    def create_event(self, **kwargs: object) -> object:
        """Create calendar event."""
    def update_event(self, **kwargs: object) -> object:
        """Update calendar event."""

router = APIRouter(prefix="/ai", tags=["ai"])


class AiRequest(BaseModel):
    """Incoming AI request payload."""

    prompt: str
    context: dict[str, object] | None = None


class AiResponseModel(BaseModel):
    """Serialized AI response returned by the route."""

    message: str
    result: object | None = None


@router.post("/")
def handle_ai(request: AiRequest) -> AiResponseModel:
    """Handle an AI prompt and execute the first requested tool call."""
    ai_client = get_ai_client()
    calendar_client = cast("CalendarClientProtocol", get_calendar_client())

    ai_response = ai_client.send_message(
        prompt=request.prompt,
        context=request.context,
    )

    if not ai_response.tool_calls:
        return AiResponseModel(message=ai_response.message)

    tool_call = ai_response.tool_calls[0]
    result: object | None = None

    if tool_call.tool_name == "create_event":
        result = calendar_client.create_event(**tool_call.arguments)

    elif tool_call.tool_name == "list_events":
        result = calendar_client.list_events(**tool_call.arguments)

    elif tool_call.tool_name == "update_event":
        result = _handle_update_event(calendar_client, tool_call.arguments)

    elif tool_call.tool_name == "create_event_from_ticket":
        # For the ticket vertical - TBC
        result = {"status": "not implemented yet"}

    return AiResponseModel(
        message=ai_response.message,
        result=result,
    )


def _handle_update_event(
    calendar_client: CalendarClientProtocol,
    arguments: Mapping[str, object],
) -> object:
    """Resolve an event reference and update the matching event."""
    update_arguments = dict(arguments)
    event_reference_obj = update_arguments.pop("event_reference", None)

    if not isinstance(event_reference_obj, str):
        return {"error": "Missing event_reference"}

    matched_event_id = _resolve_event_id(calendar_client, event_reference_obj)

    if matched_event_id is None:
        return {"error": f"No event found for reference: {event_reference_obj}"}

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
        title: object | None = None
        event_id: object | None = None

        if isinstance(event, Mapping):
            title = event.get("title")
            event_id = event.get("id")
        else:
            title = getattr(event, "title", None)
            event_id = getattr(event, "id", None)

        if (
            isinstance(title, str)
            and isinstance(event_id, str)
            and title.strip().lower() == normalized_reference
        ):
            return event_id

    return None


