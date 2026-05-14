"""Tests for AI route handling.

These tests validate that the /ai endpoint correctly delegates to the AI client
and returns the final response string. Tool execution is handled internally
within the AI orchestration layer and is not tested here.
"""

# ruff: noqa: D101, D102
from collections.abc import Generator
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from google_calendar_service.deps import get_ai_client, get_calendar_client, get_issue_client
from google_calendar_service.main import app

HTTP_OK = 200
HTTP_BAD_REQUEST = 400
HTTP_TOO_MANY_REQUESTS = 429
HTTP_BAD_GATEWAY = 502
HTTP_INTERNAL_SERVER_ERROR = 500
client = TestClient(app, raise_server_exceptions=False)


class FakeAiClient:
    """Fake AI client that simulates the tool loop and returns a final response."""

    def run_chat_with_tools(self, **kwargs: Any) -> str:
        """Return a static AI response."""
        return "AI final response"


class FakeAiClientDomainError:
    def run_chat_with_tools(self, **kwargs: Any) -> str:
        msg = "bad prompt"
        raise ValueError(msg)


class FakeAiClientInfraError:
    def run_chat_with_tools(self, **kwargs: Any) -> str:
        msg = "provider down"
        raise RuntimeError(msg)


class FakeAiClientRateLimitError:
    def run_chat_with_tools(self, **kwargs: Any) -> str:
        import httpx
        from openai import RateLimitError

        raise RateLimitError(
            message="quota exceeded",
            response=httpx.Response(status_code=429, request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions")),
            body={"error": {"message": "quota exceeded", "type": "insufficient_quota"}},
        )


class FakeAiClientUnexpectedError:
    def run_chat_with_tools(self, **kwargs: Any) -> str:
        msg = "disk full"
        raise OSError(msg)


def _override_deps(ai_cls: type) -> None:
    app.dependency_overrides[get_ai_client] = ai_cls
    app.dependency_overrides[get_calendar_client] = object
    app.dependency_overrides[get_issue_client] = object


@pytest.fixture(autouse=True)
def clear_overrides() -> Generator[None]:
    """Clear dependency overrides after each test."""
    yield
    app.dependency_overrides.clear()


class TestAiRoutes:
    """Test suite for AI route behavior."""

    def test_handle_ai_returns_message(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Ensure the route returns the final AI response."""
        _override_deps(FakeAiClient)

        response = client.post("/ai/", json={"prompt": "What can you do?"})

        assert response.status_code == HTTP_OK
        assert response.json() == {"message": "AI final response"}


class TestChatRequestStatusCounter:
    """Verify that the chat.request.status_class counter is incremented correctly."""

    @staticmethod
    def _install_capturing_counter(monkeypatch: pytest.MonkeyPatch) -> list[tuple[int, dict[str, str]]]:
        recorded: list[tuple[int, dict[str, str]]] = []
        monkeypatch.setattr(
            "google_calendar_service.routes.ai_routes.chat_request_status_counter",
            SimpleNamespace(add=lambda value, attributes: recorded.append((value, attributes))),
        )
        return recorded

    def test_ok_increments_counter(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _override_deps(FakeAiClient)
        recorded = self._install_capturing_counter(monkeypatch)

        response = client.post("/ai/", json={"prompt": "hello"})

        assert response.status_code == HTTP_OK
        assert recorded == [(1, {"status_class": "ok"})]

    def test_domain_error_increments_counter(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _override_deps(FakeAiClientDomainError)
        recorded = self._install_capturing_counter(monkeypatch)

        response = client.post("/ai/", json={"prompt": "bad"})

        assert response.status_code == HTTP_BAD_REQUEST
        assert recorded == [(1, {"status_class": "domain_error"})]

    def test_runtime_error_increments_counter(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _override_deps(FakeAiClientInfraError)
        recorded = self._install_capturing_counter(monkeypatch)

        response = client.post("/ai/", json={"prompt": "fail"})

        assert response.status_code == HTTP_BAD_GATEWAY
        assert recorded == [(1, {"status_class": "infra_error"})]

    def test_rate_limit_error_increments_counter(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _override_deps(FakeAiClientRateLimitError)
        recorded = self._install_capturing_counter(monkeypatch)

        response = client.post("/ai/", json={"prompt": "too many"})

        assert response.status_code == HTTP_TOO_MANY_REQUESTS
        assert response.json()["detail"] == "AI provider quota exceeded. Please check your OpenAI plan and billing details."
        assert recorded == [(1, {"status_class": "infra_error"})]

    def test_unexpected_error_increments_counter(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _override_deps(FakeAiClientUnexpectedError)
        recorded = self._install_capturing_counter(monkeypatch)

        response = client.post("/ai/", json={"prompt": "boom"})

        assert response.status_code == HTTP_INTERNAL_SERVER_ERROR
        assert recorded == [(1, {"status_class": "infra_error"})]
