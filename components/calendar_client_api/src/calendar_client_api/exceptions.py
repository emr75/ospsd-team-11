"""Domain exceptions for the calendar client API."""


class CalendarClientError(Exception):
    """Base exception for all calendar client errors."""


class EventNotFoundError(CalendarClientError):
    """Raised when a requested event does not exist."""

    def __init__(self, event_id: str) -> None:
        """Initialize with the ID of the missing event."""
        self.event_id = event_id
        super().__init__(f"Event not found: {event_id}")


class AuthorizationError(CalendarClientError):
    """Raised when the client lacks valid credentials or permissions."""


class ValidationError(CalendarClientError):
    """Raised when the request payload fails validation."""


class ServiceUnavailableError(CalendarClientError):
    """Raised when the remote service is unreachable or returned a server error."""
