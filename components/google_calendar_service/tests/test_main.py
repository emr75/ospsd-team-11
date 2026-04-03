# ruff: noqa: D101, D102, D103, D107
"""Tests for the Google Calendar FastAPI service."""

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from calendar_client_api.event import Attendee, Event, EventCreate, EventUpdate
from fastapi.testclient import TestClient
from google_calendar_service.main import app
from google_calendar_service.routes import event_routes

HTTP_OK = 200
DEFAULT_MAX_RESULTS = 10

client = TestClient(app)


@pytest.fixture(autouse=True)
def override_get_client_dependency() -> Iterator[None]:
    """Override the events router _get_client dependency with a fake client."""
    app.dependency_overrides[event_routes._get_client] = fake_get_client
    yield
    app.dependency_overrides.pop(event_routes._get_client, None)


@dataclass(frozen=True)
class FakeEventData:
    """Concrete event data used to back a fake Event implementation."""

    event_id: str
    title: str
    start_time: datetime
    end_time: datetime
    description: str | None = None
    location: str | None = None
    attendees: list[Attendee] | None = None
    attachments: list[str] | None = None


class FakeEvent(Event):
    """Fake event used for service tests."""

    def __init__(self, data: FakeEventData) -> None:
        self._data = data

    @property
    def id(self) -> str:
        return self._data.event_id

    @property
    def title(self) -> str:
        return self._data.title

    @property
    def start_time(self) -> datetime:
        return self._data.start_time

    @property
    def end_time(self) -> datetime:
        return self._data.end_time

    @property
    def description(self) -> str | None:
        return self._data.description

    @property
    def location(self) -> str | None:
        return self._data.location

    @property
    def attendees(self) -> list[Attendee]:
        return self._data.attendees or []

    @property
    def attachments(self) -> list[str]:
        return self._data.attachments or []


class FakeCalendarClient:
    """Fake calendar client used for service tests."""

    def list_events(self, max_results: int = DEFAULT_MAX_RESULTS) -> Iterable[Event]:
        assert max_results == DEFAULT_MAX_RESULTS
        return [
            FakeEvent(
                FakeEventData(
                    event_id="test_123",
                    title="Networking Event",
                    start_time=datetime(2026, 3, 18, 10, 0, tzinfo=UTC),
                    end_time=datetime(2026, 3, 18, 11, 0, tzinfo=UTC),
                    description="NYU event",
                    location="2 MetroTech",
                    attendees=[Attendee(email="test@example.com", name="Joe")],
                    attachments=["https://example.com/doc"],
                )
            ),
        ]

    def get_event(self, event_id: str) -> Event:
        assert event_id == "test_123"
        return FakeEvent(
            FakeEventData(
                event_id="test_123",
                title="Networking Event",
                start_time=datetime(2026, 3, 18, 10, 0, tzinfo=UTC),
                end_time=datetime(2026, 3, 18, 11, 0, tzinfo=UTC),
                description="NYU event",
                location="2 MetroTech",
                attendees=[Attendee(email="test@example.com", name="Joe")],
                attachments=["https://example.com/doc"],
            )
        )

    def create_event(self, event_create: EventCreate) -> Event:
        assert event_create.title == "Java Exam"
        assert event_create.description == "Java Midterm"
        assert event_create.location == "2 MetroTech"
        assert len(event_create.attendees) == 1
        assert event_create.attendees[0] == Attendee(email="designer@example.com", name="Designer")
        assert event_create.attachments == ["https://example.com/spec"]

        return FakeEvent(
            FakeEventData(
                event_id="evt_created",
                title=event_create.title,
                start_time=event_create.start_time,
                end_time=event_create.end_time,
                description=event_create.description,
                location=event_create.location,
                attendees=event_create.attendees,
                attachments=event_create.attachments,
            )
        )

    def update_event(self, event_id: str, event_update: EventUpdate) -> Event:
        assert event_id == "test_123"
        assert event_update.title == "Updated Java Midterm"
        assert event_update.location == "New 2 MetroTech Room"

        return FakeEvent(
            FakeEventData(
                event_id="test_123",
                title="Updated Java Midterm",
                start_time=datetime(2026, 3, 18, 10, 0, tzinfo=UTC),
                end_time=datetime(2026, 3, 18, 11, 0, tzinfo=UTC),
                description=None,
                location="2 MetroTech Room",
                attendees=[Attendee(email="test@example.com", name="Joe")],
                attachments=["https://example.com/doc"],
            )
        )

    def delete_event(self, event_id: str) -> None:
        assert event_id == "test_123"


def fake_get_client() -> FakeCalendarClient:
    return FakeCalendarClient()


class TestHealthEndpoint:
    def test_returns_ok_status(self) -> None:
        response = client.get("/health")

        assert response.status_code == HTTP_OK
        assert response.json() == {"status": "ok"}


class TestListEventsEndpoint:
    def test_returns_serialized_events(self) -> None:
        response = client.get("/events/")

        assert response.status_code == HTTP_OK
        assert response.json() == {
            "events": [
                {
                    "id": "test_123",
                    "title": "Networking Event",
                    "start_time": "2026-03-18T10:00:00Z",
                    "end_time": "2026-03-18T11:00:00Z",
                    "description": "NYU event",
                    "location": "2 MetroTech",
                    "attendees": [
                        {
                            "email": "test@example.com",
                            "name": "Joe",
                        },
                    ],
                    "attachments": ["https://example.com/doc"],
                },
            ],
        }


class TestGetEventEndpoint:
    def test_returns_serialized_event(self) -> None:
        response = client.get("/events/test_123")

        assert response.status_code == HTTP_OK
        assert response.json() == {
            "event": {
                "id": "test_123",
                "title": "Networking Event",
                "start_time": "2026-03-18T10:00:00Z",
                "end_time": "2026-03-18T11:00:00Z",
                "description": "NYU event",
                "location": "2 MetroTech",
                "attendees": [
                    {
                        "email": "test@example.com",
                        "name": "Joe",
                    },
                ],
                "attachments": ["https://example.com/doc"],
            },
        }


class TestCreateEventEndpoint:
    def test_creates_and_returns_serialized_event(self) -> None:
        response = client.post(
            "/events/",
            json={
                "title": "Java Exam",
                "start_time": "2026-03-20T14:00:00+00:00",
                "end_time": "2026-03-20T15:00:00+00:00",
                "attendees": [
                    {
                        "email": "designer@example.com",
                        "name": "Designer",
                    },
                ],
                "attachments": ["https://example.com/spec"],
                "description": "Java Midterm",
                "location": "2 MetroTech",
            },
        )

        assert response.status_code == HTTP_OK
        assert response.json() == {
            "event": {
                "id": "evt_created",
                "title": "Java Exam",
                "start_time": "2026-03-20T14:00:00Z",
                "end_time": "2026-03-20T15:00:00Z",
                "description": "Java Midterm",
                "location": "2 MetroTech",
                "attendees": [
                    {
                        "email": "designer@example.com",
                        "name": "Designer",
                    },
                ],
                "attachments": ["https://example.com/spec"],
            },
        }


class TestUpdateEventEndpoint:
    def test_updates_and_returns_serialized_event(self) -> None:
        response = client.patch(
            "/events/test_123",
            json={
                "title": "Updated Java Midterm",
                "location": "New 2 MetroTech Room",
            },
        )

        assert response.status_code == HTTP_OK
        assert response.json() == {
            "event": {
                "id": "test_123",
                "title": "Updated Java Midterm",
                "start_time": "2026-03-18T10:00:00Z",
                "end_time": "2026-03-18T11:00:00Z",
                "description": None,
                "location": "2 MetroTech Room",
                "attendees": [
                    {
                        "email": "test@example.com",
                        "name": "Joe",
                    },
                ],
                "attachments": ["https://example.com/doc"],
            },
        }


class TestDeleteEventEndpoint:
    def test_deletes_event(self) -> None:
        response = client.delete("/events/test_123")

        assert response.status_code == HTTP_OK
        assert response.json() == {"status": "deleted"}
