# OpenAI AI Client Implementation

This page documents the `openai_ai_client_impl` package, the OpenAI-backed implementation of `ai_client_api`.

Importing this package registers `OpenAiClient` with the `ai_client_api` dependency injection registry. Consumers should still code against `ai_client_api`; the implementation package is imported to activate the provider.

## What this component contains

- **OpenAI provider adapter**: `OpenAiClient`, backed by the OpenAI Responses API.
- **Tool definitions** for calendar and cross-service workflows.
- **Response parser** that converts OpenAI message and function-call outputs into `AiResponse`.
- **Registration helpers** for dependency injection.

## Configuration

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | API key used by the OpenAI SDK |
| `OPENAI_MODEL` | No | Model override; defaults to the package default |

## Public API

::: openai_ai_client_impl.client_impl.OpenAiClient
    options:
      show_root_heading: true
      show_source: true

::: openai_ai_client_impl.client_impl.get_openai_client
    options:
      show_root_heading: true
      show_source: true

::: openai_ai_client_impl.client_impl.register_openai_client
    options:
      show_root_heading: true
      show_source: true

## Tool Calling

The implementation exposes tool definitions to the model so it can request structured actions. Current supported tool names include:

- `create_event`
- `list_events`
- `update_event`
- `create_event_from_issue`

The returned `AiResponse.tool_calls` list contains provider-neutral `AiToolCall` objects, so the service layer can map tool calls to calendar or cross-service workflows without depending on OpenAI SDK types.

## Usage

```python
import openai_ai_client_impl  # Registers the OpenAI provider.
from ai_client_api import get_client

client = get_client()
response = client.send_message("List my meetings tomorrow")
```
