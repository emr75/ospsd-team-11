"""Tests for issue-to-calendar integration flow."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

from google_calendar_service.integrations import issue_to_calendar

if TYPE_CHECKING:
    from api.issue import Issue  # type: ignore[import-untyped]

ISSUE_ID = "123"


class FakeIssueClient:
    """Fake issue client that records calls and returns a mock issue."""

    def __init__(self) -> None:
        """Initialize fake issue client state."""
        self.requested_issue_id: str | None = None

    def get_issue(self, issue_id: str) -> Issue:
        """Return a mock issue and record the requested ID."""
        self.requested_issue_id = issue_id
        return cast(
            "Issue",
            SimpleNamespace(
                id=123,
                title="Broken auth redirect",
                desc="Investigate redirect_uri mismatch in OAuth callback flow.",
                status="open",
            ),
        )


class FakeCalendarClient:
    """Fake calendar client that records create_event calls."""

    def __init__(self) -> None:
        """Initialize recorded calendar create calls."""
        self.create_event_calls: list[dict[str, object]] = []

    def create_event(self, **kwargs: Any) -> Any:
        """Record event creation and return a mock event."""
        self.create_event_calls.append(kwargs)
        return SimpleNamespace(
            id="evt-999",
            title=kwargs["title"],
        )


def test_build_event_payload_from_issue_includes_issue_fields() -> None:
    """Verify payload includes title, time, and issue-derived description fields."""
    issue = cast(
        "Issue",
        SimpleNamespace(
            id=123,
            title="Broken auth redirect",
            desc="Investigate redirect_uri mismatch in OAuth callback flow.",
            status="open",
        ),
    )

    payload = issue_to_calendar.build_event_payload_from_issue(
        issue=issue,
        start="2026-04-23T15:00:00-04:00",
        end="2026-04-23T16:00:00-04:00",
    )

    assert payload["title"] == "Issue Review: Broken auth redirect"
    assert payload["start"] == "2026-04-23T15:00:00-04:00"
    assert payload["end"] == "2026-04-23T16:00:00-04:00"

    description = payload["description"]
    assert isinstance(description, str)
    assert "Issue ID: 123" in description
    assert "Investigate redirect_uri mismatch in OAuth callback flow." in description
    assert "Status: open" in description


def test_create_event_from_issue_flow_fetches_issue_and_creates_calendar_event() -> None:
    """Verify full flow: issue is fetched and event is created with correct payload."""
    fake_issue_client = FakeIssueClient()
    fake_calendar_client = FakeCalendarClient()

    result = issue_to_calendar.create_event_from_issue_flow(
        issue_id=ISSUE_ID,
        start="2026-04-23T15:00:00-04:00",
        end="2026-04-23T16:00:00-04:00",
        issue_client=fake_issue_client,
        calendar_client=fake_calendar_client,
    )

    assert fake_issue_client.requested_issue_id == ISSUE_ID

    assert len(fake_calendar_client.create_event_calls) == 1
    create_call = fake_calendar_client.create_event_calls[0]
    description = create_call["description"]

    assert create_call["title"] == "Issue Review: Broken auth redirect"
    assert create_call["start"] == datetime.fromisoformat("2026-04-23T15:00:00-04:00")
    assert create_call["end"] == datetime.fromisoformat("2026-04-23T16:00:00-04:00")
    assert isinstance(description, str)
    assert "Issue ID: 123" in description
    assert "Status: open" in description

    assert result == {
        "issue_id": "123",
        "event_id": "evt-999",
        "event_title": "Issue Review: Broken auth redirect",
        "status": "created",
    }
