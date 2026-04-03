"""Unit tests for google_calendar_service.session_store."""

from __future__ import annotations

import asyncio
import base64
import hashlib
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from google_calendar_service.oauth_utils import generate_oauth_state, generate_pkce_pair
from google_calendar_service.session_store import (
    SessionData,
    clear_oauth_tokens_in_session,
    consume_oauth_handshake_from_session,
    create_session,
    delete_session,
    get_oauth_tokens_from_session,
    read_session,
    set_oauth_handshake_in_session,
    set_oauth_tokens_in_session,
)

STATE_TTL_SECONDS = 300
TOKEN_TTL_SECONDS = 1800


class TestSessionDataHandshake:
    """Tests for SessionData OAuth handshake helper methods."""

    def test_with_oauth_handshake_sets_fields(self) -> None:
        """Set state, verifier, and expiry when handshake is stored."""
        now = datetime.now(UTC)
        session = SessionData().with_oauth_handshake(
            state="state-1",
            code_verifier="verifier-1",
            ttl_seconds=STATE_TTL_SECONDS,
        )

        assert session.oauth_state == "state-1"
        assert session.oauth_code_verifier == "verifier-1"
        assert session.oauth_state_expires_at is not None
        assert session.oauth_state_expires_at > now

    def test_with_oauth_handshake_rejects_non_positive_ttl(self) -> None:
        """Raise ValueError for invalid handshake TTL values."""
        with pytest.raises(ValueError, match="ttl_seconds"):
            SessionData().with_oauth_handshake(
                state="state-1",
                code_verifier="verifier-1",
                ttl_seconds=0,
            )

    def test_get_oauth_handshake_returns_record_for_valid_state(self) -> None:
        """Return handshake record when state matches and has not expired."""
        session = SessionData().with_oauth_handshake(
            state="state-1",
            code_verifier="verifier-1",
            ttl_seconds=STATE_TTL_SECONDS,
        )

        record = session.get_oauth_handshake(state="state-1")

        assert record is not None
        assert record.state == "state-1"
        assert record.code_verifier == "verifier-1"

    def test_get_oauth_handshake_returns_none_for_mismatch_or_expired(self) -> None:
        """Return None for mismatched state and expired records."""
        session = SessionData().with_oauth_handshake(
            state="state-1",
            code_verifier="verifier-1",
            ttl_seconds=STATE_TTL_SECONDS,
        )

        mismatched = session.get_oauth_handshake(state="other-state")
        expired = session.get_oauth_handshake(
            state="state-1",
            now=datetime.now(UTC) + timedelta(seconds=STATE_TTL_SECONDS + 1),
        )

        assert mismatched is None
        assert expired is None

    def test_clear_oauth_handshake_clears_fields(self) -> None:
        """Clear all handshake-related fields."""
        session = SessionData().with_oauth_handshake(
            state="state-1",
            code_verifier="verifier-1",
            ttl_seconds=STATE_TTL_SECONDS,
        )

        cleared = session.clear_oauth_handshake()

        assert cleared.oauth_state is None
        assert cleared.oauth_code_verifier is None
        assert cleared.oauth_state_expires_at is None


class TestSessionDataTokens:
    """Tests for SessionData OAuth token helper methods."""

    def test_with_oauth_tokens_sets_token_fields(self) -> None:
        """Store access/refresh token and token expiry."""
        expires_at = datetime.now(UTC) + timedelta(seconds=TOKEN_TTL_SECONDS)

        session = SessionData().with_oauth_tokens(
            access_token="access-1",
            refresh_token="refresh-1",
            expires_at=expires_at,
        )

        assert session.oauth_access_token == "access-1"
        assert session.oauth_refresh_token == "refresh-1"
        assert session.oauth_token_expires_at == expires_at

    def test_with_oauth_tokens_preserves_existing_refresh_token(self) -> None:
        """Keep existing refresh token when a new one is not provided."""
        expires_at = datetime.now(UTC) + timedelta(seconds=TOKEN_TTL_SECONDS)
        initial = SessionData(oauth_refresh_token="persisted-refresh")

        updated = initial.with_oauth_tokens(
            access_token="new-access",
            expires_at=expires_at,
            refresh_token=None,
        )

        assert updated.oauth_refresh_token == "persisted-refresh"
        assert updated.oauth_access_token == "new-access"

    def test_get_oauth_tokens_returns_none_when_missing_or_expired(self) -> None:
        """Return None if token data is absent or expired."""
        missing = SessionData().get_oauth_tokens()
        expired_session = SessionData().with_oauth_tokens(
            access_token="access-1",
            refresh_token="refresh-1",
            expires_at=datetime.now(UTC) - timedelta(seconds=1),
        )
        expired = expired_session.get_oauth_tokens()

        assert missing is None
        assert expired is None

    def test_get_oauth_tokens_returns_record_when_valid(self) -> None:
        """Return token record when token is present and not expired."""
        expires_at = datetime.now(UTC) + timedelta(seconds=TOKEN_TTL_SECONDS)
        session = SessionData().with_oauth_tokens(
            access_token="access-1",
            refresh_token="refresh-1",
            expires_at=expires_at,
        )

        record = session.get_oauth_tokens()

        assert record is not None
        assert record.access_token == "access-1"
        assert record.refresh_token == "refresh-1"
        assert record.expires_at == expires_at

    def test_clear_oauth_tokens_clears_fields(self) -> None:
        """Clear all token-related fields."""
        expires_at = datetime.now(UTC) + timedelta(seconds=TOKEN_TTL_SECONDS)
        session = SessionData().with_oauth_tokens(
            access_token="access-1",
            refresh_token="refresh-1",
            expires_at=expires_at,
        )

        cleared = session.clear_oauth_tokens()

        assert cleared.oauth_access_token is None
        assert cleared.oauth_refresh_token is None
        assert cleared.oauth_token_expires_at is None


class TestOAuthUtilityGenerators:
    """Tests for OAuth helper token/state generation functions."""

    def test_generate_oauth_state_returns_non_empty_and_unique(self) -> None:
        """Generate non-empty random-looking state values."""
        state_a = generate_oauth_state()
        state_b = generate_oauth_state()

        assert state_a
        assert state_b
        assert state_a != state_b

    def test_generate_pkce_pair_matches_expected_s256_challenge(self) -> None:
        """Generate PKCE verifier/challenge pair with valid S256 challenge."""
        code_verifier, code_challenge = generate_pkce_pair()

        digest = hashlib.sha256(code_verifier.encode("utf-8")).digest()
        expected_challenge = base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")

        assert code_verifier
        assert code_challenge
        assert code_challenge == expected_challenge


class TestAsyncSessionStoreHelpers:
    """Tests for async session CRUD and OAuth helper functions."""

    def test_create_read_and_delete_session(self) -> None:
        """Create a session, read it, then delete it."""
        session_id = asyncio.run(create_session())
        try:
            session = asyncio.run(read_session(session_id=session_id))
            assert session is not None
            assert isinstance(session, SessionData)
        finally:
            asyncio.run(delete_session(session_id=session_id))

        deleted = asyncio.run(read_session(session_id=session_id))
        assert deleted is None

    def test_set_and_consume_oauth_handshake(self) -> None:
        """Persist OAuth handshake and consume it exactly once."""
        session_id = asyncio.run(create_session())
        try:
            asyncio.run(
                set_oauth_handshake_in_session(
                    session_id=session_id,
                    state="state-1",
                    code_verifier="verifier-1",
                    ttl_seconds=STATE_TTL_SECONDS,
                )
            )

            consumed = asyncio.run(
                consume_oauth_handshake_from_session(
                    session_id=session_id,
                    state="state-1",
                )
            )
            consumed_again = asyncio.run(
                consume_oauth_handshake_from_session(
                    session_id=session_id,
                    state="state-1",
                )
            )

            assert consumed is not None
            assert consumed.state == "state-1"
            assert consumed.code_verifier == "verifier-1"
            assert consumed_again is None
        finally:
            asyncio.run(delete_session(session_id=session_id))

    def test_consume_oauth_handshake_with_wrong_state_returns_none_and_clears(self) -> None:
        """Return None for wrong state and clear handshake after consume attempt."""
        session_id = asyncio.run(create_session())
        try:
            asyncio.run(
                set_oauth_handshake_in_session(
                    session_id=session_id,
                    state="state-1",
                    code_verifier="verifier-1",
                    ttl_seconds=STATE_TTL_SECONDS,
                )
            )

            wrong_state = asyncio.run(
                consume_oauth_handshake_from_session(
                    session_id=session_id,
                    state="wrong-state",
                )
            )
            correct_after_wrong = asyncio.run(
                consume_oauth_handshake_from_session(
                    session_id=session_id,
                    state="state-1",
                )
            )

            assert wrong_state is None
            assert correct_after_wrong is None
        finally:
            asyncio.run(delete_session(session_id=session_id))

    def test_set_oauth_handshake_raises_for_missing_session(self) -> None:
        """Raise KeyError when setting handshake for missing session."""
        with pytest.raises(KeyError, match="session"):
            asyncio.run(
                set_oauth_handshake_in_session(
                    session_id=uuid4(),
                    state="state-1",
                    code_verifier="verifier-1",
                    ttl_seconds=STATE_TTL_SECONDS,
                )
            )

    def test_set_get_and_clear_oauth_tokens(self) -> None:
        """Persist OAuth tokens, read them, and clear them."""
        session_id = asyncio.run(create_session())
        expires_at = datetime.now(UTC) + timedelta(seconds=TOKEN_TTL_SECONDS)

        try:
            asyncio.run(
                set_oauth_tokens_in_session(
                    session_id=session_id,
                    access_token="access-1",
                    refresh_token="refresh-1",
                    expires_at=expires_at,
                )
            )

            tokens = asyncio.run(get_oauth_tokens_from_session(session_id=session_id))
            assert tokens is not None
            assert tokens.access_token == "access-1"
            assert tokens.refresh_token == "refresh-1"
            assert tokens.expires_at == expires_at

            asyncio.run(clear_oauth_tokens_in_session(session_id=session_id))
            cleared_tokens = asyncio.run(get_oauth_tokens_from_session(session_id=session_id))
            assert cleared_tokens is None
        finally:
            asyncio.run(delete_session(session_id=session_id))

    def test_set_oauth_tokens_raises_for_missing_session(self) -> None:
        """Raise KeyError when setting tokens for missing session."""
        with pytest.raises(KeyError, match="session"):
            asyncio.run(
                set_oauth_tokens_in_session(
                    session_id=uuid4(),
                    access_token="access-1",
                    refresh_token="refresh-1",
                    expires_at=datetime.now(UTC) + timedelta(seconds=TOKEN_TTL_SECONDS),
                )
            )
