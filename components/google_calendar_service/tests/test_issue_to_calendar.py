# ruff: noqa: D100, D101, D102, D103, D107
from types import SimpleNamespace

import pytest
from google_calendar_service.integrations import issue_to_calendar


class FakeIssueClient:
    def __init__(self) -> None:
        self.requested_issue_id: str | None = None
        self.requested_board_id: str | None = None

    def get_issue(self, issue_id: str) -> object:
        self.requested_issue_id = issue_id
        return SimpleNamespace(
            id="123",
            title="Broken auth redirect",
            desc="Investigate redirect_uri mismatch in OAuth callback flow.",
            status=SimpleNamespace(value="open"),
            due_date="2026-04-25",
            members=["joe", "nathaniel"],
            board_id="board-1",
        )

    def get_board(self, board_id: str) -> object:
        self.requested_board_id = board_id
        return SimpleNamespace(board_name="Sprint Board")


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
    issue = SimpleNamespace(
        id="123",
        title="Broken auth redirect",
        desc="Investigate redirect_uri mismatch in OAuth callback flow.",
        status=SimpleNamespace(value="open"),
        due_date="2026-04-25",
        members=["alice", "bob"],
    )

    payload = issue_to_calendar.build_event_payload_from_issue(
        issue=issue,
        board_name="Sprint Board",
        start="2026-04-23T15:00:00-04:00",
        end="2026-04-23T16:00:00-04:00",
    )

    assert payload["title"] == "Issue Review: Broken auth redirect"
    assert payload["start"] == "2026-04-23T15:00:00-04:00"
    assert payload["end"] == "2026-04-23T16:00:00-04:00"

    description = payload["description"]
    assert isinstance(description, str)
    assert "Board: Sprint Board" in description
    assert "Issue ID: 123" in description
    assert "Investigate redirect_uri mismatch in OAuth callback flow." in description
    assert "Status: open" in description
    assert "Due date: 2026-04-25" in description
    assert "Assignees: alice, bob" in description


def test_create_event_from_issue_flow_fetches_issue_and_creates_calendar_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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

    assert fake_issue_client.requested_issue_id == "123"
    assert fake_issue_client.requested_board_id == "board-1"

    assert len(fake_calendar_client.create_event_calls) == 1
    create_call = fake_calendar_client.create_event_calls[0]
    description = create_call["description"]

    assert create_call["title"] == "Issue Review: Broken auth redirect"
    assert create_call["start"] == "2026-04-23T15:00:00-04:00"
    assert create_call["end"] == "2026-04-23T16:00:00-04:00"
    assert isinstance(description, str)
    assert "Board: Sprint Board" in description
    assert "Issue ID: 123" in description


def test_create_event_from_issue_flow_still_creates_event_when_board_lookup_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_calendar_client = FakeCalendarClient()

    class BoardFailureIssueClient(FakeIssueClient):
        def get_board(self, board_id: str) -> object:
            raise RuntimeError("board lookup failed") # noqa: TRY003, EM101

    fake_issue_client = BoardFailureIssueClient()

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

    assert len(fake_calendar_client.create_event_calls) == 1
    create_call = fake_calendar_client.create_event_calls[0]
    description = create_call["description"]

    assert isinstance(description, str)
    assert "Board:" not in description
