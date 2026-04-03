# ruff: noqa: D102
"""Unit tests for the calendar_client_api domain exceptions."""

import pytest
from calendar_client_api.exceptions import (
    AuthorizationError,
    CalendarClientError,
    EventNotFoundError,
    ServiceUnavailableError,
    ValidationError,
)


class TestExceptionHierarchy:
    """All domain exceptions should derive from CalendarClientError."""

    def test_event_not_found_is_calendar_client_error(self) -> None:
        assert issubclass(EventNotFoundError, CalendarClientError)

    def test_authorization_error_is_calendar_client_error(self) -> None:
        assert issubclass(AuthorizationError, CalendarClientError)

    def test_validation_error_is_calendar_client_error(self) -> None:
        assert issubclass(ValidationError, CalendarClientError)

    def test_service_unavailable_is_calendar_client_error(self) -> None:
        assert issubclass(ServiceUnavailableError, CalendarClientError)

    def test_calendar_client_error_is_exception(self) -> None:
        assert issubclass(CalendarClientError, Exception)


class TestEventNotFoundError:
    """Tests for EventNotFoundError."""

    def test_stores_event_id(self) -> None:
        err = EventNotFoundError("evt_42")

        assert err.event_id == "evt_42"

    def test_message_contains_event_id(self) -> None:
        err = EventNotFoundError("evt_42")

        assert "evt_42" in str(err)

    def test_catchable_as_calendar_client_error(self) -> None:
        with pytest.raises(CalendarClientError):
            raise EventNotFoundError(event_id="evt_1")


class TestAuthorizationError:
    """Tests for AuthorizationError."""

    def test_message_preserved(self) -> None:
        err = AuthorizationError("Token expired")

        assert str(err) == "Token expired"

    def test_catchable_as_calendar_client_error(self) -> None:
        msg = "forbidden"
        with pytest.raises(CalendarClientError):
            raise AuthorizationError(msg)


class TestValidationError:
    """Tests for ValidationError."""

    def test_message_preserved(self) -> None:
        err = ValidationError("title is required")

        assert str(err) == "title is required"

    def test_catchable_as_calendar_client_error(self) -> None:
        msg = "bad input"
        with pytest.raises(CalendarClientError):
            raise ValidationError(msg)


class TestServiceUnavailableError:
    """Tests for ServiceUnavailableError."""

    def test_message_preserved(self) -> None:
        err = ServiceUnavailableError("connection refused")

        assert str(err) == "connection refused"

    def test_catchable_as_calendar_client_error(self) -> None:
        msg = "timeout"
        with pytest.raises(CalendarClientError):
            raise ServiceUnavailableError(msg)
