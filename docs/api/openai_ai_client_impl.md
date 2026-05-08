# OpenAI AI Client Implementation

This page documents the `openai_ai_client_impl` package, the OpenAI-backed implementation of `ai_client_api`.

Importing this package registers `OpenAiClient` with the `ai_client_api` dependency injection registry. Consumers should still code against `ai_client_api`; the implementation package is imported to activate the provider.

## What this component contains

- **OpenAI provider adapter**: `OpenAiClient`, backed by the OpenAI Chat Completions API.
- **Tool loop execution** that calls a service-provided tool handler and feeds results back to the model.
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

The OpenAI implementation runs the model/tool loop. The service layer defines and dispatches tools in `google_calendar_service.integrations.tools`. Current service tool names include:

- `create_event`
- `list_events`
- `update_event`
- `create_event_from_issue`
- `list_issue_boards`
- `list_issues`
- `get_issue`
- `create_issue`
- `update_issue`
- `schedule_issue_work_session`

The service layer owns the provider-neutral tool definitions and dispatch, so the AI provider only runs the tool loop. Issue deletion is not exposed to the model. `schedule_issue_work_session` combines issue details with calendar availability to schedule the first open work slot in a user-provided time window.

## Usage

```python
import openai_ai_client_impl  # Registers the OpenAI provider.
from ai_client_api import get_client

client = get_client()
message = client.send_message("List my meetings tomorrow")
```
