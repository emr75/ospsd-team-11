"""Authentication routes for Google Calendar Service API, handling OAuth login/logout and callback processing."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID  # noqa: TC003 - required at runtime for FastAPI/Pydantic annotation resolution

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import RedirectResponse
from fastapi_sessions.frontends.session_frontend import FrontendError  # type: ignore[import-untyped]

from google_calendar_service.models import StatusResponse
from google_calendar_service.oauth_utils import (
    build_google_authorization_url,
    exchange_code_for_tokens,
    generate_oauth_state,
    generate_pkce_pair,
)
from google_calendar_service.session_store import (
    clear_oauth_tokens_in_session,
    consume_oauth_handshake_from_session,
    cookie,
    create_session,
    delete_session,
    optional_cookie,
    set_oauth_handshake_in_session,
    set_oauth_tokens_in_session,
)
from google_calendar_service.settings import settings

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/login")
async def login(previous_session_id: Annotated[UUID | FrontendError, Depends(optional_cookie)]) -> RedirectResponse:
    """Start OAuth login flow and redirect to Google consent screen."""
    if not isinstance(previous_session_id, FrontendError):
        await delete_session(session_id=previous_session_id)

    session_id = await create_session()
    state = generate_oauth_state()
    code_verifier, code_challenge = generate_pkce_pair()

    await set_oauth_handshake_in_session(
        session_id=session_id,
        state=state,
        code_verifier=code_verifier,
        ttl_seconds=settings.oauth.state_ttl_seconds,
    )

    authorization_url = build_google_authorization_url(state=state, code_challenge=code_challenge)
    response = RedirectResponse(url=authorization_url, status_code=status.HTTP_302_FOUND)
    cookie.attach_to_response(response, session_id)
    return response


@router.post("/logout")
async def logout(session_id: Annotated[UUID | FrontendError, Depends(optional_cookie)], response: Response) -> StatusResponse:
    """Log out by clearing OAuth token/session state and removing session cookie."""
    if not isinstance(session_id, FrontendError):
        await clear_oauth_tokens_in_session(session_id=session_id)
        await delete_session(session_id=session_id)

    cookie.delete_from_response(response)
    return StatusResponse(status="logged out")


@router.get("/callback")
async def callback(
    session_id: Annotated[UUID, Depends(cookie)],
    code: Annotated[str | None, Query()] = None,
    state: Annotated[str | None, Query()] = None,
    error: Annotated[str | None, Query()] = None,
) -> StatusResponse:
    """Handle OAuth callback, validate state, exchange code, and persist session tokens."""
    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OAuth provider returned error: {error}",
        )

    if code is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing authorization code",
        )

    if state is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing OAuth state",
        )

    handshake = await consume_oauth_handshake_from_session(session_id=session_id, state=state)
    if handshake is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OAuth state",
        )

    access_token, refresh_token, expires_at = await exchange_code_for_tokens(code=code, code_verifier=handshake.code_verifier)

    await set_oauth_tokens_in_session(
        session_id=session_id,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=expires_at,
    )

    return StatusResponse(status="authenticated")
