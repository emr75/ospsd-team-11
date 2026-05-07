"""Integration flow for creating calendar events from issue tracker issues."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from api.issue import Issue  # type: ignore[import-untyped]

    from google_calendar_service.integrations.protocol import CalendarCreateEventProtocol, IssueClientProtocol


def build_event_payload_from_issue(
    issue: Issue,
    start: str,
    end: str,
) -> dict[str, Any]:
    """Build calendar event payload from an issue."""
    description_parts: list[str] = [f"Issue ID: {issue.id}"]

    issue_description = getattr(issue, "desc", None)
    if isinstance(issue_description, str) and issue_description:
        description_parts.append(issue_description)

    issue_status = getattr(issue, "status", None)
    if issue_status is not None:
        status_text = getattr(issue_status, "value", issue_status)
        description_parts.append(f"Status: {status_text}")

    return {
        "title": f"Issue Review: {issue.title}",
        "start": start,
        "end": end,
        "description": "\n".join(description_parts),
    }


def create_event_from_issue_flow(
    issue_id: str,
    start: str,
    end: str,
    issue_client: IssueClientProtocol,
    calendar_client: CalendarCreateEventProtocol,
) -> dict[str, Any]:
    """Create a calendar event using details from an issue."""
    issue = issue_client.get_issue(issue_id)
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
        "status": "created",
    }
