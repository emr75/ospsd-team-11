"""Tests for OpenAI AI client implementation."""

import json
from typing import Any, cast

import ai_client_api.registry as registry_module
from openai_ai_client_impl.client_impl import OpenAiClient, register_openai_client

# ---------------------------------------------------------------------------
# Helpers for building fake OpenAI response objects
# ---------------------------------------------------------------------------


def _make_message(content: str | None, tool_calls: list[Any] | None = None) -> Any:
    """Build a fake OpenAI message object."""
    return type("Message", (), {"content": content, "tool_calls": tool_calls})()


def _make_response(content: str | None, tool_calls: list[Any] | None = None) -> Any:
    """Build a fake OpenAI completion response."""
    return type(
        "Response",
        (),
        {"choices": [type("Choice", (), {"message": _make_message(content, tool_calls)})()]},
    )()


def _make_tool_call(call_id: str, name: str, arguments: str) -> Any:
    """Build a fake OpenAI tool-call object."""
    func = type("Function", (), {"name": name, "arguments": arguments})()
    return type("ToolCall", (), {"id": call_id, "function": func})()


def _fake_openai_client(completions: Any) -> Any:
    """Wrap a fake completions object in a structure OpenAiClient expects."""
    return type("FakeOpenAI", (), {"chat": type("Chat", (), {"completions": completions})()})()


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def test_register_openai_client_registers_factory() -> None:
    """Ensure the OpenAI client registers correctly."""
    registry_module._registry["client_factory"] = None

    register_openai_client()

    assert registry_module._registry["client_factory"] is not None


# ---------------------------------------------------------------------------
# send_message
# ---------------------------------------------------------------------------


def test_send_message_returns_text_response() -> None:
    """Ensure send_message returns text from OpenAI response."""

    class FakeChatCompletions:
        def __init__(self) -> None:
            self.called_with: dict[str, Any] | None = None

        def create(self, **kwargs: Any) -> Any:
            self.called_with = kwargs
            return _make_response("Hello from AI")

    completions = FakeChatCompletions()
    fake_client = _fake_openai_client(completions)
    client = OpenAiClient(client=cast("Any", fake_client), model="gpt-test")

    result = client.send_message(prompt="Hello")

    assert result == "Hello from AI"
    assert completions.called_with is not None
    assert completions.called_with["model"] == "gpt-test"


def test_send_message_includes_context_in_system_prompt() -> None:
    """Ensure context dict is serialized into the system prompt."""

    class FakeChatCompletions:
        def __init__(self) -> None:
            self.called_with: dict[str, Any] | None = None

        def create(self, **kwargs: Any) -> Any:
            self.called_with = kwargs
            return _make_response("ok")

    completions = FakeChatCompletions()
    client = OpenAiClient(client=cast("Any", _fake_openai_client(completions)))

    client.send_message(prompt="Hi", context={"timezone": "UTC"})

    assert completions.called_with is not None
    system_msg = completions.called_with["messages"][0]["content"]
    assert "Context JSON" in system_msg
    assert "UTC" in system_msg


# ---------------------------------------------------------------------------
# run_chat_with_tools — no tool calls (immediate return)
# ---------------------------------------------------------------------------


def test_run_chat_with_tools_returns_final_text() -> None:
    """Ensure tool loop returns final message when no tool calls occur."""

    class FakeCompletions:
        def create(self, **kwargs: Any) -> Any:
            return _make_response("Final answer")

    client = OpenAiClient(client=cast("Any", _fake_openai_client(FakeCompletions())))

    result = client.run_chat_with_tools(
        system_prompt="Test",
        user_message="Hello",
        tools=[],
        handle_tool=lambda *_: "",
    )

    assert result == "Final answer"


# ---------------------------------------------------------------------------
# run_chat_with_tools — single tool-call round-trip
# ---------------------------------------------------------------------------


def test_run_chat_with_tools_executes_tool_call_and_returns_final_text() -> None:
    """Ensure model tool calls are dispatched and the final text is returned."""
    call_log: list[tuple[str, dict[str, Any]]] = []

    class FakeCompletions:
        def __init__(self) -> None:
            self._call_count = 0

        def create(self, **kwargs: Any) -> Any:
            self._call_count += 1
            if self._call_count == 1:
                return _make_response(
                    content=None,
                    tool_calls=[_make_tool_call("tc1", "list_events", '{"limit": 5}')],
                )
            return _make_response("Here are your events.")

    def handle(name: str, args: dict[str, Any]) -> str:
        call_log.append((name, args))
        return json.dumps([{"id": "e1", "title": "Standup"}])

    client = OpenAiClient(client=cast("Any", _fake_openai_client(FakeCompletions())))

    result = client.run_chat_with_tools(
        system_prompt="sys",
        user_message="Show events",
        tools=[],
        handle_tool=handle,
    )

    assert result == "Here are your events."
    assert len(call_log) == 1
    assert call_log[0] == ("list_events", {"limit": 5})


# ---------------------------------------------------------------------------
# run_chat_with_tools — malformed JSON arguments fallback
# ---------------------------------------------------------------------------


def test_run_chat_with_tools_handles_malformed_json_arguments() -> None:
    """Ensure malformed JSON in tool arguments falls back to empty dict."""
    received_args: list[dict[str, Any]] = []

    class FakeCompletions:
        def __init__(self) -> None:
            self._call_count = 0

        def create(self, **kwargs: Any) -> Any:
            self._call_count += 1
            if self._call_count == 1:
                return _make_response(
                    content=None,
                    tool_calls=[_make_tool_call("tc1", "list_events", "not-valid-json")],
                )
            return _make_response("done")

    def handle(name: str, args: dict[str, Any]) -> str:
        received_args.append(args)
        return "{}"

    client = OpenAiClient(client=cast("Any", _fake_openai_client(FakeCompletions())))

    client.run_chat_with_tools(
        system_prompt="s",
        user_message="u",
        tools=[],
        handle_tool=handle,
    )

    assert received_args == [{}]


# ---------------------------------------------------------------------------
# run_chat_with_tools — non-dict JSON arguments fallback
# ---------------------------------------------------------------------------


def test_run_chat_with_tools_handles_non_dict_json_arguments() -> None:
    """Ensure valid JSON that is not a dict falls back to empty dict."""
    received_args: list[dict[str, Any]] = []

    class FakeCompletions:
        def __init__(self) -> None:
            self._call_count = 0

        def create(self, **kwargs: Any) -> Any:
            self._call_count += 1
            if self._call_count == 1:
                return _make_response(
                    content=None,
                    tool_calls=[_make_tool_call("tc1", "do_thing", '"just a string"')],
                )
            return _make_response("done")

    def handle(name: str, args: dict[str, Any]) -> str:
        received_args.append(args)
        return "{}"

    client = OpenAiClient(client=cast("Any", _fake_openai_client(FakeCompletions())))

    client.run_chat_with_tools(
        system_prompt="s",
        user_message="u",
        tools=[],
        handle_tool=handle,
    )

    assert received_args == [{}]


# ---------------------------------------------------------------------------
# run_chat_with_tools — handle_tool raises an exception
# ---------------------------------------------------------------------------


def test_run_chat_with_tools_catches_handle_tool_exception() -> None:
    """Ensure exceptions from handle_tool are serialized as error JSON."""
    tool_results: list[str] = []

    class FakeCompletions:
        def __init__(self) -> None:
            self._call_count = 0

        def create(self, **kwargs: Any) -> Any:
            self._call_count += 1
            if self._call_count == 1:
                return _make_response(
                    content=None,
                    tool_calls=[_make_tool_call("tc1", "bad_tool", "{}")],
                )
            # Capture the tool result that was appended to messages
            messages = kwargs.get("messages", [])
            tool_results.extend(m["content"] for m in messages if m.get("role") == "tool")
            return _make_response("Handled error")

    msg = "something broke"

    def handle(_name: str, _args: dict[str, Any]) -> str:
        raise RuntimeError(msg)

    client = OpenAiClient(client=cast("Any", _fake_openai_client(FakeCompletions())))

    result = client.run_chat_with_tools(
        system_prompt="s",
        user_message="u",
        tools=[],
        handle_tool=handle,
    )

    assert result == "Handled error"
    assert len(tool_results) == 1
    parsed = json.loads(tool_results[0])
    assert parsed["error"] == "something broke"
    assert parsed["tool"] == "bad_tool"


# ---------------------------------------------------------------------------
# run_chat_with_tools — max tool rounds exhausted
# ---------------------------------------------------------------------------


def test_run_chat_with_tools_returns_limit_message_on_max_rounds() -> None:
    """Ensure the loop exits with a limit message after max_tool_rounds."""

    class FakeCompletions:
        def create(self, **kwargs: Any) -> Any:
            return _make_response(
                content=None,
                tool_calls=[_make_tool_call("tc1", "loop_forever", "{}")],
            )

    client = OpenAiClient(client=cast("Any", _fake_openai_client(FakeCompletions())))

    result = client.run_chat_with_tools(
        system_prompt="s",
        user_message="u",
        tools=[],
        handle_tool=lambda *_: "{}",
        max_tool_rounds=2,
    )

    assert result == "Tool loop limit reached; try a narrower request."
