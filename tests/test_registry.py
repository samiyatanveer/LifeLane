"""
test_registry.py — Unit tests for AmbulanceRegistry, AmbulanceEntry, and MockRegistry.
"""
import pytest
from lifelane_engine.dispatch.registry import (
    AmbulanceEntry,
    AmbulanceRegistry,
    MockRegistry,
    RegistrationStatus,
    hash_credential,
)


class TestHashCredential:
    def test_returns_hex_string(self):
        h = hash_credential("secret")
        assert isinstance(h, str)
        assert len(h) == 64  # SHA-256 hex

    def test_deterministic(self):
        assert hash_credential("abc") == hash_credential("abc")

    def test_different_inputs_differ(self):
        assert hash_credential("a") != hash_credential("b")

    def test_no_plaintext_stored(self):
        h = hash_credential("my-secret")
        assert "my-secret" not in h


class TestAmbulanceRegistry:
    def _make_entry(self, lifelane_id="LL-099", device_id="DEV-099") -> AmbulanceEntry:
        return AmbulanceEntry(
            lifelane_id=lifelane_id,
            registration_number=f"REG-{lifelane_id}",
            service_name="Test EMS",
            device_id=device_id,
            credential_hash=hash_credential("test-cred"),
        )

    def test_register_and_lookup_by_lifelane_id(self):
        registry = AmbulanceRegistry()
        entry = self._make_entry()
        registry.register(entry)
        found = registry.lookup_by_lifelane_id("LL-099")
        assert found is not None
        assert found.lifelane_id == "LL-099"

    def test_lookup_by_device_id(self):
        registry = AmbulanceRegistry()
        registry.register(self._make_entry())
        found = registry.lookup_by_device_id("DEV-099")
        assert found is not None

    def test_lookup_by_registration_number(self):
        registry = AmbulanceRegistry()
        registry.register(self._make_entry())
        found = registry.lookup_by_registration("REG-LL-099")
        assert found is not None

    def test_lookup_unknown_returns_none(self):
        registry = AmbulanceRegistry()
        assert registry.lookup_by_lifelane_id("NONEXISTENT") is None
        assert registry.lookup_by_device_id("NODEV") is None

    def test_update_status_to_suspended(self):
        registry = AmbulanceRegistry()
        registry.register(self._make_entry())
        ok = registry.update_status("LL-099", RegistrationStatus.SUSPENDED)
        assert ok is True
        entry = registry.lookup_by_lifelane_id("LL-099")
        assert entry.registration_status == RegistrationStatus.SUSPENDED

    def test_update_status_unknown_returns_false(self):
        registry = AmbulanceRegistry()
        assert registry.update_status("UNKNOWN", RegistrationStatus.ACTIVE) is False

    def test_list_all(self):
        registry = AmbulanceRegistry()
        registry.register(self._make_entry("LL-001", "DEV-001"))
        registry.register(self._make_entry("LL-002", "DEV-002"))
        all_entries = registry.list_all()
        assert len(all_entries) == 2


class TestMockRegistry:
    def test_build_default_has_two_entries(self):
        registry = MockRegistry.build_default()
        assert len(registry) == 2

    def test_dev_001_is_active(self):
        registry = MockRegistry.build_default()
        entry = registry.lookup_by_device_id("DEV-001")
        assert entry is not None
        assert entry.is_active()

    def test_credential_hashes_match(self):
        registry = MockRegistry.build_default()
        entry = registry.lookup_by_device_id("DEV-001")
        cred = MockRegistry.mock_credential("DEV-001")
        assert hash_credential(cred) == entry.credential_hash

