"""Request and response models for the Google Calendar Service API."""

from datetime import datetime

from calendar_client_api.event import UNSET, Attendee, Event, EventCreate, EventUpdate
from pydantic import BaseModel


# Convert FastAPI request models into EventCreate/EventUpdate for the client interface.
class AttendeeRequest(BaseModel):
    """Request model for an event attendee."""

    email: str
    name: str | None = None


class EventCreateRequest(BaseModel):
    """Request model for creating an event."""

    title: str
    start_time: datetime
    end_time: datetime
    attendees: list[AttendeeRequest]
    attachments: list[str]
    description: str | None = None
    location: str | None = None

    def to_event_create(self) -> EventCreate:
        """Convert request data to EventCreate."""
        return EventCreate(
            title=self.title,
            start_time=self.start_time,
            end_time=self.end_time,
            attendees=[Attendee(email=attendee.email, name=attendee.name) for attendee in self.attendees],
            attachments=self.attachments,
            description=self.description,
            location=self.location,
        )


class EventUpdateRequest(BaseModel):
    """Request model for updating an event."""

    title: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    description: str | None = None
    location: str | None = None

    def to_event_update(self) -> EventUpdate:
        """Convert request data to EventUpdate."""
        return EventUpdate(
            title=self.title if self.title is not None else UNSET,
            start_time=self.start_time if self.start_time is not None else UNSET,
            end_time=self.end_time if self.end_time is not None else UNSET,
            description=self.description if self.description is not None else UNSET,
            location=self.location if self.location is not None else UNSET,
        )


# FastAPI response models.
class AttendeeResponse(BaseModel):
    """Response model for an event attendee."""

    email: str
    name: str | None = None


class EventResponse(BaseModel):
    """Response model for a calendar event."""

    id: str
    title: str
    start_time: datetime
    end_time: datetime
    description: str | None = None
    location: str | None = None
    attendees: list[AttendeeResponse]
    attachments: list[str]


class EventEnvelope(BaseModel):
    """Response envelope for a single event."""

    event: EventResponse


class EventsEnvelope(BaseModel):
    """Response envelope for multiple events."""

    events: list[EventResponse]


class StatusResponse(BaseModel):
    """Response model for status messages."""

    status: str


class AiRequest(BaseModel):
    """Incoming AI request payload."""

    prompt: str
    context: dict[str, object] | None = None


class AiResponseModel(BaseModel):
    """Serialized AI response returned by the route."""

    message: str
    result: object | None = None


def to_attendee_response(attendee: Attendee) -> AttendeeResponse:
    """Convert an attendee domain model to a response DTO."""
    return AttendeeResponse(
        email=attendee.email,
        name=attendee.name,
    )


def to_event_response(event: Event) -> EventResponse:
    """Convert an event domain model to a response DTO."""
    return EventResponse(
        id=event.id,
        title=event.title,
        start_time=event.start_time,
        end_time=event.end_time,
        description=event.description,
        location=event.location,
        attendees=[to_attendee_response(attendee) for attendee in event.attendees],
        attachments=event.attachments,
    )
