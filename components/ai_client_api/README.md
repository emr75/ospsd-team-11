# ai_client_api

## Role

Defines the abstract interface and dependency injection registry for AI client interactions. This package contains no concrete implementation and has zero external dependencies.

## Dependencies

None (Python stdlib only)

## Public API

| Export | Type | Description |
|--------|------|-------------|
| `AiClient` | ABC | Abstract base class with `send_message(...)` and `run_chat_with_tools(...)` |
| `register_client(factory)` | function | Registers a factory function `() -> AiClient` with the DI registry |
| `get_client()` | function | Returns a new `AiClient` instance from the registered factory. Raises `RuntimeError` if no factory is registered |

## Client Contract

- `send_message(prompt, context=None) -> str` handles simple single-turn text prompts.
- `run_chat_with_tools(system_prompt, user_message, tools, handle_tool, max_tool_rounds=8) -> str` runs a provider-specific tool-calling loop. The service layer owns tool definitions and dispatch, while implementations only need to call the model and feed tool results back into the conversation.
