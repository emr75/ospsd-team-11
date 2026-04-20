"""Dependency injection registry for AI clients."""

from collections.abc import Callable

from ai_client_api.client import AiClient

_ClientFactory = Callable[[], AiClient]

_registry: dict[str, _ClientFactory | None] = {"client_factory": None}


def register_client(factory: _ClientFactory) -> None:
    """Register the concrete AI client factory."""
    _registry["client_factory"] = factory


def get_client() -> AiClient:
    """Return the registered AI client."""
    factory = _registry["client_factory"]
    if factory is None:
        err_msg = "No AI client has been registered."
        raise RuntimeError(err_msg)
    return factory()
