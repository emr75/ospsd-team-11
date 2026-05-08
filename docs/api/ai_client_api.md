# AI Client API

This page documents the `ai_client_api` package, which defines the provider-neutral AI client contract.

`ai_client_api` is a port in the project architecture. Application code depends on this package instead of importing OpenAI or another provider directly. Concrete providers register themselves through the dependency injection registry.

## What this component contains

- **Client interface**: `AiClient`, the abstract contract for single-turn prompts and provider-specific tool loops.
- **Dependency injection registry**: `register_client` and `get_client` for selecting a concrete AI implementation at runtime.

## Client Contract

::: ai_client_api.client.AiClient
    options:
      show_root_heading: true
      show_source: true

## Dependency Injection Registry

::: ai_client_api.registry.get_client
    options:
      show_root_heading: true
      show_source: true

::: ai_client_api.registry.register_client
    options:
      show_root_heading: true
      show_source: true

## Usage

```python
from ai_client_api import get_client

client = get_client()
message = client.send_message(
    prompt="Schedule a team sync tomorrow at 3 PM",
    context={"timezone": "America/New_York"},
)

print(message)
```

Tool-calling workflows are driven by the service layer:

```python
answer = client.run_chat_with_tools(
    system_prompt="Use tools only when needed.",
    user_message="Find time for issue 123 tomorrow.",
    tools=[...],
    handle_tool=lambda name, arguments: "{}",
)
```
