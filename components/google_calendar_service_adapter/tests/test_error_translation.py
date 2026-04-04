"""Unit tests for HTTP error → domain exception translation in the adapter."""

import httpx
from calendar_client_api.exceptions import (
    AuthorizationError,
    CalendarClientError,
    EventNotFoundError,
    ServiceUnavailableError,
    ValidationError,
)
from google_calendar_service_adapter.client_adapter import _translate_http_error
from google_calendar_service_client.errors import UnexpectedStatus


class TestTranslateHttpError:
    """Tests for _translate_http_error mapping function."""

    def test_404_with_event_id_returns_event_not_found(self) -> None:
        """A 404 with an event_id should produce EventNotFoundError."""
        err = UnexpectedStatus(status_code=404, content=b"Not Found")

        result = _translate_http_error(err, event_id="evt_42")

        assert isinstance(result, EventNotFoundError)
        assert result.event_id == "evt_42"
        assert "evt_42" in str(result)

    def test_404_without_event_id_returns_generic_error(self) -> None:
        """A 404 without an event_id should fall through to CalendarClientError."""
        err = UnexpectedStatus(status_code=404, content=b"Not Found")

        result = _translate_http_error(err, event_id=None)

        assert type(result) is CalendarClientError

    def test_401_returns_authorization_error(self) -> None:
        """A 401 should produce AuthorizationError."""
        err = UnexpectedStatus(status_code=401, content=b"Unauthorized")

        result = _translate_http_error(err)

        assert isinstance(result, AuthorizationError)

    def test_403_returns_authorization_error(self) -> None:
        """A 403 should produce AuthorizationError."""
        err = UnexpectedStatus(status_code=403, content=b"Forbidden")

        result = _translate_http_error(err)

        assert isinstance(result, AuthorizationError)

    def test_422_returns_validation_error(self) -> None:
        """A 422 should produce ValidationError."""
        err = UnexpectedStatus(status_code=422, content=b"Unprocessable Entity")

        result = _translate_http_error(err)

        assert isinstance(result, ValidationError)

    def test_500_returns_service_unavailable(self) -> None:
        """A 500 should produce ServiceUnavailableError."""
        err = UnexpectedStatus(status_code=500, content=b"Internal Server Error")

        result = _translate_http_error(err)

        assert isinstance(result, ServiceUnavailableError)

    def test_502_returns_service_unavailable(self) -> None:
        """A 502 should produce ServiceUnavailableError."""
        err = UnexpectedStatus(status_code=502, content=b"Bad Gateway")

        result = _translate_http_error(err)

        assert isinstance(result, ServiceUnavailableError)

    def test_unknown_status_returns_generic_calendar_client_error(self) -> None:
        """An unexpected status (e.g., 409) should produce base CalendarClientError."""
        err = UnexpectedStatus(status_code=409, content=b"Conflict")

        result = _translate_http_error(err)

        assert type(result) is CalendarClientError

    def test_httpx_connect_error_returns_service_unavailable(self) -> None:
        """An httpx connection error should produce ServiceUnavailableError."""
        request = httpx.Request("GET", "http://localhost:8000/events")
        err = httpx.ConnectError("Connection refused", request=request)

        result = _translate_http_error(err)

        assert isinstance(result, ServiceUnavailableError)

    def test_httpx_timeout_error_returns_service_unavailable(self) -> None:
        """An httpx timeout should produce ServiceUnavailableError."""
        request = httpx.Request("GET", "http://localhost:8000/events")
        err = httpx.ReadTimeout("Read timed out", request=request)

        result = _translate_http_error(err)

        assert isinstance(result, ServiceUnavailableError)

    def test_all_domain_exceptions_inherit_from_calendar_client_error(self) -> None:
        """Every translated exception should be a subclass of CalendarClientError."""
        cases: list[UnexpectedStatus | httpx.HTTPError] = [
            UnexpectedStatus(status_code=404, content=b""),
            UnexpectedStatus(status_code=401, content=b""),
            UnexpectedStatus(status_code=422, content=b""),
            UnexpectedStatus(status_code=500, content=b""),
            UnexpectedStatus(status_code=409, content=b""),
            httpx.ConnectError("fail", request=httpx.Request("GET", "http://x")),
        ]

        for err in cases:
            result = _translate_http_error(err, event_id="evt_1")
            assert isinstance(result, CalendarClientError), f"Failed for {err!r}"
