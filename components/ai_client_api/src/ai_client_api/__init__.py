"""Public interface for the AI client API package."""

from ai_client_api.client import AiClient
from ai_client_api.registry import get_client, register_client

__all__ = ["AiClient", "get_client", "register_client"]
