"""Tests for AI orchestration logic in agent.py."""

from typing import Any, cast

import pytest
from google_calendar_service.integrations import agent


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
        return {"id": "created-1", **kwargs}

    def update_event(self, **kwargs: object) -> object:
        """Record and return fake updated event."""
        self.updated_events.append(dict(kwargs))
        return {"id": "updated-1", **kwargs}


def test_run_ai_turn_calls_ai_client_with_expected_inputs() -> None:
    """Ensure run_ai_turn calls the AI client correctly."""
    ai = FakeAiClient()
    calendar = FakeCalendarClient()

    result = agent.run_ai_turn(
        prompt="Schedule a meeting",
        context={"timezone": "UTC"},
        ai_client=ai,
        calendar_client=calendar,
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

    result = cast(
        "dict[str, object]",
        agent._dispatch_tool(
            name="create_event",
            arguments={
                "title": "Meeting",
                "start": "2026-04-21T15:00:00",
                "end": "2026-04-21T16:00:00",
            },
            calendar_client=calendar,
        ),
    )

    assert result["id"] == "created-1"


def test_dispatch_tool_list_events() -> None:
    """Ensure list_events tool is dispatched correctly."""
    calendar = FakeCalendarClient()

    result = cast(
        "list[dict[str, object]]",
        agent._dispatch_tool(
            name="list_events",
            arguments={},
            calendar_client=calendar,
        ),
    )

    assert result[0]["id"] == "event-1"


def test_dispatch_tool_update_event_missing_reference() -> None:
    """Ensure update_event raises TypeError when reference is missing."""
    calendar = FakeCalendarClient()

    with pytest.raises(TypeError, match="Missing event_reference"):
        agent._dispatch_tool(
            name="update_event",
            arguments={},
            calendar_client=calendar,
        )


def test_dispatch_tool_unknown_tool() -> None:
    """Ensure unknown tool raises ValueError."""
    calendar = FakeCalendarClient()

    with pytest.raises(ValueError, match="Unknown tool"):
        agent._dispatch_tool(
            name="unknown_tool",
            arguments={},
            calendar_client=calendar,
        )
