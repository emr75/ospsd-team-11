"""Abstract AI client contract for assistant workflows."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any


class AiClient(ABC):
    """Abstract contract for any AI client implementation."""

    @abstractmethod
    def send_message(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
    ) -> str:
        """Send a single prompt to the AI model and return text."""
        raise NotImplementedError

    @abstractmethod
    def run_chat_with_tools(
        self,
        *,
        system_prompt: str,
        user_message: str,
        tools: list[dict[str, Any]],
        handle_tool: Callable[[str, dict[str, Any]], str],
        max_tool_rounds: int = 8,
    ) -> str:
        """Run a chat completion loop that lets the model call tools."""
        raise NotImplementedError
