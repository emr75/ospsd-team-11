"""E2E tests for the direct implementation using interface-only consumer code via DI.

This suite models real user behavior at the highest abstraction level:
- consumer depends only on `calendar_client_api.CalendarClient`
- implementation is injected through DI
- consumer flow uses only the interface methods
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock

import pytest
from calendar_client_api import CalendarClient, EventCreate, EventUpdate, get_client, register_client
from calendar_client_api.registry import _ClientRegistry
from google_calendar_client_impl import GoogleCalendarClient

if TYPE_CHECKING:
    from collections.abc import Iterator

pytestmark = [pytest.mark.e2e, pytest.mark.circleci]

_NOW = datetime(2026, 8, 1, 10, 0, tzinfo=UTC)
_END = _NOW + timedelta(hours=1)


class _Executable:
    """Helper that mimics Google API objects exposing `.execute()`."""

    def __init__(self, payload: dict[str, object] | None) -> None:
        self._payload = payload

    def execute(self) -> dict[str, object] | None:
        """Return configured payload."""
        return self._payload


@pytest.fixture(autouse=True)
def _reset_registry() -> Iterator[None]:
    """Ensure DI registry does not leak state across tests."""
    _ClientRegistry.clear()
    yield
    _ClientRegistry.clear()


def _build_mock_google_service() -> MagicMock:  # noqa: C901
    """Create an in-memory fake Google Calendar service resource."""
    service = MagicMock()
    events_resource = MagicMock()
    service.events.return_value = events_resource

    store: dict[str, dict[str, object]] = {}
    counter = {"value": 0}

    def insert(**kwargs: object) -> _Executable:
        body = cast("dict[str, object]", kwargs["body"])
        counter["value"] += 1
        event_id = f"e2e_direct_{counter['value']:03d}"

        summary = cast("str", body["summary"])
        start_data = cast("dict[str, str]", body["start"])
        end_data = cast("dict[str, str]", body["end"])

        payload: dict[str, object] = {
            "id": event_id,
            "summary": summary,
            "start": {"dateTime": start_data["dateTime"]},
            "end": {"dateTime": end_data["dateTime"]},
            "status": "confirmed",
        }

        description = body.get("description")
        location = body.get("location")
        if isinstance(description, str):
            payload["description"] = description
        if isinstance(location, str):
            payload["location"] = location

        store[event_id] = payload
        return _Executable(payload)

    def get(**kwargs: object) -> _Executable:
        event_id = cast("str", kwargs["eventId"])
        return _Executable(store[event_id])

    def list_(**kwargs: object) -> _Executable:
        del kwargs
        return _Executable({"kind": "calendar#events", "items": list(store.values())})

    def patch(**kwargs: object) -> _Executable:
        event_id = cast("str", kwargs["eventId"])
        body = cast("dict[str, object]", kwargs["body"])

        current = store[event_id].copy()
        if "summary" in body:
            current["summary"] = cast("str", body["summary"])
        if "description" in body:
            current["description"] = cast("str | None", body["description"])
        if "location" in body:
            current["location"] = cast("str | None", body["location"])
        store[event_id] = current
        return _Executable(current)

    def delete(**kwargs: object) -> _Executable:
        event_id = cast("str", kwargs["eventId"])
        store.pop(event_id, None)
        return _Executable(None)

    events_resource.insert.side_effect = insert
    events_resource.get.side_effect = get
    events_resource.list.side_effect = list_
    events_resource.patch.side_effect = patch
    events_resource.delete.side_effect = delete

    return service


def _consumer_flow(client: CalendarClient) -> None:
    """Consumer workflow that uses only the CalendarClient interface."""
    created = client.create_event(
        EventCreate(
            title="[e2e-direct] created",
            start_time=_NOW,
            end_time=_END,
            description="Created in e2e direct flow",
            location="Room A",
            attendees=[],
            attachments=[],
        )
    )
    assert created.id
    assert created.title == "[e2e-direct] created"

    fetched = client.get_event(created.id)
    assert fetched.id == created.id
    assert fetched.title == created.title

    events = list(client.list_events_between(_NOW - timedelta(minutes=5), _END + timedelta(minutes=5)))
    assert any(event.id == created.id for event in events)

    updated = client.update_event(
        created.id,
        EventUpdate(
            title="[e2e-direct] updated",
            description="Updated in e2e direct flow",
            location="Room B",
        ),
    )
    assert updated.id == created.id
    assert updated.title == "[e2e-direct] updated"
    assert updated.description == "Updated in e2e direct flow"
    assert updated.location == "Room B"

    client.delete_event(created.id)
    events_after_delete = list(client.list_events_between(_NOW - timedelta(minutes=5), _END + timedelta(minutes=5)))
    assert all(event.id != created.id for event in events_after_delete)


def test_interface_consumer_flow_with_di_injected_google_impl() -> None:
    """Same user-facing consumer code works with DI-injected direct implementation."""
    mock_service = _build_mock_google_service()

    # Inject concrete implementation via DI registry.
    register_client(lambda: GoogleCalendarClient(service=mock_service))

    # User code resolves only the abstract interface.
    client = get_client()
    assert isinstance(client, CalendarClient)

    _consumer_flow(client)
