"""Integration tests for AI client DI wiring via the ai_client_api registry."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import ai_client_api.registry as registry_module
import openai_ai_client_impl
import pytest
from ai_client_api import AiClient, get_client, register_client

if TYPE_CHECKING:
    from collections.abc import Iterator

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _clear_ai_registry() -> Iterator[None]:
    """Ensure AI client registry state does not leak across tests."""
    registry_module._registry["client_factory"] = None
    yield
    registry_module._registry["client_factory"] = None


def test_import_side_effect_registers_ai_factory() -> None:
    """Importing openai_ai_client_impl auto-registers a factory in the AI client registry."""
    assert registry_module._registry["client_factory"] is None

    importlib.reload(openai_ai_client_impl)

    assert registry_module._registry["client_factory"] is not None


@patch.dict("os.environ", {"OPENAI_API_KEY": "test-key-for-di"})
def test_get_client_returns_ai_client_instance() -> None:
    """Consumers resolving through DI receive an AiClient implementation."""
    importlib.reload(openai_ai_client_impl)

    client = get_client()

    assert isinstance(client, AiClient)


def test_get_client_raises_when_no_ai_client_registered() -> None:
    """get_client() raises RuntimeError when no AI implementation is registered."""
    with pytest.raises(RuntimeError, match=r"No AI client has been registered\."):
        get_client()


@patch.dict("os.environ", {"OPENAI_API_KEY": "test-key-for-di"})
def test_multiple_imports_keep_registry_usable() -> None:
    """Repeated imports do not break the registry for interface-based consumers."""
    importlib.reload(openai_ai_client_impl)
    importlib.reload(openai_ai_client_impl)

    client = get_client()

    assert isinstance(client, AiClient)


@patch.dict("os.environ", {"OPENAI_API_KEY": "test-key-for-di"})
def test_register_client_replaces_previous_factory() -> None:
    """A custom factory overrides the auto-registered OpenAI factory."""
    importlib.reload(openai_ai_client_impl)

    class StubAiClient(AiClient):
        """Minimal AiClient stub for DI swap verification."""

        def send_message(self, prompt: str, context: dict[str, Any] | None = None) -> str:
            return "stub"

        def run_chat_with_tools(self, **kwargs: Any) -> str:
            return "stub"

    sentinel = StubAiClient()
    register_client(lambda: sentinel)

    resolved = get_client()
    assert resolved is sentinel

    importlib.reload(openai_ai_client_impl)

    reloaded = get_client()
    assert isinstance(reloaded, AiClient)
    assert reloaded is not sentinel
