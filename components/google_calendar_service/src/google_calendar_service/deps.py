"""Module for handling the integration with Google Calendar, OpenAI, and issue tracker clients.

This module provides FastAPI dependency providers for CalendarClient, AiClient,
and the shared issue-tracker Client. It utilizes session data for OAuth token
management and ensures that clients are properly authenticated before use.

Functions:
    - get_calendar_client: Fetches a CalendarClient instance with tokens
      acquired from the current user session.
    - get_ai_client: Returns an AiClient instance configured using OpenAI.
    - get_issue_client: Returns an issue-tracker Client backed by Team 3's
      deployed service via their ServiceClientAdapter.

"""

import os
from typing import Annotated
from uuid import UUID

from ai_client_api import AiClient

# The issue-tracker package does not ship a py.typed marker.
from api.client import Client as IssueClient  # type: ignore[import-untyped]
from calendar_client_api import CalendarClient
from fastapi import Depends, HTTPException
from google_calendar_client_impl import CredentialsToken, get_calendar_client_with_credentials
from issue_tracker_client_adapter.adapter import ServiceClientAdapter
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


def get_issue_client() -> IssueClient:
    """Get an issue-tracker Client backed by Team 3's deployed service."""
    base_url = os.environ.get("ISSUE_TRACKER_SERVICE_URL", "")
    session_id = os.environ.get("ISSUE_TRACKER_SESSION_ID")
    return ServiceClientAdapter(base_url=base_url, session_id=session_id)
