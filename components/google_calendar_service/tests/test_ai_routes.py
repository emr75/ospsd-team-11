"""Tests for AI route handling.

These tests validate that the /ai endpoint correctly delegates to the AI client
and returns the final response string. Tool execution is handled internally
within the AI orchestration layer and is not tested here.
"""

from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from google_calendar_service.main import app
from google_calendar_service.routes import ai_routes

HTTP_OK = 200
client = TestClient(app)


class FakeAiClient:
    """Fake AI client that simulates the tool loop and returns a final response."""

    def run_chat_with_tools(self, **kwargs: Any) -> str:
        """Return a static AI response."""
        return "AI final response"


@pytest.fixture(autouse=True)
def clear_overrides() -> Generator[None]:
    """Clear dependency overrides after each test."""
    yield
    app.dependency_overrides.clear()


class TestAiRoutes:
    """Test suite for AI route behavior."""

    def test_handle_ai_returns_message(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Ensure the route returns the final AI response."""
        monkeypatch.setattr(ai_routes, "get_ai_client", FakeAiClient)
        monkeypatch.setattr(ai_routes, "get_calendar_client", object)

        response = client.post("/ai/", json={"prompt": "What can you do?"})

        assert response.status_code == HTTP_OK
        assert response.json() == {"message": "AI final response"}
