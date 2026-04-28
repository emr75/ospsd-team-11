# ruff: noqa: D100, D103

from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import ai_client_api.registry as registry_module
from ai_client_api.client import AiResponse
from openai_ai_client_impl.client_impl import (
    OpenAiClient,
    _build_tools,
    _build_user_prompt,
    _parse_response,
    register_openai_client,
)

if TYPE_CHECKING:
    from openai import OpenAI


def test_build_user_prompt_without_context_returns_prompt_only() -> None:
    result = _build_user_prompt("Schedule a meeting", None)

    assert result == "Schedule a meeting"


def test_build_user_prompt_with_context_includes_context_json() -> None:
    result = _build_user_prompt(
        "Schedule a meeting",
        {"timezone": "America/New_York"},
    )

    assert "Schedule a meeting" in result
    assert "Context JSON" in result
    assert "America/New_York" in result


def test_build_tools_contains_expected_tool_names() -> None:
    tools = _build_tools()
    tool_names = {tool["name"] for tool in tools}

    assert "create_event" in tool_names
    assert "list_events" in tool_names
    assert "update_event" in tool_names
    assert "create_event_from_issue" in tool_names


def test_parse_response_returns_message_only_when_no_tool_calls() -> None:
    response = SimpleNamespace(
        output=[
            SimpleNamespace(
                type="message",
                content=[SimpleNamespace(type="output_text", text="Here is your answer.")],
            )
        ]
    )

    result = _parse_response(response)

    assert result == AiResponse(
        message="Here is your answer.",
        tool_calls=[],
    )


def test_parse_response_extracts_function_call_arguments() -> None:
    response = SimpleNamespace(
        output=[
            SimpleNamespace(
                type="message",
                content=[SimpleNamespace(type="output_text", text="I can schedule that.")],
            ),
            SimpleNamespace(
                type="function_call",
                name="create_event",
                arguments='{"title":"Team Sync","start":"2026-04-21T15:00:00-04:00","end":"2026-04-21T16:00:00-04:00"}',
            ),
        ]
    )

    result = _parse_response(response)

    assert result.message == "I can schedule that."
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].tool_name == "create_event"
    assert result.tool_calls[0].arguments["title"] == "Team Sync"


def test_parse_response_handles_invalid_json_arguments() -> None:
    response = SimpleNamespace(
        output=[
            SimpleNamespace(
                type="function_call",
                name="create_event",
                arguments="{invalid json}",
            )
        ]
    )

    result = _parse_response(response)

    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].tool_name == "create_event"
    assert result.tool_calls[0].arguments == {}


def test_register_openai_client_registers_factory() -> None:
    registry_module._registry["client_factory"] = None

    register_openai_client()

    assert registry_module._registry["client_factory"] is not None


# Send message unit test


def test_send_message_calls_openai_and_returns_parsed_response() -> None:
    fake_response = SimpleNamespace(
        output=[
            SimpleNamespace(
                type="message",
                content=[SimpleNamespace(type="output_text", text="I can schedule that.")],
            ),
            SimpleNamespace(
                type="function_call",
                name="create_event",
                arguments='{"title":"Meeting","start":"2026-04-21T15:00:00-04:00","end":"2026-04-21T16:00:00-04:00"}',
            ),
        ]
    )

    class FakeResponses:
        def __init__(self) -> None:
            self.called_with: dict[str, object] | None = None

        def create(self, **kwargs: object) -> object:
            self.called_with = kwargs
            return fake_response

    class FakeOpenAIClient:
        def __init__(self) -> None:
            self.responses = FakeResponses()

    fake_client = FakeOpenAIClient()
    client = OpenAiClient(client=cast("OpenAI", fake_client), model="gpt-test")

    result = client.send_message(
        prompt="Schedule a meeting tomorrow",
        context={"timezone": "America/New_York"},
    )

    assert result.message == "I can schedule that."
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].tool_name == "create_event"
    assert fake_client.responses.called_with is not None
    assert fake_client.responses.called_with["model"] == "gpt-test"
