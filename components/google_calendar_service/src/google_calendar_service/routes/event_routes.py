"""Routes for managing Google Calendar events."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from google_calendar_client_impl import CredentialsToken, GoogleCalendarClient, get_calendar_client_with_credentials

from google_calendar_service.models import (
    EventCreateRequest,
    EventEnvelope,
    EventsEnvelope,
    EventUpdateRequest,
    StatusResponse,
    to_event_response,
)
from google_calendar_service.session_store import (
    SessionData,
    cookie,
    verifier,
)
from google_calendar_service.settings import settings


def _get_client(
    _session_id: Annotated[UUID, Depends(cookie)],
    session_data: Annotated[SessionData, Depends(verifier)],
) -> GoogleCalendarClient:
    """Get a GoogleCalendarClient instance with tokens from the current session."""
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


router = APIRouter(prefix="/events", tags=["events"])


@router.get("/")
def list_events(
    client: Annotated[GoogleCalendarClient, Depends(_get_client)], max_results: Annotated[int, Query(ge=1)] = 10
) -> EventsEnvelope:
    """List calendar events."""
    events = client.list_events(max_results=max_results)
    return EventsEnvelope(events=[to_event_response(event) for event in events])


@router.get("/{event_id}")
def get_event(client: Annotated[GoogleCalendarClient, Depends(_get_client)], event_id: str) -> EventEnvelope:
    """Get a single calendar event by ID."""
    event = client.get_event(event_id)
    return EventEnvelope(event=to_event_response(event))


@router.post("/")
def create_event(client: Annotated[GoogleCalendarClient, Depends(_get_client)], event: EventCreateRequest) -> EventEnvelope:
    """Create a calendar event."""
    created_event = client.create_event(event.to_event_create())
    return EventEnvelope(event=to_event_response(created_event))


@router.patch("/{event_id}")
def update_event(
    client: Annotated[GoogleCalendarClient, Depends(_get_client)], event_id: str, event: EventUpdateRequest
) -> EventEnvelope:
    """Update a calendar event."""
    updated_event = client.update_event(event_id, event.to_event_update())
    return EventEnvelope(event=to_event_response(updated_event))


@router.delete("/{event_id}")
def delete_event(client: Annotated[GoogleCalendarClient, Depends(_get_client)], event_id: str) -> StatusResponse:
    """Delete a calendar event."""
    client.delete_event(event_id)
    return StatusResponse(status="deleted")
