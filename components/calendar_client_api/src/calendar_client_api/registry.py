"""Registry for CalendarClient implementations."""

from collections.abc import Callable
from typing import ClassVar

from calendar_client_api import CalendarClient

Factory = Callable[[], CalendarClient]


class _ClientRegistry:
    _factory: ClassVar[Factory | None] = None

    @classmethod
    def register(cls, factory: Factory) -> None:
        cls._factory = factory

    @classmethod
    def get(cls) -> CalendarClient:
        if cls._factory is None:
            error_str = "No CalendarClient registered."
            raise RuntimeError(error_str)
        return cls._factory()

    @classmethod
    def clear(cls) -> None:
        cls._factory = None
        cls._factory_credentials = None


def register_client(factory: Factory) -> None:
    """Register a CalendarClient via dependency injection."""
    _ClientRegistry.register(factory)


def get_client() -> CalendarClient:
    """Return an instance of the registered CalendarClient via dependency injection.

    Raises error if no implementation has been registered.
    """
    return _ClientRegistry.get()
