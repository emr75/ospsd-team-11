"""Unit tests for the calendar_client_api client module.

Contains unit tests for the CalendarClient class and the get_client function.
"""

import inspect
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime
from unittest.mock import Mock

import calendar_client_api
import calendar_client_api.client
import pytest
from calendar_client_api.client import CalendarClient
from calendar_client_api.event import Event, EventCreate, EventUpdate
from calendar_client_api.registry import _ClientRegistry, get_client, register_client


@pytest.fixture(autouse=True)
def clear_client_registry() -> Iterator[None]:
    """Ensure registry state does not leak across tests."""
    _ClientRegistry.clear()
    yield
    _ClientRegistry.clear()


class TestCalendarClientABC:
    """Test cases for the CalendarClient abstract base class."""

    def test_cannot_instantiate_abstract_class(self) -> None:
        """Test that CalendarClient cannot be instantiated directly."""
        with pytest.raises(TypeError):
            CalendarClient()  # type: ignore[abstract] # intentionally instantiating ABC to test TypeError

    def test_defines_expected_abstract_methods(self) -> None:
        """Test that CalendarClient declares exactly the expected abstract methods."""
        expected_methods = {
            "create_event_from_dto",
            "get_event_by_id",
            "list_upcoming_events",
            "list_events_between",
            "update_event_from_patch",
            "delete_event",
        }

        abstract_methods = CalendarClient.__abstractmethods__

        assert expected_methods == abstract_methods

    def test_abstract_methods_are_decorated(self) -> None:
        """Test that all contract methods are explicitly abstract."""
        method_names = {
            "create_event_from_dto",
            "get_event_by_id",
            "list_upcoming_events",
            "list_events_between",
            "update_event_from_patch",
            "delete_event",
        }

        for method_name in method_names:
            assert getattr(CalendarClient, method_name).__isabstractmethod__

    def test_minimal_concrete_subclass_can_be_instantiated(self) -> None:
        """Test that implementing all abstract methods allows instantiation."""

        class MinimalClient(CalendarClient):
            def create_event_from_dto(self, event_create: EventCreate) -> Event:
                raise NotImplementedError

            def get_event_by_id(self, event_id: str) -> Event:
                raise NotImplementedError

            def list_upcoming_events(self, max_results: int = 10) -> Iterable[Event]:
                raise NotImplementedError

            def list_events_between(self, start: datetime, end: datetime) -> Iterable[Event]:
                raise NotImplementedError

            def update_event_from_patch(self, event_id: str, event_patch: EventUpdate) -> Event:
                raise NotImplementedError

            def delete_event(self, event_id: str) -> None:
                raise NotImplementedError

        client = MinimalClient()
        assert isinstance(client, CalendarClient)

    def test_list_events_default_max_results_is_10(self) -> None:
        """Test that list_events keeps backward-compatible default max_results."""
        default_max_results = 10
        signature = inspect.signature(CalendarClient.list_upcoming_events)
        assert signature.parameters["max_results"].default == default_max_results

    def test_calendar_client_comprehensive_mock(self) -> None:
        """Verifies all methods work together in a comprehensive test."""
        mock_client = Mock(spec=CalendarClient)
        mock_event = Mock(spec=Event)
        mock_event_create = Mock(spec=EventCreate)
        mock_event_update = Mock(spec=EventUpdate)

        # Set up method return values
        mock_client.create_event_from_dto.return_value = mock_event
        mock_client.get_event_by_id.return_value = mock_event
        mock_client.list_upcoming_events.return_value = [mock_event]
        mock_client.list_events_between.return_value = [mock_event]
        mock_client.update_event_from_patch.return_value = mock_event
        mock_client.delete_event.return_value = None

        # Test all methods
        result_create = mock_client.create_event_from_dto(mock_event_create)
        result_get = mock_client.get_event_by_id("event_123")
        result_list = mock_client.list_upcoming_events(10)
        result_list_between = mock_client.list_events_between(
            datetime(2026, 1, 1, tzinfo=UTC),
            datetime(2026, 1, 2, tzinfo=UTC),
        )
        result_update = mock_client.update_event_from_patch("event_123", mock_event_update)
        result_delete = mock_client.delete_event("event_123")

        # Verify results
        assert result_create is mock_event
        assert result_get is mock_event
        assert result_list == [mock_event]
        assert result_list_between == [mock_event]
        assert result_update is mock_event
        assert result_delete is None

        # Verify calls
        mock_client.create_event_from_dto.assert_called_once_with(mock_event_create)
        mock_client.get_event_by_id.assert_called_once_with("event_123")
        mock_client.list_upcoming_events.assert_called_once_with(10)
        mock_client.update_event_from_patch.assert_called_once_with("event_123", mock_event_update)
        mock_client.delete_event.assert_called_once_with("event_123")


class TestGetClient:
    """Test cases for the get_client dependency injection factory."""

    def test_get_client_uses_factory_each_call(self) -> None:
        """Test that get_client invokes the factory on every call."""
        created_clients: list[CalendarClient] = []
        expected_clients = 2

        def fake_factory() -> CalendarClient:
            client = Mock(spec=CalendarClient)
            created_clients.append(client)
            return client

        register_client(fake_factory)
        first = get_client()
        second = get_client()

        assert len(created_clients) == expected_clients
        assert first is created_clients[0]
        assert second is created_clients[1]
        assert first is not second

    def test_get_client_propagates_factory_error(self) -> None:
        """Test that factory exceptions are not swallowed by get_client."""

        def fake_factory() -> CalendarClient:
            error_str = "factory failed"
            raise ValueError(error_str)

        register_client(fake_factory)
        with pytest.raises(ValueError, match="factory failed"):
            get_client()

    def test_clear_registry_then_get_raises_runtime_error(self) -> None:
        """Test that clearing registry resets get_client to unregistered state."""
        register_client(lambda: Mock(spec=CalendarClient))
        get_client()

        _ClientRegistry.clear()
        with pytest.raises(RuntimeError, match=r"No CalendarClient registered\."):
            get_client()

    def test_module_level_reexport_raises_runtime_error(self) -> None:
        """Test that package-level get_client mirrors registry behavior."""
        with pytest.raises(RuntimeError, match=r"No CalendarClient registered\."):
            calendar_client_api.get_client()
