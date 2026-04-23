# ruff: noqa: D100, D101, D102, D103, D107
from datetime import datetime
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import pytest
from google_calendar_service.integrations import issue_to_calendar

if TYPE_CHECKING:
    from issue_tracker_client_api.client import Issue

# For fake content
ISSUE_ID = 123
BOARD_ID = "board-1"

class FakeIssueClient:
    def __init__(self) -> None:
        self.requested_board: str | None = None
        self.requested_issue_id: int | None = None

    def get_issue(self, board: str, issue_id: int) -> object:
        self.requested_board = board
        self.requested_issue_id = issue_id
        return SimpleNamespace(
            id=123,
            title="Broken auth redirect",
            body="Investigate redirect_uri mismatch in OAuth callback flow.",
            state=SimpleNamespace(value="open"),
        )


class FakeCalendarClient:
    def __init__(self) -> None:
        self.create_event_calls: list[dict[str, object]] = []

    def create_event(self, **kwargs: object) -> object:
        self.create_event_calls.append(kwargs)
        return SimpleNamespace(
            id="evt-999",
            title=kwargs["title"],
        )


def test_build_event_payload_from_issue_includes_issue_fields() -> None:
    issue = cast("Issue", SimpleNamespace(
        id=123,
        title="Broken auth redirect",
        body="Investigate redirect_uri mismatch in OAuth callback flow.",
        state=SimpleNamespace(value="open"),
    ))

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
    assert "State: open" in description

def test_create_event_from_issue_flow_fetches_issue_and_creates_calendar_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TRELLO_BOARD_ID", "board-1")

    fake_issue_client = FakeIssueClient()
    fake_calendar_client = FakeCalendarClient()

    monkeypatch.setattr(
        issue_to_calendar,
        "get_issue_client",
        lambda *_: fake_issue_client,
    )
    monkeypatch.setattr(
        issue_to_calendar,
        "get_calendar_client",
        lambda: fake_calendar_client,
    )

    issue_to_calendar.create_event_from_issue_flow(
        issue_id="123",
        start="2026-04-23T15:00:00-04:00",
        end="2026-04-23T16:00:00-04:00",
    )

    assert fake_issue_client.requested_issue_id == ISSUE_ID
    assert fake_issue_client.requested_board == BOARD_ID

    assert len(fake_calendar_client.create_event_calls) == 1
    create_call = fake_calendar_client.create_event_calls[0]
    description = create_call["description"]

    assert create_call["title"] == "Issue Review: Broken auth redirect"
    assert create_call["start"] == datetime.fromisoformat("2026-04-23T15:00:00-04:00")
    assert create_call["end"] == datetime.fromisoformat("2026-04-23T16:00:00-04:00")
    assert isinstance(description, str)
    assert "Issue ID: 123" in description
