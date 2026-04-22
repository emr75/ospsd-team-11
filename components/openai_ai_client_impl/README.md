# openai_ai_client_impl

## Role

Concrete implementation of the `ai_client_api` interface backed by the OpenAI Responses API. Importing this package automatically registers it with the DI registry, so any call to `get_client()` will return an `OpenAiClient` instance.

## Dependencies

| Package | Purpose |
|---------|---------|
| `ai-client-api` | Abstract interface (workspace dependency) |
| `openai` | OpenAI Python SDK for interacting with the Responses API |

## Public API

| Export | Type | Description |
|--------|------|-------------|
| `OpenAiClient` | class | Implements `AiClient`. Sends prompts to OpenAI and returns structured responses with optional tool calls |
| `get_openai_client()` | function | Factory function that creates a new `OpenAiClient` instance |
| `register_openai_client()` | function | Registers the OpenAI client with the DI registry |

## Configuration

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | Required API key for authenticating with OpenAI |
| `OPENAI_MODEL` | Optional model override (defaults to `gpt-4o-mini`) |

## DI Auto-Registration

On import, the package calls `register_client(get_openai_client)`, so consumers only need:

```python
import openai_ai_client_impl

client = get_client()  # returns an OpenAiClient
```
