"""Tests for OAuth helpers and auth endpoints in Google Calendar Service."""
# ruff: noqa: C901, PYI034, ASYNC109, EM101, TRY003

from __future__ import annotations

import asyncio
import json
import urllib.parse
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID

import google_calendar_service.oauth_utils as oauth_module
import google_calendar_service.routes.auth_routes as auth_module
import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from google_calendar_service.main import app
from google_calendar_service.session_store import OAuthStateRecord, optional_cookie
from google_calendar_service.session_store import cookie as session_cookie

HTTP_OK = 200
HTTP_BAD_REQUEST = 400
HTTP_FOUND = 302
HTTP_BAD_GATEWAY = 502

client = TestClient(app)


class TestAuthHelperFunctions:
    """Tests for oauth_utils helpers."""

    def test_build_google_authorization_url_contains_expected_params(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Build provider URL with expected OAuth parameters."""
        fake_settings = SimpleNamespace(
            oauth=SimpleNamespace(
                require_client_id=lambda: "id-1",
                require_redirect_uri=lambda: "http://localhost:8000/auth/callback",
                scopes="scope.a scope.b",
                prompt="select_account",
                auth_url="https://accounts.google.com/o/oauth2/v2/auth",
            )
        )
        monkeypatch.setattr(oauth_module, "settings", fake_settings)

        url = oauth_module.build_google_authorization_url(
            state="state-1",
            code_challenge="challenge-1",
        )
        parsed = urllib.parse.urlparse(url)
        params = urllib.parse.parse_qs(parsed.query)

        assert parsed.scheme == "https"
        assert params["client_id"] == ["id-1"]
        assert params["redirect_uri"] == ["http://localhost:8000/auth/callback"]
        assert params["response_type"] == ["code"]
        assert params["scope"] == ["scope.a scope.b"]
        assert params["state"] == ["state-1"]
        assert params["code_challenge"] == ["challenge-1"]
        assert params["code_challenge_method"] == ["S256"]
        assert params["access_type"] == ["offline"]

    def test_exchange_code_for_tokens_success_and_fallback_expiry(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Return tokens and use fallback expiry when provider value is invalid."""
        fake_settings = SimpleNamespace(
            oauth=SimpleNamespace(
                require_web_credentials=lambda: (
                    "id-1",
                    "secret-1",
                    "http://localhost:8000/auth/callback",
                ),
                token_url="https://oauth2.googleapis.com/token",
                token_request_timeout_seconds=10,
            )
        )
        monkeypatch.setattr(oauth_module, "settings", fake_settings)

        class FakeResponse:
            is_error = False
            text = "ok"

            def json(self) -> dict[str, object]:
                return {
                    "access_token": "access-1",
                    "refresh_token": "refresh-1",
                    "expires_in": "not-an-int",
                }

        class FakeAsyncClient:
            async def __aenter__(self) -> FakeAsyncClient:
                return self

            async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
                del exc_type, exc, tb

            async def post(
                self,
                url: str,
                *,
                data: dict[str, str],
                timeout: int,
                headers: dict[str, str],
            ) -> FakeResponse:
                del url, data, timeout, headers
                return FakeResponse()

        monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

        before = datetime.now(UTC)
        access_token, refresh_token, expires_at = asyncio.run(
            oauth_module.exchange_code_for_tokens(code="code-1", code_verifier="verifier-1")
        )
        after = datetime.now(UTC)

        assert access_token == "access-1"
        assert refresh_token == "refresh-1"
        assert before + timedelta(seconds=3590) <= expires_at <= after + timedelta(seconds=3610)

    def test_exchange_code_for_tokens_handles_provider_errors(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Handle request/network error, HTTP error, bad JSON, and missing token."""
        fake_settings = SimpleNamespace(
            oauth=SimpleNamespace(
                require_web_credentials=lambda: (
                    "id-1",
                    "secret-1",
                    "http://localhost:8000/auth/callback",
                ),
                token_url="https://oauth2.googleapis.com/token",
                token_request_timeout_seconds=10,
            )
        )
        monkeypatch.setattr(oauth_module, "settings", fake_settings)

        request = httpx.Request("POST", "https://oauth2.googleapis.com/token")

        class RequestErrorClient:
            async def __aenter__(self) -> RequestErrorClient:
                return self

            async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
                del exc_type, exc, tb

            async def post(
                self,
                url: str,
                *,
                data: dict[str, str],
                timeout: int,
                headers: dict[str, str],
            ) -> None:
                del url, data, timeout, headers
                raise httpx.RequestError("boom", request=request)

        monkeypatch.setattr(httpx, "AsyncClient", RequestErrorClient)
        with pytest.raises(HTTPException) as exc_request_error:
            asyncio.run(oauth_module.exchange_code_for_tokens(code="code-1", code_verifier="verifier-1"))
        assert exc_request_error.value.status_code == HTTP_BAD_GATEWAY

        class ErrorResponse:
            is_error = True
            text = "bad request"

            def json(self) -> dict[str, object]:
                return {}

        class HttpErrorClient:
            async def __aenter__(self) -> HttpErrorClient:
                return self

            async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
                del exc_type, exc, tb

            async def post(
                self,
                url: str,
                *,
                data: dict[str, str],
                timeout: int,
                headers: dict[str, str],
            ) -> ErrorResponse:
                del url, data, timeout, headers
                return ErrorResponse()

        monkeypatch.setattr(httpx, "AsyncClient", HttpErrorClient)
        with pytest.raises(HTTPException) as exc_http_error:
            asyncio.run(oauth_module.exchange_code_for_tokens(code="code-1", code_verifier="verifier-1"))
        assert exc_http_error.value.status_code == HTTP_BAD_GATEWAY

        class NonJsonResponse:
            is_error = False
            text = "not-json"

            def json(self) -> dict[str, object]:
                raise json.JSONDecodeError("bad json", doc="not-json", pos=0)

        class NonJsonClient:
            async def __aenter__(self) -> NonJsonClient:
                return self

            async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
                del exc_type, exc, tb

            async def post(
                self,
                url: str,
                *,
                data: dict[str, str],
                timeout: int,
                headers: dict[str, str],
            ) -> NonJsonResponse:
                del url, data, timeout, headers
                return NonJsonResponse()

        monkeypatch.setattr(httpx, "AsyncClient", NonJsonClient)
        with pytest.raises(HTTPException) as exc_bad_json:
            asyncio.run(oauth_module.exchange_code_for_tokens(code="code-1", code_verifier="verifier-1"))
        assert exc_bad_json.value.status_code == HTTP_BAD_GATEWAY

        class MissingTokenResponse:
            is_error = False
            text = "ok"

            def json(self) -> dict[str, object]:
                return {"refresh_token": "refresh-1", "expires_in": 1200}

        class MissingTokenClient:
            async def __aenter__(self) -> MissingTokenClient:
                return self

            async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
                del exc_type, exc, tb

            async def post(
                self,
                url: str,
                *,
                data: dict[str, str],
                timeout: int,
                headers: dict[str, str],
            ) -> MissingTokenResponse:
                del url, data, timeout, headers
                return MissingTokenResponse()

        monkeypatch.setattr(httpx, "AsyncClient", MissingTokenClient)
        with pytest.raises(HTTPException) as exc_missing_access:
            asyncio.run(oauth_module.exchange_code_for_tokens(code="code-1", code_verifier="verifier-1"))
        assert exc_missing_access.value.status_code == HTTP_BAD_GATEWAY


class TestAuthEndpoints:
    """Tests for auth/login, auth/callback, and auth/logout endpoints."""

    def test_login_redirects_and_clears_previous_session(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Delete previous session, create new one, and redirect to provider."""
        previous_session_id = UUID("00000000-0000-0000-0000-000000000111")
        new_session_id = UUID("00000000-0000-0000-0000-000000000222")
        observed: dict[str, object] = {}

        async def fake_delete_session(*, session_id: UUID) -> None:
            observed["deleted_session_id"] = session_id

        async def fake_create_session() -> UUID:
            return new_session_id

        async def fake_set_oauth_handshake_in_session(
            *,
            session_id: UUID,
            state: str,
            code_verifier: str,
            ttl_seconds: int,
        ) -> None:
            observed["set_session_id"] = session_id
            observed["set_state"] = state
            observed["set_code_verifier"] = code_verifier
            observed["set_ttl"] = ttl_seconds

        app.dependency_overrides[optional_cookie] = lambda: previous_session_id
        monkeypatch.setattr(auth_module, "delete_session", fake_delete_session)
        monkeypatch.setattr(auth_module, "create_session", fake_create_session)
        monkeypatch.setattr(auth_module, "generate_oauth_state", lambda: "state-1")
        monkeypatch.setattr(auth_module, "generate_pkce_pair", lambda: ("verifier-1", "challenge-1"))
        monkeypatch.setattr(auth_module, "settings", SimpleNamespace(oauth=SimpleNamespace(state_ttl_seconds=123)))
        monkeypatch.setattr(auth_module, "set_oauth_handshake_in_session", fake_set_oauth_handshake_in_session)
        monkeypatch.setattr(
            auth_module,
            "build_google_authorization_url",
            lambda *, state, code_challenge: f"https://example.com/oauth?state={state}&cc={code_challenge}",
        )

        try:
            response = client.get("/auth/auth/login", follow_redirects=False)
        finally:
            app.dependency_overrides.pop(optional_cookie, None)

        assert response.status_code == HTTP_FOUND
        assert response.headers["location"] == "https://example.com/oauth?state=state-1&cc=challenge-1"
        assert observed["deleted_session_id"] == previous_session_id
        assert observed["set_session_id"] == new_session_id
        assert observed["set_state"] == "state-1"
        assert observed["set_code_verifier"] == "verifier-1"

    def test_logout_without_session_returns_logged_out(self) -> None:
        """Return 200 and logged-out status even when no session exists."""
        client.cookies.clear()
        response = client.post("/auth/auth/logout")

        assert response.status_code == HTTP_OK
        assert response.json() == {"status": "logged out"}

    def test_callback_error_branches(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Return 400 for provider error, missing code/state, and invalid handshake."""
        session_id = UUID("00000000-0000-0000-0000-000000000333")
        app.dependency_overrides[session_cookie] = lambda: session_id

        async def fake_consume_none(*, session_id: UUID, state: str) -> None:
            del session_id, state

        monkeypatch.setattr(auth_module, "consume_oauth_handshake_from_session", fake_consume_none)

        try:
            provider_error = client.get("/auth/auth/callback", params={"error": "access_denied"})
            assert provider_error.status_code == HTTP_BAD_REQUEST

            missing_code = client.get("/auth/auth/callback", params={"state": "state-1"})
            assert missing_code.status_code == HTTP_BAD_REQUEST

            missing_state = client.get("/auth/auth/callback", params={"code": "code-1"})
            assert missing_state.status_code == HTTP_BAD_REQUEST

            invalid_state = client.get("/auth/auth/callback", params={"code": "code-1", "state": "state-1"})
            assert invalid_state.status_code == HTTP_BAD_REQUEST
        finally:
            app.dependency_overrides.pop(session_cookie, None)

    def test_callback_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Exchange code and persist tokens when callback is valid."""
        session_id = UUID("00000000-0000-0000-0000-000000000444")
        expires_at = datetime.now(UTC) + timedelta(seconds=3600)
        observed: dict[str, object] = {}

        async def fake_consume(*, session_id: UUID, state: str) -> OAuthStateRecord:
            observed["consume_session_id"] = session_id
            observed["consume_state"] = state
            return OAuthStateRecord(
                state=state,
                code_verifier="verifier-1",
                expires_at=expires_at,
            )

        async def fake_exchange(*, code: str, code_verifier: str) -> tuple[str, str | None, datetime]:
            observed["exchange_code"] = code
            observed["exchange_verifier"] = code_verifier
            return ("access-1", "refresh-1", expires_at)

        async def fake_set_tokens(
            *,
            session_id: UUID,
            access_token: str,
            expires_at: datetime,
            refresh_token: str | None = None,
        ) -> None:
            observed["set_session_id"] = session_id
            observed["set_access_token"] = access_token
            observed["set_refresh_token"] = refresh_token
            observed["set_expires_at"] = expires_at

        app.dependency_overrides[session_cookie] = lambda: session_id
        monkeypatch.setattr(auth_module, "consume_oauth_handshake_from_session", fake_consume)
        monkeypatch.setattr(auth_module, "exchange_code_for_tokens", fake_exchange)
        monkeypatch.setattr(auth_module, "set_oauth_tokens_in_session", fake_set_tokens)

        try:
            response = client.get(
                "/auth/auth/callback",
                params={"code": "code-1", "state": "state-1"},
            )
        finally:
            app.dependency_overrides.pop(session_cookie, None)

        assert response.status_code == HTTP_OK
        assert response.json() == {"status": "authenticated"}
        assert observed["consume_session_id"] == session_id
        assert observed["consume_state"] == "state-1"
        assert observed["exchange_code"] == "code-1"
        assert observed["exchange_verifier"] == "verifier-1"
        assert observed["set_session_id"] == session_id
        assert observed["set_access_token"] == "access-1"
        assert observed["set_refresh_token"] == "refresh-1"
        assert observed["set_expires_at"] == expires_at
