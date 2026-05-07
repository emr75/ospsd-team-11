"""Tests for AI orchestration logic in agent.py."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

import pytest
from google_calendar_service.integrations import agent

if TYPE_CHECKING:
    from api.issue import Issue  # type: ignore[import-untyped]


class FakeAiClient:
    """Fake AI client that captures inputs and returns a fixed response."""

    def __init__(self) -> None:
        """Initialize captured call storage."""
        self.called_with: dict[str, Any] | None = None

    def run_chat_with_tools(self, **kwargs: Any) -> str:
        """Capture tool-loop inputs and return a fixed response."""
        self.called_with = kwargs
        return "Final AI response"


class FakeCalendarClient:
    """Fake calendar client for testing tool dispatch."""

    def __init__(self) -> None:
        """Initialize recorded calendar operations."""
        self.created_events: list[dict[str, object]] = []
        self.updated_events: list[dict[str, object]] = []

    def list_events(self, **kwargs: object) -> list[object]:
        """Return fake calendar events."""
        return [
            {
                "id": "event-1",
                "title": "Standup",
                "start": "2026-04-29T10:00:00",
                "end": "2026-04-29T10:30:00",
            }
        ]

    def create_event(self, **kwargs: object) -> object:
        """Record and return fake created event."""
        self.created_events.append(dict(kwargs))
        return SimpleNamespace(id="created-1", **kwargs)

    def update_event(self, **kwargs: object) -> object:
        """Record and return fake updated event."""
        self.updated_events.append(dict(kwargs))
        return SimpleNamespace(id="updated-1", **kwargs)


class FakeIssueClient:
    """Fake issue client for testing tool dispatch."""

    def __init__(self) -> None:
        """Initialize recorded issue operations."""
        self.requested_issue_id: str | None = None

    def get_issue(self, issue_id: str) -> Issue:
        """Return a fake issue and record the requested ID."""
        self.requested_issue_id = issue_id
        return cast(
            "Issue",
            SimpleNamespace(
                id=issue_id,
                title="Bug: login broken",
                desc="Login page returns 500.",
                status="open",
            ),
        )


def test_run_ai_turn_calls_ai_client_with_expected_inputs() -> None:
    """Ensure run_ai_turn calls the AI client correctly."""
    ai = FakeAiClient()
    calendar = FakeCalendarClient()
    issue = FakeIssueClient()

    result = agent.run_ai_turn(
        prompt="Schedule a meeting",
        context={"timezone": "UTC"},
        ai_client=ai,
        calendar_client=calendar,
        issue_client=issue,
    )

    assert result == "Final AI response"
    assert ai.called_with is not None
    assert ai.called_with["system_prompt"] == agent.SYSTEM_PROMPT
    assert "Schedule a meeting" in ai.called_with["user_message"]
    assert "Context JSON" in ai.called_with["user_message"]
    assert isinstance(ai.called_with["tools"], list)


def test_dispatch_tool_create_event() -> None:
    """Ensure create_event tool is dispatched correctly."""
    calendar = FakeCalendarClient()
    issue = FakeIssueClient()

    result = agent._dispatch_tool(
        name="create_event",
        arguments={
            "title": "Meeting",
            "start": "2026-04-21T15:00:00",
            "end": "2026-04-21T16:00:00",
        },
        calendar_client=calendar,
        issue_client=issue,
    )

    assert result.id == "created-1"  # type: ignore[attr-defined]


def test_dispatch_tool_list_events() -> None:
    """Ensure list_events tool is dispatched correctly."""
    calendar = FakeCalendarClient()
    issue = FakeIssueClient()

    result = cast(
        "list[dict[str, object]]",
        agent._dispatch_tool(
            name="list_events",
            arguments={},
            calendar_client=calendar,
            issue_client=issue,
        ),
    )

    assert result[0]["id"] == "event-1"


def test_dispatch_tool_update_event_missing_reference() -> None:
    """Ensure update_event raises TypeError when reference is missing."""
    calendar = FakeCalendarClient()
    issue = FakeIssueClient()

    with pytest.raises(TypeError, match="Missing event_reference"):
        agent._dispatch_tool(
            name="update_event",
            arguments={},
            calendar_client=calendar,
            issue_client=issue,
        )


def test_dispatch_tool_unknown_tool() -> None:
    """Ensure unknown tool raises ValueError."""
    calendar = FakeCalendarClient()
    issue = FakeIssueClient()

    with pytest.raises(ValueError, match="Unknown tool"):
        agent._dispatch_tool(
            name="unknown_tool",
            arguments={},
            calendar_client=calendar,
            issue_client=issue,
        )


def test_dispatch_tool_create_event_from_issue() -> None:
    """Ensure create_event_from_issue tool dispatches with injected clients."""
    calendar = FakeCalendarClient()
    issue = FakeIssueClient()

    result = cast(
        "dict[str, object]",
        agent._dispatch_tool(
            name="create_event_from_issue",
            arguments={
                "issue_id": "42",
                "start": "2026-05-01T10:00:00",
                "end": "2026-05-01T11:00:00",
            },
            calendar_client=calendar,
            issue_client=issue,
        ),
    )

    assert result["status"] == "created"
    assert result["issue_id"] == "42"
    assert issue.requested_issue_id == "42"
    assert len(calendar.created_events) == 1
