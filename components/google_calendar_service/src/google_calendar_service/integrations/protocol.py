"""Protocols for calendar and issue service clients."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from api.issue import Issue  # type: ignore[import-untyped]

    from google_calendar_service.integrations.agent import ToolDefinition, ToolHandler


class CalendarClientProtocol(Protocol):
    """Protocol for calendar client methods used by AI orchestration."""

    def list_events(self, **kwargs: object) -> list[object]:
        """Return calendar events."""

    def create_event(self, **kwargs: object) -> object:
        """Create calendar event."""

    def update_event(self, **kwargs: object) -> object:
        """Update calendar event."""


class IssueClientProtocol(Protocol):
    """Protocol for issue tracker clients used by this integration."""

    def get_issue(self, issue_id: str) -> Issue:
        """Return an issue by its ID."""


class CalendarCreateEventProtocol(Protocol):
    """Protocol for calendar event creation used by this integration."""

    def create_event(self, **kwargs: object) -> CreatedEventProtocol:
        """Create a calendar event."""


class CreatedEventProtocol(Protocol):
    """Protocol for calendar events returned by create_event."""

    id: str
    title: str


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
