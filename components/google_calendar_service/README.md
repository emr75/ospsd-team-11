# google_calendar_service

## Role

`google_calendar_service` is a FastAPI deployment layer for calendar operations.  
It exposes HTTP endpoints for:

- OAuth login/callback/logout
- session management for OAuth state and tokens
- calendar event CRUD operations
- health checks

It translates HTTP requests/responses to and from the domain contracts defined in `calendar_client_api`, while delegating Google Calendar operations to `google_calendar_client_impl`.

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `calendar-client-api` | Domain contracts (`Event`, `EventCreate`, `EventUpdate`, `Attendee`) |
| `google-calendar-client-impl` | Google Calendar implementation used by service routes |
| `fastapi` | Web framework for API routes and DI |
| `fastapi-sessions` | Cookie-based session frontend/backend utilities |
| `httpx` | Outbound HTTP calls (OAuth token exchange) |
| `uvicorn` | ASGI server runtime |
| `python-dotenv` | Environment loading |

---

## Main Modules

| Module | Responsibility |
|--------|----------------|
| `main.py` | Creates the FastAPI app and registers routers |
| `settings.py` | Loads and validates OAuth/session configuration from environment |
| `models.py` | Request/response DTOs and conversion helpers |
| `oauth_utils.py` | PKCE/state generation and OAuth token exchange |
| `session_store.py` | Session cookie frontend, backend, verifier, token/state helpers |
| `routes/auth_routes.py` | `/auth/login`, `/auth/callback`, `/auth/logout` |
| `routes/event_routes.py` | `/events` CRUD endpoints with authenticated session dependency |
| `routes/health_routes.py` | `/health` endpoint |

---

## API Endpoints

### Health

- `GET /health`  
  Returns:
  ```json
  {"status": "ok"}
  ```

### Auth

- `GET /auth/login`  
  Creates a session, stores OAuth handshake (`state`, PKCE verifier), and redirects to Google OAuth.

- `GET /auth/callback?code=...&state=...`  
  Validates and consumes OAuth handshake, exchanges authorization code for tokens, stores tokens in session.

- `POST /auth/logout`  
  Clears session token state (if present), deletes session cookie, returns:
  ```json
  {"status": "logged out"}
  ```

### Events

All event routes depend on a valid authenticated session with non-expired OAuth tokens.

- `GET /events/` — list events (`max_results` query parameter, default `10`)
- `GET /events/{event_id}` — get one event
- `POST /events/` — create event
- `PATCH /events/{event_id}` — partial update
- `DELETE /events/{event_id}` — delete event, returns:
  ```json
  {"status": "deleted"}
  ```

---

## Configuration

### OAuth

Common variables:

- `GOOGLE_CALENDAR_CLIENT_ID`
- `GOOGLE_CALENDAR_CLIENT_SECRET`
- `GOOGLE_CALENDAR_REDIRECT_URI` (default: `http://localhost:8000/auth/callback`)
- `GOOGLE_CALENDAR_SCOPES`
- `GOOGLE_CALENDAR_OAUTH_AUTH_URL`
- `GOOGLE_CALENDAR_OAUTH_TOKEN_URL`
- `GOOGLE_CALENDAR_OAUTH_ALLOWED_TOKEN_HOSTS`
- `GOOGLE_CALENDAR_OAUTH_PROMPT`
- `GOOGLE_CALENDAR_OAUTH_STATE_TTL_SECONDS`
- `GOOGLE_CALENDAR_OAUTH_TOKEN_TIMEOUT_SECONDS`

### Session

- `GOOGLE_CALENDAR_SESSION_COOKIE_NAME`
- `GOOGLE_CALENDAR_SESSION_IDENTIFIER`
- `GOOGLE_CALENDAR_SESSION_SECRET`
- `GOOGLE_CALENDAR_SESSION_COOKIE_SECURE`

---

## Run Locally

From repository root:

```bash
uv sync --all-packages --extra dev
uv run uvicorn google_calendar_service.main:app --reload
```

Service default URL: `http://127.0.0.1:8000`

---

## Test Scope

Component tests are in:

- `components/google_calendar_service/tests/test_main.py`
- `components/google_calendar_service/tests/test_oauth.py`
- `components/google_calendar_service/tests/test_session_store.py`

Run:

```bash
uv run pytest components/google_calendar_service/tests
```
