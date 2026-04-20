"""Abstract AI client contract for calendar and cross-service assistant workflows."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AiToolCall:
    """A structured tool call requested by the AI model."""

    tool_name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class AiResponse:
    """Result returned by the AI client."""

    message: str
    tool_calls: list[AiToolCall]


class AiClient(ABC):
    """Abstract contract for any AI client implementation."""

    @abstractmethod
    def send_message(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
    ) -> AiResponse:
        """Send a prompt to the AI model and return its response."""
        raise NotImplementedError
