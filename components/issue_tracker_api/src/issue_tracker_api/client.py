"""Abstract interface and dependency injection for issue tracker clients."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from enum import Enum


class IssueTrackerError(Exception):
    """Base exception for issue tracker API errors."""


class IssueError(IssueTrackerError):
    """Exception raised for issue-related failures."""


class BoardError(IssueTrackerError):
    """Exception raised for board-related failures."""


class Status(str, Enum):
    """Supported issue status values."""

    TO_DO = "to_do"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


@dataclass(frozen=True)
class Issue:
    """Issue tracker issue model."""

    id: str
    title: str
    desc: str | None = None
    members: list[str] | None = None
    due_date: str | None = None
    status: Status = Status.TO_DO
    board_id: str | None = None


@dataclass(frozen=True)
class Board:
    """Issue tracker board model."""

    id: str
    board_name: str


ClientFactory = Callable[[bool], "Client"]

_client_factory: ClientFactory | None = None


class Client(ABC):
    """Abstract base class for an issue tracker client."""

    @abstractmethod
    def get_issue(self, issue_id: str) -> Issue:
        """Return a single issue by ID."""
        raise NotImplementedError

    @abstractmethod
    def get_board(self, board_id: str) -> Board:
        """Return a single board by ID."""
        raise NotImplementedError

    @abstractmethod
    def get_issues(self, board_id: str) -> Iterator[Issue]:
        """Return issues on a board."""
        raise NotImplementedError

    @abstractmethod
    def get_boards(self) -> Iterator[Board]:
        """Return all boards."""
        raise NotImplementedError

    @abstractmethod
    def update_issue( # noqa: PLR0913
        self,
        issue_id: str,
        title: str | None = None,
        desc: str | None = None,
        members: list[str] | None = None,
        due_date: str | None = None,
        status: Status | None = None,
        board_id: str | None = None,
    ) -> Issue:
        """Update an issue."""
        raise NotImplementedError

    @abstractmethod
    def update_board(
        self,
        board_id: str,
        name: str | None = None,
    ) -> Board:
        """Update a board."""
        raise NotImplementedError

    @abstractmethod
    def delete_issue(self, issue_id: str) -> bool:
        """Delete an issue."""
        raise NotImplementedError

    @abstractmethod
    def delete_board(self, board_id: str) -> bool:
        """Delete a board."""
        raise NotImplementedError

    @abstractmethod
    def create_issue( # noqa: PLR0913
        self,
        title: str,
        board_id: str,
        desc: str | None = None,
        members: list[str] | None = None,
        due_date: str | None = None,
        status: Status = Status.TO_DO,
    ) -> Issue:
        """Create an issue."""
        raise NotImplementedError

    @abstractmethod
    def create_board(self, name: str) -> Board:
        """Create a board."""
        raise NotImplementedError


def register_client(factory: ClientFactory) -> None:
    """Register a concrete issue tracker client factory."""
    global _client_factory  # noqa: PLW0603
    _client_factory = factory


def get_client(*, interactive: bool = False) -> Client:
    """Return the registered issue tracker client."""
    if _client_factory is None:
        message = "No concrete issue tracker client factory has been registered."
        raise IssueTrackerError(message)

    return _client_factory(interactive)
