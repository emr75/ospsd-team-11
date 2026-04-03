"""Centralized runtime settings for the Google Calendar service."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Final
from urllib.parse import urlparse

from google_calendar_client_impl.client_impl import load_env

DEFAULT_OAUTH_REDIRECT_URI: Final[str] = "http://localhost:8000/auth/callback"
DEFAULT_OAUTH_SCOPE: Final[str] = "https://www.googleapis.com/auth/calendar"
DEFAULT_OAUTH_AUTH_URL: Final[str] = "https://accounts.google.com/o/oauth2/v2/auth"
DEFAULT_OAUTH_TOKEN_URL: Final[str] = "https://oauth2.googleapis.com/token"  # noqa: S105 - URL, not a secret
DEFAULT_OAUTH_PROMPT: Final[str] = "consent"
DEFAULT_OAUTH_STATE_TTL_SECONDS: Final[int] = 600
DEFAULT_TOKEN_REQUEST_TIMEOUT_SECONDS: Final[int] = 10
DEFAULT_ALLOWED_TOKEN_HOSTS: Final[tuple[str, ...]] = ("oauth2.googleapis.com",)

DEFAULT_SESSION_COOKIE_NAME: Final[str] = "google_calendar_session_id"
DEFAULT_SESSION_IDENTIFIER: Final[str] = "google_calendar_service_verifier"
DEFAULT_SESSION_SECRET: Final[str] = "dev-only"  # noqa: S105 - local dev default, override via env
DEFAULT_SESSION_COOKIE_SECURE: Final[bool] = False


@dataclass(frozen=True)
class OAuthSettings:
    """OAuth-related configuration."""

    client_id: str | None
    client_secret: str | None
    redirect_uri: str | None
    scopes: str
    auth_url: str
    token_url: str
    prompt: str
    state_ttl_seconds: int
    token_request_timeout_seconds: int
    allowed_token_hosts: tuple[str, ...]

    def require_client_id(self) -> str:
        """Return client ID or raise if missing."""
        if self.client_id:
            return self.client_id
        msg = "Missing required environment variable: GOOGLE_CALENDAR_CLIENT_ID"
        raise ValueError(msg)

    def require_client_secret(self) -> str:
        """Return client secret or raise if missing."""
        if self.client_secret:
            return self.client_secret
        msg = "Missing required environment variable: GOOGLE_CALENDAR_CLIENT_SECRET"
        raise ValueError(msg)

    def require_redirect_uri(self) -> str:
        """Return redirect URI or raise if missing."""
        if self.redirect_uri:
            return self.redirect_uri
        msg = "Missing required environment variable: GOOGLE_CALENDAR_REDIRECT_URI"
        raise ValueError(msg)

    def require_web_credentials(self) -> tuple[str, str, str]:
        """Return required OAuth web credentials as a tuple."""
        return (
            self.require_client_id(),
            self.require_client_secret(),
            self.require_redirect_uri(),
        )


@dataclass(frozen=True)
class SessionSettings:
    """Session/cookie configuration."""

    cookie_name: str
    identifier: str
    secret: str
    cookie_secure: bool


@dataclass(frozen=True)
class ServiceSettings:
    """All service settings grouped in one object."""

    oauth: OAuthSettings
    session: SessionSettings


def _env_bool(name: str, *, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, *, default: int, min_value: int = 1) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = int(raw)
    if value < min_value:
        msg = f"{name} must be >= {min_value}, got {value}"
        raise ValueError(msg)
    return value


def _normalize_scopes(raw: str | None) -> str:
    if raw is None or not raw.strip():
        return DEFAULT_OAUTH_SCOPE
    scopes = [scope for chunk in raw.split(",") for scope in chunk.split() if scope]
    return " ".join(scopes) if scopes else DEFAULT_OAUTH_SCOPE


def _normalize_allowed_hosts(raw: str | None) -> tuple[str, ...]:
    if raw is None or not raw.strip():
        return DEFAULT_ALLOWED_TOKEN_HOSTS
    hosts = tuple(host.strip().lower() for host in raw.split(",") if host.strip())
    return hosts or DEFAULT_ALLOWED_TOKEN_HOSTS


def _validate_https_url(url: str, *, setting_name: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname is None:
        msg = f"{setting_name} must be a valid https URL"
        raise ValueError(msg)


def _validate_token_endpoint(token_url: str, allowed_hosts: tuple[str, ...]) -> None:
    _validate_https_url(token_url, setting_name="GOOGLE_CALENDAR_OAUTH_TOKEN_URL")
    hostname = urlparse(token_url).hostname
    if hostname is None or hostname.lower() not in {host.lower() for host in allowed_hosts}:
        msg = "GOOGLE_CALENDAR_OAUTH_TOKEN_URL host is not allowed"
        raise ValueError(msg)


def get_settings() -> ServiceSettings:
    """Load service settings from environment variables."""
    load_env()
    oauth = OAuthSettings(
        client_id=os.getenv("GOOGLE_CALENDAR_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CALENDAR_CLIENT_SECRET"),
        redirect_uri=os.getenv("GOOGLE_CALENDAR_REDIRECT_URI", DEFAULT_OAUTH_REDIRECT_URI),
        scopes=_normalize_scopes(os.getenv("GOOGLE_CALENDAR_SCOPES")),
        auth_url=os.getenv("GOOGLE_CALENDAR_OAUTH_AUTH_URL", DEFAULT_OAUTH_AUTH_URL),
        token_url=os.getenv("GOOGLE_CALENDAR_OAUTH_TOKEN_URL", DEFAULT_OAUTH_TOKEN_URL),
        prompt=os.getenv("GOOGLE_CALENDAR_OAUTH_PROMPT", DEFAULT_OAUTH_PROMPT),
        state_ttl_seconds=_env_int(
            "GOOGLE_CALENDAR_OAUTH_STATE_TTL_SECONDS",
            default=DEFAULT_OAUTH_STATE_TTL_SECONDS,
            min_value=1,
        ),
        token_request_timeout_seconds=_env_int(
            "GOOGLE_CALENDAR_OAUTH_TOKEN_TIMEOUT_SECONDS",
            default=DEFAULT_TOKEN_REQUEST_TIMEOUT_SECONDS,
            min_value=1,
        ),
        allowed_token_hosts=_normalize_allowed_hosts(os.getenv("GOOGLE_CALENDAR_OAUTH_ALLOWED_TOKEN_HOSTS")),
    )

    # Validate URL settings early.
    _validate_https_url(oauth.auth_url, setting_name="GOOGLE_CALENDAR_OAUTH_AUTH_URL")
    _validate_token_endpoint(oauth.token_url, oauth.allowed_token_hosts)

    session = SessionSettings(
        cookie_name=os.getenv("GOOGLE_CALENDAR_SESSION_COOKIE_NAME", DEFAULT_SESSION_COOKIE_NAME),
        identifier=os.getenv("GOOGLE_CALENDAR_SESSION_IDENTIFIER", DEFAULT_SESSION_IDENTIFIER),
        secret=os.getenv("GOOGLE_CALENDAR_SESSION_SECRET", DEFAULT_SESSION_SECRET),
        cookie_secure=_env_bool(
            "GOOGLE_CALENDAR_SESSION_COOKIE_SECURE",
            default=DEFAULT_SESSION_COOKIE_SECURE,
        ),
    )

    return ServiceSettings(
        oauth=oauth,
        session=session,
    )


settings = get_settings()
