# ruff: noqa: D100, D101, D103
from typing import Any, Protocol, cast

from api.client import get_client as get_issue_client  # type: ignore[import-untyped]
from api.issue import Issue  # type: ignore[import-untyped]
from calendar_client_api import get_client as get_calendar_client


class CreatedEventProtocol(Protocol):
    id: str
    title: str

class CalendarCreateEventProtocol(Protocol):
    def create_event(self, **kwargs: object) -> CreatedEventProtocol:
        """Create a calendar event."""

def build_event_payload_from_issue(issue: Issue, board_name: str | None, start: str, end: str) -> dict[str, Any]:
    description_parts: list[str] = []

    if board_name:
        description_parts.append(f"Board: {board_name}")

    description_parts.append(f"Issue ID: {issue.id}")

    if issue.desc:
        description_parts.append(issue.desc)

    if issue.status:
        description_parts.append(f"Status: {issue.status.value}")

    if issue.due_date:
        description_parts.append(f"Due date: {issue.due_date}")

    if issue.members:
        description_parts.append(f"Assignees: {', '.join(issue.members)}")

    return {
        "title": f"Issue Review: {issue.title}",
        "start": start,
        "end": end,
        "description": "\n".join(description_parts),
    }


def create_event_from_issue_flow(issue_id: str, start: str, end: str) -> dict[str, Any]:
    issue_client = get_issue_client(interactive=False)
    calendar_client = cast("CalendarCreateEventProtocol", get_calendar_client())

    issue = issue_client.get_issue(issue_id)

    board_name: str | None = None
    try:
        board = issue_client.get_board(issue.board_id)
        board_name = board.board_name
    except RuntimeError:
        board_name = None

    event_payload = build_event_payload_from_issue(issue, board_name, start, end)

    event = calendar_client.create_event(
        title=event_payload["title"],
        start=event_payload["start"],
        end=event_payload["end"],
        description=event_payload["description"],
    )

    return {
        "issue_id": issue.id,
        "event_id": event.id,
        "event_title": event.title,
        "board_name": board_name,
        "status": "created",
    }
