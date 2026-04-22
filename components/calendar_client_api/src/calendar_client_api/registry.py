"""Registry for CalendarClient implementations."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import ClassVar

from calendar_client_api import CalendarClient


@dataclass(frozen=True)
class CredentialsToken:
    """Structured representation of OAuth credentials for token-based auth."""

    client_id: str
    client_secret: str
    token_uri: str
    scopes: list[str]
    access_token: str
    refresh_token: str | None = None


Factory = Callable[[], CalendarClient]
FactoryCredential = Callable[[CredentialsToken], CalendarClient]


class _ClientRegistry:
    _factory: ClassVar[Factory | None] = None
    _factory_credentials: ClassVar[FactoryCredential | None] = None

    @classmethod
    def register(cls, factory: Factory) -> None:
        cls._factory = factory

    @classmethod
    def register_with_credentials(cls, factory: FactoryCredential) -> None:
        cls._factory_credentials = factory

    @classmethod
    def get(cls) -> CalendarClient:
        if cls._factory is None:
            error_str = "No CalendarClient registered."
            raise RuntimeError(error_str)
        return cls._factory()

    @classmethod
    def get_with_credentials(cls, creds_token: CredentialsToken) -> CalendarClient:
        if cls._factory_credentials is None:
            error_str = "No CalendarClient registered."
            raise RuntimeError(error_str)
        return cls._factory_credentials(creds_token)

    @classmethod
    def clear(cls) -> None:
        cls._factory = None
        cls._factory_credentials = None


def register_client(factory: Factory) -> None:
    """Register a CalendarClient via dependency injection."""
    _ClientRegistry.register(factory)


def register_client_with_credentials(factory: FactoryCredential) -> None:
    """Register a CalendarClient via dependency injection."""
    _ClientRegistry.register_with_credentials(factory)


def get_client() -> CalendarClient:
    """Return an instance of the registered CalendarClient via dependency injection.

    Raises error if no implementation has been registered.
    """
    return _ClientRegistry.get()


def get_client_with_credentials(creds_token: CredentialsToken) -> CalendarClient:
    """Return an instance of the registered CalendarClient via dependency injection."""
    return _ClientRegistry.get_with_credentials(creds_token)
