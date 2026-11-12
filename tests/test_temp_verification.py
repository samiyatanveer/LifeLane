"""
test_temp_verification.py — Unit tests for TempVerifier and TempVerificationRequest.
"""
import pytest
from lifelane_engine.dispatch.temp_verification import (
    DEFAULT_VALID_OPERATOR_TOKENS,
    MOCK_PLATE_REGISTRY,
    TempVerificationOutcome,
    TempVerificationRequest,
    TempVerifier,
)
from lifelane_engine.dispatch.verification_state import VerificationConfidence

T0 = 100_000.0


def _verifier() -> TempVerifier:
    return TempVerifier(expiry_s=180.0)


class TestDispatchOperator:
    def test_valid_token_with_gps_and_hospital(self):
        v = _verifier()
        req = TempVerificationRequest(
            verification_method="DISPATCH_OPERATOR",
            operator_token=DEFAULT_VALID_OPERATOR_TOKENS[0],
            gps_latitude=33.720,
            gps_longitude=73.040,
            hospital_id="H1",
            emergency_description="Cardiac arrest",
        )
        v.verify(req, now=T0)
        assert req.outcome == TempVerificationOutcome.VERIFIED
        assert req.confidence == VerificationConfidence.HIGH

    def test_invalid_token_fails(self):
        v = _verifier()
        req = TempVerificationRequest(
            verification_method="DISPATCH_OPERATOR",
            operator_token="BAD-TOKEN",
            gps_latitude=33.720,
            gps_longitude=73.040,
            hospital_id="H1",
        )
        v.verify(req, now=T0)
        assert req.outcome == TempVerificationOutcome.NOT_VERIFIED

    def test_missing_hospital_fails(self):
        v = _verifier()
        req = TempVerificationRequest(
            verification_method="DISPATCH_OPERATOR",
            operator_token=DEFAULT_VALID_OPERATOR_TOKENS[0],
            gps_latitude=33.720,
            gps_longitude=73.040,
            hospital_id="",
        )
        v.verify(req, now=T0)
        assert req.outcome == TempVerificationOutcome.NOT_VERIFIED

    def test_manual_location_accepted_instead_of_gps(self):
        """Decision 2A: manual location accepted if no GPS."""
        v = _verifier()
        req = TempVerificationRequest(
            verification_method="DISPATCH_OPERATOR",
            operator_token=DEFAULT_VALID_OPERATOR_TOKENS[0],
            manual_location_description="approaching J1 from north",
            hospital_id="H1",
        )
        v.verify(req, now=T0)
        assert req.outcome == TempVerificationOutcome.VERIFIED
        assert req.gps_source == "MANUAL"


class TestAmbulanceApp:
    def test_full_payload_verified(self):
        v = _verifier()
        req = TempVerificationRequest(
            verification_method="AMBULANCE_APP",
            announced_registration="UNREG-001",
            gps_latitude=33.720,
            gps_longitude=73.040,
            hospital_id="H1",
            emergency_description="Trauma case",
        )
        v.verify(req, now=T0)
        assert req.outcome == TempVerificationOutcome.VERIFIED
        assert req.confidence == VerificationConfidence.MEDIUM

    def test_missing_description_fails(self):
        v = _verifier()
        req = TempVerificationRequest(
            verification_method="AMBULANCE_APP",
            announced_registration="UNREG-001",
            gps_latitude=33.720,
            gps_longitude=73.040,
            hospital_id="H1",
            emergency_description="",  # missing
        )
        v.verify(req, now=T0)
        assert req.outcome == TempVerificationOutcome.NOT_VERIFIED

    def test_missing_location_fails(self):
        v = _verifier()
        req = TempVerificationRequest(
            verification_method="AMBULANCE_APP",
            announced_registration="UNREG-001",
            hospital_id="H1",
            emergency_description="Emergency",
        )
        v.verify(req, now=T0)
        assert req.outcome == TempVerificationOutcome.NOT_VERIFIED


class TestLicensePlate:
    def test_known_plate_verified_low_confidence(self):
        v = _verifier()
        plate = list(MOCK_PLATE_REGISTRY.keys())[0]
        req = TempVerificationRequest(
            verification_method="LICENSE_PLATE",
            plate_number=plate,
        )
        v.verify(req, now=T0)
        assert req.outcome == TempVerificationOutcome.VERIFIED
        assert req.confidence == VerificationConfidence.LOW

    def test_unknown_plate_not_verified(self):
        v = _verifier()
        req = TempVerificationRequest(
            verification_method="LICENSE_PLATE",
            plate_number="XX-9999",
        )
        v.verify(req, now=T0)
        assert req.outcome == TempVerificationOutcome.NOT_VERIFIED

    def test_empty_plate_fails(self):
        v = _verifier()
        req = TempVerificationRequest(
            verification_method="LICENSE_PLATE",
            plate_number="",
        )
        v.verify(req, now=T0)
        assert req.outcome == TempVerificationOutcome.NOT_VERIFIED


class TestUnknownMethod:
    def test_unknown_method_not_verified(self):
        v = _verifier()
        req = TempVerificationRequest(
            verification_method="BIOMETRIC_SCAN",
        )
        v.verify(req, now=T0)
        assert req.outcome == TempVerificationOutcome.NOT_VERIFIED

    def test_expiry_set_on_verification(self):
        v = TempVerifier(expiry_s=300.0)
        req = TempVerificationRequest(
            verification_method="DISPATCH_OPERATOR",
            operator_token=DEFAULT_VALID_OPERATOR_TOKENS[0],
            gps_latitude=33.72,
            gps_longitude=73.04,
            hospital_id="H1",
        )
        v.verify(req, now=T0)
        assert req.expires_at == pytest.approx(T0 + 300.0)

