"""
test_session_manager.py — Unit tests for SessionManager.
"""
import pytest
from lifelane_engine.dispatch.session_manager import (
    DuplicateSessionError,
    SessionManager,
)


T0 = 10_000.0


class TestSessionCreation:
    def test_create_session_returns_session(self):
        sm = SessionManager(session_ttl_s=3600)
        sess = sm.create_session("LL-001", "DEV-001", now=T0)
        assert sess.ambulance_id == "LL-001"
        assert sess.device_id == "DEV-001"

    def test_session_is_active_before_expiry(self):
        sm = SessionManager(session_ttl_s=3600)
        sess = sm.create_session("LL-001", "DEV-001", now=T0)
        assert sm.validate_session(sess.session_id, now=T0 + 100) is True

    def test_session_expired_after_ttl(self):
        sm = SessionManager(session_ttl_s=60)
        sess = sm.create_session("LL-001", "DEV-001", now=T0)
        assert sm.validate_session(sess.session_id, now=T0 + 61) is False

    def test_duplicate_session_raises(self):
        sm = SessionManager(session_ttl_s=3600)
        sm.create_session("LL-001", "DEV-001", now=T0)
        with pytest.raises(DuplicateSessionError):
            sm.create_session("LL-001", "DEV-001", now=T0 + 1)

    def test_unknown_session_id_invalid(self):
        sm = SessionManager()
        assert sm.validate_session("no-such-session", now=T0) is False


class TestSessionInvalidation:
    def test_invalidate_session(self):
        sm = SessionManager(session_ttl_s=3600)
        sess = sm.create_session("LL-001", "DEV-001", now=T0)
        ok = sm.invalidate_session(sess.session_id, reason="logout")
        assert ok is True
        assert sm.validate_session(sess.session_id, now=T0 + 1) is False

    def test_invalidate_unknown_returns_false(self):
        sm = SessionManager()
        assert sm.invalidate_session("no-such-id") is False

    def test_get_active_session(self):
        sm = SessionManager(session_ttl_s=3600)
        sm.create_session("LL-001", "DEV-001", now=T0)
        active = sm.get_active_session("LL-001", now=T0 + 10)
        assert active is not None
        assert active.ambulance_id == "LL-001"


class TestCleanup:
    def test_cleanup_expired(self):
        sm = SessionManager(session_ttl_s=30)
        sm.create_session("LL-001", "DEV-001", now=T0)
        sm.create_session("LL-002", "DEV-002", now=T0)
        removed = sm.cleanup_expired(now=T0 + 31)
        assert len(removed) == 2

