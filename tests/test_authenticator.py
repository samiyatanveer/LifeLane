"""
test_authenticator.py — Unit tests for AmbulanceAuthenticator.
"""
import pytest
from lifelane_engine.dispatch.authenticator import AmbulanceAuthenticator
from lifelane_engine.dispatch.registry import MockRegistry, RegistrationStatus


def _make_auth():
    registry = MockRegistry.build_default()
    auth = AmbulanceAuthenticator(registry)
    return auth, registry


class TestAuthentication:
    def test_valid_credentials_succeed(self):
        auth, _ = _make_auth()
        result = auth.authenticate("DEV-001", MockRegistry.mock_credential("DEV-001"))
        assert result.success is True
        assert result.ambulance_id == "LL-001"
        assert result.reason == "OK"

    def test_wrong_credential_fails(self):
        auth, _ = _make_auth()
        result = auth.authenticate("DEV-001", "wrong-password")
        assert result.success is False
        assert "Credential mismatch" in result.reason

    def test_unknown_device_fails(self):
        auth, _ = _make_auth()
        result = auth.authenticate("DEV-UNKNOWN", "any-credential")
        assert result.success is False
        assert "not registered" in result.reason

    def test_suspended_ambulance_fails(self):
        auth, registry = _make_auth()
        registry.update_status("LL-001", RegistrationStatus.SUSPENDED)
        result = auth.authenticate("DEV-001", MockRegistry.mock_credential("DEV-001"))
        assert result.success is False
        assert "SUSPENDED" in result.reason

    def test_revoked_ambulance_fails(self):
        auth, registry = _make_auth()
        registry.update_status("LL-001", RegistrationStatus.REVOKED)
        result = auth.authenticate("DEV-001", MockRegistry.mock_credential("DEV-001"))
        assert result.success is False
        assert "REVOKED" in result.reason

    def test_second_ambulance_authenticates(self):
        auth, _ = _make_auth()
        result = auth.authenticate("DEV-002", MockRegistry.mock_credential("DEV-002"))
        assert result.success is True
        assert result.ambulance_id == "LL-002"

    def test_empty_credential_fails(self):
        auth, _ = _make_auth()
        result = auth.authenticate("DEV-001", "")
        # Empty credential will not match the hash
        assert result.success is False

    def test_result_contains_device_id(self):
        auth, _ = _make_auth()
        result = auth.authenticate("DEV-001", MockRegistry.mock_credential("DEV-001"))
        assert result.device_id == "DEV-001"

