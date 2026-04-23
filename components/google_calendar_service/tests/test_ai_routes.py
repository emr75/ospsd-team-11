# ruff: noqa: D101, D102, D103

"""Tests for AI route handling."""

from collections.abc import Generator
from typing import Any

import pytest
from ai_client_api.client import AiResponse, AiToolCall
from fastapi.testclient import TestClient
from google_calendar_service.main import app
from google_calendar_service.routes import ai_routes

HTTP_OK = 200

client = TestClient(app)


class FakeAiClientNoTools:
    def send_message(self, prompt: str, context: dict[str, Any] | None = None) -> AiResponse:
        return AiResponse(message="Here is your answer.", tool_calls=[])


class FakeAiClientCreateEvent:
    def send_message(self, prompt: str, context: dict[str, Any] | None = None) -> AiResponse:
        return AiResponse(
            message="I can schedule that.",
            tool_calls=[
                AiToolCall(
                    tool_name="create_event",
                    arguments={
                        "title": "Meeting",
                        "start": "2026-04-21T15:00:00-04:00",
                        "end": "2026-04-21T16:00:00-04:00",
                        "description": "",
                        "location": None,
                    },
                )
            ],
        )


class FakeAiClientListEvents:
    def send_message(self, prompt: str, context: dict[str, Any] | None = None) -> AiResponse:
        return AiResponse(
            message="Let me check.",
            tool_calls=[
                AiToolCall(
                    tool_name="list_events",
                    arguments={
                        "start": "2026-04-21T00:00:00-04:00",
                        "end": "2026-04-28T00:00:00-04:00",
                    },
                )
            ],
        )


class FakeAiClientIssue:
    def send_message(self, prompt: str, context: dict[str, Any] | None = None) -> AiResponse:
        return AiResponse(
            message="I can create that from the issue.",
            tool_calls=[
                AiToolCall(
                    tool_name="create_event_from_issue",
                    arguments={
                        "issue_id": "123",
                        "start": "2026-04-23T15:00:00-04:00",
                        "end": "2026-04-23T16:00:00-04:00",
                    },
                )
            ],
        )


class FakeCalendarClient:
    def create_event(self, **kwargs: Any) -> dict[str, Any]:
        return {"status": "created", "args": kwargs}

    def list_events(self, **kwargs: Any) -> list[dict[str, Any]]:
        return [{"id": "evt_1", "title": "Team Sync", "args": kwargs}]

    def update_event(self, **kwargs: Any) -> dict[str, Any]:
        return {"status": "updated", "args": kwargs}

class FakeAiClientUpdateEvent:
    def send_message(self, prompt: str, context: dict[str, Any] | None = None) -> AiResponse:
        return AiResponse(
            message="I will update that.",
            tool_calls=[
                AiToolCall(
                    tool_name="update_event",
                    arguments={
                        "event_reference": "Team Sync",
                        "start_time": "2026-04-21T16:00:00-04:00",
                        "end_time": "2026-04-21T17:00:00-04:00",
                    },
                )
            ],
        )


@pytest.fixture(autouse=True)
def clear_overrides() -> Generator[None]:
    yield
    app.dependency_overrides.clear()


class TestAiRoutes:
    def test_handle_ai_returns_message_when_no_tool_calls(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(ai_routes, "get_ai_client", FakeAiClientNoTools)
        monkeypatch.setattr(ai_routes, "get_calendar_client", FakeCalendarClient)

        response = client.post("/ai/", json={"prompt": "What can you do?"})

        assert response.status_code == HTTP_OK
        assert response.json() == {
            "message": "Here is your answer.",
            "result": None,
        }

    def test_handle_ai_executes_create_event_tool_call(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(ai_routes, "get_ai_client", FakeAiClientCreateEvent)
        monkeypatch.setattr(ai_routes, "get_calendar_client", FakeCalendarClient)

        response = client.post("/ai/", json={"prompt": "Schedule a meeting tomorrow at 3pm"})

        assert response.status_code == HTTP_OK
        assert response.json()["message"] == "I can schedule that."
        assert response.json()["result"]["status"] == "created"

    def test_handle_ai_executes_list_events_tool_call(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(ai_routes, "get_ai_client", FakeAiClientListEvents)
        monkeypatch.setattr(ai_routes, "get_calendar_client", FakeCalendarClient)

        response = client.post("/ai/", json={"prompt": "What's on my calendar this week?"})

        assert response.status_code == HTTP_OK
        assert response.json()["message"] == "Let me check."
        assert response.json()["result"][0]["id"] == "evt_1"

    def test_handle_ai_executes_create_event_from_issue_tool_call(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(ai_routes, "get_ai_client", FakeAiClientIssue)
        monkeypatch.setattr(ai_routes, "get_calendar_client", FakeCalendarClient)

        def fake_create_event_from_issue_flow(
            issue_id: str,
            start: str,
            end: str,
        ) -> dict[str, Any]:
            assert issue_id == "123"
            assert start == "2026-04-23T15:00:00-04:00"
            assert end == "2026-04-23T16:00:00-04:00"
            return {
                "issue_id": "123",
                "event_id": "evt_999",
                "event_title": "Issue Review: Broken auth redirect",
                "board_name": "Sprint Board",
                "status": "created",
            }

        monkeypatch.setattr(
            ai_routes,
            "create_event_from_issue_flow",
            fake_create_event_from_issue_flow,
        )

        response = client.post("/ai/", json={"prompt": "Create a meeting from issue #123"})

        assert response.status_code == HTTP_OK
        assert response.json() == {
            "message": "I can create that from the issue.",
            "result": {
                "issue_id": "123",
                "event_id": "evt_999",
                "event_title": "Issue Review: Broken auth redirect",
                "board_name": "Sprint Board",
                "status": "created",
            },
        }

    def test_handle_ai_executes_update_event_tool_call(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(ai_routes, "get_ai_client", FakeAiClientUpdateEvent)
        monkeypatch.setattr(ai_routes, "get_calendar_client", FakeCalendarClient)

        response = client.post("/ai/", json={"prompt": "Move Team Sync to 4pm"})

        assert response.status_code == HTTP_OK
        assert response.json()["message"] == "I will update that."
        assert response.json()["result"]["status"] == "updated"
        assert response.json()["result"]["args"]["event_id"] == "evt_1"


    def test_handle_ai_returns_error_when_update_event_reference_not_found(
        self,
        monkeypatch: pytest.MonkeyPatch,
        ) -> None:
        monkeypatch.setattr(ai_routes, "get_ai_client", FakeAiClientUpdateEvent)

        class FakeCalendarClientNoMatch(FakeCalendarClient):
            def list_events(self, **kwargs: Any) -> list[dict[str, Any]]:
                return [{"id": "evt_2", "title": "Other Meeting", "args": kwargs}]

        monkeypatch.setattr(ai_routes, "get_calendar_client", FakeCalendarClientNoMatch)

        response = client.post("/ai/", json={"prompt": "Move Team Sync to 4pm"})

        assert response.status_code == HTTP_OK
        assert response.json()["result"] == {
            "error": "No event found for reference: Team Sync"
        }
