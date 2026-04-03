"""Session and OAuth utilities for the Google Calendar service.

This module centralizes:
- Session cookie/frontend configuration
- In-memory session backend and verifier
- OAuth token helpers stored in session data
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID, uuid4

from fastapi import HTTPException
from fastapi_sessions.backends.implementations import InMemoryBackend  # type: ignore[import-untyped]
from fastapi_sessions.frontends.implementations import (  # type: ignore[import-untyped]
    CookieParameters,
    SessionCookie,
)
from fastapi_sessions.session_verifier import SessionVerifier  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict

from google_calendar_service.settings import settings

logger = logging.getLogger(__name__)


def _to_utc(value: datetime) -> datetime:
    """Convert datetime to UTC timezone."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class OAuthStateRecord(BaseModel):
    """OAuth handshake record loaded from session."""

    model_config = ConfigDict(frozen=True)

    state: str
    code_verifier: str
    expires_at: datetime


class OAuthTokenRecord(BaseModel):
    """OAuth token record loaded from session."""

    model_config = ConfigDict(frozen=True)

    access_token: str
    expires_at: datetime
    refresh_token: str | None = None


class SessionData(BaseModel):
    """Session payload stored by fastapi-sessions."""

    oauth_state: str | None = None
    oauth_code_verifier: str | None = None
    oauth_state_expires_at: datetime | None = None

    oauth_access_token: str | None = None
    oauth_refresh_token: str | None = None
    oauth_token_expires_at: datetime | None = None

    def with_oauth_handshake(self, *, state: str, code_verifier: str, ttl_seconds: int) -> SessionData:
        """Return a copy with OAuth handshake values set."""
        if ttl_seconds <= 0:
            msg = f"invalid ttl_seconds: {ttl_seconds} (must be > 0)"
            raise ValueError(msg)

        now = datetime.now(UTC)
        return self.model_copy(
            update={
                "oauth_state": state,
                "oauth_code_verifier": code_verifier,
                "oauth_state_expires_at": now + timedelta(seconds=ttl_seconds),
            },
        )

    def get_oauth_handshake(self, *, state: str, now: datetime | None = None) -> OAuthStateRecord | None:
        """Return handshake record if state matches and not expired."""
        current = now or datetime.now(UTC)

        if self.oauth_state is None or self.oauth_code_verifier is None or self.oauth_state_expires_at is None:
            return None
        if state != self.oauth_state:
            return None
        if self.oauth_state_expires_at <= current:
            return None

        return OAuthStateRecord(
            state=self.oauth_state,
            code_verifier=self.oauth_code_verifier,
            expires_at=self.oauth_state_expires_at,
        )

    def clear_oauth_handshake(self) -> SessionData:
        """Return a copy with OAuth handshake fields cleared."""
        return self.model_copy(
            update={
                "oauth_state": None,
                "oauth_code_verifier": None,
                "oauth_state_expires_at": None,
            }
        )

    def with_oauth_tokens(self, *, access_token: str, expires_at: datetime, refresh_token: str | None = None) -> SessionData:
        """Return a copy with OAuth token fields set/updated.

        If `refresh_token` is omitted, any existing refresh token is preserved.
        """
        persisted_refresh = refresh_token if refresh_token is not None else self.oauth_refresh_token
        return self.model_copy(
            update={
                "oauth_access_token": access_token,
                "oauth_refresh_token": persisted_refresh,
                "oauth_token_expires_at": _to_utc(expires_at),
            }
        )

    def get_oauth_tokens(self, *, now: datetime | None = None) -> OAuthTokenRecord | None:
        """Return token record if present and not expired."""
        current = now or datetime.now(UTC)

        if self.oauth_access_token is None or self.oauth_token_expires_at is None:
            return None
        if self.oauth_token_expires_at <= current:
            return None

        return OAuthTokenRecord(
            access_token=self.oauth_access_token,
            expires_at=self.oauth_token_expires_at,
            refresh_token=self.oauth_refresh_token,
        )

    def clear_oauth_tokens(self) -> SessionData:
        """Return a copy with OAuth token fields cleared."""
        return self.model_copy(
            update={
                "oauth_access_token": None,
                "oauth_refresh_token": None,
                "oauth_token_expires_at": None,
            }
        )


def _make_session_cookie(*, auto_error: bool) -> SessionCookie:
    return SessionCookie(
        cookie_name=settings.session.cookie_name,
        identifier=settings.session.identifier,
        auto_error=auto_error,
        secret_key=settings.session.secret,
        cookie_params=CookieParameters(
            secure=settings.session.cookie_secure,
            httponly=settings.session.cookie_secure,
        ),
    )


cookie = _make_session_cookie(auto_error=True)
optional_cookie = _make_session_cookie(auto_error=False)

backend = InMemoryBackend[UUID, SessionData]()


class BasicSessionVerifier(SessionVerifier[UUID, SessionData]):  # type: ignore[misc]
    """Session verifier used by FastAPI dependency injection."""

    def __init__(
        self,
        *,
        identifier: str,
        auto_error: bool,
        backend: InMemoryBackend[UUID, SessionData],
        auth_http_exception: HTTPException,
    ) -> None:
        """Initialize verifier."""
        self._identifier = identifier
        self._auto_error = auto_error
        self._backend = backend
        self._auth_http_exception = auth_http_exception

    @property
    def identifier(self) -> str:
        """Return verifier identifier."""
        return self._identifier

    @property
    def backend(self) -> InMemoryBackend[UUID, SessionData]:
        """Return backend instance."""
        return self._backend

    @property
    def auto_error(self) -> bool:
        """Return whether auth errors raise automatically."""
        return self._auto_error

    @property
    def auth_http_exception(self) -> HTTPException:
        """Return auth HTTP exception."""
        return self._auth_http_exception

    def verify_session(self, model: SessionData) -> bool:
        """Return whether the session payload exists."""
        return model is not None


verifier = BasicSessionVerifier(
    identifier=settings.session.identifier,
    auto_error=True,
    backend=backend,
    auth_http_exception=HTTPException(status_code=403, detail="invalid session"),
)


async def create_session() -> UUID:
    """Create and persist a new session."""
    session_id = uuid4()
    await backend.create(session_id, SessionData())
    return session_id


async def read_session(*, session_id: UUID) -> SessionData | None:
    """Read session by id."""
    return cast("SessionData | None", await backend.read(session_id))


async def delete_session(*, session_id: UUID) -> None:
    """Delete session by id."""
    try:
        await backend.delete(session_id)
    except KeyError:
        msg = f"error deleting session {session_id}"
        logger.info(msg)


async def set_oauth_handshake_in_session(*, session_id: UUID, state: str, code_verifier: str, ttl_seconds: int) -> SessionData:
    """Store OAuth state + PKCE verifier in an existing session."""
    current = cast("SessionData | None", await backend.read(session_id))
    if current is None:
        msg = f"cannot set OAuth handshake: session {session_id} not found"
        raise KeyError(msg)

    updated = current.with_oauth_handshake(state=state, code_verifier=code_verifier, ttl_seconds=ttl_seconds)
    await backend.update(session_id, updated)
    return updated


async def consume_oauth_handshake_from_session(*, session_id: UUID, state: str) -> OAuthStateRecord | None:
    """Validate + consume OAuth handshake from session."""
    current = cast("SessionData | None", await backend.read(session_id))
    if current is None:
        return None

    record = current.get_oauth_handshake(state=state)
    await backend.update(session_id, current.clear_oauth_handshake())
    return record


async def set_oauth_tokens_in_session(
    *,
    session_id: UUID,
    access_token: str,
    expires_at: datetime,
    refresh_token: str | None = None,
) -> SessionData:
    """Store OAuth tokens in an existing session."""
    current = cast("SessionData | None", await backend.read(session_id))
    if current is None:
        msg = f"cannot set OAuth tokens: session {session_id} not found"
        raise KeyError(msg)

    updated = current.with_oauth_tokens(access_token=access_token, expires_at=expires_at, refresh_token=refresh_token)
    await backend.update(session_id, updated)
    return updated


async def get_oauth_tokens_from_session(*, session_id: UUID) -> OAuthTokenRecord | None:
    """Read non-expired OAuth tokens from a session."""
    current = cast("SessionData | None", await backend.read(session_id))
    if current is None:
        return None
    return current.get_oauth_tokens()


async def clear_oauth_tokens_in_session(*, session_id: UUID) -> SessionData | None:
    """Clear OAuth token fields from a session."""
    current = cast("SessionData | None", await backend.read(session_id))
    if current is None:
        return None

    updated = current.clear_oauth_tokens()
    await backend.update(session_id, updated)
    return updated
