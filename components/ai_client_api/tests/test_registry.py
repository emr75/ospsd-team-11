# ruff: noqa: D100, D103

from collections.abc import Generator
from unittest.mock import Mock

import ai_client_api.registry as registry_module
import pytest
from ai_client_api.client import AiClient
from ai_client_api.registry import get_client, register_client


@pytest.fixture(autouse=True)
def clear_registry() -> Generator[None]:
    registry_module._registry["client_factory"] = None
    yield
    registry_module._registry["client_factory"] = None


def test_get_client_raises_when_no_client_registered() -> None:
    with pytest.raises(RuntimeError, match=r"No AI client has been registered\."):
        get_client()


def test_register_client_allows_get_client_to_return_registered_client() -> None:
    mock_client = Mock(spec=AiClient)

    def factory() -> AiClient:
        return mock_client

    register_client(factory)

    client = get_client()

    assert client is mock_client
