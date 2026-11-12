"""
test_verification_state.py — Unit tests for VerificationRecord and related enums.
"""
import pytest
from lifelane_engine.dispatch.verification_state import (
    VerificationConfidence,
    VerificationLevel,
    VerificationMethod,
    VerificationRecord,
)


def _make_record(level=VerificationLevel.DETECTED, expires_at=None):
    return VerificationRecord(
        ambulance_id="TEST-001",
        is_registered=True,
        verification_level=level,
        expires_at=expires_at,
        detection_timestamp=1000.0,
    )


class TestVerificationLevelOrdering:
    def test_all_four_levels_exist(self):
        levels = list(VerificationLevel)
        assert VerificationLevel.UNDETECTED in levels
        assert VerificationLevel.DETECTED in levels
        assert VerificationLevel.VERIFIED in levels
        assert VerificationLevel.AUTHORIZED in levels

    def test_can_authorize_from_verified(self):
        record = _make_record(VerificationLevel.VERIFIED)
        assert record.can_authorize() is True

    def test_can_authorize_from_authorized(self):
        record = _make_record(VerificationLevel.AUTHORIZED)
        assert record.can_authorize() is True

    def test_cannot_authorize_from_detected(self):
        record = _make_record(VerificationLevel.DETECTED)
        assert record.can_authorize() is False

    def test_cannot_authorize_from_undetected(self):
        record = _make_record(VerificationLevel.UNDETECTED)
        assert record.can_authorize() is False


class TestExpiry:
    def test_not_expired_before_deadline(self):
        record = _make_record(expires_at=2000.0)
        assert record.is_expired(now=1500.0) is False

    def test_expired_after_deadline(self):
        record = _make_record(expires_at=1000.0)
        assert record.is_expired(now=1500.0) is True

    def test_no_expiry_set(self):
        record = _make_record(expires_at=None)
        assert record.is_expired(now=99999.0) is False


class TestEscalation:
    def test_escalate_detected_to_verified(self):
        record = _make_record(VerificationLevel.DETECTED)
        record.escalate_to_verified(
            method=VerificationMethod.DISPATCH_OPERATOR,
            confidence=VerificationConfidence.HIGH,
            verified_at=1100.0,
            expires_at=1700.0,
        )
        assert record.verification_level == VerificationLevel.VERIFIED
        assert record.verification_confidence == VerificationConfidence.HIGH

    def test_escalate_verified_to_authorized(self):
        record = _make_record(VerificationLevel.VERIFIED)
        record.escalate_to_authorized()
        assert record.verification_level == VerificationLevel.AUTHORIZED

    def test_cannot_escalate_undetected_to_verified(self):
        record = _make_record(VerificationLevel.UNDETECTED)
        with pytest.raises(ValueError):
            record.escalate_to_verified(
                method=VerificationMethod.NONE,
                confidence=VerificationConfidence.NONE,
                verified_at=100.0,
                expires_at=200.0,
            )

    def test_cannot_escalate_detected_to_authorized(self):
        record = _make_record(VerificationLevel.DETECTED)
        with pytest.raises(ValueError):
            record.escalate_to_authorized()

