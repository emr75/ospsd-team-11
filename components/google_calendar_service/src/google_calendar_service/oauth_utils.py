"""Utilities for handling Google OAuth flows, including PKCE generation and token exchange."""

import base64
import hashlib
import json
import secrets
import urllib
from datetime import UTC, datetime, timedelta

import httpx
from fastapi import HTTPException, status

from google_calendar_service.settings import settings


def generate_oauth_state(num_bytes: int = 32) -> str:
    """Generate a cryptographically random OAuth state token."""
    return secrets.token_urlsafe(num_bytes)


def generate_pkce_pair(verifier_bytes: int = 64) -> tuple[str, str]:
    """Generate PKCE `(code_verifier, code_challenge)` pair using S256."""
    code_verifier = secrets.token_urlsafe(verifier_bytes)
    digest = hashlib.sha256(code_verifier.encode("utf-8")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")
    return code_verifier, code_challenge


def build_google_authorization_url(*, state: str, code_challenge: str) -> str:
    """Build Google OAuth authorization URL."""
    try:
        client_id = settings.oauth.require_client_id()
        redirect_uri = settings.oauth.require_redirect_uri()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": settings.oauth.scopes,
        "state": state,
        "access_type": "offline",
        "include_granted_scopes": "true",
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "prompt": settings.oauth.prompt,
    }
    return f"{settings.oauth.auth_url}?{urllib.parse.urlencode(params)}"


async def exchange_code_for_tokens(*, code: str, code_verifier: str) -> tuple[str, str | None, datetime]:
    """Exchange auth code for OAuth tokens with Google."""
    try:
        client_id, client_secret, redirect_uri = settings.oauth.require_web_credentials()
        token_url = settings.oauth.token_url
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    form_data = {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
        "code_verifier": code_verifier,
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                token_url,
                data=form_data,
                timeout=settings.oauth.token_request_timeout_seconds,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not reach token endpoint: {exc}",
        ) from exc

    if response.is_error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Token exchange failed with provider: {response.text}",
        )

    try:
        payload = response.json()
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Provider returned a non-JSON token response",
        ) from exc

    access_token = payload.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Provider token response missing access_token",
        )

    refresh_token = payload.get("refresh_token")
    refresh_token_value = refresh_token if isinstance(refresh_token, str) and refresh_token else None

    raw_expires_in = payload.get("expires_in", 3600)
    try:
        expires_in = int(raw_expires_in)
    except (TypeError, ValueError):
        expires_in = 3600

    expires_at = datetime.now(UTC) + timedelta(seconds=max(expires_in, 1))
    return access_token, refresh_token_value, expires_at
