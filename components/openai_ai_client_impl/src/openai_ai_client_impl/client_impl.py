"""OpenAI implementation of the AiClient interface with tool-calling loop."""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

import ai_client_api
from ai_client_api import AiClient
from openai import OpenAI


class OpenAiClient(AiClient):
    """Concrete AI client backed by OpenAI Chat Completions."""

    DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    def __init__(
        self,
        client: OpenAI | None = None,
        *,
        model: str | None = None,
    ) -> None:
        """Initialize the OpenAI AI client."""
        self._model: str = model or os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
        self._client = client or OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    def send_message(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
    ) -> str:
        """Send a prompt to OpenAI and return a text response."""
        system_prompt = self._build_system_prompt(context)

        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
        )

        msg = response.choices[0].message
        return (msg.content or "").strip()

    def run_chat_with_tools(
        self,
        *,
        system_prompt: str,
        user_message: str,
        tools: list[dict[str, Any]],
        handle_tool: Callable[[str, dict[str, Any]], str],
        max_tool_rounds: int = 8,
    ) -> str:
        """Run a multi-turn completion with tool-calling loop."""
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        rounds = 0

        while rounds < max_tool_rounds:
            rounds += 1

            response = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
            )  # type: ignore[call-overload]
                # OpenAI SDK type stubs do not fully support tools/tool_choice combination
            msg = response.choices[0].message

            if not msg.tool_calls:
                return (msg.content or "").strip()

            messages.append(
                {
                    "role": "assistant",
                    "content": msg.content,
                    "tool_calls": [
                        {
                            "id": tool_call.id,
                            "type": "function",
                            "function": {
                                "name": tool_call.function.name,
                                "arguments": tool_call.function.arguments,
                            },
                        }
                        for tool_call in msg.tool_calls
                    ],
                }
            )

            for tool_call in msg.tool_calls:
                raw_args = tool_call.function.arguments or "{}"

                try:
                    args = json.loads(raw_args)
                except json.JSONDecodeError:
                    args = {}

                if not isinstance(args, dict):
                    args = {}

                try:
                    result = handle_tool(tool_call.function.name, args)
                except Exception as exc:  # noqa: BLE001
                    result = json.dumps(
                        {
                            "error": str(exc),
                            "tool": tool_call.function.name,
                        }
                    )

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result,
                    }
                )

        return "Tool loop limit reached; try a narrower request."

    @staticmethod
    def _build_system_prompt(context: dict[str, Any] | None = None) -> str:
        """Build the system prompt for single-turn messages."""
        base_prompt = (
            "You are a concise assistant for calendar and cross-service workflows. "
            "Answer clearly, and do not fabricate results."
        )

        if not context:
            return base_prompt

        context_json = json.dumps(context, default=str)
        return f"{base_prompt}\nContext JSON: {context_json}"


def get_openai_client() -> OpenAiClient:
    """Return a concrete OpenAI AI client."""
    return OpenAiClient()


def register_openai_client() -> None:
    """Register the OpenAI implementation with the AI client API."""
    ai_client_api.register_client(get_openai_client)
