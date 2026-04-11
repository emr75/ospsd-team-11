"""E2E tests for the calendar client.

These tests encode exactly that contract.  The two test functions are
**identical in consumer code** — the only difference is which implementation
was injected via DI, handled entirely by the fixtures below.  The consumer
workflow (``_consumer_flow``) never imports or references any concrete type.

Fixtures
--------
``library_impl_client``
    Registers ``GoogleCalendarClient`` via DI and yields a ``CalendarClient``.
    Calls the real Google Calendar API — requires credentials in the environment.
``service_adapter_client``
    Registers ``ServiceCalendarClient`` via DI and yields a ``CalendarClient``.
    Calls the live deployed service at ``CALENDAR_SERVICE_BASE_URL`` (default: localhost:8000).
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from calendar_client_api import (
    AuthorizationError,
    CalendarClient,
    EventCreate,
    EventUpdate,
    get_client,
    register_client,
)
from calendar_client_api.registry import _ClientRegistry
from google_calendar_service_adapter import register_service_calendar_client

if TYPE_CHECKING:
    from collections.abc import Iterator

pytestmark = [pytest.mark.e2e, pytest.mark.local_credentials]

_NOW = datetime(2026, 8, 1, 10, 0, tzinfo=UTC)
_END = _NOW + timedelta(hours=1)


# ---------------------------------------------------------------------------
# Fixtures for DI wiring.
# Both fixtures yield a ``CalendarClient``; the consumer code below never
# sees the concrete type behind it.
# ---------------------------------------------------------------------------


@pytest.fixture
def library_impl_client() -> Iterator[CalendarClient]:
    """Inject GoogleCalendarClient via DI; credentials resolved from env vars or token.json.

    Calls ``load_env()`` to load ``.env`` into the environment, then registers a
    factory that creates ``GoogleCalendarClient(interactive=True)``.  The client
    resolves credentials in priority order: env vars → ``token.json``.
    """
    from google_calendar_client_impl import GoogleCalendarClient, load_env

    load_env()
    _ClientRegistry.clear()
    register_client(lambda: GoogleCalendarClient(interactive=True))
    yield get_client()
    _ClientRegistry.clear()


@pytest.fixture
def service_adapter_client() -> Iterator[CalendarClient]:
    """Inject ServiceCalendarClient via DI and yield a CalendarClient.

    Reads from the environment (via ``.env``):
      - ``CALENDAR_SERVICE_BASE_URL``  service base URL (default: http://localhost:8000)
      - ``CALENDAR_COOKIE_ID``         session cookie name used by the service
      - ``CALENDAR_COOKIE_VALUE``      session cookie value from a prior OAuth login

    If ``CALENDAR_COOKIE_VALUE`` is not set the test is skipped with a descriptive
    message, avoiding a confusing HTTP 307 redirect failure.
    """
    from google_calendar_client_impl import load_env

    load_env()

    cookie_value = os.environ.get("CALENDAR_COOKIE_VALUE")
    if not cookie_value:
        pytest.skip(
            "CALENDAR_COOKIE_VALUE is not set. "
            "Start the service, log in via OAuth, capture the session cookie value, "
            "and add CALENDAR_COOKIE_VALUE=<value> to your .env file."
        )

    _ClientRegistry.clear()
    register_service_calendar_client()
    client = get_client()

    try:
        list(client.list_upcoming_events(max_results=1))
    except AuthorizationError:
        _ClientRegistry.clear()
        pytest.skip(
            "CALENDAR_COOKIE_VALUE is set but not authorized. "
            "Refresh your OAuth session cookie by logging in again and updating "
            "CALENDAR_COOKIE_VALUE in .env."
        )

    yield client
    _ClientRegistry.clear()


# ---------------------------------------------------------------------------
# Shared consumer workflow. Uses ONLY the abstract CalendarClient interface.
#
# This function is the proof of the Adapter Pattern / location transparency:
# it runs unchanged regardless of which backend is injected.
# ---------------------------------------------------------------------------


def _consumer_flow(client: CalendarClient, *, title_prefix: str) -> None:
    """Exercise the full CRUD lifecycle using only the CalendarClient interface."""
    # Create
    created = client.create_event_from_dto(
        EventCreate(
            title=f"{title_prefix} created",
            start_time=_NOW,
            end_time=_END,
            description="Created in e2e flow",
            location="Room A",
            attendees=[],
            attachments=[],
        )
    )
    assert created.id
    assert title_prefix in created.title

    # Read
    fetched = client.get_event_by_id(created.id)
    assert fetched.id == created.id
    assert fetched.title == created.title

    # List
    window_start = _NOW - timedelta(minutes=5)
    window_end = _END + timedelta(minutes=5)
    events = list(client.list_events_between(window_start, window_end))
    assert any(event.id == created.id for event in events)

    # Update
    updated = client.update_event_from_patch(
        created.id,
        EventUpdate(
            title=f"{title_prefix} updated",
            description="Updated in e2e flow",
            location="Room B",
        ),
    )
    assert updated.id == created.id
    assert updated.title == f"{title_prefix} updated"
    assert updated.description == "Updated in e2e flow"
    assert updated.location == "Room B"

    # Delete
    client.delete_event(created.id)
    events_after_delete = list(client.list_events_between(window_start, window_end))
    assert all(event.id != created.id for event in events_after_delete)


# ---------------------------------------------------------------------------
# Same consumer flow, two different DI-injected backends.
# ---------------------------------------------------------------------------


def test_consumer_flow_with_library_impl(library_impl_client: CalendarClient) -> None:
    """Consumer interface-only flow works when the library implementation is injected via DI."""
    _consumer_flow(library_impl_client, title_prefix="[e2e-library]")


def test_consumer_flow_with_service_adapter(service_adapter_client: CalendarClient) -> None:
    """Identical consumer flow works when the service adapter is injected via DI."""
    _consumer_flow(service_adapter_client, title_prefix="[e2e-service]")
