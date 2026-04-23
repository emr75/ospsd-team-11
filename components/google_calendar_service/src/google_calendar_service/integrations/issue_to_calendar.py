# ruff: noqa: D100, D101, D103
import os
from datetime import datetime
from typing import Any, Protocol, cast

import issue_tracker_client_impl  # noqa: F401
from calendar_client_api import get_client as get_calendar_client
from issue_tracker_client_api.client import Issue
from issue_tracker_client_api.client import get_client as get_issue_client


class CreatedEventProtocol(Protocol):
    id: str
    title: str

class CalendarCreateEventProtocol(Protocol):
    def create_event(self, **kwargs: object) -> CreatedEventProtocol:
        """Create a calendar event."""

def build_event_payload_from_issue(
    issue: Issue,
    start: str,
    end: str,
) -> dict[str, Any]:
    description_parts: list[str] = [f"Issue ID: {issue.id}"]

    if issue.body:
        description_parts.append(issue.body)

    description_parts.append(f"State: {issue.state.value}")

    return {
        "title": f"Issue Review: {issue.title}",
        "start": start,
        "end": end,
        "description": "\n".join(description_parts),
    }


def create_event_from_issue_flow(issue_id: str, start: str, end: str) -> dict[str, Any]:
    board_id = os.environ["TRELLO_BOARD_ID"]
    issue_client = get_issue_client()
    calendar_client = cast("CalendarCreateEventProtocol", get_calendar_client())

    issue = issue_client.get_issue(board_id, int(issue_id))
    event_payload = build_event_payload_from_issue(issue, start, end)

    parsed_start = datetime.fromisoformat(event_payload["start"])
    parsed_end = datetime.fromisoformat(event_payload["end"])

    event = calendar_client.create_event(
        title=event_payload["title"],
        start=parsed_start,
        end=parsed_end,
        description=event_payload["description"],
    )

    return {
        "issue_id": str(issue.id),
        "event_id": event.id,
        "event_title": event.title,
        "board_id": board_id,
        "status": "created",
    }
