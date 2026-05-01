"""Module for handling the integration with Google Calendar and OpenAI clients.

This module provides functions to get instances of CalendarClient and AiClient
with necessary configurations and authentication tokens. It utilizes session
data for OAuth token management and ensures that clients are properly authenticated
before use.

Functions:
    - get_calendar_client: Fetches a CalendarClient instance with tokens
      acquired from the current user session.
    - get_ai_client: Returns an AiClient instance configured using OpenAI.

"""

from typing import Annotated
from uuid import UUID

from ai_client_api import AiClient
from calendar_client_api import CalendarClient
from fastapi import Depends, HTTPException
from google_calendar_client_impl import CredentialsToken, get_calendar_client_with_credentials
from openai_ai_client_impl import get_openai_client
from starlette import status

from google_calendar_service.session_store import SessionData, cookie, verifier
from google_calendar_service.settings import settings


def get_calendar_client(
    _session_id: Annotated[UUID, Depends(cookie)],
    session_data: Annotated[SessionData, Depends(verifier)],
) -> CalendarClient:
    """Get a CalendarClient instance with tokens from the current session."""
    tokens = session_data.get_oauth_tokens()
    if tokens is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No valid OAuth tokens found in session",
        )

    creds_token = CredentialsToken(
        client_id=settings.oauth.require_client_id(),
        client_secret=settings.oauth.require_client_secret(),
        token_uri=settings.oauth.token_url,
        scopes=settings.oauth.scopes.split(),
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
    )

    return get_calendar_client_with_credentials(creds_token=creds_token)


def get_ai_client() -> AiClient:
    """Get an AiClient instance configured using OpenAI."""
    return get_openai_client()
