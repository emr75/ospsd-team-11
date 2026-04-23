"""OpenAI implementation of the AiClient interface."""

import json
import os
from typing import Any, Protocol

import ai_client_api
from ai_client_api import AiClient, AiResponse, AiToolCall
from openai import OpenAI


class OpenAIResponseProtocol(Protocol):
    """Protocol for the subset of OpenAI response fields used by the parser."""

    output: list[object]


class OpenAiClient(AiClient):
    """Concrete AI client backed by the OpenAI Responses API."""

    # In case gpt-4o-mini is nt available
    DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    def __init__(
        self,
        client: OpenAI | None = None,
        *,
        model: str | None = None,
    ) -> None:
        """Initialize the OpenAI AI client."""
        self._model = model or os.getenv("OPENAI_MODEL", self.DEFAULT_MODEL)
        self._client = client or OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    def send_message(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
    ) -> AiResponse:
        """Send a prompt to OpenAI and return parsed tool calls."""
        system_prompt = _build_system_prompt()
        user_prompt = _build_user_prompt(prompt=prompt, context=context)

        response = self._client.responses.create( # type: ignore[call-overload]
            model=self._model,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            tools=_build_tools(),
            tool_choice = (
                {"type": "function", "name": "create_event_from_issue"}
                    if "issue" in prompt.lower()
                else "auto"
            )
        )

        return _parse_response(response)


def _build_system_prompt() -> str:
    return (
        "You are an assistant for calendar and cross-service workflows. "
        "Use tool calls whenever an action is required. "
        "Do not guess or fabricate results. "
        "Always return valid JSON arguments when calling tools. "
        "If no tool is needed, return a concise natural language response."
    )

def _build_user_prompt(prompt: str, context: dict[str, Any] | None) -> str:
    if context is None:
        return prompt
    context_json = json.dumps(context, default=str)
    return f"User prompt:\n{prompt}\n\nContext JSON:\n{context_json}"


def _build_tools() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "name": "create_event",
            "description": "Create a new calendar event.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "start": {"type": "string", "description": "ISO 8601 datetime"},
                    "end": {"type": "string", "description": "ISO 8601 datetime"},
                    "description": {"type": "string"},
                    "location": {"type": ["string", "null"]},
                },
                "required": ["title", "start", "end"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "list_events",
            "description": "List calendar events within a date range.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start": {"type": "string", "description": "ISO 8601 datetime"},
                    "end": {"type": "string", "description": "ISO 8601 datetime"},
                },
                "required": ["start", "end"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "update_event",
            "description": "Update or reschedule an existing calendar event.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_reference": {
                        "type": "string",
                        "description": "Human-readable event reference, such as meeting title.",
                    },
                    "start_time": {"type": "string", "description": "ISO 8601 datetime"},
                    "end_time": {"type": "string", "description": "ISO 8601 datetime"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "location": {"type": ["string", "null"]},
                },
                "required": ["event_reference"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "create_event_from_issue",
            "description": "Create a calendar event from an issue when the user asks to schedule a meeting related to an issue.",
            "parameters": {
                "type": "object",
                "properties": {
                    "issue_id": {"type": "string"},
                    "start": {"type": "string", "description": "ISO 8601 datetime"},
                    "end": {"type": "string", "description": "ISO 8601 datetime"},
                },
                "required": ["issue_id", "start", "end"],
                "additionalProperties": False,
            },
        },
    ]


def _parse_response(response: OpenAIResponseProtocol) -> AiResponse:
    message_parts: list[str] = []
    tool_calls: list[AiToolCall] = []

    for item in getattr(response, "output", []):
        item_type = getattr(item, "type", None)

        if item_type == "message":
            for content in getattr(item, "content", []):
                if getattr(content, "type", None) in {"output_text", "text"}:
                    text = getattr(content, "text", "")
                    if text:
                        message_parts.append(text)

        if item_type == "function_call":
            raw_arguments = getattr(item, "arguments", "{}")
            try:
                parsed_arguments = json.loads(raw_arguments)
            except json.JSONDecodeError:
                parsed_arguments = {}
            tool_calls.append(
                AiToolCall(
                    tool_name=item.name,
                    arguments=parsed_arguments,
                )
            )

    return AiResponse(
        message="\n".join(part for part in message_parts if part).strip(),
        tool_calls=tool_calls,
    )


def get_openai_client() -> OpenAiClient:
    """Return a concrete OpenAI AI client."""
    return OpenAiClient()


def register_openai_client() -> None:
    """Register the OpenAI implementation with the AI client API."""
    ai_client_api.register_client(get_openai_client)
