# Google Calendar FastAPI Service

This page documents the `google_calendar_service` package, which exposes Google Calendar capabilities via FastAPI routes.

`google_calendar_service` acts as the HTTP service boundary in the project’s ports/adapters architecture. It translates incoming API requests into domain operations and returns typed response envelopes.

## What this component contains

- **FastAPI app assembly** in `main.py`
- **Authentication routes** (`/auth/login`, `/auth/callback`, `/auth/logout`)
- **Event routes** (`/events/`, `/events/{event_id}`)
- **Health route** (`/health`)
- **OAuth utilities** (PKCE/state generation and token exchange)
- **Session storage + verifier utilities**
- **Request/response models** and conversion helpers

---

## Application Entry Point

::: google_calendar_service.main.app
    options:
      show_root_heading: true
      show_source: true

---

## Route Modules

### Auth Routes

::: google_calendar_service.routes.auth_routes
    options:
      show_root_heading: true
      show_source: true

### Event Routes

::: google_calendar_service.routes.event_routes
    options:
      show_root_heading: true
      show_source: true

### Health Routes

::: google_calendar_service.routes.health_routes
    options:
      show_root_heading: true
      show_source: true

---

## Data Models and Mapping

::: google_calendar_service.models
    options:
      show_root_heading: true
      show_source: true

---

## OAuth Utilities

::: google_calendar_service.oauth_utils
    options:
      show_root_heading: true
      show_source: true

---

## Session Store Utilities

::: google_calendar_service.session_store
    options:
      show_root_heading: true
      show_source: true

---

## Settings

::: google_calendar_service.settings
    options:
      show_root_heading: true
      show_source: true

---

## Endpoint Summary

- `GET /health` — service health check
- `GET /auth/login` — starts OAuth flow and redirects
- `GET /auth/callback` — validates state, exchanges code, stores tokens
- `POST /auth/logout` — clears session/token state
- `GET /events/` — list events
- `GET /events/{event_id}` — fetch one event
- `POST /events/` — create event
- `PATCH /events/{event_id}` — partial update
- `DELETE /events/{event_id}` — delete event