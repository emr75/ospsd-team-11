# Calendar Client API

This page documents the `CalendarClient` interface used by the Calendar Client system.

`calendar_client_api` defines an implementation-independent interface for calendar operations. Concrete providers (e.g., Google Calendar) must adapt their raw provider data into objects that satisfy the abstract base classes and datamodels defined here.

## What this component contains

- **The client interface**: `CalendarClient`, the provider-agnostic contract for calendar operations.
- **Domain exceptions**: common exception types that adapters use to hide provider/transport details.
- **Dependency injection registry**: `register_client` and `get_client` for selecting a concrete provider implementation at runtime.

## The Client Interface

::: calendar_client_api.client.CalendarClient
    options:
      show_root_heading: true
      show_source: true

## Dependency Injection Registry

::: calendar_client_api.registry.get_client
    options:
      show_root_heading: true
      show_source: true

::: calendar_client_api.registry.register_client
    options:
      show_root_heading: true
      show_source: true

## Domain Exceptions

::: calendar_client_api.exceptions
    options:
      show_root_heading: true
      show_source: true
