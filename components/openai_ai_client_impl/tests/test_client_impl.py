"""Tests for OpenAI AI client implementation."""

from typing import Any, cast

import ai_client_api.registry as registry_module
from openai_ai_client_impl.client_impl import OpenAiClient, register_openai_client


def test_register_openai_client_registers_factory() -> None:
    """Ensure the OpenAI client registers correctly."""
    registry_module._registry["client_factory"] = None

    register_openai_client()

    assert registry_module._registry["client_factory"] is not None


def test_send_message_returns_text_response() -> None:
    """Ensure send_message returns text from OpenAI response."""

    class FakeChatCompletions:
        def __init__(self) -> None:
            self.called_with: dict[str, Any] | None = None

        def create(self, **kwargs: Any) -> Any:
            self.called_with = kwargs

            return type(
                "Response",
                (),
                {
                    "choices": [
                        type(
                            "Choice",
                            (),
                            {
                                "message": type(
                                    "Message",
                                    (),
                                    {"content": "Hello from AI", "tool_calls": None},
                                )()
                            },
                        )
                    ]
                },
            )()

    class FakeOpenAIClient:
        def __init__(self) -> None:
            self.chat = type("Chat", (), {"completions": FakeChatCompletions()})()

    fake_client = FakeOpenAIClient()
    client = OpenAiClient(client=cast("Any", fake_client), model="gpt-test")

    result = client.send_message(prompt="Hello")

    assert result == "Hello from AI"
    assert fake_client.chat.completions.called_with is not None
    assert fake_client.chat.completions.called_with["model"] == "gpt-test"


def test_run_chat_with_tools_returns_final_text() -> None:
    """Ensure tool loop returns final message when no tool calls occur."""

    class FakeChatCompletions:
        def create(self, **kwargs: Any) -> Any:
            return type(
                "Response",
                (),
                {
                    "choices": [
                        type(
                            "Choice",
                            (),
                            {
                                "message": type(
                                    "Message",
                                    (),
                                    {"content": "Final answer", "tool_calls": None},
                                )()
                            },
                        )
                    ]
                },
            )()

    class FakeOpenAIClient:
        def __init__(self) -> None:
            self.chat = type("Chat", (), {"completions": FakeChatCompletions()})()

    client = OpenAiClient(client=cast("Any", FakeOpenAIClient()))

    result = client.run_chat_with_tools(
        system_prompt="Test",
        user_message="Hello",
        tools=[],
        handle_tool=lambda *_: "",
    )

    assert result == "Final answer"
