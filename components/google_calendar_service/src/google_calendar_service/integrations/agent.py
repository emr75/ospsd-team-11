"""AI agent orchestration for calendar and issue workflows."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from google_calendar_service.integrations.tools import TOOLS, make_tool_handler

if TYPE_CHECKING:
    from ai_client_api import AiClient
    from api.client import Client as IssueClient  # type: ignore[import-untyped]
    from calendar_client_api import CalendarClient

SYSTEM_PROMPT = (
    "You are an assistant for calendar and cross-service workflows. "
    "Use tools when the user asks to list, create, update, or schedule calendar events. "
    "Use the issue-related tool when the user asks to schedule something based on an issue. "
    "Do not invent tool results. After tools are executed, summarize the result clearly."
)


def run_ai_turn(
    *,
    prompt: str,
    context: dict[str, object] | None,
    ai_client: AiClient,
    calendar_client: CalendarClient,
    issue_client: IssueClient,
) -> str:
    """Run one AI conversation turn with calendar and issue tools."""
    user_message = _build_user_message(prompt=prompt, context=context)

    return ai_client.run_chat_with_tools(
        system_prompt=SYSTEM_PROMPT,
        user_message=user_message,
        tools=TOOLS,
        handle_tool=make_tool_handler(calendar_client, issue_client),
    )


def _build_user_message(
    *,
    prompt: str,
    context: dict[str, object] | None,
) -> str:
    """Build the user message with optional structured context."""
    if not context:
        return prompt

    return f"{prompt}\n\nContext JSON:\n{json.dumps(context, default=str)}"
