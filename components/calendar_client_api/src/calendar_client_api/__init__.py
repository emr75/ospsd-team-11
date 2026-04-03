"""Public exports for the calendar_client_api package."""

from calendar_client_api.client import (
    CalendarClient as CalendarClient,
)
from calendar_client_api.event import (
    Attendee as Attendee,
)
from calendar_client_api.event import (
    Event as Event,
)
from calendar_client_api.event import (
    EventCreate as EventCreate,
)
from calendar_client_api.event import (
    EventUpdate as EventUpdate,
)
from calendar_client_api.exceptions import (
    AuthorizationError as AuthorizationError,
)
from calendar_client_api.exceptions import (
    CalendarClientError as CalendarClientError,
)
from calendar_client_api.exceptions import (
    EventNotFoundError as EventNotFoundError,
)
from calendar_client_api.exceptions import (
    ServiceUnavailableError as ServiceUnavailableError,
)
from calendar_client_api.exceptions import (
    ValidationError as ValidationError,
)
from calendar_client_api.registry import (
    get_client as get_client,
)
from calendar_client_api.registry import (
    register_client as register_client,
)
