"""Integration tests using interface-first consumer style via DI."""

from __future__ import annotations

import importlib
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, Mock, patch

import google_calendar_client_impl
import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator
from calendar_client_api import CalendarClient, EventCreate, EventUpdate, get_client, register_client
from calendar_client_api.registry import _ClientRegistry
from google_calendar_client_impl import GoogleCalendarClient


class _Executable:
    """Small helper that mimics Google API `.execute()` chains."""

    def __init__(self, payload: dict[str, object] | None) -> None:
        self._payload = payload

    def execute(self) -> dict[str, object] | None:
        """Return the configured payload."""
        return self._payload


@pytest.fixture(autouse=True)
def _clean_registry() -> Iterator[None]:
    """Reset DI registry state before and after each test."""
    _ClientRegistry.clear()
    yield
    _ClientRegistry.clear()


@pytest.mark.integration
def test_interface_consumer_flow_works_with_di_injected_impl() -> None:
    """A consumer using only CalendarClient works with an injected implementation."""
    now = datetime(2026, 7, 1, 10, 0, tzinfo=UTC)
    end = now + timedelta(hours=1)

    created_payload: dict[str, object] = {
        "id": "evt_001",
        "summary": "Interface-first created",
        "start": {"dateTime": "2026-07-01T10:00:00+00:00"},
        "end": {"dateTime": "2026-07-01T11:00:00+00:00"},
        "description": "created in integration test",
        "location": "Room A",
        "status": "confirmed",
    }
    updated_payload: dict[str, object] = {
        "id": "evt_001",
        "summary": "Interface-first updated",
        "start": {"dateTime": "2026-07-01T10:00:00+00:00"},
        "end": {"dateTime": "2026-07-01T11:00:00+00:00"},
        "description": "updated description",
        "location": "Room B",
        "status": "confirmed",
    }

    service = MagicMock()
    events_resource = service.events.return_value

    events_resource.insert.return_value = _Executable(created_payload)
    events_resource.get.return_value = _Executable(created_payload)
    events_resource.list.return_value = _Executable({"items": [created_payload]})
    events_resource.patch.return_value = _Executable(updated_payload)
    events_resource.delete.return_value = _Executable(None)

    # DI registration with concrete impl; consumer still resolves abstract interface.
    register_client(lambda: GoogleCalendarClient(service=service))

    client = get_client()
    assert isinstance(client, CalendarClient)

    created = client.create_event(
        EventCreate(
            title="Interface-first created",
            start_time=now,
            end_time=end,
            description="created in integration test",
            location="Room A",
            attendees=[],
            attachments=[],
        )
    )
    assert created.id == "evt_001"
    assert created.title == "Interface-first created"

    fetched = client.get_event(created.id)
    assert fetched.id == created.id
    assert fetched.title == created.title

    listed = list(client.list_events_between(now - timedelta(minutes=5), end + timedelta(minutes=5)))
    assert any(event.id == created.id for event in listed)

    updated = client.update_event(
        created.id,
        EventUpdate(title="Interface-first updated", description="updated description", location="Room B"),
    )
    assert updated.id == created.id
    assert updated.title == "Interface-first updated"
    assert updated.description == "updated description"
    assert updated.location == "Room B"

    client.delete_event(created.id)
    events_resource.delete.assert_called_once_with(calendarId="primary", eventId=created.id)


@pytest.mark.integration
@patch("google_calendar_client_impl.client_impl.build", return_value=Mock())
@patch(
    "google_calendar_client_impl.client_impl.GoogleCalendarClient._auth_from_env",
    return_value=Mock(valid=True, refresh_token=None),
)
def test_import_side_effect_registers_client_for_interface_consumers(*_: Mock) -> None:
    """Importing implementation package auto-registers a DI factory used by interface consumers."""
    assert _ClientRegistry._factory is None

    importlib.reload(google_calendar_client_impl)
    client = get_client()

    assert isinstance(client, CalendarClient)
