# Calendar Client Platform

This project is a Python 3.13 `uv` workspace for provider-neutral calendar operations, a FastAPI Google Calendar service, and AI-assisted calendar/issue workflows.

The system is composed of the following components:

- `calendar_client_api` defines the calendar contract.
- `google_calendar_client_impl` a Google Calendar implementation of the calendar contract.
- `google_calendar_service` exposes calendar operations and AI workflows over HTTP.
- `google_calendar_service_adapter` calls the HTTP service while still implementing the calendar contract.
- `ai_client_api` and `openai_ai_client_impl` provide the AI abstraction used by the service's `/ai/` route.

Use this documentation for architecture notes, component responsibilities, telemetry/IaC details, and API reference pages generated with `mkdocstrings`.
