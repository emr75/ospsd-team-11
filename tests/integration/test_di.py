"""Integration tests for DI wiring via interface-only consumer usage."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING
from unittest.mock import Mock, patch

import google_calendar_client_impl
import pytest
from calendar_client_api import CalendarClient, get_client, register_client
from calendar_client_api.registry import _ClientRegistry

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture(autouse=True)
def clear_client_registry() -> Iterator[None]:
    """Ensure registry state does not leak across tests."""
    _ClientRegistry.clear()
    yield
    _ClientRegistry.clear()


def _assert_calendar_client(value: object) -> None:
    """Assert value satisfies the abstract CalendarClient interface."""
    assert isinstance(value, CalendarClient)


@pytest.mark.integration
def test_import_auto_registers_factory() -> None:
    """Import side effect registers a DI factory in the interface registry."""
    assert _ClientRegistry._factory is None

    importlib.reload(google_calendar_client_impl)

    assert _ClientRegistry._factory is not None


@pytest.mark.integration
@patch("google_calendar_client_impl.client_impl.build", return_value=Mock())
@patch(
    "google_calendar_client_impl.client_impl.GoogleCalendarClient._auth_from_env",
    return_value=Mock(valid=True, refresh_token=None),
)
def test_get_client_returns_interface_instance(*_: Mock) -> None:
    """Consumers resolving through DI receive a CalendarClient implementation."""
    importlib.reload(google_calendar_client_impl)

    client = get_client()

    _assert_calendar_client(client)


@pytest.mark.integration
def test_get_client_raises_runtime_error_when_registry_empty() -> None:
    """get_client() raises RuntimeError when no implementation is registered."""
    with pytest.raises(RuntimeError, match=r"No CalendarClient registered\."):
        get_client()


@pytest.mark.integration
@patch("google_calendar_client_impl.client_impl.build", return_value=Mock())
@patch(
    "google_calendar_client_impl.client_impl.GoogleCalendarClient._auth_from_env",
    return_value=Mock(valid=True, refresh_token=None),
)
def test_multiple_imports_do_not_break_registration(*_: Mock) -> None:
    """Repeated imports keep registry usable for interface-based consumers."""
    importlib.reload(google_calendar_client_impl)
    importlib.reload(google_calendar_client_impl)

    client = get_client()

    _assert_calendar_client(client)


@pytest.mark.integration
@patch("google_calendar_client_impl.client_impl.build", return_value=Mock())
@patch(
    "google_calendar_client_impl.client_impl.GoogleCalendarClient._auth_from_env",
    return_value=Mock(valid=True, refresh_token=None),
)
def test_get_client_returns_new_instance_each_call(*_: Mock) -> None:
    """DI factory is invoked on each call and returns distinct client instances."""
    importlib.reload(google_calendar_client_impl)

    first = get_client()
    second = get_client()

    _assert_calendar_client(first)
    _assert_calendar_client(second)
    assert first is not second


@pytest.mark.integration
@patch("google_calendar_client_impl.client_impl.build", return_value=Mock())
@patch(
    "google_calendar_client_impl.client_impl.GoogleCalendarClient._auth_from_env",
    return_value=Mock(valid=True, refresh_token=None),
)
def test_register_client_replaces_previous_factory_then_import_restores_impl(*_: Mock) -> None:
    """Registry override works, and implementation import can re-register default factory."""
    fake_client = Mock(spec=CalendarClient)
    register_client(lambda: fake_client)

    resolved = get_client()
    _assert_calendar_client(resolved)
    assert resolved is fake_client

    importlib.reload(google_calendar_client_impl)

    reloaded_client = get_client()
    _assert_calendar_client(reloaded_client)
    assert reloaded_client is not fake_client


@pytest.mark.integration
@patch("google_calendar_client_impl.client_impl.GoogleCalendarClient._auth_from_interactive", return_value=None)
@patch("google_calendar_client_impl.client_impl.GoogleCalendarClient._auth_from_file", return_value=None)
@patch("google_calendar_client_impl.client_impl.GoogleCalendarClient._auth_from_env", return_value=None)
def test_get_client_propagates_factory_error(*_: Mock) -> None:
    """Factory initialization/auth failures propagate through the interface accessor."""
    importlib.reload(google_calendar_client_impl)

    with pytest.raises(RuntimeError, match="Failed to authenticate with Google Calendar API"):
        get_client()
