# ai_client_api

## Role

Defines the abstract interface and dependency injection registry for AI client interactions. This package contains no concrete implementation and has zero external dependencies.

## Dependencies

None (Python stdlib only)

## Public API

| Export | Type | Description |
|--------|------|-------------|
| `AiClient` | ABC | Abstract base class with method: `send_message(prompt, context)` |
| `AiResponse` | dataclass | Structured response containing `message` and `tool_calls` |
| `AiToolCall` | dataclass | Represents a tool call with `tool_name` and `arguments` |
| `register_client(factory)` | function | Registers a factory function `() -> AiClient` with the DI registry |
| `get_client()` | function | Returns a new `AiClient` instance from the registered factory. Raises `RuntimeError` if no factory is registered |
