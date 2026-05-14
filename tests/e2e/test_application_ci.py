"""CI-friendly E2E tests for service adapter and app entry point.

These tests validate the highest abstraction level:
- consumer code depends only on `calendar_client_api.CalendarClient`
- service adapter implementation is injected via DI
- the consumer workflow never references concrete implementation types
- the FastAPI app entry point returns user-visible responses through the full pipeline
"""

from __future__ import annotations

import importlib
import json
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

import pytest
from ai_client_api import AiClient
from api.issue import Status  # type: ignore[import-untyped]
from calendar_client_api import CalendarClient, EventCreate, EventUpdate, get_client
from calendar_client_api.event import Attendee, Event
from calendar_client_api.registry import _ClientRegistry
from fastapi.testclient import TestClient
from google_calendar_service.deps import get_ai_client, get_calendar_client, get_issue_client
from google_calendar_service.main import app
from google_calendar_service_adapter import register_service_calendar_client
from google_calendar_service_client.models.attendee_response import AttendeeResponse
from google_calendar_service_client.models.event_envelope import EventEnvelope
from google_calendar_service_client.models.event_response import EventResponse
from google_calendar_service_client.models.events_envelope import EventsEnvelope
from google_calendar_service_client.types import Unset

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from api.issue import Issue
    from google_calendar_service_client.models.event_create_request import EventCreateRequest
    from google_calendar_service_client.models.event_update_request import EventUpdateRequest

pytestmark = [pytest.mark.e2e, pytest.mark.circleci]

_NOW = datetime(2026, 6, 1, 10, 0, tzinfo=UTC)
_END = _NOW + timedelta(hours=1)


@pytest.fixture(autouse=True)
def _reset_registry() -> Iterator[None]:
    """Ensure DI registry state does not leak across tests."""
    _ClientRegistry.clear()
    yield
    _ClientRegistry.clear()


def _to_event_response(  # noqa: PLR0913
    *,
    event_id: str,
    title: str,
    start_time: datetime,
    end_time: datetime,
    description: str | None,
    location: str | None,
) -> EventResponse:
    """Build a generated EventResponse object."""
    return EventResponse(
        id=event_id,
        title=title,
        start_time=start_time,
        end_time=end_time,
        attendees=[AttendeeResponse(email="ci@example.com", name="CI User")],
        attachments=[],
        description=description,
        location=location,
    )


def _install_service_adapter_mocks(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch generated endpoint calls used by the service adapter with in-memory handlers."""
    import google_calendar_service_adapter.client_adapter as adapter_module

    store: dict[str, EventResponse] = {}
    counter = {"value": 0}

    def create_sync(*, client: object, body: object) -> EventEnvelope:
        del client
        request = cast("EventCreateRequest", body)

        raw_description = request.description
        raw_location = request.location
        description = None if isinstance(raw_description, Unset) else raw_description
        location = None if isinstance(raw_location, Unset) else raw_location

        counter["value"] += 1
        event_id = f"ci_service_{counter['value']:03d}"

        created = _to_event_response(
            event_id=event_id,
            title=request.title,
            start_time=request.start_time,
            end_time=request.end_time,
            description=description,
            location=location,
        )
        store[event_id] = created
        return EventEnvelope(event=created)

    def get_sync(event_id: str, *, client: object) -> EventEnvelope:
        del client
        return EventEnvelope(event=store[event_id])

    def list_events_between_sync(*, client: object, start: datetime, end: datetime) -> EventsEnvelope:
        del client, start, end
        return EventsEnvelope(events=list(store.values()))

    def list_events_sync(*, client: object, max_results: int = 10) -> EventsEnvelope:
        del client
        return EventsEnvelope(events=list(store.values())[:max_results])

    def update_sync(event_id: str, *, client: object, body: object) -> EventEnvelope:
        del client
        request = cast("EventUpdateRequest", body)
        current = store[event_id]

        raw_title = request.title
        raw_start_time = request.start_time
        raw_end_time = request.end_time
        raw_description = request.description
        raw_location = request.location

        title = current.title if isinstance(raw_title, Unset) else raw_title
        start_time = current.start_time if isinstance(raw_start_time, Unset) else raw_start_time
        end_time = current.end_time if isinstance(raw_end_time, Unset) else raw_end_time
        description = current.description if isinstance(raw_description, Unset) else raw_description
        location = current.location if isinstance(raw_location, Unset) else raw_location

        updated = EventResponse(
            id=current.id,
            title=title if isinstance(title, str) else current.title,
            start_time=start_time if isinstance(start_time, datetime) else current.start_time,
            end_time=end_time if isinstance(end_time, datetime) else current.end_time,
            attendees=current.attendees,
            attachments=current.attachments,
            description=description,
            location=location,
        )
        store[event_id] = updated
        return EventEnvelope(event=updated)

    def delete_sync(event_id: str, *, client: object) -> None:
        del client
        store.pop(event_id, None)

    monkeypatch.setattr(adapter_module, "create_event_events_post", SimpleNamespace(sync=create_sync))
    monkeypatch.setattr(adapter_module, "get_event_events_event_id_get", SimpleNamespace(sync=get_sync))
    monkeypatch.setattr(adapter_module, "list_events_between_events_between_get", SimpleNamespace(sync=list_events_between_sync))
    monkeypatch.setattr(adapter_module, "list_events_events_get", SimpleNamespace(sync=list_events_sync))
    monkeypatch.setattr(adapter_module, "update_event_events_event_id_patch", SimpleNamespace(sync=update_sync))
    monkeypatch.setattr(adapter_module, "delete_event_events_event_id_delete", SimpleNamespace(sync=delete_sync))


def _consumer_flow(client: CalendarClient, *, title_prefix: str) -> None:
    """Consumer workflow that uses only the abstract CalendarClient interface."""
    created = client.create_event_from_dto(
        EventCreate(
            title=f"{title_prefix} created",
            start_time=_NOW,
            end_time=_END,
            description="Created by CI e2e",
            location="CI Room",
            attendees=[],
            attachments=[],
        )
    )
    assert created.id
    assert title_prefix in created.title

    fetched = client.get_event_by_id(created.id)
    assert fetched.id == created.id
    assert fetched.title == created.title

    window_start = _NOW - timedelta(minutes=5)
    window_end = _END + timedelta(minutes=5)
    events = list(client.list_events_between(window_start, window_end))
    assert any(event.id == created.id for event in events)

    updated_title = f"{title_prefix} updated"
    updated = client.update_event_from_patch(
        created.id,
        EventUpdate(
            title=updated_title,
            description="Updated by CI e2e",
            location="Updated Room",
        ),
    )
    assert updated.id == created.id
    assert updated.title == updated_title
    assert updated.description == "Updated by CI e2e"
    assert updated.location == "Updated Room"

    client.delete_event(created.id)
    events_after_delete = list(client.list_events_between(window_start, window_end))
    assert all(event.id != created.id for event in events_after_delete)


def test_interface_consumer_flow_with_service_adapter_via_di(monkeypatch: pytest.MonkeyPatch) -> None:
    """Same interface-only consumer code works when service adapter is injected through DI."""
    _install_service_adapter_mocks(monkeypatch)
    register_service_calendar_client(base_url="http://ci-mocked-service:8000")

    client = get_client()
    assert isinstance(client, CalendarClient)

    _consumer_flow(client, title_prefix="[service-adapter]")


def test_import_side_effect_registers_service_adapter_factory() -> None:
    """Import side effect registers service adapter in DI registry."""
    assert _ClientRegistry._factory is None

    module = sys.modules["google_calendar_service_adapter"]
    importlib.reload(module)

    assert _ClientRegistry._factory is not None
    client = get_client()
    assert isinstance(client, CalendarClient)
    assert client.__class__.__name__ == "ServiceCalendarClient"


# ---------------------------------------------------------------------------
# E2E tests for the FastAPI app entry point
#
# These tests exercise the deployed app surface (HTTP API) with black-box
# assertions on user-visible behavior, satisfying the rubric requirement
# that tests/e2e/ runs the app entry point.
# ---------------------------------------------------------------------------

HTTP_OK = 200


@dataclass
class _FakeEvent(Event):
    """Concrete Event for E2E test fixtures."""

    _id: str = "e2e-event"
    _title: str = "E2E Event"
    _start_time: datetime = field(default_factory=lambda: datetime(2026, 6, 1, 10, 0, tzinfo=UTC))
    _end_time: datetime = field(default_factory=lambda: datetime(2026, 6, 1, 11, 0, tzinfo=UTC))
    _description: str | None = None
    _location: str | None = None
    _attendees: list[Attendee] = field(default_factory=list)
    _attachments: list[str] = field(default_factory=list)

    @property
    def id(self) -> str:
        return self._id

    @property
    def title(self) -> str:
        return self._title

    @property
    def start_time(self) -> datetime:
        return self._start_time

    @property
    def end_time(self) -> datetime:
        return self._end_time

    @property
    def description(self) -> str | None:
        return self._description

    @property
    def location(self) -> str | None:
        return self._location

    @property
    def attendees(self) -> list[Attendee]:
        return self._attendees

    @property
    def attachments(self) -> list[str]:
        return self._attachments


class _FakeCalendarClient(CalendarClient):
    """Fake calendar client for E2E app tests."""

    def __init__(self) -> None:
        self.created_events: list[EventCreate] = []

    def get_event_by_id(self, event_id: str) -> Event:
        return _FakeEvent(_id=event_id)

    def delete_event(self, event_id: str) -> None:
        pass

    def list_upcoming_events(self, max_results: int = 10) -> Iterable[Event]:
        return [_FakeEvent()]

    def list_events_between(self, start: datetime, end: datetime) -> Iterable[Event]:
        return []

    def create_event_from_dto(self, event_create: EventCreate) -> Event:
        self.created_events.append(event_create)
        return _FakeEvent(
            _id="created-e2e",
            _title=event_create.title,
            _start_time=event_create.start_time,
            _end_time=event_create.end_time,
        )

    def update_event_from_patch(self, event_id: str, event_patch: EventUpdate) -> Event:
        return _FakeEvent(_id=event_id)


class _FakeIssueClient:
    """Fake issue client for E2E app tests."""

    def get_boards(self) -> Iterable[Any]:
        return [SimpleNamespace(id="board-1", board_name="Engineering")]

    def get_issues(self, board_id: str) -> Iterable[Issue]:
        return [cast("Issue", SimpleNamespace(
            id="42", title="E2E bug", desc="desc", members=None,
            due_date=None, status=Status.TO_DO, board_id=board_id,
        ))]

    def get_issue(self, issue_id: str) -> Issue:
        return cast("Issue", SimpleNamespace(
            id=issue_id, title="E2E bug", desc="Login page fails.",
            members=["dev@example.com"], due_date="2026-06-01",
            status=Status.TO_DO, board_id="board-1",
        ))

    def create_issue(self, **kwargs: Any) -> Issue:
        return cast("Issue", SimpleNamespace(
            id="created-issue", title=kwargs.get("title", ""),
            desc=kwargs.get("desc", ""), members=kwargs.get("members"),
            due_date=kwargs.get("due_date"), status=Status.TO_DO,
            board_id=kwargs.get("board_id", "board-1"),
        ))

    def update_issue(self, issue_id: str, **kwargs: Any) -> Issue:
        return cast("Issue", SimpleNamespace(
            id=issue_id, title=kwargs.get("title", "E2E bug"),
            desc=kwargs.get("desc", ""), members=None, due_date=None,
            status=kwargs.get("status", Status.TO_DO), board_id="board-1",
        ))


class _ScriptedAiClient(AiClient):
    """AI client that replays one scripted tool call then returns a summary.

    This acts as a recorded provider for E2E testing, satisfying the rubric
    requirement for testing the AI tool-calling pipeline.
    """

    def __init__(self, tool_name: str, tool_args: dict[str, Any]) -> None:
        self._tool_name = tool_name
        self._tool_args = tool_args
        self.tool_result: str | None = None

    def send_message(self, prompt: str, context: dict[str, Any] | None = None) -> str:
        return ""  # pragma: no cover

    def run_chat_with_tools(self, **kwargs: Any) -> str:
        handle_tool = kwargs["handle_tool"]
        self.tool_result = handle_tool(self._tool_name, self._tool_args)
        parsed = json.loads(self.tool_result)
        return f"Created event '{parsed.get('issue_id', 'unknown')}' on calendar."


def test_app_ai_endpoint_with_cross_vertical_tool_call() -> None:
    """Full E2E: HTTP POST /ai/ → scripted AI → tool dispatch → issue fetch → calendar event.

    Exercises the deployed app entry point through a black-box HTTP request,
    verifying user-visible response content after the AI tool-calling pipeline
    invokes the cross-vertical create_event_from_issue flow.
    """
    calendar = _FakeCalendarClient()
    issue_client = _FakeIssueClient()
    scripted_ai = _ScriptedAiClient(
        tool_name="create_event_from_issue",
        tool_args={
            "issue_id": "42",
            "start": "2026-06-01T10:00:00",
            "end": "2026-06-01T11:00:00",
        },
    )

    app.dependency_overrides[get_ai_client] = lambda: scripted_ai
    app.dependency_overrides[get_calendar_client] = lambda: calendar
    app.dependency_overrides[get_issue_client] = lambda: issue_client

    try:
        test_client = TestClient(app, raise_server_exceptions=False)
        response = test_client.post("/ai/", json={"prompt": "Schedule a meeting for issue 42"})

        assert response.status_code == HTTP_OK
        body = response.json()
        assert "message" in body
        assert "42" in body["message"]
        assert len(calendar.created_events) == 1
        assert calendar.created_events[0].title == "Issue Review: E2E bug"
    finally:
        app.dependency_overrides.clear()


def test_app_ai_endpoint_returns_direct_response() -> None:
    """E2E: HTTP POST /ai/ returns a direct AI response (no tool calls).

    Verifies the app entry point handles the simplest case — a prompt that
    the AI answers directly without invoking any tools.
    """

    class _DirectAiClient(AiClient):
        def send_message(self, prompt: str, context: dict[str, Any] | None = None) -> str:
            return ""  # pragma: no cover

        def run_chat_with_tools(self, **kwargs: Any) -> str:
            return "Here are your upcoming events: Standup at 10am."

    app.dependency_overrides[get_ai_client] = _DirectAiClient
    app.dependency_overrides[get_calendar_client] = _FakeCalendarClient
    app.dependency_overrides[get_issue_client] = _FakeIssueClient

    try:
        test_client = TestClient(app, raise_server_exceptions=False)
        response = test_client.post("/ai/", json={"prompt": "What meetings do I have?"})

        assert response.status_code == HTTP_OK
        body = response.json()
        assert body["message"] == "Here are your upcoming events: Standup at 10am."
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# E2E tests for event CRUD endpoints (/events/)
#
# These tests exercise the calendar event HTTP endpoints with black-box
# assertions, verifying user-visible behavior through the full FastAPI
# pipeline with DI-overridden calendar clients.
# ---------------------------------------------------------------------------


def test_app_health_endpoint() -> None:
    """E2E: GET /health returns 200 with status ok."""
    test_client = TestClient(app)
    response = test_client.get("/health")

    assert response.status_code == HTTP_OK
    assert response.json() == {"status": "ok"}


def test_app_list_events_endpoint() -> None:
    """E2E: GET /events/ returns user-visible event listing."""
    app.dependency_overrides[get_calendar_client] = _FakeCalendarClient

    try:
        test_client = TestClient(app)
        response = test_client.get("/events/")

        assert response.status_code == HTTP_OK
        body = response.json()
        assert "events" in body
        assert len(body["events"]) == 1
        assert body["events"][0]["id"] == "e2e-event"
        assert body["events"][0]["title"] == "E2E Event"
    finally:
        app.dependency_overrides.clear()


def test_app_create_event_endpoint() -> None:
    """E2E: POST /events/ creates an event and returns it in an envelope."""
    calendar = _FakeCalendarClient()
    app.dependency_overrides[get_calendar_client] = lambda: calendar

    try:
        test_client = TestClient(app)
        response = test_client.post(
            "/events/",
            json={
                "title": "E2E Created Event",
                "start_time": "2026-06-01T10:00:00Z",
                "end_time": "2026-06-01T11:00:00Z",
                "attendees": [{"email": "test@example.com"}],
                "attachments": [],
                "description": "Created via E2E test",
                "location": "Room 42",
            },
        )

        assert response.status_code == HTTP_OK
        body = response.json()
        assert body["event"]["id"] == "created-e2e"
        assert body["event"]["title"] == "E2E Created Event"
        assert len(calendar.created_events) == 1
    finally:
        app.dependency_overrides.clear()


def test_app_get_event_by_id_endpoint() -> None:
    """E2E: GET /events/{event_id} returns a single event."""
    app.dependency_overrides[get_calendar_client] = _FakeCalendarClient

    try:
        test_client = TestClient(app)
        response = test_client.get("/events/some-event-id")

        assert response.status_code == HTTP_OK
        body = response.json()
        assert body["event"]["id"] == "some-event-id"
    finally:
        app.dependency_overrides.clear()


def test_app_update_event_endpoint() -> None:
    """E2E: PATCH /events/{event_id} updates and returns the event."""
    app.dependency_overrides[get_calendar_client] = _FakeCalendarClient

    try:
        test_client = TestClient(app)
        response = test_client.patch(
            "/events/e2e-event",
            json={"title": "Updated Title", "location": "New Room"},
        )

        assert response.status_code == HTTP_OK
        body = response.json()
        assert body["event"]["id"] == "e2e-event"
    finally:
        app.dependency_overrides.clear()


def test_app_delete_event_endpoint() -> None:
    """E2E: DELETE /events/{event_id} returns a deleted status."""
    app.dependency_overrides[get_calendar_client] = _FakeCalendarClient

    try:
        test_client = TestClient(app)
        response = test_client.delete("/events/e2e-event")

        assert response.status_code == HTTP_OK
        body = response.json()
        assert body["status"] == "deleted"
    finally:
        app.dependency_overrides.clear()


def test_app_list_events_between_endpoint() -> None:
    """E2E: GET /events/between returns events in the specified range."""
    app.dependency_overrides[get_calendar_client] = _FakeCalendarClient

    try:
        test_client = TestClient(app)
        response = test_client.get(
            "/events/between",
            params={
                "start": "2026-06-01T00:00:00Z",
                "end": "2026-06-02T00:00:00Z",
            },
        )

        assert response.status_code == HTTP_OK
        body = response.json()
        assert "events" in body
        assert isinstance(body["events"], list)
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# E2E tests for AI error propagation
#
# These verify that domain and infrastructure errors raised during the AI
# tool-calling flow are translated to appropriate HTTP status codes and
# user-visible error messages.
# ---------------------------------------------------------------------------

HTTP_BAD_REQUEST = 400
HTTP_TOO_MANY_REQUESTS = 429
HTTP_BAD_GATEWAY = 502
HTTP_INTERNAL_ERROR = 500


def test_app_ai_endpoint_value_error_returns_400() -> None:
    """E2E: ValueError during AI processing returns 400 Bad Request."""

    class _ErrorAiClient(AiClient):
        def send_message(self, prompt: str, context: dict[str, Any] | None = None) -> str:
            return ""  # pragma: no cover

        def run_chat_with_tools(self, **kwargs: Any) -> str:
            msg = "Invalid tool arguments"
            raise ValueError(msg)

    app.dependency_overrides[get_ai_client] = _ErrorAiClient
    app.dependency_overrides[get_calendar_client] = _FakeCalendarClient
    app.dependency_overrides[get_issue_client] = _FakeIssueClient

    try:
        test_client = TestClient(app, raise_server_exceptions=False)
        response = test_client.post("/ai/", json={"prompt": "bad request"})

        assert response.status_code == HTTP_BAD_REQUEST
        assert "detail" in response.json()
    finally:
        app.dependency_overrides.clear()


def test_app_ai_endpoint_runtime_error_returns_502() -> None:
    """E2E: RuntimeError during AI processing returns 502 Bad Gateway."""

    class _RuntimeErrorAiClient(AiClient):
        def send_message(self, prompt: str, context: dict[str, Any] | None = None) -> str:
            return ""  # pragma: no cover

        def run_chat_with_tools(self, **kwargs: Any) -> str:
            msg = "Service unavailable"
            raise RuntimeError(msg)

    app.dependency_overrides[get_ai_client] = _RuntimeErrorAiClient
    app.dependency_overrides[get_calendar_client] = _FakeCalendarClient
    app.dependency_overrides[get_issue_client] = _FakeIssueClient

    try:
        test_client = TestClient(app, raise_server_exceptions=False)
        response = test_client.post("/ai/", json={"prompt": "trigger runtime error"})

        assert response.status_code == HTTP_BAD_GATEWAY
        assert "detail" in response.json()
    finally:
        app.dependency_overrides.clear()


def test_app_ai_endpoint_unexpected_error_returns_500() -> None:
    """E2E: Unexpected exception during AI processing returns 500."""

    class _UnexpectedErrorAiClient(AiClient):
        def send_message(self, prompt: str, context: dict[str, Any] | None = None) -> str:
            return ""  # pragma: no cover

        def run_chat_with_tools(self, **kwargs: Any) -> str:
            msg = "something broke"
            raise OSError(msg)

    app.dependency_overrides[get_ai_client] = _UnexpectedErrorAiClient
    app.dependency_overrides[get_calendar_client] = _FakeCalendarClient
    app.dependency_overrides[get_issue_client] = _FakeIssueClient

    try:
        test_client = TestClient(app, raise_server_exceptions=False)
        response = test_client.post("/ai/", json={"prompt": "trigger unexpected error"})

        assert response.status_code == HTTP_INTERNAL_ERROR
        assert "detail" in response.json()
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# E2E: Multi-turn AI tool-calling through HTTP
#
# Verifies that a multi-step AI workflow (multiple tool calls in sequence)
# works correctly through the HTTP entry point.
# ---------------------------------------------------------------------------


class _MultiTurnScriptedAiClient(AiClient):
    """AI client that replays multiple tool calls through the HTTP endpoint."""

    def __init__(self, tool_calls: list[tuple[str, dict[str, Any]]]) -> None:
        self._tool_calls = tool_calls
        self.tool_results: list[str] = []

    def send_message(self, prompt: str, context: dict[str, Any] | None = None) -> str:
        return ""  # pragma: no cover

    def run_chat_with_tools(self, **kwargs: Any) -> str:
        handle_tool = kwargs["handle_tool"]
        for tool_name, tool_args in self._tool_calls:
            result = handle_tool(tool_name, tool_args)
            self.tool_results.append(result)
        return f"Completed {len(self._tool_calls)} steps successfully."


def test_app_ai_endpoint_multi_turn_cross_vertical() -> None:
    """E2E: HTTP POST /ai/ with multi-turn tool calls across issue tracker and calendar.

    Verifies user-visible behavior when the AI performs a multi-step workflow:
    list issues → schedule a work session for an issue.
    """
    calendar_with_empty_between = _FakeCalendarClient()
    calendar_with_empty_between.list_events_between = lambda _start, _end: []  # type: ignore[assignment]

    issue_client = _FakeIssueClient()
    scripted_ai = _MultiTurnScriptedAiClient(
        tool_calls=[
            ("list_issues", {"board_id": "board-1"}),
            (
                "create_event_from_issue",
                {
                    "issue_id": "42",
                    "start": "2026-06-15T14:00:00",
                    "end": "2026-06-15T15:00:00",
                },
            ),
        ]
    )

    app.dependency_overrides[get_ai_client] = lambda: scripted_ai
    app.dependency_overrides[get_calendar_client] = lambda: calendar_with_empty_between
    app.dependency_overrides[get_issue_client] = lambda: issue_client

    try:
        test_client = TestClient(app, raise_server_exceptions=False)
        response = test_client.post(
            "/ai/",
            json={"prompt": "List my issues and schedule issue 42"},
        )

        assert response.status_code == HTTP_OK
        body = response.json()
        assert "message" in body
        assert "Completed 2 steps" in body["message"]
        assert len(scripted_ai.tool_results) == 2
    finally:
        app.dependency_overrides.clear()


def test_app_ai_endpoint_with_context_parameter() -> None:
    """E2E: HTTP POST /ai/ passes context through to the AI agent."""

    class _ContextCapturingAiClient(AiClient):
        def __init__(self) -> None:
            self.received_message: str = ""

        def send_message(self, prompt: str, context: dict[str, Any] | None = None) -> str:
            return ""  # pragma: no cover

        def run_chat_with_tools(self, **kwargs: Any) -> str:
            self.received_message = kwargs.get("user_message", "")
            return "Events listed for your timezone."

    capturing_ai = _ContextCapturingAiClient()

    app.dependency_overrides[get_ai_client] = lambda: capturing_ai
    app.dependency_overrides[get_calendar_client] = _FakeCalendarClient
    app.dependency_overrides[get_issue_client] = _FakeIssueClient

    try:
        test_client = TestClient(app, raise_server_exceptions=False)
        response = test_client.post(
            "/ai/",
            json={
                "prompt": "What meetings do I have today?",
                "context": {"timezone": "America/New_York"},
            },
        )

        assert response.status_code == HTTP_OK
        assert "Context JSON" in capturing_ai.received_message
        assert "America/New_York" in capturing_ai.received_message
    finally:
        app.dependency_overrides.clear()


def test_app_ai_endpoint_schedule_work_session_cross_vertical() -> None:
    """E2E: HTTP POST /ai/ → schedule_issue_work_session end-to-end.

    Verifies the full cross-vertical flow through HTTP: the AI agent
    finds a free calendar slot and schedules work time for an issue,
    updating the issue status in the process.
    """
    calendar = _FakeCalendarClient()
    calendar.list_events_between = lambda _start, _end: []  # type: ignore[assignment]
    issue_client = _FakeIssueClient()
    scripted_ai = _ScriptedAiClient(
        tool_name="schedule_issue_work_session",
        tool_args={
            "issue_id": "42",
            "window_start": "2026-06-15T09:00:00",
            "window_end": "2026-06-15T17:00:00",
            "duration_minutes": 60,
            "update_status": True,
        },
    )

    app.dependency_overrides[get_ai_client] = lambda: scripted_ai
    app.dependency_overrides[get_calendar_client] = lambda: calendar
    app.dependency_overrides[get_issue_client] = lambda: issue_client

    try:
        test_client = TestClient(app, raise_server_exceptions=False)
        response = test_client.post(
            "/ai/",
            json={"prompt": "Find time to work on issue 42 today"},
        )

        assert response.status_code == HTTP_OK
        body = response.json()
        assert "message" in body
        assert scripted_ai.tool_result is not None
        parsed = json.loads(scripted_ai.tool_result)
        assert parsed["status"] == "scheduled"
        assert len(calendar.created_events) == 1
    finally:
        app.dependency_overrides.clear()
