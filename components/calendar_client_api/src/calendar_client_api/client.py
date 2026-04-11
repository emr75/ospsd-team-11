"""Core Calendar client contract definitions and factory placeholder."""

from abc import ABC, abstractmethod
from collections.abc import Iterable
from datetime import datetime

from calendar_client_api.event import Event, EventCreate, EventUpdate


class CalendarClient(ABC):
    """Abstract class defines the contract/methods for any calendar client."""

    @abstractmethod
    def create_event_from_dto(self, event_create: EventCreate) -> Event:
        """Create Calendar event."""
        raise NotImplementedError

    @abstractmethod
    def get_event_by_id(self, event_id: str) -> Event:
        """Return an event and its details based on ID."""
        raise NotImplementedError

    @abstractmethod
    def list_upcoming_events(self, max_results: int = 10) -> Iterable[Event]:
        """List calendar events and their details."""
        raise NotImplementedError

    @abstractmethod
    def list_events_between(self, start: datetime, end: datetime) -> Iterable[Event]:
        """List calendar events and their details between two datetime range."""
        raise NotImplementedError

    @abstractmethod
    def update_event_from_patch(self, event_id: str, event_patch: EventUpdate) -> Event:
        """Update a calendar event."""
        raise NotImplementedError

    @abstractmethod
    def delete_event(self, event_id: str) -> None:
        """Delete an event by ID."""
        raise NotImplementedError
